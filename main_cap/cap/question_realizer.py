"""
Question Realizer — Phase 2 of ResumeDiscussion_v2 (Chapter 12).

Consumes ONLY a QuestionSpecification, ConversationMemory, and (for
follow-ups) an explicit angle/focus hint, and produces an InterviewQuestion.
It NEVER decides what to ask — that is the Planner's job (Chapter 10),
completely untouched here. Its only responsibility is phrasing: choosing a
family (via discussion_policy.py), choosing a non-repeating phrasing
variant within that family (deterministically — no `random`), choosing a
transition, and assembling the final `InterviewQuestion`.

This module is a pure function with respect to state: `realize()` and
`realize_followup()` never mutate `ConversationMemory` themselves — the
caller is responsible for calling `ConversationMemory.record_turn(...)`
after presenting the question, mirroring how `Planner.plan_next()` is
read-only and `Planner.advance()` is the explicit follow-up call (Chapter 9,
Phase 1's Planner/TopicPool split of read vs. mutate).

DETERMINISM (Phase 2, Section 4): every choice this module makes — family,
phrasing variant, transition, follow-up angle — is a pure function of the
QuestionSpecification's own id, its content, and ConversationMemory's
recorded history. No `random` module anywhere in this file. Variant
selection uses `zlib.crc32`, NOT Python's built-in `hash()` — `hash()` on
strings is salted per-process (PYTHONHASHSEED) and would make the exact
same session replay produce different wording on a different run, which
would violate Section 4's "same interview replay should always produce
identical output."
"""

from __future__ import annotations

import zlib
from typing import Optional

import discussion_policy
from conversation_memory import ConversationMemory
from interview_question import InterviewQuestion
from question_families import PhrasingContext, ReasoningType, get_family
from question_specification import QuestionSpecification, SourceType


def _stable_index(*parts: str, modulus: int) -> int:
    """A deterministic, process-independent index derived from `parts` —
    unlike `hash()`, `zlib.crc32` is not salted, so this produces the same
    value every run, on every machine, forever (the exact guarantee Section
    4's "same replay -> identical output" requirement needs)."""
    if modulus <= 0:
        return 0
    digest = zlib.crc32("::".join(parts).encode("utf-8"))
    return digest % modulus


def _build_context(spec: QuestionSpecification) -> PhrasingContext:
    grounding = spec.grounding
    if grounding.project is not None:
        return PhrasingContext(
            category=spec.category, text_seed=spec.text_seed,
            title=grounding.project.title, technologies=grounding.project.technologies,
            role="", company="", certification_name="", source_id=spec.source_id,
        )
    if grounding.experience is not None:
        return PhrasingContext(
            category=spec.category, text_seed=spec.text_seed,
            title="", technologies=(), role=grounding.experience.role,
            company=grounding.experience.company, certification_name="",
            source_id=spec.source_id,
        )
    return PhrasingContext(
        category=spec.category, text_seed=spec.text_seed,
        title="", technologies=(), role="", company="",
        certification_name=grounding.certification.name, source_id=spec.source_id,
    )


def _project_reference(spec: QuestionSpecification) -> Optional[str]:
    return spec.grounding.project.title if spec.grounding.project is not None else None


def _select_variant_index(spec: QuestionSpecification, family: str, variant_count: int,
                           memory: ConversationMemory) -> int:
    """Deterministic base index from (spec id, family), flipped to the
    other variant if it would exactly repeat the immediately preceding
    phrasing style — the Phase 1 pattern (Chapter 12.4's style rotation),
    applied at the variant level instead of the family level."""
    idx = _stable_index(spec.id, family, modulus=variant_count)
    if memory.last_phrasing_style() == (family, idx) and variant_count > 1:
        idx = (idx + 1) % variant_count
    return idx


def _render(spec: QuestionSpecification, family: str, memory: ConversationMemory) -> tuple[str, int]:
    definition = get_family(family)
    ctx = _build_context(spec)
    variant_idx = _select_variant_index(spec, family, len(definition.phrasing_variants), memory)
    text = definition.phrasing_variants[variant_idx](ctx)
    return text, variant_idx


def realize(spec: QuestionSpecification, memory: ConversationMemory, turn_number: int) -> InterviewQuestion:
    """Realize a fresh (non-follow-up) turn for `spec`. Returns the
    InterviewQuestion; the caller must call `memory.record_turn(question,
    variant_index)` afterward — this function does not mutate memory."""
    family = discussion_policy.select_family(spec, memory)
    text, variant_idx = _render(spec, family, memory)
    transition = discussion_policy.select_transition(spec, memory)
    full_text = f"{transition}{text}" if transition else text

    question = InterviewQuestion(
        question_text=full_text,
        transition_text=transition,
        specification=spec,
        family=family,
        reasoning_type=get_family(family).reasoning_type,
        project_reference=_project_reference(spec),
        is_followup=False,
        turn_number=turn_number,
        metadata=(
            ("category", spec.category.value),
            ("source_type", spec.source_type.value),
            ("source_id", spec.source_id),
        ),
    )
    return question, variant_idx


