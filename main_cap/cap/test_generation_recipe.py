"""Tests for generation_recipe.py — Dataset Generation RFC Section 5/6, Promptbook Section 5/6."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from evaluation_result import ConceptObservationStatus
from generation_recipe import GenerationRecipe, sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import ConceptInclusionTarget, ContradictionType, QualityTier, ReasoningCategoryTarget


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis", "FastAPI"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_produce_same_recipe(self):
        r1 = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching", "eviction policy"), QualityTier.GOOD)
        r2 = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching", "eviction policy"), QualityTier.GOOD)
        self.assertEqual(r1, r2)

    def test_different_recipe_id_can_produce_different_targets(self):
        results = {
            sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.ADEQUATE).concept_targets
            for i in range(30)
        }
        self.assertGreater(len(results), 1, "expected variation across recipe_ids at ADEQUATE tier")


class TestConceptTargets(unittest.TestCase):
    def test_one_target_per_expected_concept(self):
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching", "eviction policy"), QualityTier.GOOD)
        self.assertEqual({t.concept for t in recipe.concept_targets}, {"caching", "eviction policy"})

    def test_excellent_tier_skews_toward_demonstrated(self):
        statuses = [
            t.status
            for i in range(50)
            for t in sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.EXCELLENT).concept_targets
        ]
        demonstrated_ratio = statuses.count(ConceptObservationStatus.DEMONSTRATED) / len(statuses)
        self.assertGreater(demonstrated_ratio, 0.5)

    def test_poor_tier_skews_toward_omitted(self):
        statuses = [
            t.status
            for i in range(50)
            for t in sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.POOR).concept_targets
        ]
        omitted_ratio = statuses.count(ConceptObservationStatus.OMITTED) / len(statuses)
        self.assertGreater(omitted_ratio, 0.5)

    def test_not_every_excellent_example_demonstrates_everything(self):
        """Dataset Generation RFC Section 5 — probabilistic, not rigid, to
        avoid a spurious 'any gap => overall poor' shortcut."""
        statuses = {
            t.status
            for i in range(50)
            for t in sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.EXCELLENT).concept_targets
        }
        self.assertIn(ConceptObservationStatus.SUPERFICIAL, statuses | {ConceptObservationStatus.OMITTED})


class TestReasoningTargets(unittest.TestCase):
    def test_absent_target_has_zero_severity(self):
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, (), QualityTier.EXCELLENT)
        for t in recipe.reasoning_targets:
            if not t.present:
                self.assertEqual(t.severity, 0.0)

    def test_present_target_has_positive_severity(self):
        found_present = False
        for i in range(50):
            recipe = sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, (), QualityTier.POOR)
            for t in recipe.reasoning_targets:
                if t.present:
                    found_present = True
                    self.assertGreater(t.severity, 0.0)
        self.assertTrue(found_present)

    def test_only_relevant_categories_targeted(self):
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.RECALL, (), QualityTier.GOOD)
        categories = {t.category for t in recipe.reasoning_targets}
        self.assertNotIn("debugging", categories)  # RECALL never relevant to debugging


class TestOffTopic(unittest.TestCase):
    def test_off_topic_has_no_targets(self):
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.OFF_TOPIC)
        self.assertEqual(recipe.concept_targets, ())
        self.assertEqual(recipe.reasoning_targets, ())
        self.assertTrue(recipe.is_off_topic)


class TestContradictory(unittest.TestCase):
    def test_contradictory_has_exactly_one_type(self):
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.CONTRADICTORY)
        self.assertTrue(recipe.is_contradictory)
        self.assertIsInstance(recipe.contradiction_type, ContradictionType)

    def test_contradictory_still_carries_concept_targets(self):
        """Promptbook Section 3: contradictory answers are otherwise
        normal-quality, so concept/reasoning targets are still sampled."""
        recipe = sample_recipe("r1", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.CONTRADICTORY)
        self.assertEqual({t.concept for t in recipe.concept_targets}, {"caching"})

    def test_contradiction_type_deterministic_but_varies_across_ids(self):
        types = {
            sample_recipe(f"r{i}", _spec(), "Q?", ReasoningType.DEBUGGING, (), QualityTier.CONTRADICTORY).contradiction_type
            for i in range(20)
        }
        self.assertGreater(len(types), 1)


class TestRecipeValidation(unittest.TestCase):
    def test_off_topic_recipe_with_targets_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            GenerationRecipe(
                recipe_id="r1", specification=_spec(), question_text="Q?", reasoning_type=ReasoningType.DEBUGGING,
                quality_tier=QualityTier.OFF_TOPIC, is_off_topic=True,
                concept_targets=(ConceptInclusionTarget(concept="x", status=ConceptObservationStatus.OMITTED),),
                diversity_seed="d", style_seed="s",
            )

    def test_contradictory_recipe_without_type_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            GenerationRecipe(
                recipe_id="r1", specification=_spec(), question_text="Q?", reasoning_type=ReasoningType.DEBUGGING,
                quality_tier=QualityTier.CONTRADICTORY, is_contradictory=True,
                diversity_seed="d", style_seed="s",
            )


if __name__ == "__main__":
    unittest.main()
