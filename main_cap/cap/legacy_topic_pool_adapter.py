"""
Legacy TopicPool compatibility adapter — Phase 1.5 (Integration & Hardening)
of ResumeDiscussion_v2.

Before Phase 1.5, `discussion_engine.py` contained its own, independent
`TopicPool` implementation (dict-shaped units, its own priority table, its
own project/experience matching) alongside the new, typed planning
subsystem built in Phase 1 (`question_specification.py`, `traceability.py`,
`coverage_tracker.py`, `topic_pool.py`, `planner.py`). That was two planning
implementations in one project — exactly the duplication Phase 1.5 exists
to remove.

This module is the ONE thing that replaces `discussion_engine.py`'s
internal `TopicPool` class. It contains **no planning logic of its own** —
no priority table, no matching, no scoring, no selection algorithm. Every
one of those concerns is delegated straight to `topic_pool.TopicPool`. What
this module *does* provide is a compatibility surface: the phrasing
functions in `discussion_engine.py` (`_phrase_topic`, `_phrase_followup`,
etc. — Chapter 12's Question Realizer, explicitly out of scope to rewrite
in Phase 1.5) and the existing test suites (`test_e2e.py`,
`_verify_traceability.py`) all expect a dict-shaped "unit" that can be read
with `unit["category"]`/`unit.get(...)` and *mutated in place* with
`unit["status"] = "covered"`, `unit["followups_used"] += 1`, etc. — because
that is how the old `TopicPool` worked, and it is not this phase's job to
change Realizer-adjacent code.

`_UnitView` is what makes that possible without reintroducing uncontrolled
mutation: it is a live, `Mapping`-shaped view over one Question
Specification's identity plus its `UnitLifecycleState`, and every write
through it is translated into a call on `topic_pool.TopicPool`'s hardened,
invariant-preserving API (`mark_active`/`mark_covered`/`mark_skipped`/
`mark_followup_used`/`set_style_used`). Existing code that does
`unit["status"] = "covered"` keeps working exactly as before; underneath,
that write now goes through the same hardened state machine Phase 1.5's
Task 2 built, so `CoverageTracker` can never fall out of sync no matter
which caller — old or new — is driving it.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, Optional

from question_specification import QuestionCategory as _QuestionCategory
from topic_pool import ProfileLike, TopicPool as _PlanningTopicPool

# The old unit dict's fixed key set (Chapter 11.1) — used to answer
# __iter__/__len__ without re-deriving it from a snapshot every time.
_UNIT_KEYS = (
    "id", "category", "text_seed", "grounding", "status", "followups_used",
    "priority_boost", "source_type", "source_id", "source_field", "reason",
    "style_used",
)


def _grounding_to_dict(grounding: Any) -> dict:
    """
    The old unit shape's `grounding` value only ever has ONE key set
    (project XOR experience XOR certification) — never all three with
    `None` fillers — because legacy code reads it as `grounding.get(
    "project", {})` and expects the *default* `{}` when the key is simply
    absent. A blind `Grounding.model_dump()` would instead produce all three
    keys with two of them `None`, which breaks that `.get(..., {})`
    fallback (the key would exist with value `None`, not be missing).
    """
    if grounding.project is not None:
        return {"project": grounding.project.model_dump()}
    if grounding.experience is not None:
        return {"experience": grounding.experience.model_dump()}
    if grounding.certification is not None:
        return {"certification": grounding.certification.model_dump()}
    return {}


class _UnitView(MutableMapping):
    """
    A live, dict-like view over one unit's QuestionSpecification (immutable)
    plus its UnitLifecycleState (mutable, hardened) inside a
    `topic_pool.TopicPool`. Reads always reflect current state; writes to
    `status`/`followups_used`/`style_used` are routed through the pool's
    hardened lifecycle API — no other keys are writable, since every other
    key is part of the immutable Question Specification provenance core
    (Chapter 11.4) and was never mutable even in the legacy implementation.
    """

    __slots__ = ("_pool", "_id")

    def __init__(self, pool: _PlanningTopicPool, spec_id: str):
        self._pool = pool
        self._id = spec_id

    def _snapshot(self) -> dict:
        spec = self._pool.get(self._id)
        if spec is None:
            raise KeyError(f"No unit with id {self._id!r} in this pool")
        lifecycle = self._pool.lifecycle_of(self._id)
        return {
            "id": spec.id,
            "category": spec.category.value,
            "text_seed": spec.text_seed,
            "grounding": _grounding_to_dict(spec.grounding),
            "status": lifecycle.status.value,
            "followups_used": lifecycle.followups_used,
            "priority_boost": spec.priority_boost,
            "source_type": spec.source_type.value,
            "source_id": spec.source_id,
            "source_field": spec.source_field,
            "reason": spec.reason,
            "style_used": lifecycle.style_used,
        }

    def __getitem__(self, key: str) -> Any:
        return self._snapshot()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "status":
            if value == "active":
                self._pool.mark_active(self._id)
            elif value == "covered":
                self._pool.mark_covered(self._id)
            elif value == "skipped":
                self._pool.mark_skipped(self._id)
            else:
                raise ValueError(
                    f"Unsupported status assignment {value!r} — expected "
                    "'active', 'covered', or 'skipped'"
                )
        elif key == "followups_used":
            current = self._pool.lifecycle_of(self._id).followups_used
            if value == current:
                return  # no-op assignment, e.g. re-reading then re-writing the same value
            if value == current + 1:
                self._pool.mark_followup_used(self._id)
            else:
                raise ValueError(
                    "followups_used may only be advanced by exactly +1 through "
                    f"this compatibility view (current={current}, attempted={value})"
                )
        elif key == "style_used":
            self._pool.set_style_used(self._id, value)
        else:
            raise KeyError(
                f"{key!r} is part of the immutable Question Specification "
                "provenance core (Chapter 11.4) and cannot be modified"
            )

    def __delitem__(self, key: str) -> None:
        raise TypeError("cannot delete keys from a unit view")

    def __iter__(self) -> Iterator[str]:
        return iter(_UNIT_KEYS)

    def __len__(self) -> int:
        return len(_UNIT_KEYS)

    def __repr__(self) -> str:
        return f"_UnitView({self._snapshot()!r})"


class TopicPool:
    """
    Thin compatibility wrapper around the Phase 1 planning subsystem. Every
    method below is a translation to `topic_pool.TopicPool`, never a
    reimplementation — see this module's docstring for the full rationale.
    The only state genuinely owned here is `recent_styles`, which is
    Question Realizer phrasing-anti-repetition bookkeeping (Chapter 12),
    not planning state, and so does not belong in the planning subsystem
    itself.
    """

    def __init__(self, profile: ProfileLike):
        self._pool = _PlanningTopicPool(profile)
        self.recent_styles: list[str] = []

    # ── Diagnostics (Chapter 11.3) ───────────────────────────────────────

    @property
    def rejected(self) -> list[dict]:
        return [
            {
                "topic": r.topic,
                "originating_project": r.originating_project,
                "originating_experience": r.originating_experience,
                "reason": r.reason,
            }
            for r in self._pool.rejected
        ]

    @property
    def units(self) -> dict:
        """Every unit currently in the pool, as live `_UnitView`s — matches
        the legacy `TopicPool.units` attribute existing tests
        (`test_e2e.py`, `_verify_traceability.py`) already depend on."""
        return {spec_id: _UnitView(self._pool, spec_id) for spec_id in self._pool.specifications}

    # ── Coverage (Chapter 14) ─────────────────────────────────────────────

    def categories_present(self) -> set:
        return {c.value for c in self._pool.categories_present()}

    def categories_covered(self) -> set:
        return {c.value for c in self._pool.categories_covered()}

    def all_categories_covered(self) -> bool:
        return self._pool.all_categories_covered()

    def remaining(self) -> int:
        return self._pool.remaining()

    # ── Lookup / selection (Chapter 10) ──────────────────────────────────

    def get(self, unit_id: str) -> Optional[_UnitView]:
        spec = self._pool.get(unit_id)
        return None if spec is None else _UnitView(self._pool, unit_id)

    def select_next(self, last_category: Optional[str]) -> Optional[_UnitView]:
        cat = _QuestionCategory(last_category) if last_category is not None else None
        spec = self._pool.select_next(cat)
        return None if spec is None else _UnitView(self._pool, spec.id)
