"""Tests for rewrite_prompt_controllers.py + rewrite_prompt_assembler.py —
Experiment 4 (Rewrite Augmentation) Stage."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus, MissingReasoningCategory
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from rewrite_prompt_assembler import (
    REWRITE_GENERATION_PROMPT_ID,
    REWRITE_PROMPT_VERSION,
    assemble_current_rewrite_prompt,
    assemble_rewrite_prompt,
    registered_rewrite_prompt_versions,
)
from rewrite_prompt_controllers import STYLE_TAGS, rewrite_style_instruction_controller
from training_example import ContradictionType, QualityTier, TrainingExample
from training_example_assembler import assemble_training_example
from generation_client import ConceptEvidenceEntry, GenerationOutput


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _source_example(tier=QualityTier.GOOD, concepts=("caching", "eviction policy"), contradictory=False) -> TrainingExample:
    recipe = sample_recipe(
        "r1", _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING,
        concepts, QualityTier.CONTRADICTORY if contradictory else tier,
    )
    answer_parts = ["I worked on this directly."]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept}.")
    note = "Introduced one deliberate contradiction." if recipe.is_contradictory else ""
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence, contradiction_note=note)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


class TestRegistry(unittest.TestCase):
    def test_default_pipeline_is_registered(self):
        self.assertIn((REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION), registered_rewrite_prompt_versions())

    def test_unknown_pipeline_raises(self):
        with self.assertRaises(KeyError):
            assemble_rewrite_prompt(_source_example(), "concise", "nonexistent", "9.9.9")


class TestAssembleRewritePrompt(unittest.TestCase):
    def test_contains_original_answer_text(self):
        source = _source_example()
        prompt = assemble_current_rewrite_prompt(source, "concise")
        self.assertIn(source.inputs.answer_text, prompt.user_text)

    def test_contains_style_instruction(self):
        source = _source_example()
        prompt = assemble_current_rewrite_prompt(source, "reflective")
        self.assertIn("REFLECTIVE", prompt.user_text)

    def test_different_styles_produce_different_prompts(self):
        source = _source_example()
        concise_prompt = assemble_current_rewrite_prompt(source, "concise")
        verbose_prompt = assemble_current_rewrite_prompt(source, "verbose")
        self.assertNotEqual(concise_prompt.user_text, verbose_prompt.user_text)

    def test_system_text_forbids_new_facts(self):
        prompt = assemble_current_rewrite_prompt(_source_example(), "concise")
        self.assertIn("NEVER invent", prompt.system_text)

    def test_stamped_with_correct_prompt_identity(self):
        prompt = assemble_current_rewrite_prompt(_source_example(), "concise")
        self.assertEqual(prompt.generation_prompt_id, REWRITE_GENERATION_PROMPT_ID)
        self.assertEqual(prompt.prompt_version, REWRITE_PROMPT_VERSION)

    def test_concept_preservation_instructions_present_for_each_target(self):
        source = _source_example(concepts=("caching", "eviction policy", "ttl"))
        prompt = assemble_current_rewrite_prompt(source, "concise")
        for target in source.synthetic.intended_concept_inclusion:
            self.assertIn(target.concept, prompt.user_text)

    def test_contradiction_instruction_present_only_when_contradictory(self):
        contradictory_source = _source_example(contradictory=True)
        normal_source = _source_example(contradictory=False)
        contradictory_prompt = assemble_current_rewrite_prompt(contradictory_source, "concise")
        normal_prompt = assemble_current_rewrite_prompt(normal_source, "concise")
        self.assertIn("deliberate contradiction", contradictory_prompt.user_text)
        self.assertNotIn("deliberate contradiction", normal_prompt.user_text)

    def test_unknown_style_raises(self):
        with self.assertRaises(ValueError):
            assemble_current_rewrite_prompt(_source_example(), "not_a_real_style")

    def test_all_style_tags_produce_a_valid_section(self):
        source = _source_example()
        for style in STYLE_TAGS:
            section = rewrite_style_instruction_controller(source, style)
            self.assertTrue(section.content.strip())


if __name__ == "__main__":
    unittest.main()
