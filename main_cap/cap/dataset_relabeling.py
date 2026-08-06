"""
Dataset Relabeling — Stage 1A of the DeBERTa Training-Data Augmentation
milestone (design reviewed and frozen across the preceding session's design
conversation; this module implements Part 1 of that design, "Per-Dimension
Labels", exactly as specified).

PROBLEM THIS FIXES: `training_example_assembler._dimension_labels()` writes
the SAME score into every relevant dimension for a synthetic example, driven
purely by `quality_tier` (excellent=0.90, good=0.70, ...). Every dimension
moves in lockstep — the model has never been trained on an example where
`technical_accuracy` is high while `communication` is poor, or where
`architecture` is strong while `debugging` is weak. This module fixes that
WITHOUT any new generation: `GenerationRecipe` already samples
per-reasoning-category presence/severity (`intended_reasoning_category_targets`)
and per-concept inclusion targets (`intended_concept_inclusion`), and both are
already serialized on every synthetic `TrainingExample`'s `synthetic` field.
This module reads that already-computed data and re-derives dimension scores
from it — a pure relabeling pass, zero new API calls, zero new text.

TWO DETERMINISTIC RULES (design Part 1, unchanged from the reviewed design):

1. Dimensions with a 1:1 `MissingReasoningCategory` counterpart
   (architecture, tradeoffs, debugging, testing, scalability, ownership,
   communication): score = tier_baseline - severity, when that category's
   `ReasoningCategoryTarget.present` is True; tier_baseline unchanged
   otherwise. Clamped to [0.0, 1.0].

2. `completeness`: score = the fraction of `intended_concept_inclusion`
   entries whose status is NOT `OMITTED` (a concept flagged
   `SUPERFICIAL` still counts as "covered" for completeness purposes —
   completeness measures BREADTH of coverage, not depth; depth is a
   different dimension's job, and this module does not touch it). Falls
   back to the tier baseline when an example carries no concept targets
   at all (off-topic recipes, by the Off-Topic Controller's own override —
   Promptbook Section 2 — never carry concept targets; there is nothing to
   compute a ratio from, so completeness stays at the off-topic floor).

EVERYTHING ELSE STAYS TIER-FLAT, DELIBERATELY: `technical_accuracy` (the
tier's own primary axis — this module does not second-guess it),
`technical_depth` and `resume_grounding` (no recipe-derived signal exists
for either — inventing one was explicitly rejected in the design review
rather than done under time pressure), and `authenticity` (never appears in
`relevant_dimensions()`'s output for any `ReasoningType` today, so it is
never present in `dimension_labels` to begin with — untouched, out of
scope for Stage 1A per the reviewed design's Phase 2 boundary).

DELIBERATE LOCAL DUPLICATION (same "deliberate independence between
pipeline stages" precedent `generation_validation.py` already establishes
for its own marker/vocabulary tables, rather than importing
`heuristic_evaluator.py` internals): the tier-baseline table and the
dimension-to-category mapping are each small, already-frozen-in-spirit
lookup tables defined privately in `training_example_assembler.py` and
`generation_recipe.py` respectively. Re-deriving already-serialized data is
this module's entire purpose, so it duplicates those two tables locally
rather than reaching into another module's private (underscore-prefixed)
names — the same reasoning already applied elsewhere in this codebase.

NOT TOUCHED BY THIS MODULE: `overall_label` (still a flat function of
quality tier — revisiting that is explicitly out of scope for Stage 1A per
the reviewed design), `missing_reasoning_labels`/`concept_labels`/
`contradiction_label` (already correct, derived from the same recipe data
this module reads, untouched here), `answer_text`, `provenance`, or any
other field. This module's only effect is replacing
`TrainingExample.labels.dimension_labels`.
"""

from __future__ import annotations

from evaluation_result import ConceptObservationStatus, MissingReasoningCategory
from reasoning_dimension_relevance import COMPLETENESS, relevant_dimensions
from training_example import DimensionLabel, QualityTier, TrainingExample

# ── Duplicated lookup tables (see module docstring for why) ────────────────

# Mirrors training_example_assembler._TIER_DIMENSION_SCORE exactly — the
# ground-truth target every relevant dimension started from before this
# module's per-dimension adjustment is layered on top.
_TIER_DIMENSION_BASELINE: dict[QualityTier, float] = {
    QualityTier.EXCELLENT: 0.90,
    QualityTier.GOOD: 0.70,
    QualityTier.ADEQUATE: 0.50,
    QualityTier.WEAK: 0.30,
    QualityTier.POOR: 0.12,
    QualityTier.OFF_TOPIC: 0.05,
    QualityTier.CONTRADICTORY: 0.70,
}

