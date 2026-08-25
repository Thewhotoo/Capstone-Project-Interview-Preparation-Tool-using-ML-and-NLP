"""
Training & Experimentation — infrastructure layer (Training & Experimentation
RFC — no RFC text was recoverable from prior chat history; this design was
proposed fresh this session from the existing codebase and established
principles, reviewed, and approved with explicit scope refinements before any
code was written).

SCOPE, AS APPROVED: this module is INFRASTRUCTURE ONLY. It owns experiment
metadata, deterministic dataset splitting, checkpoint metadata + lineage,
QWK-based benchmarking, and promotion POLICY DECISIONS. It does NOT own model
training or inference, and deliberately introduces no `ModelTrainer`,
`InferenceClient`, or `CheckpointEvaluator` — those belong to a future,
separately-scoped model-implementation layer once an actual training backend
(PyTorch/HuggingFace/DeBERTa) exists. This module stays ML-framework
agnostic: `Checkpoint.artifact_uri` is an opaque, caller-supplied pointer to
wherever trained weights actually live; this module never serializes,
loads, or runs a model.

Consequently, "promotion" here means exactly one thing: a POLICY DECISION
(`decide_promotion`) comparing a candidate's benchmark QWK against a
baseline's, per a configurable `PromotionPolicy`. It does NOT wrap a
`Checkpoint` into an `Evaluator` and does NOT call
`evaluator_registry.register_evaluator` — there is no `Evaluator`
implementation to register yet. That registration step is the future
model-implementation layer's job, gated on this function's decision.

IMPORT BOUNDARY (deliberately narrower than originally proposed, once
`ModelTrainer`/`InferenceClient`/`CheckpointEvaluator` were dropped): this
module needs only `training_example.py` (for `TrainingExample`, to build a
benchmark request) and `evaluator.py`/`evaluation_request.py` (the
`Evaluator` protocol and `EvaluationRequest`, to run a benchmark against
whatever `Evaluator`-conformant objects the caller supplies). It does NOT
import `evaluator_registry.py` (no registration happens here),
`heuristic_evaluator.py` (the caller supplies whichever baseline `Evaluator`
it wants — this module doesn't hard-code one), or `dataset_manifest.py`
(`dataset_version` stays a plain opaque string, same convention as
`generation_batch_id` elsewhere — no forced cross-import for a string). See
`test_training_experimentation.py`'s import-graph AST assertion (the same
pattern `test_dataset_manifest.py`/`test_labeling_operations.py` already
established) for the test enforcing all of this structurally.

REPRODUCIBILITY: every part of this pipeline that isn't the (out-of-scope)
neural-net training loop itself is fully `zlib.crc32`-deterministic —
`split_dataset` and `compute_qwk` never use Python's `random` module. This
guarantees an experiment is fully described and REPLAYABLE IN PRINCIPLE
(same `ExperimentConfig`, same `dataset_version`, same seed -> same split);
it does not and cannot claim bit-for-bit reproducibility of an actual
training run, which is inherently hardware/library-dependent.
"""

from __future__ import annotations

import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluator import Evaluator
from training_example import TrainingExample

TRAINING_EXPERIMENTATION_SCHEMA_VERSION = "v1"


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


def _stable_key(*parts: str) -> int:
    return zlib.crc32("::".join(parts).encode("utf-8"))


# ═════════════════════════════════════════════════════════════════════════════
# ModelFormulation — open, registry-style (see module docstring)
# ═════════════════════════════════════════════════════════════════════════════


class ModelFormulation:
    """Open, registry-style values (same discipline as
    `evaluation_result.ConfidenceSource`/`MissingReasoningCategory`) — the ML
    Architecture RFC's current frozen recommendation is ordinal regression,
    but a future RFC revision could approve another formulation as an
    additive value here, never a schema change."""

    ORDINAL_REGRESSION = "ordinal_regression"


