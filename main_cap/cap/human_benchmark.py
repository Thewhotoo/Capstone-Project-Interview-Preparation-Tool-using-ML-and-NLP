"""
Human Benchmark Schema — Step 3 infra (schema/interfaces only; no data yet).

Represents ~150-300 REAL candidate answers labeled by humans on the canonical
four dimensions — the authoritative, frozen generalization benchmark. This is
a DISTINCT type from `TrainingExample` on purpose: a human-benchmark item can
never be mistaken for, or fed into, training data.

Isolation guarantees:
  - `HumanBenchmarkItem` is not a `TrainingExample` and shares no base class.
  - Item ids are namespaced with `HUMAN_BENCHMARK_ID_PREFIX` ("hb_").
  - `assert_disjoint_from_training(...)` fails loudly if any benchmark id or
    (question, answer) pair overlaps the training set.

No generation, collection, or labeling happens here — this is the container
those later steps will populate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from evaluation_dimensions import CANONICAL_DIMENSIONS, NUM_TIERS, EvaluationDimension

HUMAN_BENCHMARK_ID_PREFIX = "hb_"
_MAX_TIER = NUM_TIERS - 1


class AdjudicationStatus(str, Enum):
    PENDING = "pending"          # awaiting a second annotator / review
    AGREED = "agreed"            # annotators agreed within tolerance
    ADJUDICATED = "adjudicated"  # a disagreement was resolved by a third party
    DISPUTED = "disputed"        # unresolved disagreement


class HumanDimensionLabel(BaseModel):
    """One annotator's score for one canonical dimension."""

    model_config = ConfigDict(frozen=True)

    dimension: str      # canonical EvaluationDimension key
    score: int          # ordinal 0..4

    @model_validator(mode="after")
    def _validate(self) -> "HumanDimensionLabel":
        if self.dimension not in {d.value for d in EvaluationDimension}:
            raise ValueError(f"unknown dimension key: {self.dimension!r}")
        if not (0 <= self.score <= _MAX_TIER):
            raise ValueError(f"score must be in [0, {_MAX_TIER}], got {self.score}")
        return self


class HumanAnnotation(BaseModel):
    """One annotator's full judgment of an item — all four dimensions scored
    independently, per the Step-1 rubric."""

    model_config = ConfigDict(frozen=True)

    annotator_id: str
    rubric_version: str
    dimension_labels: tuple[HumanDimensionLabel, ...]
    annotated_at: str = ""      # ISO8601
    notes: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "HumanAnnotation":
        if not self.annotator_id.strip():
            raise ValueError("annotator_id must not be empty")
        if not self.rubric_version.strip():
            raise ValueError("rubric_version must not be empty")
        labeled = {d.dimension for d in self.dimension_labels}
        required = {d.value for d in CANONICAL_DIMENSIONS}
        if labeled != required:
            raise ValueError(f"an annotation must score exactly the four canonical dimensions; got {sorted(labeled)}")
        return self


class HumanBenchmarkItem(BaseModel):
    """One real, human-labeled benchmark answer. NEVER a training example."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    question_text: str
    answer_text: str
    grounding_source: str                 # the source_id (project/experience/cert) the answer is about
    category: str = ""                    # QuestionCategory value, for stratified reporting
    reasoning_type: str = ""              # ReasoningType value
    expected_concepts: tuple[str, ...] = ()
    annotations: tuple[HumanAnnotation, ...] = ()
    adjudication_status: AdjudicationStatus = AdjudicationStatus.PENDING
    final_labels: tuple[HumanDimensionLabel, ...] = ()  # resolved consensus, set after adjudication

    @model_validator(mode="after")
    def _validate(self) -> "HumanBenchmarkItem":
        if not self.item_id.startswith(HUMAN_BENCHMARK_ID_PREFIX):
            raise ValueError(f"item_id must start with {HUMAN_BENCHMARK_ID_PREFIX!r} (namespace isolation)")
        if not self.question_text.strip():
            raise ValueError("question_text must not be empty")
        if not self.answer_text.strip():
            raise ValueError("answer_text must not be empty")
        if self.final_labels:
            labeled = {d.dimension for d in self.final_labels}
            required = {d.value for d in CANONICAL_DIMENSIONS}
            if labeled != required:
                raise ValueError("final_labels, when set, must cover exactly the four canonical dimensions")
        return self


def new_item_id(raw_id: str) -> str:
    """Namespaces a raw id into the human-benchmark id space."""
    return raw_id if raw_id.startswith(HUMAN_BENCHMARK_ID_PREFIX) else f"{HUMAN_BENCHMARK_ID_PREFIX}{raw_id}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_disjoint_from_training(items, training_examples) -> None:
    """Hard guard: the human benchmark must never overlap training data.
    Fails if any benchmark id also appears as a training example id, or if any
    (question, answer) pair is shared. Duck-typed on the training side
    (`.metadata.example_id`, `.inputs.question_text`, `.inputs.answer_text`)
    to avoid importing the training schema."""
    bench_ids = {it.item_id for it in items}
    train_ids = {e.metadata.example_id for e in training_examples}
    id_overlap = bench_ids & train_ids
    if id_overlap:
        raise ValueError(f"human-benchmark ids overlap training ids: {sorted(id_overlap)[:5]}")

    def _norm(q: str, a: str) -> tuple[str, str]:
        return (" ".join(q.split()).casefold(), " ".join(a.split()).casefold())

    train_pairs = {_norm(e.inputs.question_text, e.inputs.answer_text) for e in training_examples}
    for it in items:
        if _norm(it.question_text, it.answer_text) in train_pairs:
            raise ValueError(f"human-benchmark item {it.item_id!r} shares a (question, answer) with training data")
