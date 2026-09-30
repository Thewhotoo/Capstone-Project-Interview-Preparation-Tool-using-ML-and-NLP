"""
EvaluationResult — Phase 3 (RFC: AI Evaluation Engine, Revision 2 — APPROVED
AND FROZEN; Expected Concepts revision — APPROVED). Implemented exactly as
specified; no architectural deviation.

THE permanent contract every future evaluator (heuristic, Gemini, hybrid,
fine-tuned DeBERTa/RoBERTa, or anything not yet imagined) must satisfy.
Nothing about swapping the evaluator implementation may ever require
changing this schema's SHAPE — only the VALUES within its open,
registry-style fields (`MissingReasoningItem.category`, `confidence_source`)
are expected to grow over time (RFC Section 3, Section 6).

Expected Concepts revision (approved final ML RFC revision) adds
`concept_coverage` — deliberately a SEPARATE structure from
`missing_reasoning`. `missing_reasoning` describes HOW the candidate
reasoned (trade-offs, ownership, debugging, ...); `concept_coverage`
describes WHAT specific technical concepts were demonstrated, mentioned
superficially, or omitted. Conflating the two would blur a distinction that
matters for explainability — see `ConceptObservation` below.

SCHEMA VERSION BUMPED v1 -> v2 for this revision (same discipline as
`evaluation_request.py`). `evaluation_strategy_version` is NOT bumped:
concept_coverage does not change the composite scoring formula, the
dimension set, or how `overall_score` is computed — it is a purely
additive explainability structure, not a change to the rubric itself.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from question_families import ReasoningType

EVALUATION_RESULT_SCHEMA_VERSION = "v2"
# The "rubric" version (RFC Section 5) — describes HOW evaluation itself
# works (dimension set, composite formula, missing-reasoning taxonomy,
# confidence derivation), independent of which evaluator/model produced a
# given result. Bump this whenever any of those four things change; do NOT
# bump it for an evaluator/model update alone (that's evaluator_version /
# model_version's job).
EVALUATION_STRATEGY_VERSION = "v1"


_VALID_RECOMMENDED_ACTIONS = frozenset({"probe_deeper", "clarify", "move_on", "skip"})


class ConfidenceSource:
    """
    Open, registry-style well-known values (RFC Section 4) — NOT a closed
    enum. New sources are added as new string values on evaluator
    implementations, never as a schema change here. See the RFC's explicit
    design rule (Section 6): ReasoningType stays closed (stable cognitive
    taxonomy); this stays open (operational/ML-system taxonomy expected to
    grow).
    """

    HEURISTIC = "heuristic"
    MODEL = "model"
    ENSEMBLE = "ensemble"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


class MissingReasoningCategory:
    """Open, registry-style well-known values (RFC Section 3) — new
    categories are added as new string values on `MissingReasoningItem`,
    never as a schema change."""

    TRADEOFF = "tradeoff"
    ARCHITECTURE = "architecture"
    EXAMPLE = "example"
    TESTING = "testing"
    DEBUGGING = "debugging"
    METRICS = "metrics"
    EDGE_CASE = "edge_case"
    SCALABILITY = "scalability"
    DESIGN_DECISION = "design_decision"
    OWNERSHIP = "ownership"
    COMMUNICATION = "communication"


def _require_unit_interval(value: float, label: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{label} must be within [0.0, 1.0], got {value}")


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


class DimensionScore(BaseModel):
    """One evaluation dimension's score (RFC Section 4). `weight_used` is
    captured per result, not just per config, so a later reweighting never
    makes a historical result unreproducible (RFC Section 7 / Chapter
    19.7's versioning discipline, extended to the dimension level)."""

    model_config = ConfigDict(frozen=True)

    name: str
    raw_score: float
    weight_used: float
    confidence: float
    confidence_source: str
    contributes_to_overall: bool = True
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "DimensionScore":
        _require_non_empty(self.name, "name")
        _require_non_empty(self.confidence_source, "confidence_source")
        _require_unit_interval(self.raw_score, "raw_score")
        _require_unit_interval(self.confidence, "confidence")
        if self.weight_used < 0.0:
            raise ValueError("weight_used must be >= 0.0")
        return self


class EvidenceLinkedClaim(BaseModel):
    """A strength/weakness statement that must cite evidence — never a
    freestanding claim (RFC Section 5 / Chapter 12.3's "never invented"
    rule, applied to evaluation output)."""

    model_config = ConfigDict(frozen=True)

    claim: str
    dimension: str
    evidence: str

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceLinkedClaim":
        _require_non_empty(self.claim, "claim")
        _require_non_empty(self.dimension, "dimension")
        _require_non_empty(self.evidence, "evidence")
        return self


class MissingReasoningItem(BaseModel):
    """
    Generalized replacement for the five fixed `missing_*` fields from RFC
    Revision 1 (RFC Section 3, Revision 2). `category` is an open string
    (see `MissingReasoningCategory`) so new gap types are additive data,
    never a schema change.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    explanation: str
    expected_because: str
    evidence: str
    severity: float

    @model_validator(mode="after")
    def _validate(self) -> "MissingReasoningItem":
        _require_non_empty(self.category, "category")
        _require_non_empty(self.explanation, "explanation")
        _require_non_empty(self.expected_because, "expected_because")
        _require_unit_interval(self.severity, "severity")
        return self


class ConceptObservationStatus(str, Enum):
    """
    Closed — NOT a registry-style open string, unlike
    `MissingReasoningCategory`/`ConfidenceSource`. This is a fixed,
    mutually-exclusive observation state machine (three states, never
    expected to grow), the same category of taxonomy as `ReasoningType` and
    Planning's `UnitStatus` — not an evolving vocabulary. See the approved
    RFC's explicit closed-vs-open design rule.
    """

    DEMONSTRATED = "demonstrated"
    SUPERFICIAL = "superficial"
    OMITTED = "omitted"


class ConceptObservation(BaseModel):
    """
    One expected concept's observation status for a single turn (Expected
    Concepts revision, approved). `concept` itself is never predicted or
    invented — it comes from `EvaluationRequest.expected_concepts`, which is
    deterministically derived (expected_concepts_registry.py). Only
    `status`/`evidence`/`confidence` are the evaluator's own judgment.

    Deliberately separate from `MissingReasoningItem` — this describes WHAT
    was or wasn't discussed, not HOW the candidate reasoned.
    """

    model_config = ConfigDict(frozen=True)

    concept: str
    status: ConceptObservationStatus
    evidence: Optional[str] = None
    confidence: float
    confidence_source: str

    @model_validator(mode="after")
    def _validate(self) -> "ConceptObservation":
        _require_non_empty(self.concept, "concept")
        _require_non_empty(self.confidence_source, "confidence_source")
        _require_unit_interval(self.confidence, "confidence")
        if self.status == ConceptObservationStatus.OMITTED:
            if self.evidence is not None:
                raise ValueError(
                    "evidence must be None for an OMITTED concept — there is nothing to cite for "
                    "something that was never mentioned (never invented, RFC's evidence discipline)"
                )
        else:
            if self.evidence is None or not self.evidence.strip():
                raise ValueError(
                    f"evidence is required when status={self.status.value!r} — a claim that a "
                    "concept was demonstrated or superficially mentioned must cite where"
                )
        return self


class EvaluationResult(BaseModel):
    """
    Immutable. THE permanent contract (RFC Section 3). Every field's
    rationale lives in the frozen RFC; this module implements it verbatim.
    """

    model_config = ConfigDict(frozen=True)

    result_id: str
    request_id: str
    schema_version: str = EVALUATION_RESULT_SCHEMA_VERSION
    evaluation_strategy_version: str = EVALUATION_STRATEGY_VERSION
    evaluation_timestamp: str  # ISO8601

    specification_id: str
    source_id: str
    category: str
    project_reference: Optional[str] = None
    reasoning_type: ReasoningType

    evaluator_name: str
    evaluator_version: str
    model_version: tuple[tuple[str, str], ...] = ()
    dataset_version: Optional[str] = None
    training_date: Optional[str] = None

    dimensions: tuple[DimensionScore, ...]

    overall_score: float
    grade: str
    confidence: float
    confidence_source: str
    confidence_rationale: str

    reasoning: str
    strengths: tuple[EvidenceLinkedClaim, ...] = ()
    weaknesses: tuple[EvidenceLinkedClaim, ...] = ()

    missing_reasoning: tuple[MissingReasoningItem, ...] = ()

    # Expected Concepts revision (approved). WHAT was/wasn't discussed,
    # kept structurally separate from missing_reasoning's HOW. Empty when
    # `expected_concepts_registry.py` had no matching entry for this turn's
    # grounding (graceful degradation) — never invented, never an error.
    concept_coverage: tuple[ConceptObservation, ...] = ()

    # Mechanical, gap-derived only — NEVER fluent generation (RFC Section
    # 3: "if producing it requires only picking/templating from already-
    # computed structured facts, it's Evaluation's job; if it requires
    # composing new, fluent, non-templated prose, it belongs to the future
    # ImprovementGenerator"). `model_answer` deliberately does not exist on
    # this object — see that same section for why.
    suggested_improvements: tuple[str, ...] = ()
    recommended_topics: tuple[str, ...] = ()

    contradiction_detected: bool = False
    contradiction_explanation: Optional[str] = None
    resume_grounding_score: float = 0.0

    raw_model_output: tuple[tuple[str, float], ...] = ()
    calibration_version: Optional[str] = None

    recommended_action: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "EvaluationResult":
        if not self.dimensions:
            raise ValueError("EvaluationResult must contain at least one DimensionScore")
        _require_unit_interval(self.overall_score, "overall_score")
        _require_unit_interval(self.confidence, "confidence")
        _require_unit_interval(self.resume_grounding_score, "resume_grounding_score")

        # Goal 4: no opaque scores. Every result must explain itself and
        # its own confidence — enforced here, not left to convention.
        _require_non_empty(self.reasoning, "reasoning")
        _require_non_empty(self.confidence_rationale, "confidence_rationale")
        _require_non_empty(self.confidence_source, "confidence_source")

        for field_name in (
            "result_id", "request_id", "specification_id", "source_id",
            "category", "evaluator_name", "evaluator_version", "grade",
        ):
            _require_non_empty(getattr(self, field_name), field_name)

        if self.recommended_action is not None and self.recommended_action not in _VALID_RECOMMENDED_ACTIONS:
            raise ValueError(
                f"recommended_action must be one of {sorted(_VALID_RECOMMENDED_ACTIONS)}, "
                f"got {self.recommended_action!r}"
            )
        return self

    def dimension(self, name: str) -> Optional[DimensionScore]:
        """Convenience lookup — never a substitute for iterating `dimensions`
        directly when a caller needs all of them."""
        for d in self.dimensions:
            if d.name == name:
                return d
        return None
