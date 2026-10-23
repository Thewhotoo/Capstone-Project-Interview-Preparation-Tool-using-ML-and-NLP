"""
ExperienceParser — Stage 4 plugin for the Experience section (role,
company, duration, summary). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

The load-bearing parser per the Section 1.2 dependency map: `role` is the
field that gates whether an entry produces any interview questions
downstream at all (topic_pool.py Priority 3).
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from resume_engine.confidence import Confidence
from resume_engine.dates import parse_date_range
from resume_engine.interfaces import ParserResult
from resume_engine.job_title_gazetteer import JOB_TITLES
from resume_engine.location_gazetteer import LOCATIONS
from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line
from resume_engine.text_normalization import strip_date_ranges, strip_leading_bullet
from resume_engine.validation import Observation

# Validation-derived, tunable, same discipline as layout.py/sections.py.
ROLE_MATCH_THRESHOLD = 75

# Generic company-name suffix markers (a legal/organizational form), used
# ONLY in the no-gazetteer-role fallback to recognize a header that is a
# COMPANY name on its own (no role printed on the same line) -- e.g.
# "Hindustan Aeronautics Limited", where the role ("Engineering Intern")
# lives on the following body line. Without this the whole company name was
# guessed to be the `role` by the positional fallback. A small, generic
# lexical class (organizational-form nouns), never a specific company name.
_COMPANY_MARKERS = (
    "limited", "ltd", "inc", "incorporated", "llc", "llp", "plc", "gmbh",
    "corp", "corporation", "company", "co.", "pvt", "private", "technologies",
    "solutions", "systems", "industries", "enterprises", "labs",
)
_COMPANY_MARKER_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in _COMPANY_MARKERS) + r")\b", re.IGNORECASE,
)


def _looks_like_company(text: str) -> bool:
    return bool(_COMPANY_MARKER_PATTERN.search(text))

_SPLIT_PATTERNS = (
    re.compile(r"\s+at\s+", re.IGNORECASE),
    re.compile(r"\s*[—–]\s*"),
    # "--" (a plain-text em-dash stand-in, e.g. "Creative Studio -- Senior
    # Designer -- 2020-Present") MUST be tried before the single-hyphen
    # pattern below: `\s*-\s*` only consumes ONE of the two hyphens (its
    # trailing \s* matches zero chars since the next char is the second
    # hyphen, not whitespace), leaving a stray leading "-" stuck to the
    # second half ("- Senior Designer") -- which then fails the job-title
    # gazetteer match on that half and silently flips role/company via the
    # positional fallback in `_disambiguate_role_company`.
    re.compile(r"\s*--\s*"),
    re.compile(r"\s*-\s*"),
    re.compile(r"\s*,\s*"),
)

# General (not resume-specific) markers for "this half names a hosting
# institution/organization, not a personal job title" -- used ONLY inside
# the existing no-confident-gazetteer-match fallback below, to catch the
# "Org, Host Institution" header shape (e.g. a lab hosted at a university)
# that the position-based guess otherwise misreads as "Title, Company".
# Deliberately a small, generic lexical class (institution-type nouns),
# not any specific school/company name.
_INSTITUTION_MARKERS = ("university", "college", "institute", "polytechnic", "campus")
_INSTITUTION_MARKER_PATTERN = re.compile(
    r"\b(?:" + "|".join(_INSTITUTION_MARKERS) + r")\b", re.IGNORECASE,
)


def _looks_like_institution(text: str) -> bool:
    return bool(_INSTITUTION_MARKER_PATTERN.search(text))


def _split_role_company(text: str) -> tuple[str, str]:
    """Tries delimiters in priority order (" at " > dash > comma); the
    first one that produces exactly two non-empty halves wins. Falls back
    to treating the whole line as a single (unsplit) segment if none do."""
    for pattern in _SPLIT_PATTERNS:
        parts = pattern.split(text, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


def _disambiguate_role_company(part_a: str, part_b: str) -> tuple[str, str, bool]:
    """Whichever half matches the job-title gazetteer is `role` (template
    order varies: "Senior Engineer, Acme Corp" vs. "Acme Corp — Senior
    Engineer"). Returns (role, company, gazetteer_matched)."""
    if not part_b:
        return part_a, "", False
    _, score_a, _ = process.extractOne(part_a, JOB_TITLES, scorer=fuzz.token_sort_ratio, processor=str.lower)
    _, score_b, _ = process.extractOne(part_b, JOB_TITLES, scorer=fuzz.token_sort_ratio, processor=str.lower)
    if score_a >= ROLE_MATCH_THRESHOLD and score_a >= score_b:
        return part_a, part_b, True
    if score_b >= ROLE_MATCH_THRESHOLD:
        return part_b, part_a, True
    # Neither matched confidently -- documented fallback (architecture doc
    # Section 4.4): first segment = role, the more common convention.
    return part_a, part_b, False


# Head nouns of job titles ("Engineering Intern", "Operations Executive") -- a
# generic lexical class used with the gazetteer to recognise a title printed on
# the line under a company-only header (or vice versa).
_TITLE_HEAD_PATTERN = re.compile(
    r"\b(?:intern|engineer|developer|analyst|manager|designer|executive|researcher|scientist|"
    r"consultant|lead|associate|architect|specialist|administrator|officer|director|assistant|"
    r"trainee|fellow|technician|programmer|coordinator|head|founder|co-founder|volunteer)s?\b",
    re.IGNORECASE,
)
_BULLET_START = re.compile(r"^\s*[•◦▪▸►●○■□\-–—*·]")
# "Developed ...", "Built ...", "Led ..." -- a description line, not a label
_ACTION_VERB_START = re.compile(
    r"^(?:[A-Z][a-z]+ed|Built|Led|Ran|Made|Wrote|Drove|Took|Won|Set|Grew|Cut|Owned|Supported|Helped)\b")
_ADDRESS_TAIL = re.compile(r"\s+[-–—|]\s+.*\d.*$")              # "Gravity Tech - 123 Anywhere St., Any City"
_PIPE_TAIL = re.compile(r"\s+\|\s+.*$")                         # "Borcelle Company | Sydney, Australia"
_CITY_COUNTRY_TAIL = re.compile(r"\s+[A-Z][\w.]+,\s*[A-Z][\w ]+$")  # "... Bengaluru, India" (one-word city:
# a two-word pattern also swallowed the title's last word, "... Intern Bengaluru, India")
_BASED_TAIL = re.compile(r"\s+\S+-based$", re.IGNORECASE)        # "... Cyprus-based"
_JUNK_BRACKETS = re.compile(r"\[[^A-Za-z0-9\]]*\]|\(\s*\)")       # icon remnants "[ \x80 ]", empty "()"
_KNOWN_LOCATIONS = {loc.lower() for loc in LOCATIONS} | {"bangalore", "bengaluru", "remote"}


def _clean_label(text: str) -> str:
    text = _JUNK_BRACKETS.sub("", text)
    text = re.sub(r"^\s*[•◦▪▸►●○■□*·]\s*", "", text)
    return re.sub(r"\s{2,}", " ", text).strip(" ,|-–—")


def _strip_trailing_location(text: str) -> str:
    for pattern in (_ADDRESS_TAIL, _PIPE_TAIL, _CITY_COUNTRY_TAIL, _BASED_TAIL):
        stripped = pattern.sub("", text).strip()
        if stripped and stripped != text:
            text = stripped
    words = text.split()
    if len(words) > 1 and words[-1].lower().strip(",") in _KNOWN_LOCATIONS:   # "Engineering Intern Bangalore"
        text = " ".join(words[:-1])
    return text.strip(" ,|-–—")


def _title_score(text: str) -> float:
    if not text:
        return 0.0
    _, score, _ = process.extractOne(text, JOB_TITLES, scorer=fuzz.token_sort_ratio, processor=str.lower)
    return score


def _looks_like_title(text: str) -> bool:
    if not text:
        return False
    if _title_score(text) >= ROLE_MATCH_THRESHOLD:
        return True
    head = _TITLE_HEAD_PATTERN.search(text)
    return head is not None and len(text[: head.end()].split()) <= 6


def _title_prefix(text: str) -> str:
    """Cuts a title line at its head noun (keeping a parenthetical or a short
    dash qualifier right after it), dropping a second right-aligned label:
    'AI Infrastructure Security Engineer (Freelance) Cyprus-based AI Company'
    -> 'AI Infrastructure Security Engineer (Freelance)'."""
    if _title_score(text) >= ROLE_MATCH_THRESHOLD:
        return text
    head = _TITLE_HEAD_PATTERN.search(text)
    if head is None:
        return text
    tail = re.match(r"\s*(\([^)]*\)|[—–-]{1,2}\s*[A-Z][\w/&+ ]{0,25}?(?=\s{2,}|$))?", text[head.end():])
    return (text[: head.end()] + (tail.group(0) if tail else "")).strip()


def _label_line(body_lines: list[str], skip_index) -> tuple[int, str] | None:
    """The first body line directly under the header, when it reads as a short
    label (company or title, possibly followed by a location) rather than a
    description bullet or a date."""
    for i, line in enumerate(body_lines):
        if i == skip_index:
            continue
        raw = line.strip()
        if (not raw or _BULLET_START.match(raw) or _ACTION_VERB_START.match(raw)
                or raw.endswith(".") or len(raw.split()) > 10 or parse_date_range(raw) is not None):
            return None
        cleaned = _strip_trailing_location(_clean_label(raw))
        return (i, cleaned) if cleaned else None
    return None


def _find_date_range(header_text: str, body_lines: list[str]):
    """Checks the header line first (the common case -- a date printed
    inline on the same line as role/company), then each body line in
    order (a template where the date is on its own line right below).
    Returns (date_range_or_None, matched_body_line_index_or_None)."""
    date_range = parse_date_range(header_text)
    if date_range is not None:
        return date_range, None
    for i, line in enumerate(body_lines):
        date_range = parse_date_range(line)
        if date_range is not None:
            return date_range, i
    return None, None


class ExperienceParser:
    entity_name = "experience"
    required_sections: tuple[str, ...] = ("experience",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("experience")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        entry_spans = strip_section_header_line(section.spans, section.raw_header_text)
        entries = cluster_entries(entry_spans, doc.body_font_size)
        if not entries:
            return ParserResult(
                entities=[],
                confidences=[],
                observations=[
                    Observation(
                        severity="notice",
                        category="empty_section",
                        message="Experience section detected but no parseable entries found inside it.",
                        entity_ref="experience",
                    )
                ],
            )

        result_entities = []
        result_confidences = []
        observations = []

        for index, entry in enumerate(entries):
            date_range, date_line_index = _find_date_range(entry.header_text, entry.body_lines)

            header_for_split = strip_leading_bullet(entry.header_text)
            if date_range is not None and date_line_index is None:
                header_for_split = header_for_split.replace(date_range.display, "").strip(" ,-—–")
                # The printed form often differs from the normalized display
                # ("March, 2022 - March, 2025"); left in, its dash split the
                # header into role "Software Developer March, 2022" and
                # company "March, 2025". Remove the date range as printed too.
                header_for_split = re.sub(r"\s{2,}", " ", strip_date_ranges(header_for_split)).strip(" ,-—–|")

            part_a, part_b = _split_role_company(header_for_split)
            role, company, gazetteer_matched = _disambiguate_role_company(part_a, part_b)

            # Company-only header fallback (Phase 1): the header is a single
            # segment that reads as a COMPANY name (organizational-form
            # marker) rather than a job title, and nothing gazetteer-matched
            # as a role -- e.g. "Hindustan Aeronautics Limited", with the
            # role on a following body line. Put it in `company` and leave
            # `role` empty (never fabricate a title from a company name),
            # the same honest-empty discipline as the institution fallback.
            company_fallback = False
            if not gazetteer_matched and not company and role and _looks_like_company(role):
                company, role = role, ""
                company_fallback = True

            institution_fallback = False
            if not gazetteer_matched and part_b and (_looks_like_institution(part_a) or _looks_like_institution(part_b)):
                # Neither half read as a job title, and at least one half
                # reads as a hosting institution/organization (university,
                # college, institute, campus, polytechnic) rather than a
                # personal role -- e.g. "CAVE Labs – PES University EC
                # Campus" (a lab hosted at a university, not "Title –
                # Company"). Guessing which half is the role by position
                # here would fabricate a job title the resume never
                # actually stated. Preserve the header VERBATIM as the
                # organizational context instead of reconstructing it from
                # the split pieces (which could pick the wrong delimiter/
                # spacing), and leave role genuinely unknown rather than
                # invented -- the schema already supports role="" (see
                # module docstring / ExperienceEntry's default).
                role, company = "", header_for_split
                institution_fallback = True

            role, company = _clean_label(role), _clean_label(company)

            # Two-line header (Phase 2): many templates print the title and the
            # company on separate lines ("Software Developer" / "Gravity Tech -
            # 123 Anywhere St."; "ForGood.ai" / "Software Developer -- AI
            # Systems  Bengaluru, India"). When one half is missing, complete it
            # from the short label line directly under the header.
            consumed_index = None
            label = _label_line(entry.body_lines, date_line_index) if (not role or not company) else None
            if label is not None:
                label_index, label_text = label
                if not role and _looks_like_title(label_text):
                    role, consumed_index = _title_prefix(label_text), label_index
                elif role and not company and not gazetteer_matched and _looks_like_title(label_text) \
                        and not _looks_like_title(role):
                    # the header was the company, the title is on the next line
                    company, role, consumed_index = role, _title_prefix(label_text), label_index
                elif role and not company and not _looks_like_title(label_text):
                    company, consumed_index = label_text, label_index
            if consumed_index is not None:
                reasons_extra = "+two_line_header_completed"
            else:
                reasons_extra = None

            body_lines = [
                line for i, line in enumerate(entry.body_lines) if i not in (date_line_index, consumed_index)
            ]
            summary = " ".join(body_lines).strip()

            reasons = []
            score = 0.0
            if gazetteer_matched:
                reasons.append("+role_gazetteer_matched")
                score += 0.4
            elif institution_fallback:
                reasons.append("-role_not_gazetteer_matched")
                reasons.append("+role_left_empty_institutional_pattern")
            elif company_fallback:
                reasons.append("-role_not_gazetteer_matched")
                reasons.append("+company_marker_recognized_role_left_empty")
            else:
                reasons.append("-role_not_gazetteer_matched")
            if reasons_extra:
                reasons.append(reasons_extra)
            if date_range is not None and date_range.start is not None:
                reasons.append(f"+parseable_date_range:{date_range.display}")
                score += 0.3
            else:
                reasons.append("-no_parseable_dates")
                observations.append(
                    Observation(
                        severity="notice",
                        category="missing_dates",
                        message=f"Experience entry '{role}' has no parseable dates.",
                        entity_ref=f"experience[{index}]",
                    )
                )
            if summary:
                reasons.append("+non_empty_summary")
                score += 0.2
            else:
                reasons.append("-empty_summary")
            reasons.append(f"+section_confidence:{section.header_confidence:.2f}")
            score += 0.1 * section.header_confidence

            result_entities.append(
                {
                    "company": company,
                    "role": role,
                    "duration": date_range.display if date_range is not None else "",
                    "summary": summary,
                }
            )
            result_confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=result_entities, confidences=result_confidences, observations=observations)
