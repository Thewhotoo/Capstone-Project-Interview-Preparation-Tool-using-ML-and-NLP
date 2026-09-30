"""
Prompt Assembler — Stage A Synthetic Dataset Generation Pipeline (Synthetic
Dataset Generation Promptbook RFC, Section 2/10 — APPROVED AND FROZEN).

Wires the controllers in `prompt_controllers.py` into a versioned pipeline
and assembles the final system/user prompt text a `GenerationClient` sends
to the model. This is the ONLY place controller wiring is defined — no
other module hardcodes prompt text or controller order.

VERSIONING (Promptbook Section 10): `generation_prompt_id` identifies a
prompt template PACKAGE (which controllers exist, how they're wired);
`prompt_version` is a semantic version within that package. A future
revision registers a NEW (generation_prompt_id, prompt_version) pipeline via
`register_prompt_version` — it never edits an existing one in place, so
examples already generated under an older version remain reproducible
forever (the same append-only discipline already established for
`dataset_version`/`ReviewEvent`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from generation_recipe import GenerationRecipe
from prompt_controllers import (
    PromptSection,
    contradiction_controller,
    diversity_controller,
    expected_concept_controller,
    generation_prompt_controller,
    off_topic_controller,
    quality_tier_controller,
    reasoning_category_controller,
    style_controller,
    system_prompt_controller,
)

# Controllers whose output is suppressed entirely when a recipe is
# off-topic (Promptbook Section 2's override rule) — an off-topic answer
# cannot, by definition, target concepts or reasoning categories.
_SUPPRESSED_BY_OFF_TOPIC = frozenset({"expected_concept", "reasoning_category"})

VariableController = Callable[[GenerationRecipe], PromptSection]


@dataclass(frozen=True)
class AssembledPrompt:
    """The final prompt sent to a `GenerationClient` (generation_client.py),
    plus the versioning identity that must be recorded on every
    `TrainingExample` produced from it (Promptbook Section 10)."""

    generation_prompt_id: str
    prompt_version: str
    system_text: str
    user_text: str


@dataclass(frozen=True)
class _PromptPipeline:
    """One versioned controller wiring. `variable_controllers` runs in
    order; `system_controller` is invariant and always runs first."""

    system_controller: Callable[[], PromptSection]
    variable_controllers: tuple[VariableController, ...]


_PIPELINE_REGISTRY: dict[tuple[str, str], _PromptPipeline] = {}


class DuplicatePromptVersionError(ValueError):
    """Raised by `register_prompt_version` if the (id, version) pair is
    already registered — re-registering would silently redefine a prompt
    version that may have already produced published TrainingExamples,
    violating the append-only versioning discipline (Promptbook Section 10)."""


def register_prompt_version(
    generation_prompt_id: str,
    prompt_version: str,
    variable_controllers: tuple[VariableController, ...],
    system_controller: Callable[[], PromptSection] = system_prompt_controller,
) -> None:
    key = (generation_prompt_id, prompt_version)
    if key in _PIPELINE_REGISTRY:
        raise DuplicatePromptVersionError(f"{key!r} is already registered")
    _PIPELINE_REGISTRY[key] = _PromptPipeline(
        system_controller=system_controller, variable_controllers=variable_controllers,
    )


def registered_prompt_versions() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_PIPELINE_REGISTRY.keys()))


def assemble_prompt(
    recipe: GenerationRecipe,
    generation_prompt_id: str,
    prompt_version: str,
) -> AssembledPrompt:
    """Assemble the full prompt for `recipe` under a specific, previously
    registered (generation_prompt_id, prompt_version) pipeline."""
    key = (generation_prompt_id, prompt_version)
    pipeline = _PIPELINE_REGISTRY.get(key)
    if pipeline is None:
        raise KeyError(f"no prompt pipeline registered for {key!r}")

    system_section = pipeline.system_controller()
    variable_sections = [controller(recipe) for controller in pipeline.variable_controllers]

    if recipe.is_off_topic:
        variable_sections = [
            s for s in variable_sections if s.controller not in _SUPPRESSED_BY_OFF_TOPIC
        ]

    system_text = system_section.content
    user_text = "\n\n".join(s.content for s in variable_sections if s.content.strip())

    return AssembledPrompt(
        generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
        system_text=system_text, user_text=user_text,
    )


# ═════════════════════════════════════════════════════════════════════════════
# The current, default pipeline — "promptbook" v1.0.0
# ═════════════════════════════════════════════════════════════════════════════

GENERATION_PROMPT_ID = "promptbook"
PROMPT_VERSION = "1.0.0"

register_prompt_version(
    GENERATION_PROMPT_ID, PROMPT_VERSION,
    variable_controllers=(
        generation_prompt_controller,
        quality_tier_controller,
        reasoning_category_controller,
        expected_concept_controller,
        contradiction_controller,
        off_topic_controller,
        diversity_controller,
        style_controller,
    ),
)


def assemble_current_prompt(recipe: GenerationRecipe) -> AssembledPrompt:
    """Convenience wrapper around the current default (GENERATION_PROMPT_ID,
    PROMPT_VERSION) pipeline — most callers want this rather than pinning a
    specific version explicitly."""
    return assemble_prompt(recipe, GENERATION_PROMPT_ID, PROMPT_VERSION)
