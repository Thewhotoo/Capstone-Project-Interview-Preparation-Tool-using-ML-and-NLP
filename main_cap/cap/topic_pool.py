"""
TopicPool — Phase 1 of ResumeDiscussion_v2
(docs/architecture/ResumeDiscussion_v2.md, Chapters 9-11, 14).

This is the deterministic planner (Component 1, Chapter 9): it builds one
immutable QuestionSpecification per discussable fact on a Candidate Profile,
validates traceability before any unit is allowed to exist, tracks coverage
and per-unit lifecycle status, and selects the next unit to ask about using
the exact priority hierarchy and scoring rules Chapter 10.3 defines.

Phase 1 scope only: this module produces QuestionSpecifications. It does not
phrase natural-language questions (Chapter 12, Question Realizer), does not
evaluate answers (Chapter 19), and does not implement the Adaptive Controller
(Chapter 18) — `select_next` simply returns the next best UNASKED
specification; deciding whether to probe/clarify/move on belongs to a later
phase. `mark_active`/`mark_covered`/`mark_skipped` exist here only so a
caller CAN drive the lifecycle status machine described in Chapter 11.1 —
Phase 1 does not itself decide when to call them.

Determinism note (see the "Architecture decisions" section of the Phase 1
summary): Chapter 10.3 describes "today's implementation" (in
`discussion_engine.py`) as including a small random jitter purely so
repeated sessions on the same profile don't feel scripted. The explicit
Phase 1 instruction is that the Planner must remain "completely
deterministic... no randomness except deterministic tie-breaking already
defined by the architecture," and that identical Candidate Profiles must
produce identical QuestionSpecifications. This module therefore ties every
tie-break to build order (stable, deterministic) instead of `random.random()`.
This is a deliberate, documented resolution of that tension in favor of the
explicit Phase 1 instructions — not a silent redesign — see the
implementation summary for the full rationale.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

from coverage_tracker import CoverageTracker
from question_specification import (
    CATEGORY_PRIORITY,
    CertificationGrounding,
    ExperienceGrounding,
    Grounding,
    InvalidLifecycleTransitionError,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    RejectedTopic,
    SourceType,
    UnitLifecycleState,
    UnitStatus,
)
from traceability import (
    find_experience_by_label,
    find_project_by_title,
    validate_technical_topic_origin,
)

logger = logging.getLogger(__name__)

# Type alias: a Candidate Profile as consumed here may be the Pydantic model
# from candidate_profile_generator.py, or its plain-dict `.model_dump()` form
# (the shape actually stored in session state today, per Chapter 7 step 5).
# TopicPool normalizes either into plain dict access internally so it never
# depends on which representation the caller happens to hold.
ProfileLike = Union[dict, Any]


def _as_dict(entry: Any) -> dict:
    """Coerce a profile sub-entry (dict or Pydantic model instance) into a
    plain dict — mirrors the same dict-vs-model duality already handled in
    candidate_profile_generator.py's `_entry_to_dict`."""
    if isinstance(entry, dict):
        return entry
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    raise TypeError(f"Cannot coerce {type(entry)!r} into a plain dict")


def _profile_to_dict(profile: ProfileLike) -> dict:
    if isinstance(profile, dict):
        return profile
    if hasattr(profile, "model_dump"):
        return profile.model_dump()
    raise TypeError(f"Cannot coerce {type(profile)!r} into a Candidate Profile dict")


