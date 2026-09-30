"""
Rewrite Validation — Experiment 4 (Rewrite Augmentation) Stage.

Mirrors `generation_validation.py`'s shape exactly (small, pure checks
combined into one verdict; never repairs, only accepts/rejects — a failing
check always means the whole attempt is discarded and regenerated, same
"Implementation requirement 10" discipline this whole pipeline already
follows). What differs is the CONTRACT being validated: generation-time
validation checks a `GenerationOutput` against a freshly SAMPLED
`GenerationRecipe`; rewrite validation checks a `GenerationOutput` against
an EXISTING source `TrainingExample`'s already-fixed labels/targets — the
rewrite must reproduce them, not merely conform to a fresh sample of them.

FOUR of `generation_validation.py`'s five checks are reused completely
unchanged (`check_malformed_output`, `check_hallucinated_technology`,
`check_concept_count`, `check_reasoning_mismatch`, `check_contradiction_consistency`)
by reconstructing a real, fully-valid `GenerationRecipe` directly from the
source example's own already-serialized `synthetic` block
(`recipe_from_source_example` below) — every field those checks need
(`concept_targets`, `reasoning_targets`, `quality_tier`, seeds, ...) is
already sitting there, so this is a straight reconstruction of
already-computed data, not an invented adapter (the same "never invented"
evidence discipline `dataset_relabeling.py` already established). Zero
check LOGIC is duplicated.

TWO new checks are added, per this session's explicit design (approved,
with a third addition after user review):
  - `check_semantic_similarity` — an SBERT cosine-similarity gate (reusing
    the same lazy-singleton pattern `heuristic_evaluator._semantic_similarity`
    already established, duplicated locally per this codebase's "deliberate
    independence between pipeline stages" precedent, not imported).
  - `check_length_ratio` — a per-style length-ratio sanity check (a
    `concise` rewrite that's LONGER than the source, or a `verbose` one
    that's shorter, suggests the style instruction wasn't actually followed).
  - `check_semantic_drift` (LLM-judge, user-requested addition) — asks
    Gemini directly whether the rewrite's technical meaning materially
    differs from the original's, as a safeguard beyond what embedding
    similarity alone can catch (a subtle factual reversal can score as
    "similar enough" numerically while still being semantically wrong).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from generation_client import GenerationOutput
from generation_recipe import GenerationRecipe
from generation_validation import (
    check_concept_count,
    check_contradiction_consistency,
    check_hallucinated_technology,
    check_malformed_output,
    check_reasoning_mismatch,
)
from rewrite_verifier_client import RewriteVerifierClient
from training_example import TrainingExample

logger = logging.getLogger(__name__)

# SBERT cosine-similarity band (Promptbook-equivalent design for rewrites,
# approved this session): below the floor, meaning has likely drifted, not
# just been restyled; above the ceiling, the rewrite is a near-duplicate —
# no real stylistic diversity was added, defeating the point of augmentation.
_SIMILARITY_FLOOR = 0.55
_SIMILARITY_CEILING = 0.97

# Per-style expected length-ratio band (rewritten word count / original word
# count). Styles with a directional length expectation get a tight band;
# styles without one get a loose sanity band (catches only gross failures,
# e.g. a near-empty or wildly bloated rewrite, not a style violation).
_LENGTH_RATIO_BANDS: dict[str, tuple[float, float]] = {
    "concise": (0.15, 1.05),
    "verbose": (0.95, 3.0),
    "conversational": (0.4, 2.0),
    "interview_like": (0.4, 2.0),
    "highly_structured": (0.4, 2.0),
    "reflective": (0.4, 2.0),
    "confident": (0.4, 2.0),
    "cautious": (0.4, 2.0),
}

_SEM_MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class RewriteValidationVerdict:
    """Same shape as `generation_validation.ValidationVerdict` — kept as a
    distinct type (not reused directly) since a rewrite verdict is checked
    against a different contract and callers should never be able to
    accidentally pass one where the other is expected."""

    accepted: bool
    rejection_reasons: tuple[str, ...] = ()


def recipe_from_source_example(source_example: TrainingExample) -> GenerationRecipe:
    """Reconstruct a real, fully-valid `GenerationRecipe` from a source
    example's own already-serialized `synthetic` block — every field the
    reused checks need is already sitting there (see module docstring).
    Raises if `source_example.synthetic` is None (nothing to reconstruct
    from); callers are responsible for only rewriting synthetic examples."""
    if source_example.synthetic is None:
        raise ValueError("cannot reconstruct a GenerationRecipe from a non-synthetic source example")
    synthetic = source_example.synthetic
    return GenerationRecipe(
        recipe_id=source_example.metadata.example_id,
        specification=source_example.inputs.specification,
        question_text=source_example.inputs.question_text,
        reasoning_type=source_example.inputs.reasoning_type,
        expected_concepts=source_example.inputs.expected_concepts,
        quality_tier=synthetic.intended_quality_tier,
        concept_targets=synthetic.intended_concept_inclusion,
        reasoning_targets=synthetic.intended_reasoning_category_targets,
        is_off_topic=synthetic.is_off_topic,
        is_contradictory=synthetic.is_contradictory,
        contradiction_type=synthetic.contradiction_type,
        diversity_seed=synthetic.diversity_seed,
        style_seed=synthetic.style_seed,
    )


# ═════════════════════════════════════════════════════════════════════════════
# New check 1: SBERT semantic-similarity gate
# ═════════════════════════════════════════════════════════════════════════════


class _LazySemanticModel:
    """Lazy singleton, private to this module — duplicated from
    `heuristic_evaluator._LazyModels` rather than imported (module docstring)."""

    _model = None

    @classmethod
    def get(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer(_SEM_MODEL_NAME)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("SentenceTransformer unavailable, using fallback: %s", e)
                cls._model = False
        return cls._model if cls._model is not False else None


def _semantic_similarity(text_a: str, text_b: str) -> float:
    model = _LazySemanticModel.get()
    if model is None or not text_a.strip() or not text_b.strip():
        words_a, words_b = set(text_a.lower().split()), set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / max(len(words_a | words_b), 1)
    import numpy as np
    embs = model.encode([text_a, text_b])
    dot = np.dot(embs[0], embs[1])
    norm = np.linalg.norm(embs[0]) * np.linalg.norm(embs[1])
    return float(dot / norm) if norm > 0 else 0.0


def check_semantic_similarity(original_answer: str, rewritten_answer: str) -> tuple[str, ...]:
    """SBERT cosine-similarity gate (module docstring)."""
    similarity = _semantic_similarity(original_answer, rewritten_answer)
    if similarity < _SIMILARITY_FLOOR:
        return (f"semantic_drift: similarity {similarity:.3f} is below the floor {_SIMILARITY_FLOOR} — meaning likely drifted",)
    if similarity > _SIMILARITY_CEILING:
        return (f"near_duplicate: similarity {similarity:.3f} is above the ceiling {_SIMILARITY_CEILING} — no real stylistic diversity added",)
    return ()


# ═════════════════════════════════════════════════════════════════════════════
# New check 2: per-style length-ratio sanity
# ═════════════════════════════════════════════════════════════════════════════


def check_length_ratio(original_answer: str, rewritten_answer: str, style: str) -> tuple[str, ...]:
    """Per-style length-ratio sanity check (module docstring)."""
    original_words = len(original_answer.split())
    rewritten_words = len(rewritten_answer.split())
    if original_words == 0:
        return ()  # nothing to compare against; check_malformed_output already covers empty source
    ratio = rewritten_words / original_words
    band = _LENGTH_RATIO_BANDS.get(style)
    if band is None:
        return ()  # unknown style — rewrite_prompt_controllers already rejects this earlier in the pipeline
    low, high = band
    if not (low <= ratio <= high):
        return (f"length_ratio_violation: style {style!r} produced a length ratio of {ratio:.2f}, outside the expected band [{low}, {high}]",)
    return ()


# ═════════════════════════════════════════════════════════════════════════════
# New check 3 (user-requested addition): Gemini semantic-drift judge
# ═════════════════════════════════════════════════════════════════════════════


def check_semantic_drift(
    original_answer: str, rewritten_answer: str, verifier_client: RewriteVerifierClient,
) -> tuple[str, ...]:
    """LLM-judge safeguard beyond SBERT similarity alone (module docstring)."""
    verdict = verifier_client.verify(original_answer, rewritten_answer)
    if verdict.meaning_changed:
        return (f"llm_judged_semantic_drift: {verdict.explanation or '(no explanation supplied)'}",)
    return ()


# ═════════════════════════════════════════════════════════════════════════════
# Combined verdict
# ═════════════════════════════════════════════════════════════════════════════


def validate_rewrite(
    output: GenerationOutput,
    source_example: TrainingExample,
    style: str,
    verifier_client: RewriteVerifierClient,
) -> RewriteValidationVerdict:
    """Run every automatic QA check — the 4 reused generation-time checks
    (against a `GenerationRecipe` reconstructed from `source_example`'s own
    already-serialized data) plus the 3 rewrite-specific checks — and
    combine into one verdict. Off-topic source examples skip the
    concept/reasoning-mismatch checks entirely, mirroring
    `generation_validation.validate_generation`'s own skip logic (those
    targets don't exist for an off-topic example)."""
    recipe = recipe_from_source_example(source_example)
    original_answer = source_example.inputs.answer_text

    reasons: list[str] = []
    reasons.extend(check_malformed_output(output))
    reasons.extend(check_hallucinated_technology(output, recipe))
    if not recipe.is_off_topic:
        reasons.extend(check_concept_count(output, recipe))
        reasons.extend(check_reasoning_mismatch(output, recipe))
    reasons.extend(check_contradiction_consistency(output, recipe))
    reasons.extend(check_semantic_similarity(original_answer, output.answer_text))
    reasons.extend(check_length_ratio(original_answer, output.answer_text, style))
    reasons.extend(check_semantic_drift(original_answer, output.answer_text, verifier_client))
    return RewriteValidationVerdict(accepted=not reasons, rejection_reasons=tuple(reasons))
