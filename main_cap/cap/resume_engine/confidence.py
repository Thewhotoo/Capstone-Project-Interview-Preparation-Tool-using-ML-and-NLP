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
    """Concrete `interfaces.ConfidenceEngine` implementation. The weighted
    per-entity-type scoring formulas (Section 7 of the architecture doc)
    are Milestone 6 work — not implemented yet."""

    def score(self, parser_results, observations, trace=None) -> AnnotatedCandidateProfile:
        raise NotImplementedError(
            "Confidence scoring formulas are implemented in Milestone 6 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 7)."
        )
