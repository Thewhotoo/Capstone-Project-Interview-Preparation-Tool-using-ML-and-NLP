"""
Labeling Operations — Stage A / human-review subsystem (Labeling Operations
RFC — no RFC text was recoverable from prior chat history; this design was
proposed fresh this session, reviewed, and explicitly approved with five
named decisions before any code was written). Implementation only; no
architectural deviation from what was approved.

ONE COHESIVE ADDITION on top of the existing `dataset_manifest.py`
subsystem: `ReviewEvent`/`ReviewEventLog` were deliberately built with an
OPEN `event_type` vocabulary specifically so this module could define the
real reviewer-workflow vocabulary later without any schema change — this is
that later module. Nothing in `dataset_manifest.py` is modified.

STRICT INDEPENDENCE (same discipline as `dataset_manifest.py`): this module
imports only `training_example.py` and `dataset_manifest.py` (plus stdlib) —
zero dependency on `synthetic_generation_pipeline.py`, `coverage_strategy.py`,
any `generation_*`/`prompt_*` module, or any Evaluation/Conversation/
Planning module. See `test_labeling_operations.py`'s import-graph AST
assertion (the same pattern `test_dataset_manifest.py` already established).

APPROVED DECISIONS (this session):

1. `LabelingConfig.required_agreement_reviewers` defaults to 2.
2. A reviewer may revise their own verdict; only each reviewer's LATEST
   `ReviewEvent` contributes to the current derived `ReviewState`
   (`compute_review_state` folds the ordered event history per reviewer_id,
   keeping only the last one seen).
3. Any `flagged` event immediately forces `ReviewState.NEEDS_ADJUDICATION`,
   regardless of how many verdicts exist or agree, until an `adjudicated`
   event resolves it (adjudication is checked first and is terminal/
   authoritative — once issued, it always wins).
4. `ReviewerRegistry` roles are NOT permanently fixed: `register(...)` sets
   a reviewer's initial role (raises `DuplicateReviewerError` on a second
   `register` call for the same id — that's what `update_role(...)` is
   for), and `update_role(...)` supports promotions (e.g. ANNOTATOR ->
   ADJUDICATOR) on an already-registered reviewer. Both are simple,
   deterministic dict operations — no history/audit trail of role changes
   is kept (that would be a different, unrequested feature).
5. Only two roles exist: `ANNOTATOR` and `ADJUDICATOR`. No `QA_LEAD` role —
   explicitly deferred to a future, separately-scoped RFC rather than
   anticipated here.

DISCOVERED DURING IMPLEMENTATION (not a deviation — a correct reading of an
existing frozen invariant, not a schema change): `TrainingExample`'s own
`_synthetic_presence_matches_source` validator already requires a SYNTHETIC-
provenance example's `labels.label_source` to always be
`"synthetic_ground_truth"` — a synthetic example's labels ARE its ground
truth by construction. `apply_relabel` therefore only accepts a
REAL_SESSION-provenance example and raises `ValueError` otherwise, rather
than letting `model_copy` silently build a `TrainingExample` that would fail
its own frozen validator if ever reconstructed from a dict/JSON round-trip.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from dataset_manifest import ReviewEvent, ReviewEventLog, ReviewEventType
from training_example import ProvenanceSource, TrainingExample, TrainingExampleLabels


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


# ═════════════════════════════════════════════════════════════════════════════
# Reviewer identity/role
# ═════════════════════════════════════════════════════════════════════════════


class ReviewerRole(str, Enum):
    """Closed — a small, fixed taxonomy (approved decision 5: only these
    two roles for now, no QA_LEAD)."""

    ANNOTATOR = "annotator"
    ADJUDICATOR = "adjudicator"


class DuplicateReviewerError(ValueError):
    """Raised by `ReviewerRegistry.register` if `reviewer_id` is already
    registered — use `update_role` to change an existing reviewer's role
    (approved decision 4)."""


class UnknownReviewerError(ValueError):
    """Raised by `ReviewerRegistry.update_role` for a `reviewer_id` that was
    never `register`ed."""


class ReviewerRegistry:
    """Hand-curated reviewer roster (registry pattern, same style as
    `expected_concepts_registry.py`), mutable by design (approved decision
    4 — roles are NOT permanently fixed): `register` sets an initial role,
    `update_role` supports promotions on an already-registered reviewer.
    Deterministic dict operations only; no role-change history is kept."""

    def __init__(self) -> None:
        self._roles: dict[str, ReviewerRole] = {}

    def register(self, reviewer_id: str, role: ReviewerRole) -> None:
        _require_non_empty(reviewer_id, "reviewer_id")
        if reviewer_id in self._roles:
            raise DuplicateReviewerError(
                f"reviewer {reviewer_id!r} is already registered — use update_role to change their role"
            )
        self._roles[reviewer_id] = role

    def update_role(self, reviewer_id: str, role: ReviewerRole) -> None:
        if reviewer_id not in self._roles:
            raise UnknownReviewerError(f"reviewer {reviewer_id!r} is not registered")
        self._roles[reviewer_id] = role

    def role_of(self, reviewer_id: str) -> Optional[ReviewerRole]:
        return self._roles.get(reviewer_id)

    def reviewers_with_role(self, role: ReviewerRole) -> tuple[str, ...]:
        return tuple(sorted(rid for rid, r in self._roles.items() if r == role))


# ═════════════════════════════════════════════════════════════════════════════
# Review event vocabulary this subsystem owns (extends, never touches,
# dataset_manifest.ReviewEventType)
# ═════════════════════════════════════════════════════════════════════════════


class LabelingReviewEventType:
    """Open, registry-style values this subsystem contributes to
    `ReviewEvent.event_type`'s vocabulary — additive only, `dataset_manifest.py`
    is never modified. `dataset_manifest.ReviewEventType`'s existing
    `APPROVED`/`REJECTED`/`FLAGGED`/`RELABELED` remain in use alongside
    these."""

    NEEDS_ADJUDICATION = "needs_adjudication"
    ADJUDICATED = "adjudicated"


# ═════════════════════════════════════════════════════════════════════════════
# Derived review state — never stored, always folded from the event log
# ═════════════════════════════════════════════════════════════════════════════


class ReviewState(str, Enum):
    """Closed — a fixed, small workflow-state taxonomy. Always DERIVED by
    `compute_review_state` from a `ReviewEvent` history; never itself stored
    anywhere, exactly like `DatasetManifest.review_summary`'s "derive from
    the log" philosophy."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_ADJUDICATION = "needs_adjudication"
    ADJUDICATED = "adjudicated"


