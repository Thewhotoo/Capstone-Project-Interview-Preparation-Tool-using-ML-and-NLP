"""
ProjectParser — Stage 4 plugin for the Projects section (title, summary,
technologies, concepts). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

The highest fan-out Milestone 3 parser: `topic_pool.py` Priority 2 reads
`summary`/`technologies` directly; the future Cross-Reference Pass
(Milestone 5) and `traceability.py` both key off `title`; Confidence
Scoring (Milestone 6) rolls up Project confidences into the profile-level
score. `title` is therefore a hard correctness requirement, not just a
field: `traceability.find_project_by_title` does an exact, case-insensitive
match against it, so it must be extracted consistently.

`interview_seeds` is deliberately NOT implemented here -- it stays `[]`.
That's Milestone 4 (design) / Milestone 5 (implementation) work, per the
permanent graceful-degradation rule: no seeds rather than weak/generic
ones. The confidence formula below therefore omits the architecture doc's
fourth term (interview-seed template precondition satisfied, +0.2) --
documented, not silently patched; M3's ProjectParser confidence tops out
around 0.8, not 1.0, until Milestone 5 adds that term.
"""

from __future__ import annotations

import logging
import re

from resume_engine.concept_gazetteer import CONCEPTS
from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line
from resume_engine.technology_gazetteer import TECHNOLOGIES
from resume_engine.validation import Observation

logger = logging.getLogger(__name__)

_TECH_LABEL_PATTERN = re.compile(r"^(?:tech(?:nolog(?:y|ies))?|stack|built with)\s*:\s*(.+)$", re.IGNORECASE)
_TECH_SPLIT_PATTERN = re.compile(r"[,;/|]| and ", re.IGNORECASE)

_SEM_MODEL_NAME = "all-MiniLM-L6-v2"


class _LazyKeyBERT:
    """Lazy singleton, private to this module -- same pattern as
    sections.py's `_LazySemanticModel` (Milestone 2), a separate copy
    rather than a shared import, per that module's own documented
    reasoning (each ML-touching module owns its lazy-load, never a crash
    if the model can't be loaded)."""

    _model = None

    @classmethod
    def get(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                from keybert import KeyBERT

                sem_model = SentenceTransformer(_SEM_MODEL_NAME)
                cls._model = KeyBERT(model=sem_model)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("KeyBERT unavailable for ProjectParser concept extraction: %s", e)
                cls._model = False
        return cls._model if cls._model is not False else None


def _extract_technologies(body_lines: list[str], full_text: str) -> tuple[list[str], bool]:
    """(a) an explicit "Tech:"/"Stack:"/"Built with:" labeled line, merged
    with (b) inline gazetteer matches against the entry's full text.
    Returns (technologies, had_labeled_line) -- deduped by exact string
    only; alias-collapsing ("JS"/"JavaScript") is Milestone 6's
    DefaultNormalizer, not this parser's job."""
    found: list[str] = []
    had_labeled_line = False
    for line in body_lines:
        match = _TECH_LABEL_PATTERN.match(line.strip())
        if match:
            had_labeled_line = True
            for token in _TECH_SPLIT_PATTERN.split(match.group(1)):
                token = token.strip()
                if token:
                    found.append(token)

    text_lower = full_text.lower()
    for tech in TECHNOLOGIES:
        pattern = r"\b" + re.escape(tech.lower()) + r"\b"
        if re.search(pattern, text_lower) and tech not in found:
            found.append(tech)

    # Dedup, case-insensitive, preserving first-seen form.
    seen = set()
    deduped = []
    for tech in found:
        key = tech.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(tech)
    return deduped, had_labeled_line


def _extract_concepts(text: str) -> list[str]:
    """KeyBERT proposes candidate keyphrases; only phrases matching
    `concept_gazetteer.py` are kept -- bounded, deterministic given fixed
    model weights (no open-ended generation). Returns [] if KeyBERT is
    unavailable, never raises."""
    model = _LazyKeyBERT.get()
    if model is None or not text.strip():
        return []
    try:
        pairs = model.extract_keywords(text, keyphrase_ngram_range=(1, 3), stop_words="english", top_n=10)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("KeyBERT extraction failed: %s", e)
        return []

    matched = []
    phrases_lower = [p[0].lower() for p in pairs]
    for concept in CONCEPTS:
        concept_lower = concept.lower()
        if any(concept_lower in phrase or phrase in concept_lower for phrase in phrases_lower):
            matched.append(concept)
    return matched


class ProjectParser:
    entity_name = "projects"
    required_sections: tuple[str, ...] = ("projects",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("projects")
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
                        message="Projects section detected but no parseable entries found inside it.",
                        entity_ref="projects",
                    )
                ],
            )

        result_entities = []
        result_confidences = []
        observations = []

        for index, entry in enumerate(entries):
            title = entry.header_text
            body_text = " ".join(entry.body_lines)

            technologies, had_labeled_line = _extract_technologies(entry.body_lines, body_text)
            concepts = _extract_concepts(body_text)
            summary_lines = [
                line for line in entry.body_lines if not _TECH_LABEL_PATTERN.match(line.strip())
            ]
            summary = " ".join(summary_lines).strip()

            reasons = []
            score = 0.0
            if entry.header_is_corroborated:
                reasons.append("+title_formatting_corroborated")
                score += 0.4
            else:
                reasons.append("-title_not_formatting_corroborated")
            if technologies:
                reasons.append(f"+technologies_extracted:{len(technologies)}")
                score += 0.25
                if had_labeled_line:
                    reasons.append("+explicit_tech_label_found")
            else:
                reasons.append("-no_technologies_extracted")
            reasons.append(f"+section_confidence:{section.header_confidence:.2f}")
            score += 0.15 * section.header_confidence
            reasons.append("-interview_seeds_not_implemented_until_milestone_5")

            if not title:
                observations.append(
                    Observation(
                        severity="notice",
                        category="missing_title",
                        message=f"Project entry at index {index} has no extractable title.",
                        entity_ref=f"projects[{index}]",
                    )
                )
            if not technologies:
                observations.append(
                    Observation(
                        severity="info",
                        category="missing_technologies",
                        message=f"Project '{title}' has no technologies listed.",
                        entity_ref=f"projects[{index}]",
                    )
                )

            result_entities.append(
                {
                    "title": title,
                    "summary": summary,
                    "technologies": technologies,
                    "concepts": concepts,
                    "interview_seeds": [],
                }
            )
            result_confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=result_entities, confidences=result_confidences, observations=observations)
