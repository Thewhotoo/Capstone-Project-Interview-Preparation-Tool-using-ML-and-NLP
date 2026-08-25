"""
SkillsParser — Stage 4 plugin for the Skills section. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Splits the explicit Skills section on common delimiters, normalizes each
token against the shared `technology_gazetteer.py` (same single source of
truth `ProjectParser` already uses, per the architecture doc's explicit
"must agree on one canonical gazetteer, not drift" requirement). A token
that doesn't match the gazetteer is still kept verbatim (resumes list
plenty of legitimate skills -- "Leadership", "Agile" -- outside a
technology-only vocabulary), just without the gazetteer-match confidence
boost. Cross-section "demonstrated in a project" tagging is NOT this
parser's job -- that's the Cross-Reference Pass (cross_reference.py).
"""

from __future__ import annotations

import re

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import _group_into_lines, strip_section_header_line
from resume_engine.technology_gazetteer import TECHNOLOGIES
from resume_engine.validation import Observation

_SPLIT_PATTERN = re.compile(r"[,;|•·•·\n]")
_TECHNOLOGIES_LOWER = {t.lower(): t for t in TECHNOLOGIES}


def _spans_to_text(spans) -> str:
    """Reconstructs the section's text one VISUAL LINE at a time (grouping
    word-level `TextSpan`s by y0-proximity via `_entry_clustering._group_into_lines`
    -- the same line-grouping every other parser in this package already
    uses), joining lines with '\\n' so a genuine one-skill-per-line template
    still splits correctly, but words on the SAME line never do.

    Found during resume-intelligence-quality validation: `Section.spans`
    (sections.py) is word-granular (one `TextSpan` per PDF text run, not
    per physical line) -- joining every span directly with '\\n' put a line
    break between every word, including inside a single multi-word skill
    ("Hugging Face" -> "Hugging", "Face"; "VS Code" -> "VS", "Code"), since
    '\\n' is one of `_SPLIT_PATTERN`'s delimiters."""
    lines = _group_into_lines(list(spans))
    return "\n".join(line.text for line in lines if line.text)


def _split_tokens(text: str) -> list[str]:
    """Splits on common delimiters (comma, pipe, bullet, line break), then
    dedupes case-insensitively while preserving first-seen casing -- same
    dedup convention `ProjectParser._extract_technologies` already uses.

    A category-labeled skills line ("Languages: Python, Java, ...") has no
    comma between the label and its first value, so that first split token
    is "Languages: Python", not "Languages:" and "Python" separately --
    every such token is resolved the same structural way: whatever precedes
    the LAST ':' is a category label, never a skill, so only the text after
    it is kept (a colon-only token, e.g. a standalone "Databases:" label
    line with nothing after it, resolves to nothing and is dropped)."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in _SPLIT_PATTERN.split(text):
        token = raw.strip(" \t.")
        if ":" in token:
            token = token.rsplit(":", 1)[-1].strip(" \t.")
        if not token:
            continue
        key = token.lower()
        if key not in seen:
            seen.add(key)
            tokens.append(token)
    return tokens


def _canonicalize(token: str) -> tuple[str, bool]:
    """Returns (canonical_form, gazetteer_matched). An exact (case-
    insensitive) gazetteer hit is normalized to the gazetteer's own
    casing (e.g. "javascript" -> "JavaScript"); anything else is kept
    verbatim as the resume printed it."""
    canonical = _TECHNOLOGIES_LOWER.get(token.lower())
    if canonical is not None:
        return canonical, True
    return token, False


class SkillsParser:
    entity_name = "skills"
    required_sections: tuple[str, ...] = ("skills",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("skills")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        spans = strip_section_header_line(section.spans, section.raw_header_text)
        full_text = _spans_to_text(spans)
        tokens = _split_tokens(full_text)

        if not tokens:
            return ParserResult(
                entities=[],
                confidences=[],
                observations=[
                    Observation(
                        severity="notice",
                        category="empty_section",
                        message="Skills section detected but no parseable skills found inside it.",
                        entity_ref="skills",
                    )
                ],
            )

        # One Confidence per skill (interfaces.check_parser_conformance
        # requires len(entities) == len(confidences), 1:1, same contract
        # every other parser follows) -- a skill's own gazetteer-match
        # status is exactly the per-skill signal Section 7 of the
        # architecture doc describes ("high if found via gazetteer match
        # in an explicit Skills section; reduced otherwise").
        deduped: list[str] = []
        confidences: list[Confidence] = []
        seen: set[str] = set()
        for token in tokens:
            canonical, matched = _canonicalize(token)
            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(canonical)

            reasons = [f"+listed_in_explicit_skills_section:{canonical}"]
            score = 0.7 + 0.2 * section.header_confidence
            if matched:
                reasons.append("+technology_gazetteer_match")
                score = min(1.0, score + 0.2)
            else:
                reasons.append("-not_a_gazetteer_technology")
            confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=deduped, confidences=confidences, observations=[])
