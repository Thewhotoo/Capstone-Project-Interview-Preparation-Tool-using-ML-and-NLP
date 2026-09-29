"""Tests for the canonical four-dimension evaluation schema (Step 1).

Verifies the four dimensions exist with stable keys, complete 0-4 rubrics,
explicit non-overlap boundaries that keep them distinct, a legacy
compatibility bridge that partitions the old 12 dimensions, and that
introducing the schema does not break existing evaluation types.
"""

from __future__ import annotations

import pytest

from evaluation_dimensions import (
    CANONICAL_DIMENSIONS,
    LEGACY_DIMENSION_MAP,
    NUM_TIERS,
    RUBRICS,
    TIER_LABELS,
    DimensionRubric,
    EvaluationDimension,
    all_keys,
    canonical_for_legacy,
    rubric_for,
    tier_label,
)


# ── Existence + stable keys ──────────────────────────────────────────────────

def test_exactly_four_dimensions():
    assert len(EvaluationDimension) == 4
    assert len(CANONICAL_DIMENSIONS) == 4
    assert len(RUBRICS) == 4


def test_keys_are_stable():
    # These string values are persisted/keyed on -- pin them so an accidental
    # rename is caught here.
    assert EvaluationDimension.TECHNICAL_CORRECTNESS.value == "technical_correctness"
    assert EvaluationDimension.DEPTH_SPECIFICITY.value == "depth_specificity"
    assert EvaluationDimension.RELEVANCE_COMPLETENESS.value == "relevance_completeness"
    assert EvaluationDimension.GROUNDING_OWNERSHIP.value == "grounding_ownership"


def test_canonical_order_is_stable():
    assert all_keys() == (
        "technical_correctness",
        "depth_specificity",
        "relevance_completeness",
        "grounding_ownership",
    )


def test_not_a_rename_of_legacy_keys():
    # The canonical keys must be genuinely new, not the legacy names.
    legacy_names = {n for names in LEGACY_DIMENSION_MAP.values() for n in names}
    assert set(all_keys()).isdisjoint(legacy_names)


# ── Tier scale ───────────────────────────────────────────────────────────────

def test_tier_scale():
    assert NUM_TIERS == 5
    assert len(TIER_LABELS) == 5
    assert tier_label(0) == "poor"
    assert tier_label(4) == "excellent"
    with pytest.raises(ValueError):
        tier_label(5)
    with pytest.raises(ValueError):
        tier_label(-1)


# ── Rubric completeness ──────────────────────────────────────────────────────

@pytest.mark.parametrize("dimension", list(EvaluationDimension))
def test_every_dimension_has_a_complete_rubric(dimension):
    rubric = rubric_for(dimension)
    assert isinstance(rubric, DimensionRubric)
    assert rubric.key is dimension
    assert rubric.display_name.strip()
    assert rubric.definition.strip()
    assert rubric.applies_to.strip()
    assert rubric.increases and all(s.strip() for s in rubric.increases)
    assert rubric.decreases and all(s.strip() for s in rubric.decreases)


@pytest.mark.parametrize("dimension", list(EvaluationDimension))
def test_rubric_defines_all_five_tier_boundaries(dimension):
    rubric = rubric_for(dimension)
    assert set(rubric.tiers.keys()) == {0, 1, 2, 3, 4}
    assert all(rubric.tiers[t].strip() for t in range(NUM_TIERS))


# ── Contentless-answer rule (forensic repair, seed_v1 048-057 finding) ──────
# The 100-example seed's independent judging pass found the rubric had no
# tier for "no verifiable technical claim at all" (buzzword-only answers like
# "we followed best practices"), causing them to be scored inconsistently
# against a target that expected tier 0. These tests pin the fix: a
# contentless answer must be distinguishable from an outright-wrong one, and
# must default to tier 3 (not penalized here for lack of substance -- that's
# Depth & Specificity's/Relevance & Completeness's job).

