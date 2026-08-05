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
_PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/\S+", re.IGNORECASE)

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
    match = _PHONE_PATTERN.search(text)
    return match.group(0).strip() if match else ""


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


def _infer_candidate_name(lines_with_font_size: list[tuple[str, float]]) -> str:
    """The most prominent (largest font) line(s) in the contact block that
    aren't themselves an email/phone/URL match -- almost always the name
    banner Section Detection's leading-block rule (Milestone 2) folded in
    here.

    ALL lines sharing that same largest font size are joined together (in
    their original top-to-bottom order), not just the first one found:
    some templates print a first/last name as two separate stacked lines
    at identical font size (e.g. "ANGEL" / "MATAPANG") rather than one
    line, and a strict single-line pick truncated the name to just the
    first line (found during Phase 1 real-world evaluation)."""
    candidates = [
        (text, size)
        for text, size in lines_with_font_size
        if text.strip()
        and not _EMAIL_PATTERN.search(text)
        and not _PHONE_PATTERN.search(text)
        and not _LINKEDIN_PATTERN.search(text)
    ]
    if not candidates:
        return ""
    max_size = max(size for _, size in candidates)
    return " ".join(text.strip() for text, size in candidates if size == max_size)


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