# Mirrors generation_recipe._DIMENSION_TO_CATEGORY exactly — which
# dimensions have a 1:1 MissingReasoningCategory counterpart the recipe
# already sampled a presence/severity target for.
_DIMENSION_TO_REASONING_CATEGORY: dict[str, str] = {
    "architecture": MissingReasoningCategory.ARCHITECTURE,
    "tradeoffs": MissingReasoningCategory.TRADEOFF,
    "debugging": MissingReasoningCategory.DEBUGGING,
    "testing": MissingReasoningCategory.TESTING,
    "scalability": MissingReasoningCategory.SCALABILITY,
    "ownership": MissingReasoningCategory.OWNERSHIP,
    "communication": MissingReasoningCategory.COMMUNICATION,
}


def _require_unit_interval_clamped(value: float) -> float:
    """Clamp to [0.0, 1.0] — a large sampled severity subtracted from a low
    tier baseline (e.g. POOR's 0.12 minus a 0.95 severity) must never
    produce a score `DimensionLabel` itself would reject."""
    return max(0.0, min(1.0, value))


def _reasoning_derived_score(
    dimension_name: str, baseline: float, targets_by_category: dict[str, object],
) -> float:
    """Rule 1 (module docstring). Returns `baseline` unchanged for any
    dimension with no reasoning-category counterpart, or when the recipe
    never targeted that category as present for this example — this is a
    correction applied ON TOP of the tier baseline, never a replacement of
    it."""
    category = _DIMENSION_TO_REASONING_CATEGORY.get(dimension_name)
    if category is None:
        return baseline
    target = targets_by_category.get(category)
    if target is None or not target.present:
        return baseline
    return _require_unit_interval_clamped(baseline - target.severity)


def _completeness_score(baseline: float, concept_targets: tuple) -> float:
    """Rule 2 (module docstring)."""
    if not concept_targets:
        return baseline
    covered = sum(1 for t in concept_targets if t.status != ConceptObservationStatus.OMITTED)
    return covered / len(concept_targets)


def relabel_dimension_scores(example: TrainingExample) -> tuple[DimensionLabel, ...]:
    """Recomputes the full `dimension_labels` tuple for one synthetic
    `TrainingExample` from its own already-serialized `synthetic` recipe
    data. Raises if `example.synthetic` is None (a real-session example
    carries no recipe data to relabel from at all — this function is only
    meaningful for synthetic examples; `relabel_example` below is the
    caller-facing function that handles that case gracefully instead of
    raising)."""
    if example.synthetic is None:
        raise ValueError(
            "relabel_dimension_scores requires a synthetic example "
            "(example.synthetic is None) — there is no recipe data to relabel from"
        )

    tier = example.synthetic.intended_quality_tier
    baseline = _TIER_DIMENSION_BASELINE[tier]
    dims = relevant_dimensions(example.inputs.reasoning_type)
    targets_by_category = {t.category: t for t in example.synthetic.intended_reasoning_category_targets}
    concept_targets = example.synthetic.intended_concept_inclusion

    labels = []
    for name in sorted(dims):
        if name == COMPLETENESS:
            score = _completeness_score(baseline, concept_targets)
        else:
            score = _reasoning_derived_score(name, baseline, targets_by_category)
        labels.append(DimensionLabel(name=name, score=score))
    return tuple(labels)


def relabel_example(example: TrainingExample) -> TrainingExample:
    """Returns a NEW `TrainingExample` (via `model_copy`, the same
    never-mutate-in-place discipline `dataset_manifest.py` already
    established) with `labels.dimension_labels` replaced by
    `relabel_dimension_scores`'s output. Every other field — `answer_text`,
    `concept_labels`, `missing_reasoning_labels`, `contradiction_label`,
    `overall_label`, `provenance`, `metadata` — is untouched.

    A real-session example (`example.synthetic is None`) is returned
    UNCHANGED: there is no recipe data to relabel from, and inventing one
    would violate this pipeline's evidence discipline (the same "never
    invented" rule already enforced throughout `training_example.py`).
    None exist in the current dataset, but this keeps the function safe to
    run against a future mixed synthetic/real-session dataset without
    silently mishandling the real-session portion."""
    if example.synthetic is None:
        return example
    new_dimension_labels = relabel_dimension_scores(example)
    new_labels = example.labels.model_copy(update={"dimension_labels": new_dimension_labels})
    return example.model_copy(update={"labels": new_labels})
