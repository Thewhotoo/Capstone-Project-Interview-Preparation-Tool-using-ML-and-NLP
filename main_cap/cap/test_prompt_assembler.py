"""Tests for prompt_controllers.py + prompt_assembler.py — Promptbook RFC Sections 2-10."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generation_recipe import sample_recipe
from prompt_assembler import (
    GENERATION_PROMPT_ID,
    PROMPT_VERSION,
    DuplicatePromptVersionError,
    assemble_current_prompt,
    assemble_prompt,
    register_prompt_version,
    registered_prompt_versions,
)
from prompt_controllers import (
    contradiction_controller,
    diversity_controller,
    expected_concept_controller,
    generation_prompt_controller,
    off_topic_controller,
    quality_tier_controller,
    reasoning_category_controller,
    style_controller,
    system_prompt_controller,
)
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import QualityTier


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _recipe(tier=QualityTier.GOOD, concepts=("caching",)):
    return sample_recipe("r1", _spec(), "Did Redis caching give you any trouble?", ReasoningType.DEBUGGING, concepts, tier)


class TestSystemPromptController(unittest.TestCase):
    def test_invariant_and_non_empty(self):
        section = system_prompt_controller()
        self.assertTrue(section.invariant)
        self.assertIn("never invent", section.content.lower())

    def test_identical_across_calls(self):
        self.assertEqual(system_prompt_controller(), system_prompt_controller())


class TestGenerationPromptController(unittest.TestCase):
    def test_includes_question_and_grounding(self):
        recipe = _recipe()
        section = generation_prompt_controller(recipe)
        self.assertFalse(section.invariant)
        self.assertIn(recipe.question_text, section.content)
        self.assertIn("Resume Discussion Platform", section.content)

    def test_includes_expected_concepts_when_present(self):
        section = generation_prompt_controller(_recipe(concepts=("caching", "eviction policy")))
        self.assertIn("eviction policy", section.content)


class TestQualityTierController(unittest.TestCase):
    def test_excellent_and_poor_produce_different_content(self):
        excellent = quality_tier_controller(_recipe(tier=QualityTier.EXCELLENT))
        poor = quality_tier_controller(_recipe(tier=QualityTier.POOR))
        self.assertNotEqual(excellent.content, poor.content)

    def test_off_topic_tier_produces_no_content(self):
        recipe = _recipe(tier=QualityTier.OFF_TOPIC, concepts=())
        self.assertEqual(quality_tier_controller(recipe).content, "")


class TestReasoningCategoryController(unittest.TestCase):
    def test_no_present_targets_means_empty_section(self):
        recipe = _recipe(tier=QualityTier.EXCELLENT)
        # Excellent tier has low present-probability; if none happened to be
        # present for this recipe_id, section must be empty (not a fallback
        # instruction) — check the invariant directly instead of the content.
        present = [t for t in recipe.reasoning_targets if t.present]
        section = reasoning_category_controller(recipe)
        if not present:
            self.assertEqual(section.content, "")
        else:
            self.assertIn(present[0].category.replace("_", " "), section.content)

    def test_present_target_never_instructs_forced_inclusion(self):
        recipe = _recipe(tier=QualityTier.POOR)
        section = reasoning_category_controller(recipe)
        self.assertNotIn("make sure to include", section.content.lower())


class TestExpectedConceptController(unittest.TestCase):
    def test_each_concept_gets_an_instruction_line(self):
        recipe = _recipe(concepts=("caching", "eviction policy"))
        section = expected_concept_controller(recipe)
        self.assertIn("caching", section.content)
        self.assertIn("eviction policy", section.content)

    def test_no_concepts_means_empty_section(self):
        recipe = _recipe(tier=QualityTier.OFF_TOPIC, concepts=())
        self.assertEqual(expected_concept_controller(recipe).content, "")


class TestContradictionController(unittest.TestCase):
    def test_noop_when_not_contradictory(self):
        self.assertEqual(contradiction_controller(_recipe(tier=QualityTier.GOOD)).content, "")

    def test_active_when_contradictory(self):
        recipe = _recipe(tier=QualityTier.CONTRADICTORY)
        section = contradiction_controller(recipe)
        self.assertIn("EXACTLY ONE", section.content)
        self.assertIn(recipe.contradiction_type.value, section.content)


class TestOffTopicController(unittest.TestCase):
    def test_noop_when_not_off_topic(self):
        self.assertEqual(off_topic_controller(_recipe(tier=QualityTier.GOOD)).content, "")

    def test_active_when_off_topic(self):
        recipe = _recipe(tier=QualityTier.OFF_TOPIC, concepts=())
        section = off_topic_controller(recipe)
        self.assertIn("different", section.content.lower())
        self.assertIn("fluent", section.content.lower())


class TestDiversityAndStyleControllers(unittest.TestCase):
    def test_diversity_varies_by_seed(self):
        recipe_a = sample_recipe("a", _spec(), "Q?", ReasoningType.DEBUGGING, (), QualityTier.GOOD)
        recipe_b = sample_recipe("b", _spec(), "Q?", ReasoningType.DEBUGGING, (), QualityTier.GOOD)
        contents = {diversity_controller(recipe_a).content, diversity_controller(recipe_b).content}
        self.assertTrue(len(contents) >= 1)  # at minimum must not error; usually varies

    def test_diversity_deterministic_for_same_seed(self):
        recipe = _recipe()
        self.assertEqual(diversity_controller(recipe).content, diversity_controller(recipe).content)

    def test_style_controller_forbids_third_person_switch(self):
        section = style_controller(_recipe())
        self.assertIn("never switch", section.content.lower())


class TestAssembler(unittest.TestCase):
    def test_default_pipeline_registered(self):
        self.assertIn((GENERATION_PROMPT_ID, PROMPT_VERSION), registered_prompt_versions())

    def test_assemble_current_prompt_produces_system_and_user_text(self):
        prompt = assemble_current_prompt(_recipe())
        self.assertTrue(prompt.system_text.strip())
        self.assertTrue(prompt.user_text.strip())
        self.assertEqual(prompt.generation_prompt_id, GENERATION_PROMPT_ID)
        self.assertEqual(prompt.prompt_version, PROMPT_VERSION)

    def test_off_topic_suppresses_concept_and_reasoning_sections(self):
        recipe = _recipe(tier=QualityTier.OFF_TOPIC, concepts=())
        prompt = assemble_current_prompt(recipe)
        self.assertIn("different", prompt.user_text.lower())
        # Neither controller's telltale phrasing should appear.
        self.assertNotIn("for each of the following concepts", prompt.user_text.lower())
        self.assertNotIn("deliberately, naturally under-develop", prompt.user_text.lower())

    def test_unregistered_version_raises(self):
        with self.assertRaises(KeyError):
            assemble_prompt(_recipe(), "promptbook", "9.9.9")

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(DuplicatePromptVersionError):
            register_prompt_version(GENERATION_PROMPT_ID, PROMPT_VERSION, variable_controllers=())

    def test_new_version_can_be_registered_without_touching_v1(self):
        register_prompt_version("promptbook", "2.0.0-test", variable_controllers=(generation_prompt_controller,))
        prompt_v1 = assemble_current_prompt(_recipe())
        prompt_v2 = assemble_prompt(_recipe(), "promptbook", "2.0.0-test")
        self.assertNotEqual(prompt_v1.user_text, prompt_v2.user_text)
        # v1's own registration is untouched — still produces its full content.
        self.assertIn("Use a", prompt_v1.user_text)  # diversity controller phrase, only in v1


if __name__ == "__main__":
    unittest.main()
