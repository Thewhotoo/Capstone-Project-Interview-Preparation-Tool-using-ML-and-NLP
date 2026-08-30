"""
Rewrite Prompt Assembler — Experiment 4 (Rewrite Augmentation) Stage.

Mirrors `prompt_assembler.py`'s registry/versioning shape exactly (Promptbook
Section 10's append-only (generation_prompt_id, prompt_version) discipline
applies here unchanged), but wires `rewrite_prompt_controllers.py`'s
controllers — which take `(TrainingExample, style)`, not `GenerationRecipe`
— into an entirely SEPARATE registry from `prompt_assembler.py`'s. A future
revision to the generation prompt pipeline never touches the rewrite
pipeline's versioning and vice versa (independent maintenance, per the
approved architectural recommendation this session).

Reuses `prompt_assembler.AssembledPrompt` unchanged — same downstream shape
(`system_text`/`user_text`) any `GenerationClient` already consumes, so
`generation_client.py`'s `GeminiGenerationClient`/`FakeGenerationClient` work
against a rewrite prompt with zero modification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from prompt_assembler import AssembledPrompt
from prompt_controllers import PromptSection
from rewrite_prompt_controllers import (
    rewrite_source_controller,
    rewrite_style_instruction_controller,
    rewrite_system_prompt_controller,
)
from training_example import TrainingExample

VariableController = Callable[[TrainingExample, str], PromptSection]


@dataclass(frozen=True)
class _RewritePromptPipeline:
    system_controller: Callable[[], PromptSection]
    variable_controllers: tuple[VariableController, ...]


_REWRITE_PIPELINE_REGISTRY: dict[tuple[str, str], _RewritePromptPipeline] = {}


class DuplicateRewritePromptVersionError(ValueError):
    """Same append-only rationale as `prompt_assembler.DuplicatePromptVersionError`
    — re-registering would silently redefine a version that may have already
    produced published rewritten `TrainingExample`s."""


def register_rewrite_prompt_version(
    generation_prompt_id: str,
    prompt_version: str,
    variable_controllers: tuple[VariableController, ...],
    system_controller: Callable[[], PromptSection] = rewrite_system_prompt_controller,
) -> None:
    key = (generation_prompt_id, prompt_version)
    if key in _REWRITE_PIPELINE_REGISTRY:
        raise DuplicateRewritePromptVersionError(f"{key!r} is already registered")
    _REWRITE_PIPELINE_REGISTRY[key] = _RewritePromptPipeline(
        system_controller=system_controller, variable_controllers=variable_controllers,
    )


def registered_rewrite_prompt_versions() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_REWRITE_PIPELINE_REGISTRY.keys()))


def assemble_rewrite_prompt(
    source_example: TrainingExample,
    style: str,
    generation_prompt_id: str,
    prompt_version: str,
) -> AssembledPrompt:
    """Assemble the full rewrite prompt for `(source_example, style)` under a
    specific, previously registered (generation_prompt_id, prompt_version)
    pipeline. Returns the SAME `AssembledPrompt` shape `prompt_assembler.py`
    produces — any `GenerationClient` consumes either without knowing which
    pipeline produced it."""
    key = (generation_prompt_id, prompt_version)
    pipeline = _REWRITE_PIPELINE_REGISTRY.get(key)
    if pipeline is None:
        raise KeyError(f"no rewrite prompt pipeline registered for {key!r}")

    system_section = pipeline.system_controller()
    variable_sections = [controller(source_example, style) for controller in pipeline.variable_controllers]

    system_text = system_section.content
    user_text = "\n\n".join(s.content for s in variable_sections if s.content.strip())

    return AssembledPrompt(
        generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
        system_text=system_text, user_text=user_text,
    )


# ═════════════════════════════════════════════════════════════════════════════
# The current, default rewrite pipeline — "rewrite_promptbook" v1.0.0
# ═════════════════════════════════════════════════════════════════════════════

REWRITE_GENERATION_PROMPT_ID = "rewrite_promptbook"
REWRITE_PROMPT_VERSION = "1.0.0"

register_rewrite_prompt_version(
    REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
    variable_controllers=(
        rewrite_source_controller,
        rewrite_style_instruction_controller,
    ),
)


def assemble_current_rewrite_prompt(source_example: TrainingExample, style: str) -> AssembledPrompt:
    """Convenience wrapper around the current default (REWRITE_GENERATION_PROMPT_ID,
    REWRITE_PROMPT_VERSION) pipeline — most callers want this rather than
    pinning a specific version explicitly."""
    return assemble_rewrite_prompt(source_example, style, REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION)
