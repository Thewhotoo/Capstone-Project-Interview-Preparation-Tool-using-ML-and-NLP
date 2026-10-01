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

import re

from rapidfuzz import fuzz, process

from resume_engine.certification_gazetteer import CERTIFICATIONS
from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import _group_into_lines, strip_section_header_line
from resume_engine.text_normalization import reads_as_sentence, starts_with_action_verb, strip_leading_bullet
from resume_engine.validation import Observation

# Validation-derived, tunable, same discipline as the other parsers' match
# thresholds (ROLE_MATCH_THRESHOLD, LOCATION_MATCH_THRESHOLD, ...).
CERTIFICATION_MATCH_THRESHOLD = 85
STRAY_MENTION_MATCH_THRESHOLD = 90

# Lines that are certificate/credential IDs or bare numeric fragments, not
# certification NAMES. A credential ID line and its wrapped numeric tail
# ("Credential ID: UC-...", "064") were being emitted as separate
# "certifications". Generic structural patterns, never resume-specific.
_CREDENTIAL_ID_PATTERN = re.compile(
    r"(?:credential|certificate|licen[cs]e|registration|enrol(?:l)?ment|serial)\s*(?:id|no|number|#)?\s*[:#]"
    r"|\bid\s*[:#]",
    re.IGNORECASE,
)
_ID_FRAGMENT_PATTERN = re.compile(r"^[\d\s.\-/]+$")  # only digits/dashes/dots/slashes


def _is_credential_noise(text: str) -> bool:
    """True for a credential/certificate ID line or a bare numeric-fragment
    line -- metadata about a certification, never the certification name."""
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    if _ID_FRAGMENT_PATTERN.match(stripped):
        return True
    return bool(_CREDENTIAL_ID_PATTERN.search(stripped))


_COMPANY_SUFFIX_RE = re.compile(r"\b(?:inc|ltd|llc|llp|co|corp|corporation|company|pvt|plc|gmbh)\.?$", re.IGNORECASE)
_DANGLING_END_RE = re.compile(r"\b(?:to|and|or|of|the|a|an|for|with|in|on|at|by|using|new|from|into)$", re.IGNORECASE)


def _is_not_a_certification_name(text: str, next_text: str = "") -> bool:
    """True for a line inside a Certifications section that cannot be a
    certification's NAME (integration fix, resumeParser_integration.md §2):
      - a date-only line ("01 Jun 2052- present", "2021 - 2022");
      - an issuer/company line ("Giggling Platypus Co.", "Acme Inc.");
      - a fragment of a description sentence: opens lowercase, opens with an
        action verb, ends on a dangling connector ("...a new", "...Borcelle to"),
        or reads as a sentence (reads_as_sentence).
    Real certification names are short noun phrases ("AWS Certified Cloud
    Practitioner", "Cloud Certified"), which none of these rules match."""
    stripped = strip_leading_bullet(text).strip()
    if not stripped:
        return True
    letters_left = re.sub(r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?|\b(?:present|current|now|to)\b|[\d\W_]", " ", stripped)
    if not letters_left.strip():
        return True
    if stripped[0].islower() or starts_with_action_verb(stripped):
        return True
    if _COMPANY_SUFFIX_RE.search(stripped.rstrip(" ,")):
        return True
    if _DANGLING_END_RE.search(stripped.rstrip(" ,")):
        return True
    return reads_as_sentence(stripped, "", next_text)


def _lines_from_spans(spans) -> list[str]:
    """One entry per VISUAL line/bullet, not one entry per span.

    Found during a real-resume demo audit: some PDFs' text extraction
    produces one `TextSpan` per WORD (justified-text spacing splits runs at
    each space) rather than one span per bullet line. Treating each raw
    span as its own "line" -- the previous behavior here -- silently
    shredded a single certification like "Introduction to Data Engineering
    on Google Cloud" into five bogus one-word certifications ("Introduction",
    "to", "Data", "Engineering", "on"), each then driving its own nonsense
    interview question. `_group_into_lines` (the same bbox-Y-position-based
    grouping `ExperienceParser`/`ProjectParser` already rely on via this
    module) reconstructs the real visual line first, so this parser now
    sees "Introduction to Data Engineering on Google Cloud" as ONE entry --
    exactly like it already would for a PDF whose extractor happens to
    produce one span per line."""
    lines_grouped = _group_into_lines(list(spans))
    texts = [line.text.strip(" \t•·-") for line in lines_grouped]
    seen: set[str] = set()
    lines: list[str] = []
    for i, text in enumerate(texts):
        next_text = texts[i + 1] if i + 1 < len(texts) else ""
        # Phase 1: drop credential/certificate ID lines and bare numeric
        # fragments -- they are metadata, not certification names, and were
        # being counted as separate certifications. Integration fix: also
        # dates, issuer/company lines and description-sentence fragments.
        if (text and text not in seen and not _is_credential_noise(text)
                and not _is_not_a_certification_name(text, next_text)):
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