@dataclass(frozen=True)
class LabelingConfig:
    """Tunable workflow parameters. `required_agreement_reviewers` defaults
    to 2 (approved decision 1)."""

    required_agreement_reviewers: int = 2

    def __post_init__(self) -> None:
        if self.required_agreement_reviewers < 1:
            raise ValueError("required_agreement_reviewers must be >= 1")


_VERDICT_TYPES = (ReviewEventType.APPROVED, ReviewEventType.REJECTED)
_ESCALATION_TYPES = (ReviewEventType.FLAGGED, LabelingReviewEventType.NEEDS_ADJUDICATION)


def compute_review_state(
    events: tuple[ReviewEvent, ...],
    config: LabelingConfig = LabelingConfig(),
) -> ReviewState:
    """
    Pure fold over one example's `ReviewEvent` history (as returned by
    `ReviewEventLog.events_for(example_id)`, already in the order they were
    recorded) — no separate mutable state anywhere; the log stays the
    single source of truth.

    Order of checks (approved decisions 2/3):
      1. Any `adjudicated` event -> ADJUDICATED, unconditionally and
         terminally (an adjudicator's word is final).
      2. Else any `flagged`/`needs_adjudication` event -> NEEDS_ADJUDICATION.
      3. Else fold each reviewer's LATEST verdict (`approved`/`rejected`)
         event — a reviewer may revise their own earlier verdict.
      4. Distinct verdicts among distinct reviewers disagree -> NEEDS_ADJUDICATION.
      5. Enough agreeing distinct reviewers (>= `required_agreement_reviewers`)
         -> APPROVED/REJECTED. Fewer -> IN_REVIEW.
      6. No events at all -> PENDING.
    """
    if not events:
        return ReviewState.PENDING

    if any(e.event_type == LabelingReviewEventType.ADJUDICATED for e in events):
        return ReviewState.ADJUDICATED

    if any(e.event_type in _ESCALATION_TYPES for e in events):
        return ReviewState.NEEDS_ADJUDICATION

    latest_verdict_by_reviewer: dict[str, str] = {}
    for event in events:
        if event.event_type in _VERDICT_TYPES:
            latest_verdict_by_reviewer[event.reviewer_id] = event.event_type

    if not latest_verdict_by_reviewer:
        return ReviewState.PENDING

    distinct_verdicts = set(latest_verdict_by_reviewer.values())
    if len(distinct_verdicts) > 1:
        return ReviewState.NEEDS_ADJUDICATION

    verdict = next(iter(distinct_verdicts))
    if len(latest_verdict_by_reviewer) >= config.required_agreement_reviewers:
        return ReviewState.APPROVED if verdict == ReviewEventType.APPROVED else ReviewState.REJECTED
    return ReviewState.IN_REVIEW


