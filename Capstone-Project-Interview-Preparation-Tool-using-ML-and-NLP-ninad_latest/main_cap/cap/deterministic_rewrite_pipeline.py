"""
Deterministic Rewrite Pipeline — Experiment 4 (Rewrite Augmentation) Stage,
API-FREE entry point (Track B: the final training dataset must be
producible without Gemini, OpenAI, or any other external LLM API).

Mirrors `rewrite_generation_pipeline.rewrite_training_example`'s shape and
"reject an unacceptable attempt, never repair" discipline, but swaps out
BOTH LLM call sites for local, deterministic equivalents:
  - generation: `deterministic_rewrite.generate_deterministic_rewrite`
    (pure text transform) instead of a `GenerationClient`/Gemini call.
  - semantic-drift verification: `rewrite_verifier_client.SBERTDriftVerifierClient`
    (SBERT cosine similarity) instead of `GeminiSemanticVerifierClient`.

Since the generator is a pure function of `(source_example, style)` — no
sampling, no randomness — a rejected attempt would reproduce identically
on retry. This pipeline therefore makes exactly ONE attempt per unit (not
`rewrite_generation_pipeline.DEFAULT_MAX_ATTEMPTS` retries) and raises
immediately on rejection; nothing is lost, since retrying could never
change the outcome the way a fresh LLM sample could.

Reuses `rewrite_validation.validate_rewrite` and
`rewrite_assembler.assemble_rewritten_example` COMPLETELY UNCHANGED — the
exact same acceptance bar (7 automatic QA checks) a Gemini-produced
rewrite has to clear, so an API-free rewrite is held to an identical
quality standard, not a lowered one. Also reuses `RewriteOutcome` /
`RewriteRejectedError` / `RewriteUnit` from `rewrite_generation_pipeline.py`
rather than redefining them — same result/error shape either pipeline
produces, so downstream code (a batch driver, a dataset assembler) never
needs to know which generation method produced a given `RewriteOutcome`.
"""

from __future__ import annotations

import logging

from deterministic_rewrite import generate_deterministic_rewrite
from rewrite_assembler import assemble_rewritten_example
from rewrite_generation_pipeline import RewriteOutcome, RewriteRejectedError, RewriteUnit
from rewrite_validation import validate_rewrite
from rewrite_verifier_client import RewriteVerifierClient, SBERTDriftVerifierClient
from training_example import TrainingExample

logger = logging.getLogger(__name__)

# A distinct (generation_prompt_id, prompt_version) pair from the Gemini
# path's "rewrite_promptbook"/"1.0.0" — this is a genuinely different
# generation method and must be independently traceable in the dataset
# (Promptbook Section 10's append-only versioning discipline), never
# conflated with Gemini-produced rewrites.
DETERMINISTIC_REWRITE_PROMPT_ID = "deterministic_rewrite"
DETERMINISTIC_REWRITE_PROMPT_VERSION = "1.0.0"
DETERMINISTIC_GENERATOR_MODEL = "deterministic-rule-based-v1"


def deterministic_rewrite_training_example(
    source_example: TrainingExample,
    style: str,
    generation_batch_id: str,
    verifier_client: RewriteVerifierClient | None = None,
) -> RewriteOutcome:
    """Produce one validated rewritten `TrainingExample` for
    `(source_example, style)` with no LLM call anywhere in the path."""
    verifier = verifier_client or SBERTDriftVerifierClient()

    output = generate_deterministic_rewrite(source_example, style)
    verdict = validate_rewrite(output, source_example, style, verifier)

    if not verdict.accepted:
        raise RewriteRejectedError(
            source_example.metadata.example_id, style, 1, verdict.rejection_reasons
        )

    example = assemble_rewritten_example(
        source_example, output, style,
        DETERMINISTIC_REWRITE_PROMPT_ID, DETERMINISTIC_REWRITE_PROMPT_VERSION,
        DETERMINISTIC_GENERATOR_MODEL, generation_batch_id,
    )
    return RewriteOutcome(
        example=example, source_example_id=source_example.metadata.example_id, style=style,
        attempts=1, generation_prompt_id=DETERMINISTIC_REWRITE_PROMPT_ID,
        prompt_version=DETERMINISTIC_REWRITE_PROMPT_VERSION,
    )


def deterministic_rewrite_batch(
    units: tuple[RewriteUnit, ...],
    generation_batch_id: str,
) -> tuple[RewriteOutcome, ...]:
    """Generate one rewritten `TrainingExample` per `RewriteUnit`, API-free.
    A unit that fails validation raises `RewriteRejectedError` immediately
    — same "never silently drop a failed unit" discipline as
    `rewrite_generation_pipeline.rewrite_batch`; a caller who wants
    partial-batch results on partial failure catches it per-unit itself
    (see the pilot driver's own per-unit try/except pattern)."""
    verifier = SBERTDriftVerifierClient()
    outcomes = []
    for unit in units:
        outcomes.append(
            deterministic_rewrite_training_example(
                unit.source_example, unit.style, generation_batch_id, verifier
            )
        )
    return tuple(outcomes)