# ═════════════════════════════════════════════════════════════════════════════
# ExperimentConfig
# ═════════════════════════════════════════════════════════════════════════════


class ExperimentConfig(BaseModel):
    """
    Every fact needed to describe one experiment, frozen and self-contained
    — embedded permanently into whatever `Checkpoint` it produces (design
    decision: "captured per result, not just per config", the same
    precedent `DimensionScore.weight_used` already established).

    `parameters` is a plain, flexible key/value bag (approved refinement,
    replacing an earlier tuple-of-string-pairs proposal) so future
    experiment parameters (learning rate, epochs, batch size, ...) can be
    added without designing a rigid schema — or a trainer API — prematurely.
    NOTE: unlike every other frozen model in this codebase, this dict is not
    deep-frozen (Pydantic's `frozen=True` blocks reassigning the `parameters`
    attribute itself, not mutating its contents) — an explicit, acknowledged
    trade-off for simplicity per this session's approved refinement, not an
    oversight.
    """

    model_config = ConfigDict(frozen=True)

    backbone_name: str
    formulation: str = ModelFormulation.ORDINAL_REGRESSION
    parameters: dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)
    random_seed: int
    dataset_version: str
    split_ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
    schema_version: str = TRAINING_EXPERIMENTATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def _validate(self) -> "ExperimentConfig":
        _require_non_empty(self.backbone_name, "backbone_name")
        _require_non_empty(self.formulation, "formulation")
        _require_non_empty(self.dataset_version, "dataset_version")
        if any(r < 0.0 for r in self.split_ratios):
            raise ValueError("split_ratios entries must be >= 0.0")
        if abs(sum(self.split_ratios) - 1.0) > 1e-9:
            raise ValueError(f"split_ratios must sum to 1.0, got {sum(self.split_ratios)}")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# Deterministic dataset splitting
# ═════════════════════════════════════════════════════════════════════════════


class DatasetSplit(BaseModel):
    """A deterministic partition of a dataset's `TrainingExample.metadata.example_id`
    values into train/val/test — references only, mirrors
    `DatasetManifest.example_ids`'s "membership by reference, never
    ownership" philosophy."""

    model_config = ConfigDict(frozen=True)

    train_ids: tuple[str, ...] = ()
    val_ids: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "DatasetSplit":
        all_ids = self.train_ids + self.val_ids + self.test_ids
        if not all_ids:
            raise ValueError("DatasetSplit must contain at least one example id")
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("train_ids/val_ids/test_ids must not overlap or contain duplicates")
        return self


def split_dataset(
    example_ids: tuple[str, ...],
    split_ratios: tuple[float, float, float],
    seed: str,
) -> DatasetSplit:
    """
    Deterministically partition `example_ids` into train/val/test, using the
    same `zlib.crc32`-keyed stable-sort shuffle idiom `coverage_strategy.py`
    already established (reimplemented locally here rather than importing
    that module's private helper — the same "deliberate independence between
    subsystems" reasoning already documented elsewhere in this codebase, e.g.
    `heuristic_evaluator.py`'s duplicated marker lists). Given identical
    inputs, always produces an identical split.
    """
    if not example_ids:
        raise ValueError("example_ids must not be empty")
    if len(set(example_ids)) != len(example_ids):
        raise ValueError("example_ids must not contain duplicates")
    if len(split_ratios) != 3:
        raise ValueError("split_ratios must have exactly 3 entries (train, val, test)")
    if any(r < 0.0 for r in split_ratios):
        raise ValueError("split_ratios entries must be >= 0.0")
    if abs(sum(split_ratios) - 1.0) > 1e-9:
        raise ValueError(f"split_ratios must sum to 1.0, got {sum(split_ratios)}")

    order = sorted(range(len(example_ids)), key=lambda i: _stable_key(seed, "split_shuffle", str(i)))
    shuffled = tuple(example_ids[i] for i in order)

    n = len(shuffled)
    train_count = int(n * split_ratios[0])
    val_count = int(n * split_ratios[1])
    train_ids = shuffled[:train_count]
    val_ids = shuffled[train_count:train_count + val_count]
    test_ids = shuffled[train_count + val_count:]

    return DatasetSplit(train_ids=train_ids, val_ids=val_ids, test_ids=test_ids)


