"""
Discussion Policy — Phase 2 of ResumeDiscussion_v2 (Chapter 12, Sections 6+8
of the Phase 2 task).

Two responsibilities, both purely about HOW a turn is framed, never WHAT is
asked next (that remains the Planner's job, untouched — Chapter 10):

    1. `select_family` — which phrasing angle (question_families.py) best
       continues a natural, non-abrupt narrative for the project/experience/
       certification this specification is grounded in.
    2. `select_transition` — a short conversational bridge from the previous
       turn to this one ("Now let's move on to another project...") instead
       of a bare "Next question."

ARCHITECTURE NOTE — read before changing anything here: Chapter 10.3's
approved priority table ranks `project_deep_dive` (tier 5) ABOVE
`project_overview` (tier 4), so the Planner may hand this policy a deep-dive
specification as the very FIRST turn touching a given project — before any
"overview" specification for that project has been asked. The natural
conversation arc this module implements (Section 6: overview before
architecture before implementation before ...) is achieved WITHOUT
reordering anything the Planner produces: `select_family` special-cases the
very first turn on any source_id to use the "overview" family regardless of
which specification tier the Planner actually handed over, so the
CONVERSATION sounds like it opens with an overview even when the underlying
specification is technically a deep-dive one. This was a deliberate,
flagged resolution (see the Phase 2 completion report) to a genuine tension
between the approved Planner ordering and this phase's natural-flow
requirement — it does not touch, reorder, or reinterpret the Planner itself.
"""

from __future__ import annotations

from conversation_memory import ConversationMemory
from question_families import families_for_category
from question_specification import QuestionCategory, QuestionSpecification

# The natural per-category narrative arc (Section 6): as a source_id (one
# project/experience/certification) is touched more times, the conversation
# progresses through these families in order. Every name here must be a
# real registered family applicable to that category — enforced by a test
# (test_discussion_policy.py) rather than at import time, so a future family
# addition/removal surfaces as a clear test failure, not a silent KeyError
# deep in a live session.
_ARC: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.PROJECT_OVERVIEW: (
        "overview", "architecture", "ownership", "decision_making",
        "lessons_learned", "future_improvements",
    ),
    QuestionCategory.PROJECT_DEEP_DIVE: (
        "implementation", "architecture", "tradeoffs", "decision_making",
        "debugging", "optimization", "testing", "deployment", "scaling",
        "failures", "reflection",
    ),
    QuestionCategory.EXPERIENCE: (
        "responsibilities", "team_collaboration", "ownership",
        "lessons_learned", "reflection", "failures",
    ),
    QuestionCategory.CERTIFICATION: (
        "motivation", "application",
    ),
    QuestionCategory.SKILL_IN_CONTEXT: (
        "decision_making", "implementation", "tradeoffs",
    ),
}

# Transition phrases, keyed by the relationship between this turn's topic
# and the previous turn's topic. Two variants each (Section 9: no repeated
# transitions) — rotation is handled by `select_transition` via
# ConversationMemory, not baked into ordering here.
_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "same_topic": (
        "Let's stay on this for a moment — ",
        "Sticking with this a little longer — ",
    ),
    "new_project": (
        "Now let's move on to another project. ",
        "Shifting gears to a different project — ",
    ),
    "returning_project": (
        "Let's go back to this project for a moment — ",
        "Coming back to this project — ",
    ),
    "new_experience": (
        "I'd like to talk about your work experience. ",
        "Let's move on to your professional experience — ",
    ),
    "new_certification": (
        "I'd like to ask about one of your certifications. ",
        "Let's touch on a certification you hold — ",
    ),
}


def select_family(spec: QuestionSpecification, memory: ConversationMemory) -> str:
    """
    Choose the phrasing family for `spec`, given how many times its
    source_id has already been touched this session and which family was
    used most recently (any topic) — deterministic, no randomness.
    """
    arc = _ARC[spec.category]
    overall_touch_index = memory.times_source_touched(spec.source_id)
    # The arc position within THIS category, independent of how many turns
    # of OTHER categories already happened for the same source_id (a
    # project's overview/deep-dive/skill_in_context specs all share one
    # source_id but each has its own, differently-sized arc — see
    # ConversationMemory.times_source_category_touched's docstring).
    category_touch_index = memory.times_source_category_touched(spec.source_id, spec.category.value)

    if overall_touch_index == 0 and spec.category == QuestionCategory.PROJECT_DEEP_DIVE:
        # See this module's docstring: the very first turn on a project
        # always opens with "overview" framing, regardless of tier.
        candidate = "overview"
    else:
        # Cycle through the arc (modulo, not clamped) so a long tail of
        # turns in one category keeps varying instead of getting stuck
        # oscillating on the arc's last one or two entries.
        candidate = arc[category_touch_index % len(arc)]
        if candidate == "overview" and memory.family_already_used_for_source(spec.source_id, "overview"):
            # This project already got its "overview" framing from an
            # earlier category (e.g. a project_deep_dive spec opened it) —
            # don't re-open the same project a second time.
            candidate = arc[(category_touch_index + 1) % len(arc)]

    if candidate == memory.last_family():
        # Never repeat the immediately preceding family (Section 9) — step
        # forward in the arc instead of standing still.
        idx = arc.index(candidate) if candidate in arc else 0
        candidate = arc[(idx + 1) % len(arc)]

    applicable = families_for_category(spec.category)
    if candidate not in applicable:
        # Defensive fallback — should never trigger if _ARC and the family
        # registry are kept consistent (verified by
        # test_discussion_policy.py), but a silent KeyError deep in a live
        # session would be far worse than a documented fallback here.
        candidate = applicable[0]
    return candidate


def select_transition(spec: QuestionSpecification, memory: ConversationMemory) -> str:
    """Choose a transition phrase bridging the previous turn to this one —
    empty string for the very first question of a session, since there is
    nothing to transition from."""
    if memory.turn_count() == 0:
        return ""

    if memory.last_source_id() == spec.source_id:
        key = "same_topic"
    elif spec.category == QuestionCategory.CERTIFICATION:
        key = "new_certification"
    elif spec.category == QuestionCategory.EXPERIENCE:
        key = "new_experience"
    elif memory.times_source_touched(spec.source_id) > 0:
        # This project/experience/certification already came up earlier in
        # the session (just not on the immediately preceding turn) — say so
        # honestly instead of calling it "another" topic.
        key = "returning_project"
    else:
        key = "new_project"

    variants = _TRANSITIONS[key]
    for variant in variants:
        if not memory.is_transition_recently_used(variant):
            return variant
    # All variants recently used (only possible with a very short recency
    # window and rapid same-key transitions) — fall back to the first
    # rather than raise; a slightly-reused transition is a minor cosmetic
    # issue, not a correctness one.
    return variants[0]