def test_technical_correctness_distinguishes_contentless_from_incorrect():
    rubric = rubric_for(EvaluationDimension.TECHNICAL_CORRECTNESS)
    # tier 0/1 describe an actual wrong/misused claim -- never "no claim".
    assert "wrong" in rubric.tiers[0].lower() or "incorrect" in rubric.tiers[0].lower()
    assert "misconception" in rubric.tiers[0].lower() or "incorrect" in rubric.tiers[1].lower()
    # tier 3 explicitly carves out the no-verifiable-claim case, separate
    # from "largely correct with minor imprecisions".
    assert "no verifiable technical claim" in rubric.tiers[3].lower()
    assert "depth" in rubric.tiers[3].lower() or "relevance" in rubric.tiers[3].lower()


def test_technical_correctness_definition_states_contentless_rule():
    rubric = rubric_for(EvaluationDimension.TECHNICAL_CORRECTNESS)
    definition_lower = rubric.definition.lower()
    assert "no verifiable technical claim" in definition_lower
    assert "depth" in definition_lower


def test_technical_correctness_tier_4_requires_substance():
    rubric = rubric_for(EvaluationDimension.TECHNICAL_CORRECTNESS)
    # tier 4 ("fully correct") must not be satisfiable by a contentless
    # answer -- it should explicitly require actual substantive claims.
    assert "contentless" in rubric.tiers[4].lower() or "substantive" in rubric.tiers[4].lower()


# ── Distinctness ─────────────────────────────────────────────────────────────

def test_dimensions_are_distinct():
    keys = all_keys()
    assert len(set(keys)) == 4
    display_names = [rubric_for(d).display_name for d in EvaluationDimension]
    assert len(set(display_names)) == 4
    definitions = [rubric_for(d).definition for d in EvaluationDimension]
    assert len(set(definitions)) == 4


@pytest.mark.parametrize("dimension", list(EvaluationDimension))
def test_non_overlap_covers_the_other_three_dimensions(dimension):
    rubric = rubric_for(dimension)
    others = {d for d in EvaluationDimension if d is not dimension}
    # Each dimension explicitly states how it stays distinct from every other
    # canonical dimension, and never references itself.
    assert set(rubric.must_not_overlap_with.keys()) == others
    assert all(reason.strip() for reason in rubric.must_not_overlap_with.values())


# ── Legacy compatibility bridge ──────────────────────────────────────────────

def test_legacy_map_partitions_the_real_legacy_dimension_set():
    from reasoning_dimension_relevance import ALL_DIMENSIONS

    mapped = [n for names in LEGACY_DIMENSION_MAP.values() for n in names]
    # Every legacy dimension is covered exactly once (a true partition), and
    # no unknown legacy names are introduced -- so the bridge stays in sync
    # with the frozen legacy set without importing it into the module itself.
    assert sorted(mapped) == sorted(ALL_DIMENSIONS)
    assert len(mapped) == len(set(mapped)) == len(ALL_DIMENSIONS)


def test_legacy_map_keys_are_the_canonical_four():
    assert set(LEGACY_DIMENSION_MAP.keys()) == set(EvaluationDimension)


def test_canonical_for_legacy_lookup():
    assert canonical_for_legacy("technical_accuracy") is EvaluationDimension.TECHNICAL_CORRECTNESS
    assert canonical_for_legacy("resume_grounding") is EvaluationDimension.GROUNDING_OWNERSHIP
    assert canonical_for_legacy("completeness") is EvaluationDimension.RELEVANCE_COMPLETENESS
    assert canonical_for_legacy("nonexistent_dimension") is None


# ── Does not break existing evaluation infrastructure ────────────────────────

def test_existing_evaluation_types_still_import_and_work():
    # The canonical schema is additive: legacy dimension infra and the result
    # schema must be unaffected.
    import reasoning_dimension_relevance  # noqa: F401
    from evaluation_result import DimensionScore

    # legacy dimension still constructs
    legacy = DimensionScore(
        name="technical_accuracy", raw_score=0.5, weight_used=1.0,
        confidence=0.9, confidence_source="model_derived",
    )
    assert legacy.name == "technical_accuracy"


def test_canonical_key_is_usable_as_a_dimension_score_name():
    # DimensionScore.name is a free-form string, so a canonical key can be
    # used directly by a future evaluator with no schema change.
    from evaluation_result import DimensionScore

    score = DimensionScore(
        name=EvaluationDimension.GROUNDING_OWNERSHIP.value, raw_score=0.75,
        weight_used=1.0, confidence=0.8, confidence_source="model_derived",
    )
    assert score.name == "grounding_ownership"
