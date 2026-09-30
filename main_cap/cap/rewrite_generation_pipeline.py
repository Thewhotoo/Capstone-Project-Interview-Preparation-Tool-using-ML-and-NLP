"""
Rewrite Generation Pipeline — Experiment 4 (Rewrite Augmentation) Stage.

The single orchestration entry point for a rewrite: assemble a rewrite
prompt, call a generator, validate the result, and assemble a rewritten
`TrainingExample` — or, if validation fails, discard the whole attempt and
retry, up to a bounded number of attempts. Mirrors
`synthetic_generation_pipeline.py`'s shape and its "reject and regenerate,
never partially repair" discipline exactly (Implementation requirement 10
applies here too), with one necessary difference: a generation attempt salts
its `recipe_id` per retry because a FRESH recipe sample varies between
attempts; a rewrite attempt has no recipe to resample — the prompt is a
deterministic function of `(source_example, style)`, so a retry re-issues
the SAME prompt and relies on the underlying `GenerationClient`'s own
sampling to (hopefully) produce an acceptable result the second time.

Strict separation of responsibilities, same as `synthetic_generation_pipeline.py`:
this module produces rewritten `TrainingExample`s and nothing else. It does
not train a model, does not evaluate an answer, does not assemble a
`DatasetManifest`, and does not decide dataset placement (a rewrite's
train/val/test side is the caller's job — see the pilot driver, which places
a rewrite on whichever side its source example is already on).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from generation_client import GenerationClient
from rewrite_assembler import assemble_rewritten_example
from rewrite_prompt_assembler import (
    REWRITE_GENERATION_PROMPT_ID,
    REWRITE_PROMPT_VERSION,
    assemble_rewrite_prompt,
)
from rewrite_validation import validate_rewrite
from rewrite_verifier_client import RewriteVerifierClient
from training_example import TrainingExample

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3


class RewriteRejectedError(RuntimeError):
    """Raised when every attempt for one (source_example, style) pair was
    rejected by `rewrite_validation.validate_rewrite` — the caller (a batch
    driver, a human operator) decides what to do next; this pipeline never
    silently returns a rejected rewrite."""

    def __init__(self, source_example_id: str, style: str, attempts: int, last_reasons: tuple[str, ...]) -> None:
        super().__init__(
            f"rewrite of {source_example_id!r} (style={style!r}) rejected after {attempts} attempt(s); "
            f"last rejection reasons: {', '.join(last_reasons) or '(none recorded)'}"
        )
        self.source_example_id = source_example_id
        self.style = style
        self.attempts = attempts
        self.last_reasons = last_reasons


@dataclass(frozen=True)
class RewriteOutcome:
    """One rewrite's result, including how many attempts it took — same
    loggable-quality-signal rationale as `synthetic_generation_pipeline.GenerationOutcome`."""

    example: TrainingExample
    source_example_id: str
    style: str
    attempts: int
    generation_prompt_id: str
    prompt_version: str


def rewrite_training_example(
    source_example: TrainingExample,
    style: str,
    client: GenerationClient,
    verifier_client: RewriteVerifierClient,
    generation_batch_id: str,
    generation_prompt_id: str = REWRITE_GENERATION_PROMPT_ID,
    prompt_version: str = REWRITE_PROMPT_VERSION,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> RewriteOutcome:
    """Produce one validated rewritten `TrainingExample` for
    `(source_example, style)`. `style` is always an explicit caller-supplied
    parameter — never derived from `source_example.synthetic.style_seed` or
    any other implicit seed (explicit design decision this session: keeps
    style selection a pipeline parameter, not an implicit side effect, and
    lets a caller request MULTIPLE style variants of the same source
    example by calling this once per style)."""
    last_reasons: tuple[str, ...] = ()
    for attempt in range(1, max_attempts + 1):
        prompt = assemble_rewrite_prompt(source_example, style, generation_prompt_id, prompt_version)
        output = client.generate(prompt)
        verdict = validate_rewrite(output, source_example, style, verifier_client)

        if verdict.accepted:
            example = assemble_rewritten_example(
                source_example, output, style, generation_prompt_id, prompt_version,
                client.model_name, generation_batch_id,
            )
            if attempt > 1:
                logger.info(
                    "rewrite of %r (style=%r) accepted on attempt %d/%d",
                    source_example.metadata.example_id, style, attempt, max_attempts,
                )
            return RewriteOutcome(
                example=example, source_example_id=source_example.metadata.example_id, style=style,
                attempts=attempt, generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
            )

        last_reasons = verdict.rejection_reasons
        logger.warning(
            "rewrite of %r (style=%r) rejected on attempt %d/%d: %s",
            source_example.metadata.example_id, style, attempt, max_attempts, "; ".join(last_reasons),
        )

    raise RewriteRejectedError(source_example.metadata.example_id, style, max_attempts, last_reasons)


@dataclass(frozen=True)
class RewriteUnit:
    """One requested rewrite within a batch — an explicit
    (source_example, style) pair the caller wants generated. Batches are
    always an explicit list of units, never an implicit cross-product —
    the caller decides exactly which (source, style) combinations to
    request (e.g. the pilot driver requests every source × all 3 pilot
    styles, but nothing in this module assumes that shape)."""

    source_example: TrainingExample
    style: str


def rewrite_batch(
    units: tuple[RewriteUnit, ...],
    client: GenerationClient,
    verifier_client: RewriteVerifierClient,
    generation_batch_id: str,
    generation_prompt_id: str = REWRITE_GENERATION_PROMPT_ID,
    prompt_version: str = REWRITE_PROMPT_VERSION,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> tuple[RewriteOutcome, ...]:
    """Generate one rewritten `TrainingExample` per `RewriteUnit`. A unit
    that exhausts `max_attempts` raises `RewriteRejectedError`, which
    propagates immediately — a caller who wants partial-batch results on
    partial failure is expected to catch it per-unit itself; this function
    never silently drops a failed unit (same discipline as
    `synthetic_generation_pipeline.generate_batch`)."""
    outcomes = []
    for unit in units:
        outcome = rewrite_training_example(
            source_example=unit.source_example, style=unit.style, client=client, verifier_client=verifier_client,
            generation_batch_id=generation_batch_id, generation_prompt_id=generation_prompt_id,
            prompt_version=prompt_version, max_attempts=max_attempts,
        )
        outcomes.append(outcome)
    return tuple(outcomes)