# ═════════════════════════════════════════════════════════════════════════════
# Recording a review — the one place this module writes to a ReviewEventLog
# ═════════════════════════════════════════════════════════════════════════════


class UnauthorizedReviewActionError(ValueError):
    """Raised by `record_review` when `event_type` is role-gated (currently
    only `adjudicated`, restricted to `ReviewerRole.ADJUDICATOR`) and the
    acting reviewer doesn't hold that role."""

    def __init__(self, reviewer_id: str, event_type: str, required_role: ReviewerRole) -> None:
        super().__init__(
            f"reviewer {reviewer_id!r} is not registered as {required_role.value!r} "
            f"and may not record a {event_type!r} event"
        )
        self.reviewer_id = reviewer_id
        self.event_type = event_type
        self.required_role = required_role


_ROLE_GATED_EVENT_TYPES: dict[str, ReviewerRole] = {
    LabelingReviewEventType.ADJUDICATED: ReviewerRole.ADJUDICATOR,
}


def record_review(
    log: ReviewEventLog,
    example_id: str,
    reviewer_id: str,
    event_type: str,
    rationale: str,
    reviewer_registry: Optional[ReviewerRegistry] = None,
    notes: Optional[str] = None,
    event_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> ReviewEvent:
    """
    Construct and append one `ReviewEvent` — the only place this module
    mutates a `ReviewEventLog` (still, underneath, just `ReviewEventLog.record`;
    the append-only guarantee is unchanged). Role-gates `event_type`s in
    `_ROLE_GATED_EVENT_TYPES` (currently just `adjudicated`) against
    `reviewer_registry`, raising `UnauthorizedReviewActionError` if the
    registry is missing or the reviewer doesn't hold the required role —
    this is where "governance" is actually enforced.
    """
    required_role = _ROLE_GATED_EVENT_TYPES.get(event_type)
    if required_role is not None:
        actual_role = reviewer_registry.role_of(reviewer_id) if reviewer_registry is not None else None
        if actual_role != required_role:
            raise UnauthorizedReviewActionError(reviewer_id, event_type, required_role)

    event = ReviewEvent(
        event_id=event_id or f"review_{uuid.uuid4().hex[:16]}",
        example_id=example_id,
        event_type=event_type,
        reviewer_id=reviewer_id,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        rationale=rationale,
        notes=notes,
    )
    log.record(event)
    return event


# ═════════════════════════════════════════════════════════════════════════════
# Reviewer metrics — derived-only, exactly like DatasetManifest.review_summary
# ═════════════════════════════════════════════════════════════════════════════


class ReviewerMetrics(BaseModel):
    """A frozen snapshot of one reviewer's activity, computed on demand from
    a `ReviewEventLog` — never a separately stored/mutated counter."""

    model_config = ConfigDict(frozen=True)

    reviewer_id: str
    total_events: int
    event_type_counts: tuple[tuple[str, int], ...] = ()
    agreement_count: int = 0
    disagreement_count: int = 0

    @model_validator(mode="after")
    def _validate(self) -> "ReviewerMetrics":
        _require_non_empty(self.reviewer_id, "reviewer_id")
        if self.total_events < 0:
            raise ValueError("total_events must be >= 0")
        if self.agreement_count < 0 or self.disagreement_count < 0:
            raise ValueError("agreement_count/disagreement_count must be >= 0")
        if self.agreement_count + self.disagreement_count > self.total_events:
            raise ValueError("agreement_count + disagreement_count cannot exceed total_events")
        return self


def compute_reviewer_metrics(review_log: ReviewEventLog, reviewer_id: str) -> ReviewerMetrics:
    """
    Derived-only reviewer statistics. `agreement_count`/`disagreement_count`
    are a pairwise reading of "agreement": for each example this reviewer
    verdicted (`approved`/`rejected`), compare their LATEST verdict against
    every OTHER reviewer's latest verdict on that same example (an example
    with no other reviewer yet doesn't count either way — there's nothing
    to agree or disagree with).
    """
    reviewer_events = tuple(e for e in review_log.all_events() if e.reviewer_id == reviewer_id)
    type_counts: dict[str, int] = {}
    for event in reviewer_events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    example_ids = tuple(dict.fromkeys(e.example_id for e in reviewer_events))
    agreement_count = 0
    disagreement_count = 0
    for example_id in example_ids:
        latest_verdict_by_reviewer: dict[str, str] = {}
        for event in review_log.events_for(example_id):
            if event.event_type in _VERDICT_TYPES:
                latest_verdict_by_reviewer[event.reviewer_id] = event.event_type

        this_verdict = latest_verdict_by_reviewer.get(reviewer_id)
        if this_verdict is None:
            continue
        other_verdicts = {rid: v for rid, v in latest_verdict_by_reviewer.items() if rid != reviewer_id}
        if not other_verdicts:
            continue
        if all(v == this_verdict for v in other_verdicts.values()):
            agreement_count += 1
        else:
            disagreement_count += 1

    return ReviewerMetrics(
        reviewer_id=reviewer_id,
        total_events=len(reviewer_events),
        event_type_counts=tuple(sorted(type_counts.items())),
        agreement_count=agreement_count,
        disagreement_count=disagreement_count,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Relabeling — model_copy-based, same stamping precedent as dataset_manifest.py
# ═════════════════════════════════════════════════════════════════════════════


def apply_relabel(
    example: TrainingExample,
    new_labels: TrainingExampleLabels,
    labeling_guideline_version: str,
) -> TrainingExample:
    """
    Produce a NEW `TrainingExample` (the original is never mutated) whose
    `labels` is `new_labels`, forced to `label_source="human_reviewed"`
    with `labeling_guideline_version` set. The caller supplies the actual
    human judgment (`new_labels`) — this function never invents label
    content, only performs the "stamp as human-reviewed" copy mechanic,
    mirroring `dataset_manifest.assemble_manifest`'s `dataset_version`
    stamping.

    Only valid for a REAL_SESSION-provenance example — see module
    docstring's "DISCOVERED DURING IMPLEMENTATION" note: a SYNTHETIC
    example's labels are its ground truth by construction and
    `TrainingExample`'s own frozen validator already forbids relabeling one
    as human-reviewed.

    Reconstructs `TrainingExampleLabels` via its normal constructor (not
    `model_copy`) so its own `model_validator` actually re-runs against the
    forced `label_source`/`labeling_guideline_version` — `model_copy` does
    NOT re-validate, and silently building an invalid labels object would
    violate this project's "enforced at construction time, never left to
    caller discipline" rule.
    """
    if example.provenance.source != ProvenanceSource.REAL_SESSION:
        raise ValueError(
            "apply_relabel only applies to a REAL_SESSION-provenance TrainingExample — got "
            f"provenance.source={example.provenance.source.value!r}. A synthetic example's labels "
            "are its ground truth by construction and cannot be human-relabeled."
        )
    _require_non_empty(labeling_guideline_version, "labeling_guideline_version")

    relabeled = TrainingExampleLabels(**{
        **new_labels.model_dump(),
        "label_source": "human_reviewed",
        "labeling_guideline_version": labeling_guideline_version,
    })
    return example.model_copy(update={"labels": relabeled})
