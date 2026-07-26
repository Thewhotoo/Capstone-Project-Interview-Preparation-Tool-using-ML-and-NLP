"""
Planner — Phase 1 of ResumeDiscussion_v2
(docs/architecture/ResumeDiscussion_v2.md, Chapters 9, 10).

A thin, deterministic facade over TopicPool matching the architecture's data
flow exactly:

    Candidate Profile -> Conversation State -> Coverage State -> QuestionSpecification

No LLM, no Gemini, no randomness beyond the deterministic tie-breaking
already implemented in `TopicPool.select_next` (see that module's docstring
for why the legacy random-jitter tie-break was replaced with a deterministic
one for Phase 1). Given the same Candidate Profile and the same sequence of
`advance()` calls, `Planner.plan_next()` always returns the same sequence of
QuestionSpecifications — this is the determinism the Phase 1 tests verify.

Phase 2 readiness (Phase 1.5, Task 6): this is the entire stable surface a
Question Realizer needs, and nothing more —

    spec = planner.plan_next(state)          # an immutable QuestionSpecification
    # ... Realizer phrases `spec` into natural-language question text ...
    planner.advance(spec.id, UnitStatus.ACTIVE)
    # ... candidate answers, a later phase evaluates ...
    planner.advance(spec.id, UnitStatus.COVERED)  # or .SKIPPED
    # a follow-up on the SAME spec, instead of moving on:
    planner.mark_followup_used(spec.id)
    planner.set_style_used(spec.id, "tradeoffs")  # Realizer's own bookkeeping

A Question Realizer built against this surface never needs to know that
`TopicPool`, `CoverageTracker`, or `traceability.py` exist, and never needs
to change when their internals do — it only ever holds a `QuestionSpecification`
and this `Planner`'s public methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from question_specification import (
    QuestionCategory,
    QuestionSpecification,
    RejectedTopic,
    UnitStatus,
)
from topic_pool import ProfileLike, TopicPool


@dataclass(frozen=True)
class ConversationState:
    """
    The minimal conversation-level state the Planner needs to make its next
    deterministic decision (Chapter 13's `DiscussionMemory` is the full
    picture; this is the narrow slice Planning actually consumes — the rest
    of DiscussionMemory, e.g. concept mastery, belongs to Evaluation, out of
    scope for Phase 1).
    """

    last_category: Optional[QuestionCategory] = None


class Planner:
    """
    Consumes a Candidate Profile once at construction, then deterministically
    plans one Question Specification at a time as the (external) caller
    advances the conversation. The Planner itself makes no decisions about
    WHEN to move on, probe, or skip — that is the Adaptive Controller
    (Chapter 18), a later phase. `Planner.plan_next` + `Planner.advance` only
    expose the primitives a later phase's decision policy will need.
    """

    def __init__(self, profile: ProfileLike):
        self.pool = TopicPool(profile)

    # ── Coverage state (Chapter 14) ──────────────────────────────────────

    def categories_present(self) -> frozenset[QuestionCategory]:
        return self.pool.categories_present()

    def categories_covered(self) -> frozenset[QuestionCategory]:
        return self.pool.categories_covered()

    def all_categories_covered(self) -> bool:
        return self.pool.all_categories_covered()

    # ── Planning ──────────────────────────────────────────────────────────

    def plan_next(self, state: ConversationState) -> Optional[QuestionSpecification]:
        """Return the next best Question Specification given the current
        conversation state, or None if the pool is exhausted. Pure/read-only:
        does not itself advance any unit's lifecycle status."""
        return self.pool.select_next(state.last_category)

    def get(self, spec_id: str) -> Optional[QuestionSpecification]:
        """Look up a previously-planned specification by id — e.g. for a
        follow-up turn, where a later phase needs the ORIGINAL specification
        again rather than planning a new one."""
        return self.pool.get(spec_id)

    @property
    def rejected(self) -> list[RejectedTopic]:
        """Candidate topics that failed traceability validation and were
        never allowed to become a Question Specification (Chapter 11.3)."""
        return self.pool.rejected

    def advance(self, spec_id: str, outcome: UnitStatus) -> None:
        """
        Record the outcome of a specification that has been selected (and,
        in a later phase, asked and answered). `outcome` must be one of
        ACTIVE, COVERED, or SKIPPED — UNASKED is the initial state and is
        never a valid outcome to advance *to*. Invalid transitions (e.g.
        advancing an already-COVERED spec) raise
        `question_specification.InvalidLifecycleTransitionError` — see
        that module for the full state-machine invariant.
        """
        if outcome is UnitStatus.ACTIVE:
            self.pool.mark_active(spec_id)
        elif outcome is UnitStatus.COVERED:
            self.pool.mark_covered(spec_id)
        elif outcome is UnitStatus.SKIPPED:
            self.pool.mark_skipped(spec_id)
        else:
            raise ValueError(f"Not a valid advance() outcome: {outcome!r}")

    def mark_followup_used(self, spec_id: str) -> None:
        """Record that a follow-up was asked on this specification's unit —
        Chapter 17's follow-up planning, a later phase's concern; this only
        exposes the hardened counter it will need."""
        self.pool.mark_followup_used(spec_id)

    def set_style_used(self, spec_id: str, style: Optional[str]) -> None:
        """Record which phrasing style/angle a Question Realizer used for
        this specification's most recent turn (Chapter 12) — Realizer
        bookkeeping, exposed here so it has one hardened home."""
        self.pool.set_style_used(spec_id, style)

    def remaining(self) -> int:
        return self.pool.remaining()

    def total(self) -> int:
        """Total number of specifications planned for this profile (fixed
        at construction) — read-only introspection, e.g. for a progress
        indicator. Does not influence planning, selection, or termination."""
        return self.pool.total()