# ═════════════════════════════════════════════════════════════════════════════
# Follow-up infrastructure (Chapter 17 / Phase 2, Section 7)
# ═════════════════════════════════════════════════════════════════════════════
#
# INFRASTRUCTURE ONLY: this module never decides WHEN a follow-up should
# happen — that decision requires evaluating the candidate's answer, which
# is the Adaptive Controller's job (Chapter 18), explicitly out of scope
# for Phase 2. `realize_followup` is a pure function a later phase calls
# once it has already decided a follow-up is warranted; nothing in Phase 2's
# own conversation loop calls it automatically.

_FOLLOWUP_ANGLE_FAMILY = {
    # Angles that map directly onto an existing registered family (Section
    # 7's list overlaps heavily with question_families.py's families).
    "tradeoff_probing": "tradeoffs",
    "design_justification": "decision_making",
    "debugging_decisions": "debugging",
    "ownership": "ownership",
    "reflection": "reflection",
}

_FOLLOWUP_TEMPLATES: dict[str, tuple] = {
    # Angles with no direct family equivalent get their own tiny templates,
    # grounded ONLY in the specification's own text_seed/source_id — never
    # an invented detail (Chapter 17: "never invented").
    "clarification": (
        lambda ctx, focus: f"Could you clarify what you mean by {focus}?",
        lambda ctx, focus: f"When you say {focus}, what exactly does that involve?",
    ),
    "more_detail": (
        lambda ctx, focus: f"Can you go a bit deeper on {focus}?",
        lambda ctx, focus: f"What more can you tell me about {focus}?",
    ),
    "alternative_approaches": (
        lambda ctx, focus: f"Was there another way you could have approached {focus}?",
        lambda ctx, focus: f"What's an alternative you considered for {focus}, and why didn't you use it?",
    ),
}

FOLLOWUP_ANGLES: tuple[str, ...] = tuple(sorted(
    set(_FOLLOWUP_ANGLE_FAMILY) | set(_FOLLOWUP_TEMPLATES)
))


def _followup_focus(spec: QuestionSpecification, focus_hint: Optional[str]) -> str:
    """The subject a follow-up is actually about — Phase 3's evaluator hint
    if supplied, otherwise the current specification's own seed/subject,
    never invented (Chapter 17)."""
    if focus_hint:
        return focus_hint
    if spec.text_seed:
        return spec.text_seed.rstrip("?.").strip()
    return "that part of your work"


def select_followup_angle(spec: QuestionSpecification, memory: ConversationMemory,
                           followups_used_on_this_spec: int) -> str:
    """Deterministically pick a follow-up angle, rotating so consecutive
    follow-ups on the same spec don't repeat an angle, and preferring one
    not used in the immediately preceding turn overall."""
    idx = _stable_index(spec.id, str(followups_used_on_this_spec), modulus=len(FOLLOWUP_ANGLES))
    angle = FOLLOWUP_ANGLES[idx]
    if angle == memory.last_family():
        angle = FOLLOWUP_ANGLES[(idx + 1) % len(FOLLOWUP_ANGLES)]
    return angle


def realize_followup(
    spec: QuestionSpecification,
    memory: ConversationMemory,
    turn_number: int,
    followups_used_on_this_spec: int = 0,
    angle: Optional[str] = None,
    focus_hint: Optional[str] = None,
) -> tuple[InterviewQuestion, int]:
    """Realize a follow-up turn for `spec`, staying on the SAME unit
    (Chapter 17: a follow-up is a continuation, not a new topic — the
    caller keeps using the same `spec`, there is no new specification)."""
    chosen_angle = angle or select_followup_angle(spec, memory, followups_used_on_this_spec)
    focus = _followup_focus(spec, focus_hint)
    ctx = _build_context(spec)

    if chosen_angle in _FOLLOWUP_ANGLE_FAMILY:
        family = _FOLLOWUP_ANGLE_FAMILY[chosen_angle]
        text, variant_idx = _render(spec, family, memory)
        reasoning_type = get_family(family).reasoning_type
    else:
        variants = _FOLLOWUP_TEMPLATES[chosen_angle]
        variant_idx = _stable_index(spec.id, chosen_angle, modulus=len(variants))
        text = variants[variant_idx](ctx, focus)
        # Follow-up-only angles don't map to a registered family; Recall is
        # the neutral default reasoning type for a plain clarifying ask.
        reasoning_type = ReasoningType.RECALL

    transition = ""  # a follow-up continues the same topic — no transition needed
    question = InterviewQuestion(
        question_text=text,
        transition_text=transition,
        specification=spec,
        family=chosen_angle,
        reasoning_type=reasoning_type,
        project_reference=_project_reference(spec),
        is_followup=True,
        turn_number=turn_number,
        metadata=(
            ("category", spec.category.value),
            ("source_type", spec.source_type.value),
            ("source_id", spec.source_id),
            ("followup_angle", chosen_angle),
        ),
    )
    return question, variant_idx
