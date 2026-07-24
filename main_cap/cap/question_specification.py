"""
Question Specification — Phase 1 of ResumeDiscussion_v2
(docs/architecture/ResumeDiscussion_v2.md, Chapter 11).

This module defines the immutable, typed record the deterministic Planner
(Chapter 10) produces for every discussable topic on a Candidate Profile.
Nothing in this module renders natural-language question text (Chapter 12,
Question Realizer), scores an answer (Chapter 19, Evaluator), or explains a
score (Chapter 20, Explainability) — those are later phases and are
explicitly out of scope for Phase 1.

Per Chapter 11.4 ("Immutability of the Question Specification"), the
specification's provenance core — id, category, text_seed, grounding,
source_type, source_id, source_field, reason — is permanent once created and
must never be modified by any downstream component. `QuestionSpecification`
enforces this at runtime (not just by convention) via Pydantic's frozen
config, and grounding sub-objects are frozen too, with tuples rather than
lists for their list-shaped fields, so a caller cannot mutate a "frozen"
object's contents through a nested mutable container.

Chapter 11.4 also notes that session-lifecycle state (`status`,
`followups_used`, `style_used`) is not part of "what the unit fundamentally
is," and explicitly welcomes separating it out structurally rather than
mutating fields in place. `UnitLifecycleState` (below) is exactly that
separation, applied from the start rather than retrofitted later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Schema version for QuestionSpecification itself (distinct from
# CandidateProfile's schema_version, Chapter 8.5) — the same versioning
# discipline the architecture requires everywhere a permanent record can
# outlive the code that produced it (Chapter 8.5, Chapter 19.7). Bump this
# and add an explicit migration path whenever a field is added, renamed, or
# removed from QuestionSpecification's provenance core.
QUESTION_SPECIFICATION_SCHEMA_VERSION = "v1"


# ═════════════════════════════════════════════════════════════════════════════
# Enumerations
# ═════════════════════════════════════════════════════════════════════════════


class QuestionCategory(str, Enum):
    """
    The five priority tiers a discussion unit belongs to (Chapter 10.3).
    Ordering here is declaration order, not priority order — priority is
    computed explicitly by the planner/pool, never inferred from enum order.
    """

    PROJECT_DEEP_DIVE = "project_deep_dive"
    PROJECT_OVERVIEW = "project_overview"
    EXPERIENCE = "experience"
    CERTIFICATION = "certification"
    SKILL_IN_CONTEXT = "skill_in_context"


class SourceType(str, Enum):
    """Which kind of Candidate Profile entity a specification traces back to (Chapter 11.2)."""

    PROJECT = "project"
    EXPERIENCE = "experience"
    CERTIFICATION = "certification"


class UnitStatus(str, Enum):
    """Session-lifecycle status of a unit (Chapter 11.1, Chapter 14)."""

    UNASKED = "unasked"
    ACTIVE = "active"
    COVERED = "covered"
    SKIPPED = "skipped"


# Fixed priority tiers, matching the table in Chapter 10.3 exactly. Declared
# once, here, so both TopicPool's scoring and any test asserting tier
# ordering read the same single source of truth.
CATEGORY_PRIORITY: dict[QuestionCategory, int] = {
    QuestionCategory.PROJECT_DEEP_DIVE: 5,
    QuestionCategory.PROJECT_OVERVIEW: 4,
    QuestionCategory.EXPERIENCE: 3,
    QuestionCategory.CERTIFICATION: 2,
    QuestionCategory.SKILL_IN_CONTEXT: 1,
}


# ═════════════════════════════════════════════════════════════════════════════
# Grounding — the Candidate Profile sub-object a specification stays faithful to
# ═════════════════════════════════════════════════════════════════════════════


class ProjectGrounding(BaseModel):
    """Frozen snapshot of the project entry a specification is grounded in."""

    model_config = ConfigDict(frozen=True)

    title: str
    summary: str = ""
    technologies: tuple[str, ...] = Field(default_factory=tuple)
    concepts: tuple[str, ...] = Field(default_factory=tuple)


class ExperienceGrounding(BaseModel):
    """Frozen snapshot of the experience entry a specification is grounded in."""

    model_config = ConfigDict(frozen=True)

    role: str
    company: str = ""
    duration: str = ""
    summary: str = ""


class CertificationGrounding(BaseModel):
    """Frozen snapshot of the certification a specification is grounded in."""

    model_config = ConfigDict(frozen=True)

    name: str


class Grounding(BaseModel):
    """
    The actual Candidate Profile sub-object(s) a Question Specification must
    stay faithful to (Chapter 11.1). Exactly one of project/experience/
    certification is ever set — never zero, never more than one — mirroring
    the traceability rule already enforced on TechnicalTopic at profile-
    generation time (Chapter 8.3/8.4): a question is always about one real
    entity, never a blend of two, never free-floating.
    """

    model_config = ConfigDict(frozen=True)

    project: Optional[ProjectGrounding] = None
    experience: Optional[ExperienceGrounding] = None
    certification: Optional[CertificationGrounding] = None

    @model_validator(mode="after")
    def _exactly_one_entity(self) -> "Grounding":
        set_count = sum(
            entity is not None
            for entity in (self.project, self.experience, self.certification)
        )
        if set_count != 1:
            raise ValueError(
                "Grounding must reference exactly one entity (project XOR "
                f"experience XOR certification); found {set_count} set."
            )
        return self


# ═════════════════════════════════════════════════════════════════════════════
# Question Specification — the immutable provenance record (Chapter 11.4)
# ═════════════════════════════════════════════════════════════════════════════


class QuestionSpecification(BaseModel):
    """
    The permanent, immutable record of why a question exists (Chapter 11.4).

    Every field here is part of the "provenance core" the architecture
    requires to stay unchanged for the lifetime of a session:
    Planner -> Question Specification (immutable) -> Question Realizer ->
    Evaluator -> Dashboard. No downstream component may modify any field on
    this object — Pydantic's frozen config enforces that at runtime (an
    attempted assignment raises `pydantic.ValidationError`), not just by
    convention or code review.

    Session-lifecycle state that genuinely changes over the course of a
    conversation (status, followups_used, style_used) is deliberately NOT a
    field here — see `UnitLifecycleState` below and Chapter 11.4's closing
    note, which names this exact separation as a welcome structural
    clarification of the immutability principle.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    category: QuestionCategory
    text_seed: Optional[str] = None
    grounding: Grounding
    priority_boost: bool = False
    source_type: SourceType
    source_id: str
    source_field: str
    reason: str
    # Chapter 8.5's versioning discipline applied to this record too (Phase
    # 1.5, Task 4): every specification carries the schema version it was
    # built under, so an archived specification (Chapter 22.3's training
    # data) remains interpretable even after this schema evolves.
    schema_version: str = QUESTION_SPECIFICATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def _source_type_matches_grounding(self) -> "QuestionSpecification":
        """source_type must name the one entity actually set on grounding —
        the specification-level half of the traceability guarantee (the
        profile-level half lives in traceability.py)."""
        expected = {
            SourceType.PROJECT: self.grounding.project,
            SourceType.EXPERIENCE: self.grounding.experience,
            SourceType.CERTIFICATION: self.grounding.certification,
        }
        if expected[self.source_type] is None:
            raise ValueError(
                f"source_type={self.source_type.value!r} but grounding has no "
                "matching entity set"
            )
        return self

    @model_validator(mode="after")
    def _non_empty_provenance(self) -> "QuestionSpecification":
        """Every provenance field must actually say something — an empty
        `id`/`source_id`/`source_field`/`reason` would make the audit trail
        (Chapter 11.2) unusable even though the object technically exists."""
        for field_name in ("id", "source_id", "source_field", "reason"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        return self


# ═════════════════════════════════════════════════════════════════════════════
# Unit lifecycle state — mutable, tracked separately from the specification
# ═════════════════════════════════════════════════════════════════════════════


class InvalidLifecycleTransitionError(ValueError):
    """
    Raised when a requested status transition violates the unit lifecycle
    state machine (Chapter 11.1), or when a follow-up is recorded against a
    unit that isn't currently ACTIVE.

    THE INVARIANT (Phase 1.5, Task 2): `UnitLifecycleState.status` and
    `CoverageTracker`'s covered-categories set can never be observed out of
    sync. This holds because (1) `UnitLifecycleState.status` has no public
    setter — the only way to change it is `TopicPool.mark_active` /
    `mark_covered` / `mark_skipped`, and (2) every one of those three
    methods updates the lifecycle state AND `CoverageTracker` together, in
    the same method call, with no way to invoke one half without the other.
    There is no code path — anywhere in this module or its callers — that
    can move `status` away from UNASKED without `CoverageTracker` learning
    about it in the same call. See test_lifecycle_hardening.py for the
    tests proving this.
    """


# The fixed state machine a unit's status may move through (Chapter 11.1):
# unasked -> active -> (covered | skipped), or unasked straight to
# (covered | skipped) for the duplicate-collision path (Chapter 15) which
# never activates a unit before discarding it. covered/skipped are terminal
# — once resolved, a unit is never reconsidered (`select_next` only ever
# offers UNASKED units in the first place, so re-entering an old unit would
# always indicate a caller bug, not a legitimate case to support silently).
_ALLOWED_TRANSITIONS: dict[UnitStatus, frozenset[UnitStatus]] = {
    UnitStatus.UNASKED: frozenset({UnitStatus.ACTIVE, UnitStatus.COVERED, UnitStatus.SKIPPED}),
    UnitStatus.ACTIVE: frozenset({UnitStatus.COVERED, UnitStatus.SKIPPED}),
    UnitStatus.COVERED: frozenset(),
    UnitStatus.SKIPPED: frozenset(),
}


class UnitLifecycleState:
    """
    Session-lifecycle bookkeeping for one Question Specification, keyed by
    the specification's `id`. This is intentionally a *separate* mutable
    object rather than fields on `QuestionSpecification` itself, so the
    specification's provenance core can be genuinely immutable (enforced by
    Pydantic) while the pool still has somewhere to record what has
    happened to a unit over the course of a session (Chapter 11.4).

    Hardened (Phase 1.5, Task 2): `status`, `followups_used`, and
    `style_used` are read-only properties. There is no public setter for
    any of them — `state.status = UnitStatus.ACTIVE` now raises
    `AttributeError` instead of silently succeeding. The only way to change
    them is through `TopicPool`'s controlled methods (`mark_active`,
    `mark_covered`, `mark_skipped`, `mark_followup_used`, `set_style_used`),
    which call the underscore-prefixed methods below AND keep
    `CoverageTracker` in sync in the same call — see
    `InvalidLifecycleTransitionError`'s docstring for the exact invariant
    this preserves.
    """

    def __init__(self) -> None:
        self._status = UnitStatus.UNASKED
        self._followups_used = 0
        self._style_used: Optional[str] = None

    @property
    def status(self) -> UnitStatus:
        return self._status

    @property
    def followups_used(self) -> int:
        return self._followups_used

    @property
    def style_used(self) -> Optional[str]:
        return self._style_used

    def _transition(self, new_status: UnitStatus) -> None:
        """Internal — call only from `TopicPool.mark_active`/`mark_covered`/
        `mark_skipped`, which are responsible for updating `CoverageTracker`
        in the same call. Validates against `_ALLOWED_TRANSITIONS`."""
        allowed = _ALLOWED_TRANSITIONS[self._status]
        if new_status not in allowed:
            raise InvalidLifecycleTransitionError(
                f"cannot transition from {self._status.value!r} to "
                f"{new_status.value!r} (allowed from {self._status.value!r}: "
                f"{sorted(s.value for s in allowed) or 'none — terminal state'})"
            )
        self._status = new_status

    def _increment_followups(self) -> None:
        """Internal — call only from `TopicPool.mark_followup_used`, which
        enforces that a follow-up may only be recorded while ACTIVE."""
        self._followups_used += 1

    def _set_style(self, style: Optional[str]) -> None:
        """Internal — call only from `TopicPool.set_style_used`."""
        self._style_used = style


# ═════════════════════════════════════════════════════════════════════════════
# Rejected topics — kept for diagnostics/tests, never surfaced to a candidate
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RejectedTopic:
    """
    A `technical_topics` entry (or any other candidate unit) that failed
    traceability validation and was therefore never allowed to become a
    Question Specification (Chapter 8.4, Chapter 10.3, Chapter 11.3).
    """

    topic: str
    originating_project: str
    originating_experience: str
    reason: str
