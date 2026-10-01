"""
Dataset Manifest + Review Event — Stage A Synthetic Dataset Generation
Pipeline (Dataset Manifest RFC — APPROVED AND FROZEN, restated and confirmed
by the user this session since it exists only in prior chat history).
Implementation only; no architectural deviation.

ONE COHESIVE SUBSYSTEM, as approved: `DatasetManifest` derives its
`review_summary` directly from a `ReviewEventLog`, so the two are built and
tested together rather than as independent pieces.

STRICT INDEPENDENCE (approved requirement): this module imports nothing but
`training_example.py` (plus stdlib). It has zero dependency on
`synthetic_generation_pipeline.py`, `coverage_strategy.py`,
`generation_client.py`/`generation_recipe.py`/`generation_validation.py`/
`prompt_assembler.py`/`prompt_controllers.py`, or any Evaluation/Conversation/
Planning module. A `DatasetManifest` describes a dataset of `TrainingExample`s
— it must not care whether they came from Stage A synthetic generation, a
future real-session collector, or anywhere else. See
`test_dataset_manifest.py`'s import-graph AST assertion (the same pattern
`test_synthetic_generation_pipeline.py` already established) for the test
that enforces this structurally.

DESIGN DECISIONS (approved this session):

1. **`DatasetManifest` never owns or duplicates `TrainingExample` objects.**
   It references membership only, via `example_ids: tuple[str, ...]`, plus
   aggregate metadata/statistics computed once at assembly time. The actual
   stamped `TrainingExample` copies are `assemble_manifest`'s SECOND return
   value — the caller decides what to do with them (this pipeline still has
   no persistence layer, per the standing open item).

2. **Stamping is `model_copy`-based, never in-place mutation.** A frozen
   `TrainingExample`'s `metadata.dataset_version` is filled in by
   constructing a NEW object (`example.model_copy(update=...)`, with a
   nested `metadata.model_copy(update=...)` since `metadata` is itself a
   frozen sub-model) — the original, unstamped object is untouched and
   still valid. This is exactly what `training_example.py`'s own docstring
   promised: "dataset_version... gets stamped later, when a DatasetManifest
   is assembled."

3. **Whether an already-versioned example may be re-stamped into a new
   dataset lineage is a POLICY, owned by `assemble_manifest` (the assembly
   layer), not an assumption baked into `DatasetManifest`/`TrainingExample`
   themselves.** `allow_reversioning: bool = False` defaults to rejecting
   already-versioned input (fail fast, since silently re-stamping could
   silently orphan an example from its original dataset_version's meaning)
   but the model layer makes no promise that an example can never appear in
   a later lineage — that door stays open for whatever DatasetManifest
   evolution/lineage policy comes next.

4. **`dataset_version` is an opaque, caller-supplied string** — the same
   pattern already established for `generation_batch_id`/`recipe_id`
   elsewhere in this pipeline. No format/scheme is invented or enforced
   here.

5. **`ReviewEvent.event_type` is an open, registry-style string, not a
   closed `Enum`.** The Labeling Operations RFC (still design-only, no code)
   owns the actual reviewer-workflow vocabulary; freezing a closed taxonomy
   here ahead of that RFC would risk being wrong and forcing a schema
   change later. This mirrors the exact closed-vs-open reasoning already
   applied to `MissingReasoningCategory`/`ConfidenceSource` in
   `evaluation_result.py`. A few well-known seed values are provided as
   `ReviewEventType` constants — informative, not exhaustive.

6. **`ReviewEventLog` is the controlled-mutation wrapper, exactly the
   `UnitLifecycleState`/`CoverageTracker` precedent**: the log has a
   `record(...)` method and read-only accessors, and NO method anywhere
   removes or edits an existing entry — append-only is structural, not
   conventional.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from training_example import TrainingExample

DATASET_MANIFEST_SCHEMA_VERSION = "v1"


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


# ═════════════════════════════════════════════════════════════════════════════
# ReviewEventType — open, registry-style vocabulary (see design decision 5)
# ═════════════════════════════════════════════════════════════════════════════


class ReviewEventType:
    """Well-known seed values — NOT a closed enum. New review actions are
    added as new string values once the Labeling Operations RFC actually
    specifies them; this is informative precedent, never an exhaustive
    list (same discipline as `MissingReasoningCategory`/`ConfidenceSource`
    in `evaluation_result.py`)."""

    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    RELABELED = "relabeled"


# ═════════════════════════════════════════════════════════════════════════════
# ReviewEvent — one immutable audit-trail entry
# ═════════════════════════════════════════════════════════════════════════════


class ReviewEvent(BaseModel):
    """One immutable review action against one `TrainingExample`, identified
    by `example_id` (never by `dataset_version` — the same example can be
    reviewed once and that review remains meaningful even if the example
    later appears in a different manifest's lineage). Every event must
    explain itself (`rationale` is mandatory, non-empty) — the same "no
    opaque judgment" discipline already enforced on `EvaluationResult`."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    example_id: str
    event_type: str
    reviewer_id: str
    created_at: str  # ISO8601
    rationale: str
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "ReviewEvent":
        for field_name in ("event_id", "example_id", "event_type", "reviewer_id", "created_at", "rationale"):
            _require_non_empty(getattr(self, field_name), field_name)
        return self


class ReviewEventLog:
    """Append-only wrapper around a `ReviewEvent` sequence — the same
    controlled-mutation-class precedent as `UnitLifecycleState`/
    `CoverageTracker`. There is no method here that removes or edits an
    existing entry; the only way to change this object's observable state
    is `record`, which only ever appends."""

    def __init__(self) -> None:
        self._events: list[ReviewEvent] = []

    def record(self, event: ReviewEvent) -> None:
        self._events.append(event)

    def events_for(self, example_id: str) -> tuple[ReviewEvent, ...]:
        return tuple(e for e in self._events if e.example_id == example_id)

    def all_events(self) -> tuple[ReviewEvent, ...]:
        return tuple(self._events)


# ═════════════════════════════════════════════════════════════════════════════
# ReviewSummary — statistics DatasetManifest derives from a ReviewEventLog
# ═════════════════════════════════════════════════════════════════════════════


class ReviewSummary(BaseModel):
    """A frozen snapshot of review coverage for exactly the `example_ids` a
    `DatasetManifest` describes, computed once at assembly time (not a live
    query) — the same "captured per result, not just per config" versioning
    discipline `DimensionScore.weight_used` already applies."""

    model_config = ConfigDict(frozen=True)

    total_examples: int
    reviewed_examples: int
    pending_examples: int
    event_type_counts: tuple[tuple[str, int], ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "ReviewSummary":
        if self.total_examples < 0 or self.reviewed_examples < 0 or self.pending_examples < 0:
            raise ValueError("total_examples/reviewed_examples/pending_examples must be >= 0")
        if self.reviewed_examples > self.total_examples:
            raise ValueError("reviewed_examples cannot exceed total_examples")
        if self.reviewed_examples + self.pending_examples != self.total_examples:
            raise ValueError("reviewed_examples + pending_examples must equal total_examples")
        for event_type, count in self.event_type_counts:
            _require_non_empty(event_type, "event_type_counts entry's event_type")
            if count < 0:
                raise ValueError(f"event_type_counts count for {event_type!r} must be >= 0")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# DatasetManifest — the frozen dataset snapshot
# ═════════════════════════════════════════════════════════════════════════════


class DatasetManifest(BaseModel):
    """A frozen snapshot describing one published dataset version:
    membership by `example_ids` (references only — see module docstring,
    design decision 1), lineage pointers, and statistics aggregated once at
    assembly time. Never embeds a `TrainingExample` itself."""

    model_config = ConfigDict(frozen=True)

    dataset_version: str
    schema_version: str = DATASET_MANIFEST_SCHEMA_VERSION
    created_at: str  # ISO8601
    parent_dataset_version: Optional[str] = None
    superseded_by: Optional[str] = None

    example_ids: tuple[str, ...]
    generator_provenance: tuple[tuple[str, str], ...] = ()
    tier_distribution: tuple[tuple[str, int], ...] = ()
    label_source_distribution: tuple[tuple[str, int], ...] = ()
    review_summary: ReviewSummary

    @model_validator(mode="after")
    def _validate(self) -> "DatasetManifest":
        _require_non_empty(self.dataset_version, "dataset_version")
        _require_non_empty(self.created_at, "created_at")
        if not self.example_ids:
            raise ValueError("example_ids must not be empty — a manifest must describe at least one example")
        if len(set(self.example_ids)) != len(self.example_ids):
            raise ValueError("example_ids must not contain duplicates")
        if self.parent_dataset_version == self.dataset_version:
            raise ValueError("parent_dataset_version must not equal dataset_version")
        if self.superseded_by == self.dataset_version:
            raise ValueError("superseded_by must not equal dataset_version — a manifest cannot supersede itself")
        if self.review_summary.total_examples != len(self.example_ids):
            raise ValueError("review_summary.total_examples must equal len(example_ids)")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# Assembly — the only place stamping/statistics-derivation happens
# ═════════════════════════════════════════════════════════════════════════════


class AlreadyVersionedError(ValueError):
    """Raised by `assemble_manifest` when `allow_reversioning=False` (the
    default) and one or more input examples already carry a
    `metadata.dataset_version` — the default reject policy from design
    decision 3."""

    def __init__(self, example_ids: tuple[str, ...]) -> None:
        preview = ", ".join(example_ids[:5])
        more = f" (+{len(example_ids) - 5} more)" if len(example_ids) > 5 else ""
        super().__init__(
            f"{len(example_ids)} example(s) already have a dataset_version set and "
            f"allow_reversioning=False: {preview}{more}"
        )
        self.example_ids = example_ids


def _generator_provenance(examples: tuple[TrainingExample, ...]) -> tuple[tuple[str, str], ...]:
    seen: list[tuple[str, str]] = []
    seen_set: set[tuple[str, str]] = set()
    for example in examples:
        if example.synthetic is None:
            continue
        pair = (example.synthetic.generation_prompt_id, example.synthetic.prompt_version)
        if pair not in seen_set:
            seen_set.add(pair)
            seen.append(pair)
    return tuple(seen)


def _tier_distribution(examples: tuple[TrainingExample, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for example in examples:
        if example.synthetic is None:
            continue
        key = example.synthetic.intended_quality_tier.value
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _label_source_distribution(examples: tuple[TrainingExample, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for example in examples:
        key = example.labels.label_source
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _review_summary(example_ids: tuple[str, ...], review_log: ReviewEventLog) -> ReviewSummary:
    reviewed_ids: set[str] = set()
    type_counts: dict[str, int] = {}
    for example_id in example_ids:
        events = review_log.events_for(example_id)
        if events:
            reviewed_ids.add(example_id)
        for event in events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
    total = len(example_ids)
    reviewed = len(reviewed_ids)
    return ReviewSummary(
        total_examples=total, reviewed_examples=reviewed, pending_examples=total - reviewed,
        event_type_counts=tuple(sorted(type_counts.items())),
    )


def assemble_manifest(
    examples: tuple[TrainingExample, ...],
    dataset_version: str,
    review_log: Optional[ReviewEventLog] = None,
    parent_dataset_version: Optional[str] = None,
    allow_reversioning: bool = False,
) -> tuple[DatasetManifest, tuple[TrainingExample, ...]]:
    """
    Stamp `dataset_version` onto every example (via `model_copy`, never
    in-place mutation) and assemble the `DatasetManifest` describing the
    resulting batch, deriving `review_summary` from `review_log` (design
    decision — "one cohesive subsystem").

    Returns `(manifest, stamped_examples)` — the manifest references
    `stamped_examples` by id only (design decision 1); the caller owns
    whatever happens to the actual stamped objects next (persistence is
    still an open item across this whole pipeline).

    `allow_reversioning` (default `False`) is the assembly-layer policy
    from design decision 3: by default, any input example that already has
    a `metadata.dataset_version` set raises `AlreadyVersionedError` rather
    than silently being re-stamped. Passing `allow_reversioning=True` is
    the caller's explicit opt-in to place an already-versioned example into
    a new dataset lineage.
    """
    if not examples:
        raise ValueError("examples must not be empty")
    _require_non_empty(dataset_version, "dataset_version")
    if review_log is None:
        review_log = ReviewEventLog()

    if not allow_reversioning:
        already_versioned = tuple(
            e.metadata.example_id for e in examples if e.metadata.dataset_version is not None
        )
        if already_versioned:
            raise AlreadyVersionedError(already_versioned)

    stamped = tuple(
        example.model_copy(update={
            "metadata": example.metadata.model_copy(update={"dataset_version": dataset_version}),
        })
        for example in examples
    )

    example_ids = tuple(e.metadata.example_id for e in stamped)
    if len(set(example_ids)) != len(example_ids):
        raise ValueError("examples must have unique example_ids")

    manifest = DatasetManifest(
        dataset_version=dataset_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        parent_dataset_version=parent_dataset_version,
        example_ids=example_ids,
        generator_provenance=_generator_provenance(stamped),
        tier_distribution=_tier_distribution(stamped),
        label_source_distribution=_label_source_distribution(stamped),
        review_summary=_review_summary(example_ids, review_log),
    )
    return manifest, stamped


def supersede(manifest: DatasetManifest, new_dataset_version: str) -> DatasetManifest:
    """Return a NEW `DatasetManifest` (via `model_copy`) with `superseded_by`
    set — the forward-lineage half of dataset versioning. Refuses to
    re-supersede an already-superseded manifest (that would silently
    overwrite lineage history) and refuses self-supersession."""
    _require_non_empty(new_dataset_version, "new_dataset_version")
    if manifest.superseded_by is not None:
        raise ValueError(
            f"manifest {manifest.dataset_version!r} is already superseded by "
            f"{manifest.superseded_by!r} — cannot supersede it again"
        )
    if new_dataset_version == manifest.dataset_version:
        raise ValueError("a manifest cannot supersede itself")
    return manifest.model_copy(update={"superseded_by": new_dataset_version})