def split_dataset_by_group(
    example_ids: tuple[str, ...],
    group_of: dict[str, str],
    split_ratios: tuple[float, float, float],
    seed: str,
) -> DatasetSplit:
    """
    Like `split_dataset`, but partitions at the GROUP level (e.g. every
    example derived from the same `QuestionSpecification`) rather than per
    example — every `example_id` sharing a `group_of[example_id]` key ends
    up entirely within ONE of train/val/test, never split across them.

    This is the fix for topical leakage: an example-level split can put two
    examples generated from the SAME underlying question/grounding (just
    different quality tiers) into both train and test, letting a model
    "succeed" by recognizing the topic rather than generalizing to unseen
    content — session 7's experiment demonstrated exactly this failure mode.

    Same determinism discipline as `split_dataset` (`_stable_key`-shuffled,
    no `random` module) — applied to the GROUP keys, not individual ids, so
    the same `(example_ids, group_of, split_ratios, seed)` always produces
    an identical split. Ratios are approximate at the group level: since
    groups can vary in size, the resulting example-count ratios may deviate
    somewhat from `split_ratios` — inspect the returned split's actual
    sizes, same discipline `split_dataset`'s callers already follow.
    """
    if not example_ids:
        raise ValueError("example_ids must not be empty")
    if len(set(example_ids)) != len(example_ids):
        raise ValueError("example_ids must not contain duplicates")
    missing = [i for i in example_ids if i not in group_of]
    if missing:
        raise ValueError(f"{len(missing)} example_id(s) have no entry in group_of: {missing[:5]}")
    if len(split_ratios) != 3:
        raise ValueError("split_ratios must have exactly 3 entries (train, val, test)")
    if any(r < 0.0 for r in split_ratios):
        raise ValueError("split_ratios entries must be >= 0.0")
    if abs(sum(split_ratios) - 1.0) > 1e-9:
        raise ValueError(f"split_ratios must sum to 1.0, got {sum(split_ratios)}")

    groups: dict[str, list[str]] = {}
    for example_id in example_ids:
        groups.setdefault(group_of[example_id], []).append(example_id)
    group_keys = tuple(groups.keys())  # first-seen order, stable given example_ids' order

    order = sorted(range(len(group_keys)), key=lambda i: _stable_key(seed, "group_split_shuffle", str(i)))
    shuffled_group_keys = tuple(group_keys[i] for i in order)

    n = len(example_ids)
    train_target = int(n * split_ratios[0])
    val_target = int(n * split_ratios[1])

    train_ids: list[str] = []
    val_ids: list[str] = []
    test_ids: list[str] = []
    for key in shuffled_group_keys:
        members = groups[key]
        if len(train_ids) < train_target:
            train_ids.extend(members)
        elif len(val_ids) < val_target:
            val_ids.extend(members)
        else:
            test_ids.extend(members)

    return DatasetSplit(train_ids=tuple(train_ids), val_ids=tuple(val_ids), test_ids=tuple(test_ids))


# ═════════════════════════════════════════════════════════════════════════════
# Checkpoint + lineage
# ═════════════════════════════════════════════════════════════════════════════


