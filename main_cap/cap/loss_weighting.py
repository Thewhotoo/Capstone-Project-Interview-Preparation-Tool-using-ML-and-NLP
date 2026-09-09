"""
Loss Weighting — Experiment A (V5 Ablation Design Review, H1: LOSS/
CALIBRATION). Computes CORAL-threshold `pos_weight` tensors from
TRAINING-SPLIT-ONLY tier statistics, for the two dimensions the V4
diagnostic flagged (`technical_correctness`, `relevance_completeness` by
default) — no architecture change, no CORAL decoding change, no label-
encoding change. See `docs/architecture/V5_Ablation_Design_Review.md`
Section 5 for the design rationale.

CRITICAL INVARIANT: every function in this module takes ONLY the examples
the caller explicitly passes in — there is no hidden dataset lookup, no
import of `load_v2_pool`/`load_core_pool`/any split-loading function, and no
reference anywhere in this file to `artifacts/v4_diagnostic/` or any
val/test split. The caller (`run_four_dim_training.py`) is responsible for
passing ONLY the train-subset of examples; this module has no way to reach
anything else. `test_loss_weighting.py` asserts this both by contract (this
module imports nothing dataset-shaped) and by behavior (weights computed
from a small crafted train-only example list are unaffected by unrelated
val/test/V4-shaped data that is never passed in).

FORMULA (documented in detail, see module docstring section below and the
design-review doc): standard `BCEWithLogitsLoss`-style `pos_weight` per
CORAL threshold, `pos_weight_k = clip(neg_count_k / pos_count_k, clip_min,
clip_max)`, computed independently per dimension and per threshold from the
TRAINING split's own tier histogram for that dimension. This is the
`torch.nn.functional.binary_cross_entropy_with_logits(..., pos_weight=...)`
convention: since CORAL's threshold k asks the binary question "is tier >
k?", `pos_weight_k < 1` DOWN-weights the (here, typically majority) positive
class relative to the (here, typically minority) negative class at that
threshold, which is exactly the direction needed to counteract the training
pool's own tier-3/4-heavy skew on `technical_correctness` and
`relevance_completeness` without touching label encoding, CORAL decoding,
or the ordinal rank-consistency guarantee (which lives entirely in
`CoralOrdinalHead`'s monotonic bias structure — completely untouched by
loss weighting).
"""
from __future__ import annotations

from typing import Optional, Sequence

from model_dataset import score_to_tier

DEFAULT_CLIP: tuple[float, float] = (1.0 / 3.0, 3.0)
DEFAULT_WEIGHTED_DIMENSIONS: tuple[str, ...] = ("technical_correctness", "relevance_completeness")


def pos_weight_from_tier_counts(
    tier_counts: dict[int, int],
    num_classes: int = 5,
    clip: tuple[float, float] = DEFAULT_CLIP,
) -> list[float]:
    """Pure function: given a `{tier: count}` histogram (already computed
    from SOME set of examples — this function has no opinion on which set,
    that responsibility belongs to the caller), returns one `pos_weight`
    per CORAL threshold `k = 0..num_classes-2`.

    threshold k's binary sub-problem is "is tier > k?" (CORAL's own
    `coral_targets` definition, unchanged): positives = examples with
    tier > k, negatives = examples with tier <= k.

        pos_weight_k = clip(negatives_k / positives_k, clip_min, clip_max)

    Edge cases (avoid divide-by-zero, avoid unbounded weights — "avoid
    extreme weights" per the design review):
      - positives_k == 0 (no training example exceeds this threshold at
        all): the positive class is maximally rare/absent -> clip_max (the
        weight ceiling, not an unbounded value).
      - negatives_k == 0 (every training example exceeds this threshold):
        the negative class is absent -> clip_min (the weight floor).
    """
    clip_min, clip_max = clip
    weights: list[float] = []
    for k in range(num_classes - 1):
        positives = sum(c for tier, c in tier_counts.items() if tier > k)
        negatives = sum(c for tier, c in tier_counts.items() if tier <= k)
        if positives == 0:
            raw = clip_max
        elif negatives == 0:
            raw = clip_min
        else:
            raw = negatives / positives
        weights.append(max(clip_min, min(clip_max, raw)))
    return weights


def tier_counts_from_examples(examples: Sequence, dimension_name: str) -> dict[int, int]:
    """Builds a `{tier: count}` histogram for one dimension from a sequence
    of `TrainingExample`-shaped objects (duck-typed: only
    `.labels.dimension_labels[i].name`/`.score` are read — matches
    `model_dataset.collate_fn`'s own label access pattern, so binning is
    guaranteed consistent with what training actually targets). Examples
    missing a label for `dimension_name` are skipped (same "presence-only"
    masking rule `collate_fn` already uses for the canonical four-dimension
    scheme)."""
    counts: dict[int, int] = {}
    for example in examples:
        labels_by_name = {d.name: d.score for d in example.labels.dimension_labels}
        if dimension_name not in labels_by_name:
            continue
        tier = score_to_tier(labels_by_name[dimension_name])
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def compute_dimension_pos_weights(
    train_examples: Sequence,
    dimension_names: tuple[str, ...],
    num_classes: int = 5,
    weighted_dimensions: tuple[str, ...] = DEFAULT_WEIGHTED_DIMENSIONS,
    clip: tuple[float, float] = DEFAULT_CLIP,
) -> dict[str, Optional[list[float]]]:
    """Top-level entry point. `train_examples` MUST be the caller's
    train-split subset only (this function does not know or care where they
    came from — it is the caller's contract to uphold, exactly as
    `run_four_dim_training.train()` already isolates `train_loader` from
    `val_loader`/`test_loader` via `DatasetSplit`).

    Returns one entry per `dimension_names`: a list of `num_classes - 1`
    pos_weight floats for dimensions in `weighted_dimensions`, or `None`
    for every other dimension (meaning: use plain unweighted BCE for that
    dimension, byte-identical to the current V3 behavior) — this is what
    makes `depth_specificity`/`grounding_ownership` stay exactly as they
    are in V3 by default, per the design review's "don't over-engineer
    weighting for grounding" instruction, while still being generically
    overridable via `weighted_dimensions` if a future experiment wants to.
    """
    result: dict[str, Optional[list[float]]] = {}
    for name in dimension_names:
        if name not in weighted_dimensions:
            result[name] = None
            continue
        counts = tier_counts_from_examples(train_examples, name)
        result[name] = pos_weight_from_tier_counts(counts, num_classes=num_classes, clip=clip)
    return result
