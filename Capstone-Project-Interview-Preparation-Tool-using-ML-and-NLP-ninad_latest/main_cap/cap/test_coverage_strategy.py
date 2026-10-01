"""
Tests for coverage_strategy.py — Dataset Generation RFC Section 3
(Coverage & Batch Strategy).
"""

import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coverage_strategy import (
    CoverageConfig,
    CoveragePlan,
    CoverageUnit,
    plan_batch,
)
from generation_client import FakeGenerationClient
from question_families import ReasoningType
from question_specification import (
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from synthetic_generation_pipeline import generate_batch
from training_example import QualityTier


def _spec(spec_id: str, category: QuestionCategory, title: str = "Resume Discussion Platform") -> QuestionSpecification:
    if category == QuestionCategory.EXPERIENCE:
        return QuestionSpecification(
            id=spec_id, category=category, text_seed="on-call debugging",
            grounding=Grounding(experience=ExperienceGrounding(role="Engineer", company="Acme")),
            source_type=SourceType.EXPERIENCE, source_id="Acme", source_field="experience", reason="test",
        )
    return QuestionSpecification(
        id=spec_id, category=category, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title=title, technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id=title, source_field="interview_seeds", reason="test",
    )


def _diverse_pool(n_per_type: int = 3) -> tuple:
    """A pool with `n_per_type` units for every ReasoningType, alternating
    category and follow-up-ness, so tests can exercise coverage/round-robin
    behavior without relying on any single reasoning type."""
    units = []
    for rt_index, reasoning_type in enumerate(ReasoningType):
        for i in range(n_per_type):
            category = QuestionCategory.PROJECT_DEEP_DIVE if i % 2 == 0 else QuestionCategory.EXPERIENCE
            units.append(CoverageUnit(
                specification=_spec(f"{reasoning_type.value}_{i}", category),
                question_text=f"Question about {reasoning_type.value} #{i}?",
                reasoning_type=reasoning_type,
                expected_concepts=("caching",),
                is_follow_up=(i == 0),
            ))
    return tuple(units)


class TestCoverageConfig(unittest.TestCase):
    def test_default_config_is_valid(self):
        CoverageConfig()  # must not raise

    def test_rejects_ratio_out_of_range(self):
        with self.assertRaises(ValueError):
            CoverageConfig(follow_up_ratio=1.5)

    def test_rejects_contradiction_plus_off_topic_over_one(self):
        with self.assertRaises(ValueError):
            CoverageConfig(contradiction_ratio=0.6, off_topic_ratio=0.6)

    def test_rejects_core_tier_weights_not_summing_to_one(self):
        with self.assertRaises(ValueError):
            CoverageConfig(core_tier_weights=(0.5, 0.5, 0.5, 0.5, 0.5))

    def test_rejects_wrong_number_of_core_tier_weights(self):
        with self.assertRaises(ValueError):
            CoverageConfig(core_tier_weights=(1.0,))


class TestCoveragePlanValidation(unittest.TestCase):
    def test_rejects_mismatched_lengths(self):
        plan_units = plan_batch(_diverse_pool(), batch_size=5, batch_seed="seed").units
        with self.assertRaises(ValueError):
            CoveragePlan(units=plan_units, quality_tiers=(QualityTier.GOOD,))


class TestPlanBatchValidation(unittest.TestCase):
    def test_rejects_empty_pool(self):
        with self.assertRaises(ValueError):
            plan_batch((), batch_size=5, batch_seed="seed")

    def test_rejects_non_positive_batch_size(self):
        with self.assertRaises(ValueError):
            plan_batch(_diverse_pool(), batch_size=0, batch_seed="seed")


class TestDeterminism(unittest.TestCase):
    def test_identical_inputs_produce_identical_plans(self):
        pool = _diverse_pool()
        plan_a = plan_batch(pool, batch_size=30, batch_seed="batch_007")
        plan_b = plan_batch(pool, batch_size=30, batch_seed="batch_007")
        self.assertEqual([u.recipe_id for u in plan_a.units], [u.recipe_id for u in plan_b.units])
        self.assertEqual(
            [(u.specification.id, u.reasoning_type) for u in plan_a.units],
            [(u.specification.id, u.reasoning_type) for u in plan_b.units],
        )
        self.assertEqual(plan_a.quality_tiers, plan_b.quality_tiers)

    def test_different_seed_can_change_ordering(self):
        pool = _diverse_pool()
        plan_a = plan_batch(pool, batch_size=30, batch_seed="seed_a")
        plan_b = plan_batch(pool, batch_size=30, batch_seed="seed_b")
        self.assertNotEqual(plan_a.quality_tiers, plan_b.quality_tiers)


class TestTierDistribution(unittest.TestCase):
    def test_default_distribution_over_100(self):
        pool = _diverse_pool(n_per_type=15)
        plan = plan_batch(pool, batch_size=100, batch_seed="dist_100")
        counts = collections.Counter(plan.quality_tiers)
        self.assertEqual(counts[QualityTier.EXCELLENT], 18)
        self.assertEqual(counts[QualityTier.GOOD], 18)
        self.assertEqual(counts[QualityTier.ADEQUATE], 18)
        self.assertEqual(counts[QualityTier.WEAK], 18)
        self.assertEqual(counts[QualityTier.POOR], 18)
        self.assertEqual(counts[QualityTier.OFF_TOPIC], 5)
        self.assertEqual(counts[QualityTier.CONTRADICTORY], 5)
        self.assertEqual(sum(counts.values()), 100)

    def test_remainder_goes_to_excellent_downward(self):
        # batch_size=11: off_topic=int(0.55)=0, contradiction=int(0.55)=0,
        # remaining=11 -> 2.2 each floor=2 (x5=10), remainder=1 -> Excellent+1.
        pool = _diverse_pool(n_per_type=5)
        plan = plan_batch(pool, batch_size=11, batch_seed="remainder_test")
        counts = collections.Counter(plan.quality_tiers)
        self.assertEqual(counts[QualityTier.EXCELLENT], 3)
        self.assertEqual(counts[QualityTier.GOOD], 2)
        self.assertEqual(counts[QualityTier.ADEQUATE], 2)
        self.assertEqual(counts[QualityTier.WEAK], 2)
        self.assertEqual(counts[QualityTier.POOR], 2)
        self.assertEqual(sum(counts.values()), 11)

    def test_contradiction_and_off_topic_ratios_are_configurable(self):
        pool = _diverse_pool(n_per_type=10)
        config = CoverageConfig(contradiction_ratio=0.1, off_topic_ratio=0.2)
        plan = plan_batch(pool, batch_size=100, batch_seed="config_test", config=config)
        counts = collections.Counter(plan.quality_tiers)
        self.assertEqual(counts[QualityTier.CONTRADICTORY], 10)
        self.assertEqual(counts[QualityTier.OFF_TOPIC], 20)


class TestReasoningTypeCoverage(unittest.TestCase):
    def test_no_reasoning_type_is_starved(self):
        pool = _diverse_pool(n_per_type=3)
        plan = plan_batch(pool, batch_size=50, batch_seed="rt_coverage")
        seen_types = {unit.reasoning_type for unit in plan.units}
        self.assertEqual(seen_types, set(ReasoningType))

    def test_reasoning_types_are_approximately_balanced(self):
        pool = _diverse_pool(n_per_type=3)
        plan = plan_batch(pool, batch_size=100, batch_seed="rt_balance")
        counts = collections.Counter(unit.reasoning_type for unit in plan.units)
        self.assertEqual(len(counts), len(ReasoningType))
        # Follow-up and primary slots round-robin through independent
        # cursors, so perfect equality across all 10 types isn't always
        # possible when neither sub-count is a multiple of 10 (RFC Section
        # 3: "exact equality is not required when mathematically
        # impossible") — a spread of 2 across two independently-rotating
        # buckets is still "approximately uniform".
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 2)