class Checkpoint(BaseModel):
    """
    Pure metadata describing one training run's result — never the weights
    themselves. `artifact_uri` is an opaque, caller-supplied pointer to
    wherever the actual trained model lives (produced by a future,
    not-yet-built training backend); this subsystem never inspects or
    serializes it. Lineage fields (`parent_model_version`/`superseded_by`)
    mirror `DatasetManifest`'s exact pattern — reused, not reinvented.
    """

    model_config = ConfigDict(frozen=True)

    model_version: str
    schema_version: str = TRAINING_EXPERIMENTATION_SCHEMA_VERSION
    created_at: str  # ISO8601
    dataset_version: str
    experiment_config: ExperimentConfig
    artifact_uri: str
    parent_model_version: Optional[str] = None
    superseded_by: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "Checkpoint":
        _require_non_empty(self.model_version, "model_version")
        _require_non_empty(self.created_at, "created_at")
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.artifact_uri, "artifact_uri")
        if self.dataset_version != self.experiment_config.dataset_version:
            raise ValueError("dataset_version must match experiment_config.dataset_version")
        if self.parent_model_version == self.model_version:
            raise ValueError("parent_model_version must not equal model_version")
        if self.superseded_by == self.model_version:
            raise ValueError("superseded_by must not equal model_version — a checkpoint cannot supersede itself")
        return self


def assemble_checkpoint(
    model_version: str,
    experiment_config: ExperimentConfig,
    artifact_uri: str,
    parent_model_version: Optional[str] = None,
) -> Checkpoint:
    """
    Pure metadata assembly — no training happens here (see module
    docstring). `artifact_uri` is supplied by the caller; this function only
    records what experiment produced it and where it lives.
    """
    _require_non_empty(model_version, "model_version")
    _require_non_empty(artifact_uri, "artifact_uri")
    return Checkpoint(
        model_version=model_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=experiment_config.dataset_version,
        experiment_config=experiment_config,
        artifact_uri=artifact_uri,
        parent_model_version=parent_model_version,
    )


def supersede_checkpoint(checkpoint: Checkpoint, new_model_version: str) -> Checkpoint:
    """Return a NEW `Checkpoint` (via `model_copy`, never in-place mutation)
    with `superseded_by` set — mirrors `dataset_manifest.supersede` exactly:
    refuses to re-supersede an already-superseded checkpoint and refuses
    self-supersession."""
    _require_non_empty(new_model_version, "new_model_version")
    if checkpoint.superseded_by is not None:
        raise ValueError(
            f"checkpoint {checkpoint.model_version!r} is already superseded by "
            f"{checkpoint.superseded_by!r} — cannot supersede it again"
        )
    if new_model_version == checkpoint.model_version:
        raise ValueError("a checkpoint cannot supersede itself")
    return checkpoint.model_copy(update={"superseded_by": new_model_version})


# ═════════════════════════════════════════════════════════════════════════════
# Ordinal grade mapping + QWK
# ═════════════════════════════════════════════════════════════════════════════

# The five core quality grades (the same vocabulary
# `training_example_assembler._TIER_OVERALL_GRADE` already produces),
# ordered poor -> excellent. "off_topic"/"contradictory" are deliberately
# excluded — distinct behavioral failure modes, not points on this ordinal
# quality scale (Promptbook RFC's own framing, reused here).
_ORDINAL_GRADES: tuple[str, ...] = ("poor", "weak", "adequate", "good", "excellent")


def grade_to_ordinal(grade: str) -> int:
    """
    Maps a core quality grade to its ordinal position, 0 (poor) .. 4
    (excellent). Raises `ValueError` for "off_topic"/"contradictory" or any
    unrecognized grade — a caller benchmarking ordinal regression must
    explicitly exclude those first rather than have them silently coerced
    into an arbitrary ordinal position (this codebase's "never invented"
    discipline, applied to metric computation).
    """
    try:
        return _ORDINAL_GRADES.index(grade)
    except ValueError:
        raise ValueError(
            f"grade {grade!r} is not an ordinal quality grade — expected one of "
            f"{_ORDINAL_GRADES!r} (off_topic/contradictory are excluded by design)"
        ) from None


