"""
EducationParser — Stage 4 plugin for the Education section (degree, major,
institution, graduation_year). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Given this field has zero downstream functional consumers today (Section
1.2 of the architecture doc), good display quality is the bar, not
perfect recall -- entry-clustered the same way as `ExperienceParser`/
`ProjectParser` (structurally identical: a bold/larger header line plus
body), then gazetteer/regex extraction over the whole entry's text, since
degree/institution/year can appear in either order across templates.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from resume_engine.confidence import Confidence
from resume_engine.degree_gazetteer import DEGREES
from resume_engine.institution_gazetteer import INSTITUTIONS
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line
from resume_engine.validation import Observation

# Validation-derived, tunable, same discipline as ROLE_MATCH_THRESHOLD
# (experience_parser.py) / LOCATION_MATCH_THRESHOLD (contact_parser.py).
DEGREE_MATCH_THRESHOLD = 80
INSTITUTION_MATCH_THRESHOLD = 80

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
# Bounded (not a broad greedy character class -- an earlier version let the
# trailing group consume unrelated text past the institution name, e.g. a
# degree line concatenated onto the same match) title-case word sequence
# around the keyword: up to 4 leading words, an optional "of/for <Words>"
# trailing phrase (covers "Institute of Technology" style names).
_INSTITUTION_KEYWORD_PATTERN = re.compile(
    r"(?:[A-Z][A-Za-z&.'\-]*\s+){0,4}(?:University|Institute|College|Polytechnic|School)"
    r"(?:\s+(?:of|for)\s+[A-Z][A-Za-z&.'\-]*(?:\s+[A-Z][A-Za-z&.'\-]*){0,3})?"
)
# Longest gazetteer entries first so "Bachelor of Science" matches before
# the substring "BS" could accidentally win on a shorter/looser check.
_DEGREES_LONGEST_FIRST = sorted(DEGREES, key=len, reverse=True)
_MAJOR_PATTERN = re.compile(
    r"\b(?:of|in)\s+([A-Z][A-Za-z&/\-]*(?:\s+[A-Z][A-Za-z&/\-]*){0,4})"
)


def _find_degree(lines: list[str]) -> tuple[str, str]:
    """Returns (degree, line_it_was_found_on) -- the line is needed so
    `_find_major` only searches within that same printed line, never
    bleeding into an institution/year line that happens to follow it."""
    for line in lines:
        for degree in _DEGREES_LONGEST_FIRST:
            if re.search(r"\b" + re.escape(degree) + r"\b", line):
                return degree, line
    return "", ""


def _find_major(degree_line: str, degree: str) -> str:
    """Looks for "<degree> of/in <Major>" on the SAME line the degree was
    found on -- bounded to one printed line so it can't run into an
    institution name or year printed on a different line."""
    if not degree_line:
        return ""
    search_from = degree_line
    idx = degree_line.find(degree)
    if idx != -1:
        search_from = degree_line[idx + len(degree) :]
    match = _MAJOR_PATTERN.search(search_from)
    return match.group(1).strip(" ,.-") if match else ""


def _find_institution(lines: list[str]) -> tuple[str, bool]:
    """Returns (institution_text, gazetteer_matched). The keyword regex
    finds an institution-*shaped* line first (contains University/
    Institute/College/etc.), searched one line at a time so the match
    can't extend past that line's own text; the gazetteer then only
    decides confidence tier, per the architecture doc's "not required"
    rule -- an unrecognized institution is still accepted."""
    for line in lines:
        match = _INSTITUTION_KEYWORD_PATTERN.search(line)
        if match:
            candidate = match.group(0).strip(" ,.-")
            _, score, _ = process.extractOne(
                candidate, INSTITUTIONS, scorer=fuzz.token_sort_ratio, processor=str.lower
            )
            return candidate, score >= INSTITUTION_MATCH_THRESHOLD
    return "", False


def _find_graduation_year(text: str) -> str:
    match = _YEAR_PATTERN.search(text)
    return match.group(0) if match else ""


class EducationParser:
    entity_name = "education"
    required_sections: tuple[str, ...] = ("education",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("education")
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
                        message="Education section detected but no parseable entries found inside it.",
                        entity_ref="education",
                    )
                ],
            )

        result_entities = []
        result_confidences = []
        observations = []

        for index, entry in enumerate(entries):
            lines = [entry.header_text, *entry.body_lines]
            entry_text = " ".join(lines).strip()

            degree, degree_line = _find_degree(lines)
            major = _find_major(degree_line, degree) if degree else ""
            institution, institution_gazetteer_matched = _find_institution(lines)
            graduation_year = _find_graduation_year(entry_text)

            reasons = []
            score = 0.0
            if degree:
                reasons.append(f"+degree_gazetteer_matched:{degree}")
                score += 0.5
            else:
                reasons.append("-no_degree_matched")
                observations.append(
                    Observation(
                        severity="notice",
                        category="missing_degree",
                        message=f"Education entry at index {index} has no recognizable degree.",
                        entity_ref=f"education[{index}]",
                    )
                )
            if graduation_year:
                reasons.append(f"+parseable_graduation_year:{graduation_year}")
                score += 0.25
            else:
                reasons.append("-no_graduation_year_found")
            if institution:
                if institution_gazetteer_matched:
                    reasons.append(f"+institution_gazetteer_matched:{institution}")
                    score += 0.25
                else:
                    reasons.append(f"+institution_present_not_gazetteer_matched:{institution}")
                    score += 0.125
            else:
                reasons.append("-no_institution_found")

            result_entities.append(
                {
                    "degree": degree,
                    "major": major,
                    "institution": institution,
                    "graduation_year": graduation_year,
                }
            )
            result_confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=result_entities, confidences=result_confidences, observations=observations)
