"""
Synthetic Generation Pipeline — Stage A Synthetic Dataset Generation
Pipeline (Dataset Generation RFC Section 1/8, Promptbook RFC — both
APPROVED AND FROZEN). Implementation only; no architectural deviation.

The single orchestration entry point: sample a recipe, assemble a prompt,
call a generator, validate the result, and assemble a `TrainingExample` —
or, if validation fails, discard the WHOLE attempt and try again from a
fresh recipe salt, up to a bounded number of attempts (Implementation
requirement 10: "failed generations should be rejected and regenerated
rather than partially repaired" — there is no code path here that edits a
rejected `GenerationOutput`; every retry starts over from
`generation_recipe.sample_recipe`).

Strict separation of responsibilities (Implementation requirement 11): this
module produces `TrainingExample`s and nothing else. It does not train a
model, does not evaluate an answer (no `Evaluator` is imported or called),
does not perform human review, does not assemble a `DatasetManifest`, and
does not benchmark anything.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from generation_client import GenerationClient
from generation_recipe import sample_recipe
from generation_validation import validate_generation
from prompt_assembler import GENERATION_PROMPT_ID, PROMPT_VERSION, assemble_prompt
from question_families import ReasoningType
from question_specification import QuestionSpecification
from training_example import QualityTier, TrainingExample
from training_example_assembler import assemble_training_example

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3

# The target distribution across the 7 generation modes a batch cycles
# through when the caller doesn't supply an explicit tier plan (Dataset
# Generation RFC Section 3's coverage strategy owns the REAL policy for
# this in production; this fixed, deterministic cycle is a reasonable
# default keeping the pipeline usable standalone without redesigning that
# RFC's own coverage-strategy component).
DEFAULT_TIER_CYCLE: tuple[QualityTier, ...] = (
    QualityTier.EXCELLENT, QualityTier.GOOD, QualityTier.GOOD, QualityTier.ADEQUATE,
    QualityTier.ADEQUATE, QualityTier.WEAK, QualityTier.POOR,
    QualityTier.OFF_TOPIC, QualityTier.CONTRADICTORY,
)


class GenerationRejectedError(RuntimeError):
    """Raised when every attempt for one example was rejected by
    `generation_validation.validate_generation` — the caller (a batch
    driver, a human operator) decides what to do next; this pipeline never
    silently returns a rejected example."""

    def __init__(self, recipe_id: str, attempts: int, last_reasons: tuple[str, ...]) -> None:
        super().__init__(
            f"recipe {recipe_id!r} rejected after {attempts} attempt(s); "
            f"last rejection reasons: {', '.join(last_reasons) or '(none recorded)'}"
        )
        self.recipe_id = recipe_id
        self.attempts = attempts
        self.last_reasons = last_reasons


@dataclass(frozen=True)
class GenerationOutcome:
    """One example's result, including how many attempts it took — a
    non-1 `attempts` count is itself a useful, loggable quality signal
    about how well the current prompt version conforms to its own recipes."""

    example: TrainingExample
    attempts: int
    generation_prompt_id: str
    prompt_version: str


def generate_training_example(
    recipe_id: str,
    specification: QuestionSpecification,
    question_text: str,
    reasoning_type: ReasoningType,
    expected_concepts: tuple[str, ...],
    quality_tier: QualityTier,
    client: GenerationClient,
    generation_batch_id: str,
    generation_prompt_id: str = GENERATION_PROMPT_ID,
    prompt_version: str = PROMPT_VERSION,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> GenerationOutcome:
    """
    Produce one validated `TrainingExample` for `recipe_id`. Each attempt
    samples a FRESH recipe (salted by attempt number) rather than reusing or
    patching the previous attempt's recipe or output — a rejected attempt is
    always discarded whole (Implementation requirement 10).
    """
    last_reasons: tuple[str, ...] = ()
    for attempt in range(1, max_attempts + 1):
        attempt_recipe_id = recipe_id if attempt == 1 else f"{recipe_id}::attempt{attempt}"
        recipe = sample_recipe(
            attempt_recipe_id, specification, question_text, reasoning_type, expected_concepts, quality_tier,
        )
        prompt = assemble_prompt(recipe, generation_prompt_id, prompt_version)
        output = client.generate(prompt)
        verdict = validate_generation(output, recipe)

        if verdict.accepted:
            example = assemble_training_example(
                recipe, output, generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
                generator_model=client.model_name, generation_batch_id=generation_batch_id,
            )
            if attempt > 1:
                logger.info("recipe %r accepted on attempt %d/%d", recipe_id, attempt, max_attempts)
            return GenerationOutcome(
                example=example, attempts=attempt,
                generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
            )

        last_reasons = verdict.rejection_reasons
        logger.warning(
            "recipe %r rejected on attempt %d/%d: %s", recipe_id, attempt, max_attempts, "; ".join(last_reasons),
        )

    raise GenerationRejectedError(recipe_id, max_attempts, last_reasons)


@dataclass(frozen=True)
class BatchUnit:
    """One requested example within a batch — a (specification, question,
    reasoning_type, expected_concepts) tuple the caller wants a synthetic
    answer generated for, at whatever tier the batch cycle assigns it."""

    recipe_id: str
    specification: QuestionSpecification
    question_text: str
    reasoning_type: ReasoningType
    expected_concepts: tuple[str, ...] = ()


def generate_batch(
    units: tuple[BatchUnit, ...],
    client: GenerationClient,
    generation_batch_id: str,
    tier_cycle: tuple[QualityTier, ...] = DEFAULT_TIER_CYCLE,
    generation_prompt_id: str = GENERATION_PROMPT_ID,
    prompt_version: str = PROMPT_VERSION,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> tuple[GenerationOutcome, ...]:
    """
    Generate one `TrainingExample` per `BatchUnit`, cycling `tier_cycle`
    deterministically across `units` so a batch actually gets a spread of
    quality tiers rather than every unit landing on the same one. A unit
    that exhausts `max_attempts` raises `GenerationRejectedError`, which
    propagates immediately — a caller who wants partial-batch results on
    partial failure is expected to catch it per-unit itself; this function
    never silently drops a failed unit.
    """
    outcomes = []
    for index, unit in enumerate(units):
        tier = tier_cycle[index % len(tier_cycle)]
        outcome = generate_training_example(
            recipe_id=unit.recipe_id, specification=unit.specification, question_text=unit.question_text,
            reasoning_type=unit.reasoning_type, expected_concepts=unit.expected_concepts, quality_tier=tier,
            client=client, generation_batch_id=generation_batch_id,
            generation_prompt_id=generation_prompt_id, prompt_version=prompt_version, max_attempts=max_attempts,
        )
        outcomes.append(outcome)
    return tuple(outcomes)
