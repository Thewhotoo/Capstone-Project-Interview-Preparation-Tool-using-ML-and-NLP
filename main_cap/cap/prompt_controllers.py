"""
Prompt Controllers — Stage A Synthetic Dataset Generation Pipeline
(Synthetic Dataset Generation Promptbook RFC, Section 2 — APPROVED AND
FROZEN). Implemented exactly as specified.

Each controller is a small, pure function: `GenerationRecipe -> PromptSection
| None`. Every controller lives in its own function so a future prompt
version can replace ONE controller's implementation without touching the
others (Implementation requirement: "keep the implementation modular so
future prompt versions can be added without modifying existing ones") —
`prompt_assembler.py` is what wires a specific SET of controllers together
into a versioned pipeline; this module never hardcodes that wiring itself.

Controller responsibilities (Promptbook Section 2's table, restated as
code):
    system_prompt_controller          invariant — role/grounding/output contract
    generation_prompt_controller      variable  — this turn's question/grounding/expected concepts
    quality_tier_controller           variable  — behavioral target for intended_quality_tier
    reasoning_category_controller     variable  — per-category present/absent+severity targets
    expected_concept_controller       variable  — per-concept demonstrated/superficial/omitted targets
    contradiction_controller          variable, usually inactive
    off_topic_controller              variable, usually inactive, OVERRIDES the two above when active
    diversity_controller              variable  — stylistic variance across a batch
    style_controller                 variable  — internal voice consistency within one answer

No prompt text is hardcoded anywhere else in the codebase — every caller
that needs generation instructions goes through `prompt_assembler.py`,
which in turn calls only these functions.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation_result import ConceptObservationStatus
from generation_recipe import GenerationRecipe
from question_specification import QuestionSpecification


@dataclass(frozen=True)
class PromptSection:
    """One controller's output. `invariant=True` sections are assembled into
    the system prompt; `invariant=False` sections are assembled into the
    per-call user/generation prompt (Promptbook Section 2's invariant/
    variable split)."""

    controller: str
    invariant: bool
    content: str


# ═════════════════════════════════════════════════════════════════════════════
# System Prompt Controller (invariant)
# ═════════════════════════════════════════════════════════════════════════════


def system_prompt_controller() -> PromptSection:
    """The role/grounding-fidelity/output-format contract — identical on
    every call (Promptbook Section 2). Implements the grounding protocol's
    elaboration-vs-invention distinction (Section 7) as the generator's
    standing instruction, not a per-call variable."""
    content = (
        "You are generating a single, first-person interview answer as if spoken by "
        "the candidate described in the supplied grounding. You must never invent a "
        "project, technology, company, responsibility, metric, or achievement that is "
        "not present in — or a direct, plausible elaboration of — the supplied "
        "grounding. Plausible elaboration (describing HOW or WHY something already "
        "stated might have worked) is expected and required for a realistic answer; "
        "introducing a NEW, specific, checkable fact (a name, a number, an entity) "
        "that is not implied by the grounding is forbidden. Respond with ONLY the "
        "answer text itself — no meta-commentary, no restating the question, no "
        "labels or headers."
    )
    return PromptSection(controller="system_prompt", invariant=True, content=content)


# ═════════════════════════════════════════════════════════════════════════════
# Generation Prompt Controller (variable — shape fixed, content per-unit)
# ═════════════════════════════════════════════════════════════════════════════


def _grounding_description(specification: QuestionSpecification) -> str:
    grounding = specification.grounding
    if grounding.project is not None:
        p = grounding.project
        parts = [f"Project: {p.title}."]
        if p.summary:
            parts.append(f"Summary: {p.summary}.")
        if p.technologies:
            parts.append(f"Technologies: {', '.join(p.technologies)}.")
        if p.concepts:
            parts.append(f"Concepts demonstrated: {', '.join(p.concepts)}.")
        return " ".join(parts)
    if grounding.experience is not None:
        e = grounding.experience
        parts = [f"Role: {e.role} at {e.company}." if e.company else f"Role: {e.role}."]
        if e.duration:
            parts.append(f"Duration: {e.duration}.")
        if e.summary:
            parts.append(f"Summary: {e.summary}.")
        return " ".join(parts)
    return f"Certification: {grounding.certification.name}."


def generation_prompt_controller(recipe: GenerationRecipe) -> PromptSection:
    """This turn's question + structured grounding + expected concepts —
    same shape every call, different content per unit (Promptbook Section
    2)."""
    lines = [
        f"Question: {recipe.question_text}",
        f"Grounding (the ONLY facts you may reference): {_grounding_description(recipe.specification)}",
    ]
    if recipe.expected_concepts:
        lines.append(f"Concepts potentially relevant to this question: {', '.join(recipe.expected_concepts)}")
    return PromptSection(controller="generation_prompt", invariant=False, content="\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# Quality-Tier Controller (variable)
# ═════════════════════════════════════════════════════════════════════════════

_TIER_BEHAVIOR = {
    "excellent": (
        "Produce an EXCELLENT answer: strong command across most relevant dimensions, "
        "specific and concrete detail tied to the grounding (never generic), clear "
        "first-person ownership language, coherent logical structure, and technical "
        "vocabulary used correctly and precisely."
    ),
    "good": (
        "Produce a GOOD answer: solid and correct, but not exhaustive — one or two "
        "areas may be present but shallow."
    ),
    "adequate": (
        "Produce an ADEQUATE answer: correct but shallow and somewhat generic across "
        "most dimensions."
    ),
    "weak": (
        "Produce a WEAK answer: vague, with several omissions; communication may be "
        "somewhat disorganized."
    ),
    "poor": (
        "Produce a POOR answer: very short, minimal engagement; may lack first-person "
        "ownership language entirely."
    ),
}


def quality_tier_controller(recipe: GenerationRecipe) -> PromptSection:
    """Behavioral target for `intended_quality_tier`, reusing the exact
    5-band rubric already approved (Dataset Design RFC Section 4) — no new
    quality vocabulary invented here. A no-op for off_topic/contradictory
    tiers, which are governed entirely by their own controllers instead."""
    tier = recipe.quality_tier.value
    behavior = _TIER_BEHAVIOR.get(tier)
    if behavior is None:
        # off_topic / contradictory: quality is governed by the Off-Topic /
        # Contradiction controllers, not this one.
        behavior = _TIER_BEHAVIOR["good"] if tier == "contradictory" else ""
        if not behavior:
            return PromptSection(controller="quality_tier", invariant=False, content="")
    return PromptSection(controller="quality_tier", invariant=False, content=behavior)


# ═════════════════════════════════════════════════════════════════════════════
# Reasoning-Category Controller (variable)
# ═════════════════════════════════════════════════════════════════════════════

_SEVERITY_LABEL_BOUNDS = ((0.34, "minor"), (0.67, "moderate"), (1.01, "major"))


def _severity_label(severity: float) -> str:
    for bound, label in _SEVERITY_LABEL_BOUNDS:
        if severity < bound:
            return label
    return "major"


def reasoning_category_controller(recipe: GenerationRecipe) -> PromptSection:
    """Per-category present/absent+severity targets (Promptbook Section 6).
    Only categories targeted `present=True` get an explicit omission
    instruction; absent targets get NO instruction at all — forcing
    inclusion produces artificial, checklist-style prose (Promptbook
    Section 6's core design principle)."""
    present_targets = [t for t in recipe.reasoning_targets if t.present]
    if not present_targets:
        return PromptSection(controller="reasoning_category", invariant=False, content="")
    lines = ["Deliberately, naturally under-develop the following, at the stated severity:"]
    for t in present_targets:
        label = t.category.replace("_", " ")
        lines.append(
            f"- {label} ({_severity_label(t.severity)}): do not name, weigh, or resolve this — "
            f"redirect the answer's focus toward whatever content IS targeted for inclusion "
            f"instead of toward this gap. Never produce a deliberately truncated or obviously "
            f"evasive response to achieve this."
        )
    return PromptSection(controller="reasoning_category", invariant=False, content="\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# Expected-Concept Controller (variable)
# ═════════════════════════════════════════════════════════════════════════════

_CONCEPT_INSTRUCTION = {
    ConceptObservationStatus.DEMONSTRATED: (
        "address with genuine functional explanation (why/how/consequence in the "
        "context of your own described work)"
    ),
    ConceptObservationStatus.SUPERFICIAL: (
        "mention (or a close paraphrase) without functional tie-in — a name-drop or "
        "generic reference disconnected from your specific work"
    ),
    ConceptObservationStatus.OMITTED: (
        "do NOT mention, in any form — not the term, not a synonym, not a "
        "functionally-equivalent description"
    ),
}


def expected_concept_controller(recipe: GenerationRecipe) -> PromptSection:
    """Per-concept target status becomes a per-concept instruction
    (Promptbook Section 5). Paraphrase tolerance applies symmetrically:
    inclusion targets accept a paraphrase; the omission target's
    instruction extends to paraphrases and synonyms too."""
    if not recipe.concept_targets:
        return PromptSection(controller="expected_concept", invariant=False, content="")
    lines = ["For each of the following concepts:"]
    for target in recipe.concept_targets:
        lines.append(f"- {target.concept}: {_CONCEPT_INSTRUCTION[target.status]}.")
    return PromptSection(controller="expected_concept", invariant=False, content="\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# Contradiction Controller (variable, usually a no-op)
# ═════════════════════════════════════════════════════════════════════════════

_CONTRADICTION_INSTRUCTION = {
    "factual": "assert something that directly conflicts with a stated grounding fact",
    "timeline": "assert an implied sequence or duration of events that conflicts with the grounding",
    "technology": "deny or silently replace a technology explicitly listed in the grounding",
    "ownership": "assert a role or responsibility that conflicts with the grounding's stated role",
}


def contradiction_controller(recipe: GenerationRecipe) -> PromptSection:
    """A no-op unless `is_contradictory`. When active, targets ONE named
    type (Promptbook Section 8) and leaves everything else — style,
    structure, the rest of the content — under normal controls, since
    contradiction is orthogonal to fluency by design."""
    if not recipe.is_contradictory or recipe.contradiction_type is None:
        return PromptSection(controller="contradiction", invariant=False, content="")
    kind = recipe.contradiction_type.value
    content = (
        f"Introduce EXACTLY ONE deliberate {kind} contradiction: {_CONTRADICTION_INSTRUCTION[kind]}. "
        "The rest of the answer must remain internally consistent and grounding-consistent, and the "
        "whole answer must otherwise read as fluent, well-formed, plausible-quality prose — do not "
        "signal the contradiction stylistically."
    )
    return PromptSection(controller="contradiction", invariant=False, content=content)


# ═════════════════════════════════════════════════════════════════════════════
# Off-Topic Controller (variable, usually a no-op; overrides when active)
# ═════════════════════════════════════════════════════════════════════════════


def off_topic_controller(recipe: GenerationRecipe) -> PromptSection:
    """A no-op unless `is_off_topic`. When active, this is the ONLY content
    instruction — `prompt_assembler.py` is responsible for suppressing the
    Expected-Concept and Reasoning-Category controllers' output entirely
    when this is active (Promptbook Section 2's override rule)."""
    if not recipe.is_off_topic:
        return PromptSection(controller="off_topic", invariant=False, content="")
    content = (
        "Do NOT meaningfully engage with the question or grounding above. Instead, "
        "produce a fluent, coherent answer to a DIFFERENT, plausible-sounding but "
        "unrelated interview question. The answer must still read as well-formed, "
        "genuine prose — this is a deliberate off-topic response, not garbled or "
        "malformed text."
    )
    return PromptSection(controller="off_topic", invariant=False, content=content)


# ═════════════════════════════════════════════════════════════════════════════
# Diversity Controller (variable, per-unit)
# ═════════════════════════════════════════════════════════════════════════════

_VOCABULARY_REGISTERS = ("casual-professional", "measured-technical", "formal-precise")
_SENTENCE_PATTERNS = ("short, punchy sentences", "a mix of short and longer compound sentences", "longer, flowing sentences")
_ORDERINGS = ("lead with a specific detail or anecdote before general context", "overview first, then supporting detail", "state the outcome first, then explain how you got there")
_STORYTELLING = ("narrate chronologically (first..., then...)", "describe the structure/components rather than a timeline", "lead with the result, then explain the reasoning behind it")
_CONFIDENCE_TONES = ("measured and somewhat hedged", "plainly matter-of-fact", "assertive and confident")


def _pick(seed: str, axis: str, options: tuple[str, ...]) -> str:
    import zlib
    digest = zlib.crc32(f"{seed}::{axis}".encode("utf-8"))
    return options[digest % len(options)]


def diversity_controller(recipe: GenerationRecipe) -> PromptSection:
    """Injects stylistic-variance parameters, sampled deterministically from
    `diversity_seed`, so no single vocabulary/structure/tone dominates a
    batch (Promptbook Section 4) — this is what prevents "LLM voice"."""
    seed = recipe.diversity_seed
    vocabulary = _pick(seed, "vocabulary", _VOCABULARY_REGISTERS)
    sentences = _pick(seed, "sentences", _SENTENCE_PATTERNS)
    ordering = _pick(seed, "ordering", _ORDERINGS)
    storytelling = _pick(seed, "storytelling", _STORYTELLING)
    confidence = _pick(seed, "confidence", _CONFIDENCE_TONES)
    content = (
        f"Use a {vocabulary} vocabulary register. Favor {sentences}. "
        f"Order your ideas by: {ordering}. Tell it by: {storytelling}. "
        f"Adopt a {confidence} tone, independent of how correct the content actually is."
    )
    return PromptSection(controller="diversity", invariant=False, content=content)


# ═════════════════════════════════════════════════════════════════════════════
# Style Controller (variable, per-unit)
# ═════════════════════════════════════════════════════════════════════════════

_NARRATION_STYLES = ("personal and reflective", "matter-of-fact reporting")


def style_controller(recipe: GenerationRecipe) -> PromptSection:
    """Governs internal, within-answer voice consistency — distinct from
    the Diversity Controller's between-answer variance (Promptbook Section
    2's controller table)."""
    narration = _pick(recipe.style_seed, "narration", _NARRATION_STYLES)
    content = (
        f"Keep a single, consistent first-person voice throughout the answer — "
        f"consistent tense, consistent {narration} narration, and a consistent "
        f"confidence level from start to finish. Never switch to third-person or "
        f"team-only framing."
    )
    return PromptSection(controller="style", invariant=False, content=content)