class TestFollowUpRatio(unittest.TestCase):
    def test_follow_up_count_matches_configured_ratio(self):
        pool = _diverse_pool(n_per_type=3)  # i == 0 marked follow_up, i.e. 1/3 of each type
        plan = plan_batch(pool, batch_size=100, batch_seed="followup_test")
        followup_specs = {
            unit.specification.id for unit in _diverse_pool(n_per_type=3) if unit.is_follow_up
        }
        follow_up_selected = sum(1 for u in plan.units if u.specification.id in followup_specs)
        self.assertEqual(follow_up_selected, int(100 * CoverageConfig().follow_up_ratio))

    def test_falls_back_gracefully_when_no_follow_up_units_in_pool(self):
        pool = tuple(
            CoverageUnit(
                specification=_spec(f"p_{i}", QuestionCategory.PROJECT_DEEP_DIVE),
                question_text="Q?", reasoning_type=ReasoningType.DEBUGGING,
                expected_concepts=("caching",), is_follow_up=False,
            )
            for i in range(5)
        )
        plan = plan_batch(pool, batch_size=10, batch_seed="no_followup")  # must not raise
        self.assertEqual(len(plan.units), 10)

    def test_falls_back_gracefully_when_pool_is_all_follow_up(self):
        pool = tuple(
            CoverageUnit(
                specification=_spec(f"p_{i}", QuestionCategory.PROJECT_DEEP_DIVE),
                question_text="Q?", reasoning_type=ReasoningType.DEBUGGING,
                expected_concepts=("caching",), is_follow_up=True,
            )
            for i in range(5)
        )
        plan = plan_batch(pool, batch_size=10, batch_seed="all_followup")  # must not raise
        self.assertEqual(len(plan.units), 10)


class TestIntegrationWithPipeline(unittest.TestCase):
    def test_plan_wires_into_generate_batch_with_zero_pipeline_changes(self):
        pool = _diverse_pool(n_per_type=3)
        plan = plan_batch(pool, batch_size=20, batch_seed="integration_test")
        outcomes = generate_batch(
            plan.units, client=FakeGenerationClient(), generation_batch_id="batch_integration",
            tier_cycle=plan.quality_tiers,
        )
        actual_tiers = tuple(o.example.synthetic.intended_quality_tier for o in outcomes)
        self.assertEqual(actual_tiers, plan.quality_tiers)


if __name__ == "__main__":
    unittest.main()
