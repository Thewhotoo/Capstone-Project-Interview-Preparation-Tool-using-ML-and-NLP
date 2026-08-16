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
from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line
from resume_engine.validation import Observation

# Validation-derived, tunable, same discipline as layout.py/sections.py.
ROLE_MATCH_THRESHOLD = 75

_SPLIT_PATTERNS = (
    re.compile(r"\s+at\s+", re.IGNORECASE),
    re.compile(r"\s*[—–]\s*"),
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

            header_for_split = entry.header_text
            if date_range is not None and date_line_index is None:
                header_for_split = header_for_split.replace(date_range.display, "").strip(" ,-—–")

            part_a, part_b = _split_role_company(header_for_split)
            role, company, gazetteer_matched = _disambiguate_role_company(part_a, part_b)

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

            body_lines = [
                line for i, line in enumerate(entry.body_lines) if i != date_line_index
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
            else:
                reasons.append("-role_not_gazetteer_matched")
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
