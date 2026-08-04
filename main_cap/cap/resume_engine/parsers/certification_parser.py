"""
CertificationParser — Stage 4 plugin for the Certifications section. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Simplest parser: one gazetteer-normalized entry per line/bullet in an
explicit Certifications section. Also scans Skills/Summary sections for
stray certification mentions not under a dedicated heading (some resumes
only have one line: "AWS Certified, 2023" with no separate section) via
the same gazetteer.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from resume_engine.certification_gazetteer import CERTIFICATIONS
from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import strip_section_header_line
from resume_engine.validation import Observation

# Validation-derived, tunable, same discipline as the other parsers' match
# thresholds (ROLE_MATCH_THRESHOLD, LOCATION_MATCH_THRESHOLD, ...).
CERTIFICATION_MATCH_THRESHOLD = 85
STRAY_MENTION_MATCH_THRESHOLD = 90


def _lines_from_spans(spans) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for span in spans:
        text = span.text.strip(" \t•·-")
        if text and text not in seen:
            seen.add(text)
            lines.append(text)
    return lines


def _canonicalize(text: str) -> tuple[str, bool]:
    """Returns (canonical_form, gazetteer_matched) via fuzzy match against
    the certification gazetteer -- catches near-exact variants (extra
    punctuation, "AWS Certified Solutions Architect - Associate" vs. the
    gazetteer's own spacing) without requiring an exact string match."""
    match, score, _ = process.extractOne(
        text, CERTIFICATIONS, scorer=fuzz.token_sort_ratio, processor=str.lower
    )
    if score >= CERTIFICATION_MATCH_THRESHOLD:
        return match, True
    return text, False


def _stray_mentions(sections, exclude_label: str, already_found: set[str]) -> list[str]:
    """Sweeps Skills/Summary sections (if present) for gazetteer
    certification names mentioned inline, not under a dedicated
    Certifications heading -- e.g. a resume with only "AWS Certified
    Solutions Architect, 2023" as a single stray line somewhere else."""
    found: list[str] = []
    seen = set(already_found)
    for label in ("skills", "summary"):
        if label == exclude_label:
            continue
        section = sections.get(label)
        if section is None:
            continue
        text = " ".join(s.text for s in section.spans).lower()
        for cert in CERTIFICATIONS:
            key = cert.lower()
            if key in seen:
                continue
            if key in text:
                seen.add(key)
                found.append(cert)
    return found


class CertificationParser:
    entity_name = "certifications"
    required_sections: tuple[str, ...] = ("certifications",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("certifications")

        deduped: list[str] = []
        confidences: list[Confidence] = []
        seen: set[str] = set()
        observations: list[Observation] = []

        if section is not None and section.spans:
            lines = _lines_from_spans(strip_section_header_line(section.spans, section.raw_header_text))
            if not lines:
                observations.append(
                    Observation(
                        severity="notice",
                        category="empty_section",
                        message="Certifications section detected but no parseable entries found inside it.",
                        entity_ref="certifications",
                    )
                )
            for line in lines:
                canonical, matched = _canonicalize(line)
                key = canonical.lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(canonical)

                reasons = [f"+listed_in_explicit_certifications_section:{canonical}"]
                score = 0.6 + 0.15 * section.header_confidence
                if matched:
                    reasons.append("+certification_gazetteer_match")
                    score = min(1.0, score + 0.25)
                else:
                    reasons.append("-not_a_gazetteer_certification")
                confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        for cert in _stray_mentions(sections, exclude_label="certifications", already_found=seen):
            deduped.append(cert)
            confidences.append(
                Confidence(
                    score=0.5,
                    reasons=[
                        f"+found_via_stray_mention_sweep:{cert}",
                        "-not_under_dedicated_certifications_heading",
                    ],
                )
            )

        return ParserResult(entities=deduped, confidences=confidences, observations=observations)
