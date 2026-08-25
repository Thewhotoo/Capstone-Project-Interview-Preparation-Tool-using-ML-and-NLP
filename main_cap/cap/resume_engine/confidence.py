"""
Confidence — the explainability primitive used by every stage from Section
Detection onward, plus the final Confidence Scoring stage (Stage 8) that
aggregates per-entity confidence once Cross-Reference and Normalization
have run.

See docs/architecture/ResumeIntelligenceEngine.md Section 3.2 (the `+`/`-`
sign convention on `reasons`) and Section 7 (the scoring formulas). Only
the data model and the stub engine live here in Milestone 0; the actual
weighted-signal scoring formulas are Milestone 6 work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Confidence:
    """A score with its own explanation, always together, never separately.

    `reasons` entries are sign-prefixed so every renderer (PipelineTrace's
    to_console/to_html/to_json, Section 6.4) can format them identically:
    "+" = a positive signal that fired, "-" = a checked signal that was
    absent or failed. E.g. ["+found_in_explicit_skills_section",
    "-no_measurable_outcome_detected"].
    """

    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class AnnotatedCandidateProfile:
    """The output of Stage 8 (Confidence Scoring) — every parsed entity
    plus its Confidence, plus the Validation layer's Observations.

    This is NOT yet shaped to mirror the public `CandidateProfile`
    (candidate_profile_generator.py) field-for-field. Per
    docs/architecture/ResumeIntelligenceEngine.md's Milestone 0 risk notes,
    that mapping is deliberately deferred to whichever later milestone
    first has enough real parser output to design it against real data,
    rather than being guessed at here.
    """

    parser_results: dict[str, Any] = field(default_factory=dict)  # entity_name -> ParserResult
    observations: list[Any] = field(default_factory=list)  # list[Observation]
    overall_confidence: Confidence = field(default_factory=lambda: Confidence(score=0.0, reasons=[]))


class DefaultConfidenceEngine:
    """Concrete `interfaces.ConfidenceEngine` implementation -- Stage 8.

    By the time this stage runs, every entity from every parser already
    carries its own explained `Confidence` (Section 7's weighted formulas
    live INSIDE each parser -- `ContactParser`/`ExperienceParser`/
    `ProjectParser`/`EducationParser`/`SkillsParser`/`CertificationParser`
    -- not here). This stage's job is strictly aggregation: fold every
    already-computed per-entity score into one profile-level
    `overall_confidence`, using only signals earlier stages already
    produced -- never a new per-field heuristic invented at this layer.

    Mechanism: a flat, unweighted mean across every individual entity's
    `Confidence.score`, pooled across all parsers. Deliberately NOT
    weighted by entity-type "importance" (e.g. favoring projects/
    experience over education) -- that would be exactly the kind of new
    heuristic this stage is meant to avoid inventing; if a future
    milestone wants importance-weighted aggregation, that is a
    reviewable, documented change to this one function, not a silent
    assumption baked in now.
    """

    def score(self, parser_results, observations, trace=None) -> AnnotatedCandidateProfile:
        reasons: list[str] = []
        all_scores: list[float] = []

        for entity_name in sorted(parser_results.keys()):
            result = parser_results[entity_name]
            if result.confidences:
                avg = sum(c.score for c in result.confidences) / len(result.confidences)
                reasons.append(
                    f"+{entity_name}:{len(result.confidences)} entities, avg confidence {avg:.2f}"
                )
                all_scores.extend(c.score for c in result.confidences)
            else:
                reasons.append(f"-{entity_name}:no_entities_found")

        if all_scores:
            overall_score = round(sum(all_scores) / len(all_scores), 4)
        else:
            overall_score = 0.0
            reasons.append("-no_entities_found_in_any_parser")

        overall_confidence = Confidence(score=overall_score, reasons=reasons)

        return AnnotatedCandidateProfile(
            parser_results=parser_results,
            observations=observations,
            overall_confidence=overall_confidence,
        )