class TopicPool:
    """
    An adaptive pool of discussion topics built once from the Candidate
    Profile. Nothing about ordering is fixed upfront: `select_next` picks
    from whatever's still `unasked`, always within the strict priority
    hierarchy Chapter 10.3 defines, never a precomputed sequence and never a
    unit that isn't traceable back to one specific Candidate Profile entry.
    """

    def __init__(self, profile: ProfileLike):
        self.profile: dict = _profile_to_dict(profile)
        self.specifications: dict[str, QuestionSpecification] = {}
        self.lifecycle: dict[str, UnitLifecycleState] = {}
        self.rejected: list[RejectedTopic] = []
        # Preserves build order for deterministic tie-breaking (see module
        # docstring's determinism note) — Python dict insertion order is
        # already stable, but this list makes that guarantee explicit and
        # independently inspectable/testable.
        self._build_order: list[str] = []
        self._next_seq = 0

        self._build(self.profile)

        present_categories = {spec.category for spec in self.specifications.values()}
        self.coverage = CoverageTracker(present_categories)

    # ── Construction ─────────────────────────────────────────────────────

    def _new_id(self) -> str:
        unit_id = f"topic_{self._next_seq}"
        self._next_seq += 1
        return unit_id

    def _add(
        self,
        category: QuestionCategory,
        text_seed: Optional[str],
        grounding: Grounding,
        source_type: SourceType,
        source_id: str,
        source_field: str,
        reason: str,
        priority_boost: bool = False,
    ) -> str:
        unit_id = self._new_id()
        spec = QuestionSpecification(
            id=unit_id,
            category=category,
            text_seed=text_seed,
            grounding=grounding,
            priority_boost=priority_boost,
            source_type=source_type,
            source_id=source_id,
            source_field=source_field,
            reason=reason,
        )
        self.specifications[unit_id] = spec
        self.lifecycle[unit_id] = UnitLifecycleState()
        self._build_order.append(unit_id)
        return unit_id

    def _build(self, profile: dict) -> None:
        blueprint = profile.get("interview_blueprint", {}) or {}
        weaknesses = [w.lower() for w in blueprint.get("estimated_weaknesses", [])]
        projects = [_as_dict(p) for p in profile.get("projects", [])]
        experiences = [_as_dict(e) for e in profile.get("experience", [])]
        certifications = profile.get("certifications", [])

        def touches_weakness(text: str) -> bool:
            text_lower = (text or "").lower()
            return any(w in text_lower or text_lower in w for w in weaknesses if w)

        def project_grounding(project: dict) -> Grounding:
            return Grounding(
                project=ProjectGrounding(
                    title=project.get("title", ""),
                    summary=project.get("summary", ""),
                    technologies=tuple(project.get("technologies", []) or []),
                    concepts=tuple(project.get("concepts", []) or []),
                )
            )

        def experience_grounding(exp: dict) -> Grounding:
            return Grounding(
                experience=ExperienceGrounding(
                    role=exp.get("role", ""),
                    company=exp.get("company", ""),
                    duration=exp.get("duration", ""),
                    summary=exp.get("summary", ""),
                )
            )

        # Prevents literal duplicate (project, seed-text) pairs — the
        # Phase-1-appropriate, identity-level form of duplicate prevention.
        # Semantic dedup over PHRASED question text (Chapter 15) requires
        # the Question Realizer and is out of scope for Phase 1; see the
        # implementation summary.
        seen_deep_dive_seeds: set[tuple[str, str]] = set()

        # ── Priority 1: project-specific interview seeds ────────────────
        for project in projects:
            title = project.get("title", "")
            if not title:
                continue
            for seed in project.get("interview_seeds", []) or []:
                key = (title.strip().lower(), (seed or "").strip().lower())
                if key in seen_deep_dive_seeds:
                    continue
                seen_deep_dive_seeds.add(key)
                self._add(
                    QuestionCategory.PROJECT_DEEP_DIVE,
                    seed,
                    project_grounding(project),
                    source_type=SourceType.PROJECT,
                    source_id=title,
                    source_field="interview_seeds",
                    reason=f"projects[title={title!r}].interview_seeds",
                    priority_boost=touches_weakness(title) or touches_weakness(seed),
                )

        # ── Priority 2: project overview ─────────────────────────────────
        for project in projects:
            title = project.get("title", "")
            if not title:
                continue
            self._add(
                QuestionCategory.PROJECT_OVERVIEW,
                None,
                project_grounding(project),
                source_type=SourceType.PROJECT,
                source_id=title,
                source_field="summary",
                reason=f"projects[title={title!r}].summary/technologies",
                priority_boost=touches_weakness(title),
            )

        # ── Priority 3: experience ────────────────────────────────────────
        for exp in experiences:
            role = exp.get("role", "")
            if not role:
                continue
            company = exp.get("company", "")
            label = f"{role} at {company}" if company else role
            self._add(
                QuestionCategory.EXPERIENCE,
                None,
                experience_grounding(exp),
                source_type=SourceType.EXPERIENCE,
                source_id=label,
                source_field="description",
                reason=f"experience[role={role!r}].description",
            )

        # ── Priority 4: certifications ────────────────────────────────────
        for cert in certifications:
            name = cert.get("name", "") if isinstance(cert, dict) else str(cert)
            if not name:
                continue
            self._add(
                QuestionCategory.CERTIFICATION,
                None,
                Grounding(certification=CertificationGrounding(name=name)),
                source_type=SourceType.CERTIFICATION,
                source_id=name,
                source_field="name",
                reason=f"certifications[name={name!r}]",
            )

        # ── Priority 5: skills, only in the context of where they were used ─
        for topic_entry in blueprint.get("technical_topics", []) or []:
            topic_entry = _as_dict(topic_entry) if not isinstance(topic_entry, dict) else topic_entry
            topic = topic_entry.get("topic", "")
            if not topic:
                continue
            origin_project = topic_entry.get("originating_project", "")
            origin_experience = topic_entry.get("originating_experience", "")
            evidence = topic_entry.get("evidence", "")

            check = validate_technical_topic_origin(
                origin_project, origin_experience, projects, experiences
            )
            if not check.ok:
                self.rejected.append(
                    RejectedTopic(
                        topic=topic,
                        originating_project=origin_project,
                        originating_experience=origin_experience,
                        reason=check.reason,
                    )
                )
                logger.info(
                    "Rejected untraceable technical_topic %r (originating_project=%r, "
                    "originating_experience=%r): %s",
                    topic, origin_project, origin_experience, check.reason,
                )
                continue

            if origin_project.strip():
                matched_project = find_project_by_title(origin_project, projects)
                title = matched_project.get("title", "")
                self._add(
                    QuestionCategory.SKILL_IN_CONTEXT,
                    topic,
                    project_grounding(matched_project),
                    source_type=SourceType.PROJECT,
                    source_id=title,
                    source_field="technical_topics",
                    reason=f"technical_topics: {topic!r} (evidence: {evidence!r})",
                    priority_boost=touches_weakness(topic) or touches_weakness(title),
                )
            else:
                matched_experience = find_experience_by_label(origin_experience, experiences)
                role = matched_experience.get("role", "")
                company = matched_experience.get("company", "")
                label = f"{role} at {company}" if company else role
                self._add(
                    QuestionCategory.SKILL_IN_CONTEXT,
                    topic,
                    experience_grounding(matched_experience),
                    source_type=SourceType.EXPERIENCE,
                    source_id=label,
                    source_field="technical_topics",
                    reason=f"technical_topics: {topic!r} (evidence: {evidence!r})",
                    priority_boost=touches_weakness(topic),
                )

    # ── Coverage / status introspection ─────────────────────────────────

    def categories_present(self) -> frozenset[QuestionCategory]:
        return self.coverage.present()

    def categories_covered(self) -> frozenset[QuestionCategory]:
        return self.coverage.covered()

    def all_categories_covered(self) -> bool:
        return self.coverage.all_covered()

    def get(self, unit_id: str) -> Optional[QuestionSpecification]:
        return self.specifications.get(unit_id)

    def lifecycle_of(self, unit_id: str) -> Optional[UnitLifecycleState]:
        return self.lifecycle.get(unit_id)

    def remaining(self) -> int:
        return sum(
            1 for state in self.lifecycle.values() if state.status == UnitStatus.UNASKED
        )

    # ── Lifecycle transitions (Chapter 11.4, hardened — Phase 1.5, Task 2) ─
    # Phase 1 exposes these so a caller can drive the status machine; Phase
    # 1 itself does not decide WHEN to call them (that is the Adaptive
    # Controller's job, Chapter 18, out of scope here). Every method below
    # is the ONLY way to change a unit's lifecycle state — it always
    # updates `UnitLifecycleState` (via its underscore-prefixed, non-public
    # mutators) AND `CoverageTracker` together, in one call, so the two can
    # never be observed inconsistent (see `InvalidLifecycleTransitionError`
    # for the full invariant statement).

    def mark_active(self, unit_id: str) -> None:
        state = self._require_state(unit_id)
        state._transition(UnitStatus.ACTIVE)
        self.coverage.mark_covered(self.specifications[unit_id].category)

    def mark_covered(self, unit_id: str) -> None:
        state = self._require_state(unit_id)
        state._transition(UnitStatus.COVERED)
        self.coverage.mark_covered(self.specifications[unit_id].category)

    def mark_skipped(self, unit_id: str) -> None:
        state = self._require_state(unit_id)
        state._transition(UnitStatus.SKIPPED)
        self.coverage.mark_covered(self.specifications[unit_id].category)

    def mark_followup_used(self, unit_id: str) -> None:
        """Record that a follow-up was asked on this unit. Only valid while
        the unit is ACTIVE — a follow-up on a unit that isn't the current
        turn's active unit would be a caller bug, not a legitimate case."""
        state = self._require_state(unit_id)
        if state.status is not UnitStatus.ACTIVE:
            raise InvalidLifecycleTransitionError(
                f"cannot record a follow-up on unit {unit_id!r} with status "
                f"{state.status.value!r} — follow-ups only apply to the "
                "currently ACTIVE unit"
            )
        state._increment_followups()

    def set_style_used(self, unit_id: str, style: Optional[str]) -> None:
        """Record which phrasing style/angle was used for this unit's most
        recent turn — Question Realizer bookkeeping (Chapter 12), tracked
        here only so it has a single, hardened home rather than living as a
        loose mutable field on an ad hoc dict."""
        state = self._require_state(unit_id)
        state._set_style(style)

    def _require_state(self, unit_id: str) -> UnitLifecycleState:
        state = self.lifecycle.get(unit_id)
        if state is None:
            raise KeyError(f"No unit with id {unit_id!r} in this pool")
        return state

    # ── Selection (Chapter 10.3) ─────────────────────────────────────────

    def select_next(
        self, last_category: Optional[QuestionCategory]
    ) -> Optional[QuestionSpecification]:
        """
        Pick the highest-priority `unasked` unit. Dominant factor: tier
        weight (project_deep_dive > project_overview > experience >
        certification > skill_in_context). Override: a category untouched
        this session gets a large coverage-sweep bonus, so one project's
        many interview_seeds can't consume the whole session before
        experience/certifications are ever reached. Ties broken by: weak-
        area boost, category diversity against the immediately preceding
        turn, then deterministic build order (see module docstring's
        determinism note — no random component, unlike the legacy
        `discussion_engine.TopicPool`).

        Does not mutate any state — selecting a unit does not, by itself,
        advance its lifecycle status; call `mark_active`/`mark_covered`/
        `mark_skipped` explicitly once a caller decides what to do with the
        selection (Phase 1 scope: planning only, no decision policy).
        """
        candidates = [
            unit_id
            for unit_id, state in self.lifecycle.items()
            if state.status == UnitStatus.UNASKED
        ]
        if not candidates:
            logger.info("[TopicPool] select_next: pool exhausted, no unasked units remain.")
            return None

        covered_categories = self.categories_covered()
        build_index = {unit_id: i for i, unit_id in enumerate(self._build_order)}

        def score_key(unit_id: str) -> tuple:
            spec = self.specifications[unit_id]
            tier = CATEGORY_PRIORITY.get(spec.category, 0) * 10.0
            coverage_bonus = 100.0 if spec.category not in covered_categories else 0.0
            weakness_bonus = 2.0 if spec.priority_boost else 0.0
            diversity_bonus = (
                1.0 if last_category is not None and spec.category != last_category else 0.0
            )
            total = tier + coverage_bonus + weakness_bonus + diversity_bonus
            # Negate build_index so that, for equal scores, the earliest-
            # built unit sorts first when we take max() below (deterministic
            # tie-break — see module docstring).
            return (total, -build_index[unit_id])

        chosen_id = max(candidates, key=score_key)
        chosen = self.specifications[chosen_id]

        logger.info(
            "[TopicPool] SELECTED: id=%s category=%s source_type=%s source_id=%r "
            "source_field=%s reason=%s",
            chosen.id, chosen.category.value, chosen.source_type.value,
            chosen.source_id, chosen.source_field, chosen.reason,
        )
        return chosen
