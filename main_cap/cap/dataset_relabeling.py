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

TWO DETERMINISTIC RULES (design Part 1, revised this session — see
"REVISION" note below for what changed and why):

1. Dimensions with a 1:1 `MissingReasoningCategory` counterpart
   (architecture, tradeoffs, debugging, testing, scalability, ownership,
   communication): score = tier_baseline * (1 - severity), when that
   category's `ReasoningCategoryTarget.present` is True; tier_baseline
   unchanged otherwise. Clamped to [0.0, 1.0]. Severity is interpreted as
   a PROPORTIONAL reduction of the tier's own ceiling, not an absolute
   point deduction — see "REVISION 2" below for why.

2. `completeness`: measures BREADTH of topic coverage (depth is a
   different dimension's job, untouched here). Two sub-cases, both derived
   from data the recipe already sampled — never invented:

   a. When the example carries `intended_concept_inclusion` targets
      (i.e. `expected_concepts` was non-empty at recipe-sampling time):
      score = the fraction of those targets whose status is NOT `OMITTED`
      (a concept flagged `SUPERFICIAL` still counts as "covered" — breadth,
      not depth).

   b. When the example carries NO concept targets (true for reasoning
      types with no checkable technical concepts to target at all —
      REFLECTION/OWNERSHIP-shaped questions, per
      `reasoning_dimension_relevance.DIMENSION_RELEVANCE` — even though
      `completeness` is still requested for every example via
      `_ALWAYS_RELEVANT`): this is NOT "concept completeness" (there is no
      concept evidence to measure), it is "coverage of the required
      reasoning" instead — a deliberately different but equally
      evidence-grounded notion of breadth. Score is approximated from
      `intended_reasoning_category_targets`, the ONLY other already-
      serialized breadth-relevant signal the recipe sampled for this
      example: a presence-weighted average of (1 - severity) across every
      sampled reasoning-category target (not just the 7 with a 1:1
      dimension mapping — EXAMPLE/METRICS/EDGE_CASE/DESIGN_DECISION count
      too here, since they're evidence of reasoning breadth even though
      they have no dedicated scoring dimension of their own). Categories
      that rolled "not present" contribute a full 1.0 (nothing omitted
      there). Falls back to the tier baseline only when an example has
      NEITHER concept targets NOR reasoning targets at all (true off-topic
      recipes, by the Off-Topic Controller's own override — Promptbook
      Section 2 — carry neither; there is nothing to compute a ratio from).

REVISION 2 (this session, replacing the original subtractive rule for Rule
1): verification found `baseline - severity` saturates to a hard 0.0 for
100% of "present" cases on WEAK/POOR tiers, because
`generation_recipe._REASONING_GAP_PROFILE`'s severity floor for those two
tiers (0.50 / 0.65) already exceeds their own dimension baseline (0.30 /
0.12) — subtraction goes negative before clamping ever engages, collapsing
what should be a graded signal into a binary one. Root-caused, and fixed
HERE (interpretation only) rather than by retuning the generation profile,
per this project's "don't touch upstream unless downstream interpretation
cannot solve the problem" discipline: `_REASONING_GAP_PROFILE` is frozen,
untouched, exactly as it was. Verified against the real dataset (2,479
examples) that the proportional mapping (a) never saturates to exactly 0.0
for any sampled severity, (b) preserves tier ordering in aggregate (mean
present-case score is monotonically POOR < WEAK < ADEQUATE < GOOD <
EXCELLENT across all 5 affected dimensions), and (c) gives markedly more
within-tier gradation than every other downstream mapping tried (highest
coefficient-of-variation of severity-only-linear, exponential, sqrt-
dampened, and floor-clamped alternatives). One accepted property, verified
and judged healthy rather than a defect: per-EXAMPLE score ranges for
adjacent tiers still overlap at the boundary (e.g. a POOR example with no
gap present scores the same 0.12 as a WEAK example with a severe one) —
this is smaller than the overlap that already existed pre-fix for the
non-saturating tiers (ADEQUATE/GOOD/EXCELLENT), not a new defect, and
reflects realistic per-example variance rather than the artificial,
trivially-separable tiers a stricter mapping would produce.

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
    """Clamp to [0.0, 1.0] — belt-and-braces only. The proportional mapping
    (`baseline * (1 - severity)`) can never itself go outside [0.0,
    baseline] for any severity in [0.0, 1.0], so this only guards against
    a future `_TIER_DIMENSION_BASELINE` or severity range change breaking
    that invariant silently."""
    return max(0.0, min(1.0, value))


def _reasoning_derived_score(
    dimension_name: str, baseline: float, targets_by_category: dict[str, object],
) -> float:
    """Rule 1 (module docstring). Returns `baseline` unchanged for any
    dimension with no reasoning-category counterpart, or when the recipe
    never targeted that category as present for this example. When present,
    severity is interpreted as a PROPORTIONAL reduction of the tier's own
    ceiling (`baseline * (1 - severity)`), not an absolute point deduction
    — see "REVISION 2" in the module docstring for why this replaced the
    original subtractive rule."""
    category = _DIMENSION_TO_REASONING_CATEGORY.get(dimension_name)
    if category is None:
        return baseline
    target = targets_by_category.get(category)
    if target is None or not target.present:
        return baseline
    return _require_unit_interval_clamped(baseline * (1.0 - target.severity))


def _completeness_score(
    baseline: float, concept_targets: tuple, reasoning_targets: tuple,
) -> float:
    """Rule 2 (module docstring). Two sub-cases:

    (a) Concept targets exist: score = fraction of `concept_targets` NOT
        `OMITTED` — concept coverage, the original Stage 1A rule.

    (b) No concept targets, but reasoning targets exist: score =
        presence-weighted average of `(1 - severity)` across ALL sampled
        `reasoning_targets` (every category the recipe sampled for this
        example, not only the 7 with a dedicated scoring dimension) — a
        deliberately different notion of breadth ("coverage of the
        required reasoning" rather than "coverage of expected concepts"),
        used only because it is the sole other already-serialized signal
        available; never invented.

    Falls back to `baseline` only when both are empty (true off-topic
    recipes carry neither)."""
    if concept_targets:
        covered = sum(1 for t in concept_targets if t.status != ConceptObservationStatus.OMITTED)
        return covered / len(concept_targets)
    if reasoning_targets:
        per_category = [
            (1.0 - t.severity) if t.present else 1.0
            for t in reasoning_targets
        ]
        return sum(per_category) / len(per_category)
    return baseline


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
    reasoning_targets = example.synthetic.intended_reasoning_category_targets
    targets_by_category = {t.category: t for t in reasoning_targets}
    concept_targets = example.synthetic.intended_concept_inclusion

    labels = []
    for name in sorted(dims):
        if name == COMPLETENESS:
            score = _completeness_score(baseline, concept_targets, reasoning_targets)
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
