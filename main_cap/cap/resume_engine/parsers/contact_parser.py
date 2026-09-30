"""
ContactParser — Stage 4 plugin for contact/header fields (candidate_name,
email, phone, linkedin, location). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Reads `sections["contact"]` (Milestone 2's Section Detection already does
the heavy lifting here: the pre-first-header block defaults to "contact",
and a document-wide email/phone/URL regex sweep tags any matching span
into "contact" regardless of where it structurally sits) plus
`doc.hyperlinks` (for a "LinkedIn" label hyperlinked to a URL with no
visible URL text -- a real gap in today's Gemini pipeline, per the
architecture doc).

Email/phone/URL regex patterns here are deliberately a small, local copy
of sections.py's near-identical patterns, NOT an import from it --
Milestone 2 is frozen, and the established precedent (Milestone 1's
layout.py vs. Milestone 2's sections.py) is that each milestone owns its
own copy of any structurally-needed pattern rather than reaching into a
frozen module.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.location_gazetteer import LOCATIONS

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Kept for compatibility (the strict North-American shape). Phone EXTRACTION
# now uses the more permissive `_PHONE_SEARCH` below, which also handles
# international groupings like "+91 90000 12345" (5-5) that the strict 3-3-4
# pattern silently missed; digit-count validation guards against false hits.
_PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_PHONE_SEARCH = re.compile(r"\(?\+?\d[\d\s().\-]{8,15}\d")
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/\S+", re.IGNORECASE)
_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+|(?:linkedin|github|gitlab)\.com/\S+", re.IGNORECASE)

# Words that never appear in a person's NAME but DO appear on the same
# banner line or in the header block: social/profile labels, section words,
# contact labels, and common job-title nouns (a headline like "AI Engineer"
# is not a name). Generic vocabulary, never resume-specific.
_NON_NAME_WORDS: frozenset[str] = frozenset({
    "github", "gitlab", "linkedin", "profile", "portfolio", "website", "blog",
    "university", "college", "institute", "campus", "school", "department",
    "roll", "no", "email", "e-mail", "mail", "phone", "mobile", "tel", "cell",
    "contact", "address", "resume", "cv", "curriculum", "vitae",
    "objective", "summary", "about", "engineer", "engineering", "developer",
    "intern", "analyst", "manager", "scientist", "consultant", "architect",
    "designer", "administrator", "specialist", "lead", "student", "aiml",
    "ml", "ai", "sde", "swe",
})

_LINE_Y_TOLERANCE = 3.0  # points; spans within this y0 delta are one visual line

# Validation-derived, tunable (same discipline established in layout.py and
# sections.py) -- 80 comfortably separates an exact/near-exact location
# name from unrelated short text, per the same str.lower normalization
# that fixed Section Detection's case-sensitivity bug. Scorer is
# token_set_ratio, not token_sort_ratio (see _extract_location).
LOCATION_MATCH_THRESHOLD = 80


def _group_spans_into_lines(spans) -> list[list]:
    """Groups word-level spans into visual lines by y-coordinate proximity,
    never merging across a page/column change. A local copy of the same
    line-reconstruction shape used in `_entry_clustering.py` (not an
    import from it, per this module's own established precedent of never
    reaching into another parser's private module -- see this file's
    docstring on the email/phone/URL regexes).

    Found during Phase 1 real-world evaluation: `PdfDocxExtractor`
    produces WORD-level spans (not full lines). The section's spans
    include a separate whitespace-only span between most words, so the
    old `" ".join(s.text for s in section.spans)` treated every word (and
    every individual whitespace span) as an independent unit rather than
    reconstructing the actual visual line. That silently broke two
    things: the phone regex's single-character separator tolerance,
    whenever two adjacent whitespace-only spans produced a multi-space
    gap between the country code and the number; and location/name
    matching, which compared individual WORDS against the gazetteer or
    each other's font size instead of whole reconstructed lines -- so a
    multi-word location or a multi-word name was almost never recognized
    as one unit."""
    groups: list[list] = []
    for span in spans:
        if groups:
            last = groups[-1][-1]
            same_block = span.page_num == last.page_num and span.column_index == last.column_index
            if same_block and abs(span.bbox[1] - last.bbox[1]) <= _LINE_Y_TOLERANCE:
                groups[-1].append(span)
                continue
        groups.append([span])
    return groups


def _line_text(line_spans: list) -> str:
    """Joins a line's word-level spans left-to-right, collapsing the
    doubled/tripled whitespace that results from joining real inter-word
    whitespace-only spans with `str.join`'s own inserted separator (see
    `_group_spans_into_lines`)."""
    raw = " ".join(s.text for s in sorted(line_spans, key=lambda s: s.bbox[0]))
    return re.sub(r"\s+", " ", raw).strip()


def _extract_email(text: str) -> str:
    match = _EMAIL_PATTERN.search(text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    """Finds the first phone-number-shaped substring and validates it by
    digit count (10-13, optionally including a country code). More permissive
    than the strict 3-3-4 `_PHONE_PATTERN` so international groupings like
    "+91 90000 12345" (5-5) are recovered, while the digit-count check keeps
    it from matching years, IDs, or roll numbers."""
    for match in _PHONE_SEARCH.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if 10 <= len(digits) <= 13:
            # A short number group after a space that isn't needed to reach 10
            # digits is the start of the next field (an address: "123-456-7890
            # 123 Anywhere St." -> "123-456-7890"), not part of the phone.
            tail = re.match(r"^(.*\d)\s+\d{1,3}$", candidate)
            if tail and len(re.sub(r"\D", "", tail.group(1))) >= 10:
                candidate = tail.group(1)
            return candidate
    return ""


def _extract_linkedin_from_text(text: str) -> str:
    match = _LINKEDIN_PATTERN.search(text)
    return match.group(0) if match else ""


def _extract_linkedin_from_hyperlinks(hyperlinks) -> str:
    for url, _bbox, _page in hyperlinks:
        if "linkedin.com" in url.lower():
            return url
    return ""


# A location line is never legitimately introduced by one of these words
# -- a small, local guard against `token_set_ratio`'s wider net (below)
# picking up a gazetteer word (e.g. "Massachusetts") that happens to
# appear inside an unrelated section's heading text (e.g. "Massachusetts
# Institute of Technology") rather than an actual address line. Found
# during Phase 1 real-world evaluation on a resume where a pre-existing,
# unrelated Section Detection issue (a frozen Milestone 2 defect, out of
# this fix's scope) let non-contact content bleed into the "contact"
# section.
_NON_LOCATION_LEADING_WORDS = (
    "education",
    "experience",
    "skills",
    "projects",
    "leadership",
    "certifications",
    "awards",
    "summary",
    "objective",
    "coursework",
)


_HORIZONTAL_SEPARATOR_PATTERN = re.compile(r"[|•·]")  # "|", "•", "·"


def _candidate_location_segments(line: str) -> list[str]:
    """Splits a line on common horizontal-contact-bar separators
    ("|", "•", "·"). Most resumes put email/phone/location/linkedin each
    on their own line, but some print them all on one pipe- or
    bullet-delimited line (e.g. "(+91) 123... | Kolkata, India |
    name@example.com | ..."). Without splitting, the whole-line
    email/phone skip below would discard the location segment along with
    the phone/email segments it's printed next to (found during Phase 1
    real-world evaluation)."""
    segments = _HORIZONTAL_SEPARATOR_PATTERN.split(line)
    return segments if len(segments) > 1 else [line]


def _extract_location(lines: list[str]) -> tuple[str, float]:
    """Fuzzy-matches each candidate line (or, for a horizontal
    multi-field line, each `|`/`•`/`·`-delimited segment of it -- see
    `_candidate_location_segments`) against the location gazetteer,
    returns (best_match_text_as_found_in_resume, score). A candidate
    already identified as email/phone, or one that opens with a word no
    genuine location line would start with (see
    `_NON_LOCATION_LEADING_WORDS`), is skipped.

    Scorer is `token_set_ratio`, not `token_sort_ratio`: a real location
    line is usually "City, State ZIP, Country" -- several tokens, only
    one or two of which (e.g. "India") are actually in the gazetteer.
    `token_sort_ratio` scores the FULL token sequence against a
    single-word gazetteer entry, so extra tokens (the city/state/ZIP)
    heavily penalize the match even when the country name is present
    verbatim. `token_set_ratio` scores based on token
    intersection/union, so it correctly recognizes the gazetteer token as
    present regardless of how many other tokens surround it (found during
    Phase 1 real-world evaluation: "Bengaluru, Karnataka 560017, India"
    scored only 29 against "India" with token_sort_ratio, but 100 with
    token_set_ratio)."""
    best_line = ""
    best_score = 0.0
    for line in lines:
        for candidate in _candidate_location_segments(line):
            stripped = candidate.strip()
            if not stripped or _EMAIL_PATTERN.search(candidate) or _PHONE_PATTERN.search(candidate):
                continue
            if stripped.lower().startswith(_NON_LOCATION_LEADING_WORDS):
                continue
            _, score, _ = process.extractOne(candidate, LOCATIONS, scorer=fuzz.token_set_ratio, processor=str.lower)
            if score > best_score:
                best_score = score
                best_line = stripped
    return best_line, best_score


def _residual_after_contact(text: str) -> str:
    """Strips email/phone/URL/linkedin substrings out of a line, leaving
    only the residual prose -- so a line that carries the NAME alongside a
    phone number ("M S Example  +91-90000333333") still yields the name
    for scoring instead of being discarded wholesale (the prior behavior,
    which excluded any line containing contact info and so missed a name
    printed on the same line as the phone)."""
    residual = _URL_PATTERN.sub(" ", text)
    residual = _EMAIL_PATTERN.sub(" ", residual)
    phone = _extract_phone(residual)
    if phone:
        residual = residual.replace(phone, " ")
    # Drop decorative/icon glyphs (e.g. Font-Awesome contact icons that
    # extract as stray control/symbol characters like "\x83", "§", "ï")
    # so a name sharing a line with such a glyph isn't disqualified by a
    # non-name-like junk token. Keeps letters, digits, spaces, and the
    # punctuation that legitimately appears in names.
    residual = re.sub(r"[^A-Za-z0-9 .,&'/\-]", " ", residual)
    # A document-title suffix/prefix on the name line ("Jordan Example -
    # Resume", "Resume - Jordan Example", "Jordan Example CV") is not part of
    # the name; left in, it disqualified the whole line.
    residual = re.sub(r"\s*[-–—|:,]?\s*\b(?:resume|cv|curriculum\s+vitae)\s*$", "", residual, flags=re.IGNORECASE)
    residual = re.sub(r"^\s*(?:resume|cv|curriculum\s+vitae)\b\s*(?:of\b)?\s*[-–—|:,]?\s*", "", residual, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", residual).strip()


def _is_name_token(token: str) -> bool:
    """A token that could belong to a person's name: alphabetic (allowing an
    internal apostrophe/hyphen and a trailing '.' for an initial), and not a
    known non-name word (social label, section word, job-title noun)."""
    core = token.strip(".")
    if not core or not re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", core):
        return False
    return core.lower() not in _NON_NAME_WORDS


def _infer_candidate_name(lines_with_font_size: list[tuple[str, float]]) -> str:
    """Evidence-scored single-line name selection (Phase 1 rewrite).

    Replaces the prior "join every line sharing the largest font" rule,
    which glued unrelated banner lines (a headline, a GitHub/LinkedIn label,
    an institution line) into one garbled 'name' whenever they happened to
    share the name's font size. Instead: strip contact info from each line,
    then accept only lines whose residual is 2-4 tokens that are ALL
    name-like (no social/section/job-title words, no digits). Among those,
    prefer the largest font, breaking ties toward the earliest line (a name
    sits at the top of the block). Never concatenates lines.

    A name stacked across consecutive equal-font lines each holding a SINGLE
    name token ("ANGEL" / "MATAPANG") is still recovered -- but ONLY that
    narrow, adjacent, equal-font, all-single-name-token shape, never the
    old "glue every line at the max font size" rule that produced garbled
    names from unrelated banner lines.

    `lines_with_font_size` is in document order (earlier lines first)."""
    residuals = [
        (index, _residual_after_contact(text), size)
        for index, (text, size) in enumerate(lines_with_font_size)
    ]

    best_text = ""
    best_key: tuple[float, int] | None = None

    def _consider(text: str, key: tuple[float, int]) -> None:
        nonlocal best_text, best_key
        if best_key is None or key > best_key:
            best_key = key
            best_text = text

    # Single-line candidates: a residual of 2-4 all-name-like tokens.
    for index, residual, size in residuals:
        tokens = residual.split()
        if 2 <= len(tokens) <= 4 and all(_is_name_token(tok) for tok in tokens):
            _consider(residual, (size, -index))  # larger font wins; earlier breaks ties

    # Stacked candidates: a run of consecutive equal-font lines each a single
    # name-like token, forming a 2-4 token name.
    i = 0
    n = len(residuals)
    while i < n:
        tokens = residuals[i][1].split()
        if len(tokens) == 1 and _is_name_token(tokens[0]):
            size_i = residuals[i][2]
            group = []
            j = i
            while j < n:
                toks_j = residuals[j][1].split()
                if len(toks_j) == 1 and _is_name_token(toks_j[0]) and abs(residuals[j][2] - size_i) < 0.01:
                    group.append(residuals[j])
                    j += 1
                else:
                    break
            if 2 <= len(group) <= 4:
                _consider(" ".join(g[1] for g in group), (size_i, -group[0][0]))
            i = max(j, i + 1)
        else:
            i += 1

    # Last resort, letter-spaced banner names ("J U L I A N A S I L V A"): the
    # PDF gives no reliable word boundary, so return the letters as printed --
    # the old engine's output -- rather than no name at all.
    if not best_text:
        for index, residual, size in residuals:
            tokens = residual.split()
            if len(tokens) >= 4 and all(len(t) == 1 and t.isalpha() and t.isupper() for t in tokens):
                _consider(residual, (size, -index))
    return best_text


class ContactParser:
    entity_name = "contact"
    required_sections: tuple[str, ...] = ("contact",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("contact")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        line_groups = _group_spans_into_lines(section.spans)
        lines = [_line_text(group) for group in line_groups]
        full_text = " ".join(lines)
        lines_with_font_size: dict[str, float] = {}
        for group, line in zip(line_groups, lines):
            lines_with_font_size[line] = max(lines_with_font_size.get(line, 0.0), max(s.font_size for s in group))

        email = _extract_email(full_text)
        phone = _extract_phone(full_text)
        linkedin = _extract_linkedin_from_text(full_text) or _extract_linkedin_from_hyperlinks(doc.hyperlinks)
        location, location_score = _extract_location(lines)
        candidate_name = _infer_candidate_name(list(lines_with_font_size.items()))

        reasons = []
        hits = 0
        for label, value in (
            ("candidate_name", candidate_name),
            ("email", email),
            ("phone", phone),
            ("linkedin", linkedin),
        ):
            if value:
                reasons.append(f"+{label}_found")
                hits += 1
            else:
                reasons.append(f"-{label}_not_found")
        if location and location_score >= LOCATION_MATCH_THRESHOLD:
            reasons.append(f"+location_gazetteer_match:{location_score:.0f}")
            hits += 1
        else:
            location = ""
            reasons.append("-location_not_found")

        entity = {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "location": location,
        }
        score = hits / 5

        return ParserResult(entities=[entity], confidences=[Confidence(score=score, reasons=reasons)])
