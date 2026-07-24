"""
TrainingExample — Stage A Synthetic Dataset Generation Pipeline (Dataset
Design RFC, Dataset Manifest RFC — both APPROVED AND FROZEN). Implemented
exactly as specified; no architectural deviation.

THE permanent, immutable record every dataset consumer (labeling tooling,
DatasetManifest assembly, the future training pipeline) reads. This module
does not train anything, does not evaluate anything, does not review
anything, and does not assemble a DatasetManifest — it only defines and
validates the record shape those other, still-separate components consume
(RFC's strict separation of responsibilities).

Field groups, exactly as the approved schema requires:
    metadata    — record identity/versioning (never business content)
    provenance  — where this example came from (synthetic vs. real session)
    inputs      — the actual specification/question/answer this example is about
    synthetic   — present only when provenance.source == "synthetic"; the
                  generator versioning/recipe-target fields the Promptbook
                  RFC's generator-versioning discipline (Section 10) requires
    privacy     — PII/consent handling, required even when trivially "no PII"
    labels      — the ground-truth (or human-reviewed) judgment this example
                  trains/evaluates against

Immutability and versioning follow the same discipline already established
for `QuestionSpecification`/`EvaluationResult`: frozen Pydantic models,
tuples (never lists) for nested collections, an explicit schema_version so
an archived example remains interpretable after this schema evolves.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from evaluation_result import ConceptObservationStatus
from question_families import ReasoningType
from question_specification import QuestionSpecification

TRAINING_EXAMPLE_SCHEMA_VERSION = "v1"

_VALID_LABEL_SOURCES = frozenset({"synthetic_ground_truth", "human_reviewed"})


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


def _require_unit_interval(value: float, label: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{label} must be within [0.0, 1.0], got {value}")


# ═════════════════════════════════════════════════════════════════════════════
# Closed taxonomies (fixed, small, not expected to grow — same design rule
# already applied to ConceptObservationStatus/ReasoningType/UnitStatus)
# ═════════════════════════════════════════════════════════════════════════════


class ProvenanceSource(str, Enum):
    """Exactly two ways a TrainingExample can come to exist (Dataset Design
    RFC). Synthetic examples never claim to be real sessions and vice versa —
    enforced structurally by `TrainingExample._synthetic_presence_matches_source`
    below, not left to convention."""

    SYNTHETIC = "synthetic"
    REAL_SESSION = "real_session"


class QualityTier(str, Enum):
    """The 7 generation modes the Promptbook RFC names (Section 3). Also
    doubles as the ground-truth `overall_label.grade` vocabulary for
    synthetic examples — Excellent/Good/Adequate/Weak/Poor are genuine
    quality bands; Off-topic/Contradictory are distinct behavioral failure
    modes, not points on the same quality scale, but are represented here
    too because a generation recipe always targets exactly one of these 7
    modes (Promptbook Section 2's Off-Topic/Contradiction controllers)."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    WEAK = "weak"
    POOR = "poor"
    OFF_TOPIC = "off_topic"
    CONTRADICTORY = "contradictory"


class ContradictionType(str, Enum):
    """The 4 named contradiction types (Promptbook RFC Section 8) — closed,
    exhaustive by design."""

    FACTUAL = "factual"
    TIMELINE = "timeline"
    TECHNOLOGY = "technology"
    OWNERSHIP = "ownership"


# ═════════════════════════════════════════════════════════════════════════════
# metadata
# ═════════════════════════════════════════════════════════════════════════════


class TrainingExampleMetadata(BaseModel):
    """Record identity — never business content (Dataset Design RFC)."""

    model_config = ConfigDict(frozen=True)

    example_id: str
    schema_version: str = TRAINING_EXAMPLE_SCHEMA_VERSION
    # Stamped later, when a DatasetManifest is assembled (Dataset Manifest
    # RFC) — the generator that produces one example never knows which
    # published dataset_version it will end up belonging to (this pipeline
    # explicitly does not assemble DatasetManifests). None here always means
    # "not yet published," never "unknown"/"error".
    dataset_version: Optional[str] = None
    created_at: str  # ISO8601

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExampleMetadata":
        _require_non_empty(self.example_id, "example_id")
        _require_non_empty(self.schema_version, "schema_version")
        _require_non_empty(self.created_at, "created_at")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# provenance
# ═════════════════════════════════════════════════════════════════════════════


class TrainingExampleProvenance(BaseModel):
    """Where this example came from (Dataset Design RFC Section 2)."""

    model_config = ConfigDict(frozen=True)

    source: ProvenanceSource
    collection_batch_id: str
    real_session_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExampleProvenance":
        _require_non_empty(self.collection_batch_id, "collection_batch_id")
        if self.source == ProvenanceSource.REAL_SESSION and not (self.real_session_id or "").strip():
            raise ValueError("real_session_id is required when source=real_session")
        if self.source == ProvenanceSource.SYNTHETIC and self.real_session_id is not None:
            raise ValueError("real_session_id must be None for a synthetic example — never invented")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# inputs
# ═════════════════════════════════════════════════════════════════════════════


class TrainingExampleInputs(BaseModel):
    """The actual specification/question/answer this example trains against
    — structurally the same shape as `EvaluationRequest`'s core fields, so a
    TrainingExample and a live EvaluationRequest are always interpretable
    against the same evaluator (Dataset Design RFC Section 1)."""

    model_config = ConfigDict(frozen=True)

    specification: QuestionSpecification
    question_text: str
    reasoning_type: ReasoningType
    answer_text: str
    expected_concepts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExampleInputs":
        _require_non_empty(self.question_text, "question_text")
        # answer_text MAY be empty for off-topic/poor examples in principle,
        # but this pipeline never produces a genuinely empty synthetic
        # answer — see generation_validation.py's malformed-output check.
        return self


# ═════════════════════════════════════════════════════════════════════════════
# synthetic-only fields
# ═════════════════════════════════════════════════════════════════════════════


class ConceptInclusionTarget(BaseModel):
    """One concept's targeted status for this generated example (Promptbook
    RFC Section 5) — the RECIPE's intent, not an evaluator's observation."""

    model_config = ConfigDict(frozen=True)

    concept: str
    status: ConceptObservationStatus

    @model_validator(mode="after")
    def _validate(self) -> "ConceptInclusionTarget":
        _require_non_empty(self.concept, "concept")
        return self


class ReasoningCategoryTarget(BaseModel):
    """One missing-reasoning category's targeted presence/severity for this
    generated example (Promptbook RFC Section 6). `category` reuses the
    open `MissingReasoningCategory` vocabulary from `evaluation_result.py` —
    never redefined here."""

    model_config = ConfigDict(frozen=True)

    category: str
    present: bool
    severity: float = 0.0

    @model_validator(mode="after")
    def _validate(self) -> "ReasoningCategoryTarget":
        _require_non_empty(self.category, "category")
        _require_unit_interval(self.severity, "severity")
        if not self.present and self.severity != 0.0:
            raise ValueError("severity must be 0.0 when present=False — nothing is missing to grade")
        return self


class TrainingExampleSyntheticMeta(BaseModel):
    """Generator versioning + recipe-target fields (Promptbook RFC Section
    10) — present only when `TrainingExampleProvenance.source ==
    ProvenanceSource.SYNTHETIC`. Every prompt revision produces a NEW
    (generation_prompt_id, prompt_version) pair; examples already generated
    under an older version permanently retain their original tag (Promptbook
    Section 10's append-only discipline) — nothing here is ever rewritten
    in place by a later prompt revision."""

    model_config = ConfigDict(frozen=True)

    generation_prompt_id: str
    prompt_version: str
    generator_model: str
    generation_batch_id: str

    intended_quality_tier: QualityTier
    intended_concept_inclusion: tuple[ConceptInclusionTarget, ...] = ()
    intended_reasoning_category_targets: tuple[ReasoningCategoryTarget, ...] = ()

    is_off_topic: bool = False
    is_contradictory: bool = False
    contradiction_type: Optional[ContradictionType] = None

    diversity_seed: str
    style_seed: str

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExampleSyntheticMeta":
        for field_name in (
            "generation_prompt_id", "prompt_version", "generator_model",
            "generation_batch_id", "diversity_seed", "style_seed",
        ):
            _require_non_empty(getattr(self, field_name), field_name)

        # Off-topic controller override (Promptbook Section 2): an off-topic
        # example carries no concept/reasoning targets — they were
        # deliberately suppressed, never merely "empty by coincidence".
        if self.is_off_topic and (self.intended_concept_inclusion or self.intended_reasoning_category_targets):
            raise ValueError(
                "an off-topic example must not carry concept/reasoning targets — "
                "the Off-Topic Controller overrides and suppresses them (Promptbook Section 2)"
            )
        if self.is_off_topic != (self.intended_quality_tier == QualityTier.OFF_TOPIC):
            raise ValueError("is_off_topic must be consistent with intended_quality_tier == OFF_TOPIC")
        if self.is_contradictory != (self.intended_quality_tier == QualityTier.CONTRADICTORY):
            raise ValueError("is_contradictory must be consistent with intended_quality_tier == CONTRADICTORY")

        # Exactly one contradiction type when contradictory, none otherwise
        # (Promptbook Section 8: one contradiction, one type, never zero,
        # never compounding).
        if self.is_contradictory and self.contradiction_type is None:
            raise ValueError("contradiction_type is required when is_contradictory=True")
        if not self.is_contradictory and self.contradiction_type is not None:
            raise ValueError("contradiction_type must be None when is_contradictory=False")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# privacy fields
# ═════════════════════════════════════════════════════════════════════════════


class TrainingExamplePrivacy(BaseModel):
    """Required on every example regardless of provenance — even a
    synthetic example, which trivially never contained real PII, states that
    explicitly rather than leaving the question unanswered (Dataset Design
    RFC's privacy section)."""

    model_config = ConfigDict(frozen=True)

    contains_pii: bool = False
    anonymized: bool = True
    anonymization_method: Optional[str] = None
    consent_basis: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExamplePrivacy":
        if self.contains_pii and not self.anonymized:
            raise ValueError("an example containing PII must be anonymized before it can be a TrainingExample")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# labels
# ═════════════════════════════════════════════════════════════════════════════


class DimensionLabel(BaseModel):
    """One evaluation dimension's ground-truth target score (Dataset Design
    RFC Section 4's rubric, applied as a label rather than a live judgment)."""

    model_config = ConfigDict(frozen=True)

    name: str
    score: float

    @model_validator(mode="after")
    def _validate(self) -> "DimensionLabel":
        _require_non_empty(self.name, "name")
        _require_unit_interval(self.score, "score")
        return self


class ConceptLabel(BaseModel):
    """Ground-truth concept observation — same 3-state shape as
    `ConceptObservation` (evaluation_result.py), reused rather than
    redefined, but this is the LABEL an evaluator is trained against, not an
    evaluator's own output."""

    model_config = ConfigDict(frozen=True)

    concept: str
    status: ConceptObservationStatus
    evidence: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "ConceptLabel":
        _require_non_empty(self.concept, "concept")
        if self.status == ConceptObservationStatus.OMITTED and self.evidence is not None:
            raise ValueError("evidence must be None for an OMITTED concept label — never invented")
        if self.status != ConceptObservationStatus.OMITTED and not (self.evidence or "").strip():
            raise ValueError(f"evidence is required when status={self.status.value!r}")
        return self


class MissingReasoningLabel(BaseModel):
    """Ground-truth missing-reasoning target — mirrors `MissingReasoningItem`
    (evaluation_result.py)'s shape as a label rather than a live judgment."""

    model_config = ConfigDict(frozen=True)

    category: str
    present: bool
    severity: float
    explanation: str

    @model_validator(mode="after")
    def _validate(self) -> "MissingReasoningLabel":
        _require_non_empty(self.category, "category")
        _require_non_empty(self.explanation, "explanation")
        _require_unit_interval(self.severity, "severity")
        return self


class ContradictionLabel(BaseModel):
    """Ground-truth contradiction judgment (Promptbook RFC Section 8)."""

    model_config = ConfigDict(frozen=True)

    contradiction_present: bool
    contradiction_type: Optional[ContradictionType] = None
    explanation: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "ContradictionLabel":
        if self.contradiction_present:
            if self.contradiction_type is None:
                raise ValueError("contradiction_type is required when contradiction_present=True")
            if not (self.explanation or "").strip():
                raise ValueError("explanation is required when contradiction_present=True")
        else:
            if self.contradiction_type is not None:
                raise ValueError("contradiction_type must be None when contradiction_present=False")
        return self


class OverallLabel(BaseModel):
    """The holistic ground-truth judgment (Dataset Design RFC Section 4)."""

    model_config = ConfigDict(frozen=True)

    score: float
    grade: str
    rationale: str

    @model_validator(mode="after")
    def _validate(self) -> "OverallLabel":
        _require_unit_interval(self.score, "score")
        _require_non_empty(self.grade, "grade")
        _require_non_empty(self.rationale, "rationale")
        return self


class TrainingExampleLabels(BaseModel):
    """The full label set (Dataset Design RFC Section 4/7). `label_source`
    distinguishes recipe-derived synthetic ground truth from a human
    reviewer's judgment — the two are never treated as equal-confidence
    (Dataset Design RFC Section 7)."""

    model_config = ConfigDict(frozen=True)

    label_source: str
    labeling_guideline_version: Optional[str] = None

    dimension_labels: tuple[DimensionLabel, ...]
    missing_reasoning_labels: tuple[MissingReasoningLabel, ...] = ()
    concept_labels: tuple[ConceptLabel, ...] = ()
    contradiction_label: ContradictionLabel
    overall_label: OverallLabel

    @model_validator(mode="after")
    def _validate(self) -> "TrainingExampleLabels":
        if self.label_source not in _VALID_LABEL_SOURCES:
            raise ValueError(f"label_source must be one of {sorted(_VALID_LABEL_SOURCES)}, got {self.label_source!r}")
        if not self.dimension_labels:
            raise ValueError("dimension_labels must contain at least one entry")
        if self.label_source == "human_reviewed" and not (self.labeling_guideline_version or "").strip():
            raise ValueError("labeling_guideline_version is required when label_source=human_reviewed")
        if self.label_source == "synthetic_ground_truth" and self.labeling_guideline_version is not None:
            raise ValueError("labeling_guideline_version must be None for synthetic_ground_truth — no human rubric was applied")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# TrainingExample — the permanent record
# ═════════════════════════════════════════════════════════════════════════════


class TrainingExample(BaseModel):
    """The permanent, immutable dataset record (Dataset Design RFC). Every
    field group's rationale lives in the frozen RFC; this module implements
    it verbatim."""

    model_config = ConfigDict(frozen=True)

    metadata: TrainingExampleMetadata
    provenance: TrainingExampleProvenance
    inputs: TrainingExampleInputs
    privacy: TrainingExamplePrivacy
    synthetic: Optional[TrainingExampleSyntheticMeta] = None
    labels: TrainingExampleLabels

    @model_validator(mode="after")
    def _synthetic_presence_matches_source(self) -> "TrainingExample":
        if self.provenance.source == ProvenanceSource.SYNTHETIC:
            if self.synthetic is None:
                raise ValueError("synthetic metadata is required when provenance.source=synthetic")
            if self.labels.label_source != "synthetic_ground_truth":
                raise ValueError("a synthetic example's labels must have label_source=synthetic_ground_truth")
        else:
            if self.synthetic is not None:
                raise ValueError("synthetic metadata must be None for a real_session example")
        return self