def compute_qwk(y_true: tuple[int, ...], y_pred: tuple[int, ...], num_classes: int) -> float:
    """
    Quadratic Weighted Kappa — the ML Architecture RFC's named primary
    benchmark metric. A pure, dependency-free implementation of the
    standard formula: an observed confusion matrix vs. an
    expected-by-chance matrix, both weighted quadratically by ordinal
    distance between true and predicted class.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if not y_true:
        raise ValueError("y_true/y_pred must not be empty")
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2")
    for label in (*y_true, *y_pred):
        if not (0 <= label < num_classes):
            raise ValueError(f"label {label} is out of range for num_classes={num_classes}")

    n = len(y_true)
    observed = [[0] * num_classes for _ in range(num_classes)]
    true_hist = [0] * num_classes
    pred_hist = [0] * num_classes
    for t, p in zip(y_true, y_pred):
        observed[t][p] += 1
        true_hist[t] += 1
        pred_hist[p] += 1

    weights = [
        [((i - j) ** 2) / ((num_classes - 1) ** 2) for j in range(num_classes)]
        for i in range(num_classes)
    ]
    expected = [
        [true_hist[i] * pred_hist[j] / n for j in range(num_classes)]
        for i in range(num_classes)
    ]

    numerator = sum(weights[i][j] * observed[i][j] for i in range(num_classes) for j in range(num_classes))
    denominator = sum(weights[i][j] * expected[i][j] for i in range(num_classes) for j in range(num_classes))

    if denominator == 0:
        # No disagreement is even possible to weight (e.g. every true AND
        # predicted label is the same single class) -- perfect agreement by
        # definition in that degenerate case.
        return 1.0
    return 1.0 - (numerator / denominator)


# ═════════════════════════════════════════════════════════════════════════════
# Benchmarking
# ═════════════════════════════════════════════════════════════════════════════


class BenchmarkResult(BaseModel):
    """A frozen record of one benchmark run comparing a candidate `Evaluator`
    against a baseline `Evaluator` over the same examples."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    schema_version: str = TRAINING_EXPERIMENTATION_SCHEMA_VERSION
    created_at: str  # ISO8601
    dataset_version: str
    example_count: int
    candidate_evaluator_name: str
    candidate_evaluator_version: str
    baseline_evaluator_name: str
    baseline_evaluator_version: str
    candidate_qwk: float
    baseline_qwk: float

    @model_validator(mode="after")
    def _validate(self) -> "BenchmarkResult":
        for field_name in (
            "benchmark_id", "created_at", "dataset_version",
            "candidate_evaluator_name", "candidate_evaluator_version",
            "baseline_evaluator_name", "baseline_evaluator_version",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.example_count < 1:
            raise ValueError("example_count must be >= 1")
        for label, value in (("candidate_qwk", self.candidate_qwk), ("baseline_qwk", self.baseline_qwk)):
            if not (-1.0 <= value <= 1.0):
                raise ValueError(f"{label} must be within [-1.0, 1.0], got {value}")
        return self


def _build_evaluation_request(example: TrainingExample) -> EvaluationRequest:
    inputs = example.inputs
    return EvaluationRequest(
        request_id=f"benchmark_{example.metadata.example_id}",
        requested_at=datetime.now(timezone.utc).isoformat(),
        specification=inputs.specification,
        question_text=inputs.question_text,
        reasoning_type=inputs.reasoning_type,
        answer_text=inputs.answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=inputs.expected_concepts,
    )


def run_benchmark(
    candidate: Evaluator,
    baseline: Evaluator,
    examples: tuple[TrainingExample, ...],
    dataset_version: str,
) -> BenchmarkResult:
    """
    Runs `candidate` and `baseline` over the same `examples` (each turned
    into an `EvaluationRequest` via `TrainingExampleInputs`'s already-
    established structural compatibility with `EvaluationRequest`), scoring
    each evaluator's predicted grade against every example's own
    ground-truth `labels.overall_label.grade` via `compute_qwk`.

    `examples` must already be restricted to the 5 core ordinal quality
    grades — `grade_to_ordinal` raises for off_topic/contradictory examples,
    so filter those out before calling this.
    """
    if not examples:
        raise ValueError("examples must not be empty")

    y_true = tuple(grade_to_ordinal(e.labels.overall_label.grade) for e in examples)

    candidate_preds = []
    baseline_preds = []
    for example in examples:
        request = _build_evaluation_request(example)
        candidate_preds.append(grade_to_ordinal(candidate.evaluate(request).grade))
        baseline_preds.append(grade_to_ordinal(baseline.evaluate(request).grade))

    num_classes = len(_ORDINAL_GRADES)
    candidate_qwk = compute_qwk(y_true, tuple(candidate_preds), num_classes)
    baseline_qwk = compute_qwk(y_true, tuple(baseline_preds), num_classes)

    return BenchmarkResult(
        benchmark_id=f"benchmark_{uuid.uuid4().hex[:16]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=dataset_version,
        example_count=len(examples),
        candidate_evaluator_name=candidate.name,
        candidate_evaluator_version=candidate.version,
        baseline_evaluator_name=baseline.name,
        baseline_evaluator_version=baseline.version,
        candidate_qwk=candidate_qwk,
        baseline_qwk=baseline_qwk,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Promotion policy + decision (no registration — see module docstring)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PromotionPolicy:
    """Tunable promotion threshold. Defaults to requiring the candidate to
    merely match-or-beat the baseline QWK (no specific margin was ever
    specified anywhere available to this session)."""

    minimum_qwk_improvement: float = 0.0

    def __post_init__(self) -> None:
        if not (-2.0 <= self.minimum_qwk_improvement <= 2.0):
            raise ValueError("minimum_qwk_improvement must be within [-2.0, 2.0] (QWK values are within [-1.0, 1.0])")


class PromotionDecision(BaseModel):
    """The outcome of applying a `PromotionPolicy` to a `BenchmarkResult` —
    `approved=False` is a normal, expected outcome (a candidate that doesn't
    clear the bar), not an error condition."""

    model_config = ConfigDict(frozen=True)

    approved: bool
    rationale: str
    checkpoint_model_version: str
    benchmark_id: str

    @model_validator(mode="after")
    def _validate(self) -> "PromotionDecision":
        _require_non_empty(self.rationale, "rationale")
        _require_non_empty(self.checkpoint_model_version, "checkpoint_model_version")
        _require_non_empty(self.benchmark_id, "benchmark_id")
        return self


def decide_promotion(
    checkpoint: Checkpoint,
    benchmark: BenchmarkResult,
    policy: PromotionPolicy = PromotionPolicy(),
) -> PromotionDecision:
    """
    Pure policy decision — does NOT register anything anywhere. There is no
    `Evaluator`-wrapping mechanism in this milestone (see module docstring);
    once a future model-implementation layer exists to wrap a `Checkpoint`
    as a real `Evaluator`, THAT layer is responsible for calling
    `evaluator_registry.register_evaluator`, gated on this function's
    `approved` result.
    """
    if checkpoint.dataset_version != benchmark.dataset_version:
        raise ValueError(
            f"checkpoint.dataset_version ({checkpoint.dataset_version!r}) does not match "
            f"benchmark.dataset_version ({benchmark.dataset_version!r}) — refusing to decide "
            "promotion from a mismatched checkpoint/benchmark pairing"
        )

    required = benchmark.baseline_qwk + policy.minimum_qwk_improvement
    approved = benchmark.candidate_qwk >= required
    rationale = (
        f"candidate QWK {benchmark.candidate_qwk:.4f} "
        f"{'meets' if approved else 'does not meet'} the required threshold of {required:.4f} "
        f"(baseline {benchmark.baseline_qwk:.4f} + minimum_qwk_improvement {policy.minimum_qwk_improvement:.4f})"
    )
    return PromotionDecision(
        approved=approved, rationale=rationale,
        checkpoint_model_version=checkpoint.model_version, benchmark_id=benchmark.benchmark_id,
    )
