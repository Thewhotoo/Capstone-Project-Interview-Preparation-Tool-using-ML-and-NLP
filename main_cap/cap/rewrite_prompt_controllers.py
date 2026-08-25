"""
Rewrite Prompt Controllers — Experiment 4 (Rewrite Augmentation) Stage.

Mirrors `prompt_controllers.py`'s shape (small, pure, one controller per
function, wired together only in the corresponding assembler) but for a
fundamentally different input: an already-generated, already-labeled
`TrainingExample` plus an explicit style tag — never a `GenerationRecipe`.
A rewrite has no new concept/reasoning targets to sample; it inherits every
one of them from the source example's own `synthetic` block, which is
already-serialized, already-validated data (the same "never invented"
evidence discipline this whole pipeline already enforces).

Reuses `prompt_controllers.PromptSection` unchanged — the assembled-section
shape doesn't need to change for a different input type, only the
controller functions that produce it.

Kept in its own module, independent of `prompt_controllers.py`, per the
project's "deliberate independence between pipeline stages" precedent
(`generation_validation.py`'s duplicated marker tables,
`dataset_relabeling.py`'s duplicated lookup tables) — a future prompt
revision to EITHER pipeline never risks touching the other.
"""

from __future__ import annotations

from evaluation_result import ConceptObservationStatus
from prompt_controllers import PromptSection
from training_example import TrainingExample

# ═════════════════════════════════════════════════════════════════════════════
# The closed, explicit style-tag vocabulary (design Section "Rewrite Design",
# approved this session). Style is ALWAYS an explicit caller-supplied
# parameter — never derived from `style_seed` or any other per-example seed
# (explicit user decision this session: keeps style selection a pipeline
# parameter, not an implicit deterministic side effect).
# ═════════════════════════════════════════════════════════════════════════════

STYLE_TAGS: tuple[str, ...] = (
    "concise", "verbose", "conversational", "interview_like",
    "highly_structured", "reflective", "confident", "cautious",
)

_STYLE_INSTRUCTIONS: dict[str, str] = {
    "concise": (
        "Rewrite CONCISELY: shorter overall, trim any redundant or filler phrasing, "
        "get to the point quickly. Every fact, concept mention/omission, and "
        "contradiction from the original must still be present — cut wording, never content."
    ),
    "verbose": (
        "Rewrite VERBOSELY: more elaborated phrasing, more connective/explanatory "
        "language between points. Do not add any NEW fact, concept, or claim that "
        "wasn't in the original — elaborate on how it's said, not what is said."
    ),
    "conversational": (
        "Rewrite CONVERSATIONALLY: casual, spoken-register phrasing, as if talking "
        "informally rather than presenting formally. Same content, looser delivery."
    ),
    "interview_like": (
        "Rewrite in a natural INTERVIEW-ANSWER register: as if responding out loud "
        "to an interviewer, with the natural rhythm of a spoken answer (brief framing, "
        "then substance) rather than written prose."
    ),
    "highly_structured": (
        "Rewrite with a HIGHLY STRUCTURED delivery: clear logical ordering, signposted "
        "transitions (e.g. 'first... then... finally...'), as if organizing the answer "
        "deliberately for clarity."
    ),
    "reflective": (
        "Rewrite REFLECTIVELY: more personal, retrospective framing — describing not just "
        "what was done but a brief sense of how it was experienced or what was learned — "
        "without inventing any new fact or outcome not already in the original."
    ),
    "confident": (
        "Rewrite with a CONFIDENT tone: assertive, matter-of-fact phrasing, independent of "
        "how correct or complete the underlying content actually is. Do not upgrade weak "
        "or omitted content into strong content — only the DELIVERY becomes more confident."
    ),
    "cautious": (
        "Rewrite with a CAUTIOUS tone: more hedged, qualified phrasing ('I think', 'as far "
        "as I recall'), independent of how correct or complete the underlying content "
        "actually is. Do not downgrade strong content into weak content — only the "
        "DELIVERY becomes more cautious."
    ),
}


def _require_known_style(style: str) -> None:
    if style not in _STYLE_INSTRUCTIONS:
        raise ValueError(f"unknown rewrite style {style!r}; must be one of {STYLE_TAGS}")


# ═════════════════════════════════════════════════════════════════════════════
# System Prompt Controller (invariant)
# ═════════════════════════════════════════════════════════════════════════════


def rewrite_system_prompt_controller() -> PromptSection:
    """The rewrite role/preservation contract — identical on every call.
    Structurally mirrors `prompt_controllers.system_prompt_controller`'s
    role, but the content is a rewrite contract, not a generation contract:
    nothing new may be introduced, nothing existing may be dropped, only
    HOW it is said may change."""
    content = (
        "You are rewriting an existing first-person interview answer to change its "
        "communication style ONLY. You must preserve, exactly: every factual claim, "
        "every technology or concept mentioned, every concept deliberately left "
        "unmentioned (do not introduce it), every deliberate contradiction if one is "
        "present, and the overall level of technical depth and ownership already in "
        "the answer. You must NEVER invent a new fact, technology, concept, metric, or "
        "claim that was not in the original, and you must NEVER strengthen or weaken "
        "the underlying technical content — only its delivery. Respond with ONLY the "
        "rewritten answer text plus the requested structured fields — no "
        "meta-commentary, no restating the instructions."
    )
    return PromptSection(controller="rewrite_system_prompt", invariant=True, content=content)


# ═════════════════════════════════════════════════════════════════════════════
# Source Context Controller (variable) — the original answer + what must
# survive the rewrite, read entirely from the source TrainingExample's own
# already-serialized fields (never invented).
# ═════════════════════════════════════════════════════════════════════════════


def rewrite_source_controller(source_example: TrainingExample, style: str) -> PromptSection:
    lines = [
        f"Original answer to rewrite:\n{source_example.inputs.answer_text}",
    ]
    synthetic = source_example.synthetic
    if synthetic is not None and synthetic.intended_concept_inclusion:
        lines.append("Every concept below must keep the SAME status in your rewrite:")
        for target in synthetic.intended_concept_inclusion:
            if target.status == ConceptObservationStatus.OMITTED:
                instruction = "must remain UNMENTIONED — do not introduce it, not even as a paraphrase"
            elif target.status == ConceptObservationStatus.DEMONSTRATED:
                instruction = "must remain addressed with genuine functional explanation, and you must supply evidence for it"
            else:
                instruction = "must remain a brief mention only (no functional tie-in), and you must supply evidence for it"
            lines.append(f"- {target.concept}: {instruction}.")
    if synthetic is not None and synthetic.is_contradictory:
        lines.append(
            "The original contains exactly one deliberate contradiction — your rewrite "
            "must still contain that same contradiction (reworded is fine, removed is not). "
            "Report it in contradiction_note as the original did."
        )
    return PromptSection(controller="rewrite_source", invariant=False, content="\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# Style Instruction Controller (variable) — the ONLY axis a rewrite is
# allowed to move (design Section "Rewrite Design").
# ═════════════════════════════════════════════════════════════════════════════


def rewrite_style_instruction_controller(source_example: TrainingExample, style: str) -> PromptSection:
    _require_known_style(style)
    return PromptSection(controller="rewrite_style_instruction", invariant=False, content=_STYLE_INSTRUCTIONS[style])
