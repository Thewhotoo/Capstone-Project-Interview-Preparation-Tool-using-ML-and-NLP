"""Tests for deterministic_rewrite_pipeline.py — Experiment 4 (Rewrite
Augmentation) Track B: the API-free orchestration entry point."""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
import deterministic_rewrite_pipeline as pipeline_module
from deterministic_rewrite_pipeline import (
    DETERMINISTIC_REWRITE_PROMPT_ID,
    DETERMINISTIC_REWRITE_PROMPT_VERSION,
    deterministic_rewrite_batch,
    deterministic_rewrite_training_example,
)
from rewrite_generation_pipeline import RewriteRejectedError, RewriteUnit
from training_example import QualityTier, TrainingExample
from training_example_assembler import assemble_training_example


def _module_imports(module) -> set:
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestPipelineNeverImportsLLMClients(unittest.TestCase):
    """The whole point of Track B: this module must never import
    `google.genai`, and must never reach for the Gemini implementations
    -- only local, deterministic ones. (The module docstring legitimately
    NAMES the Gemini classes in prose, contrasting this pipeline with
    them -- so this checks actual import statements only, not text.)"""

    FORBIDDEN_MODULES = {"google.genai", "google", "genai"}

    def test_no_genai_import(self):
        self.assertFalse(_module_imports(pipeline_module) & self.FORBIDDEN_MODULES)


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _source_example(tier=QualityTier.GOOD, concepts=("caching",), recipe_id="r1") -> TrainingExample:
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING, concepts, tier)
    # Mirrors the real dataset's own template shape (generation_client.
    # FakeGenerationClient) so the deterministic transforms' template-aware
    # compression actually has something to compress in these tests, not
    # just generic filler words.
    answer_parts = ["I worked on this directly and can walk through what I did."]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept} — demonstrated with concrete functional detail.")
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


class TestDeterministicRewriteTrainingExample(unittest.TestCase):
    def test_successful_rewrite_returns_outcome_with_one_attempt(self):
        source = _source_example()
        outcome = deterministic_rewrite_training_example(source, "concise", "batch_1")
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(outcome.style, "concise")
        self.assertEqual(outcome.source_example_id, source.metadata.example_id)
        self.assertEqual(outcome.generation_prompt_id, DETERMINISTIC_REWRITE_PROMPT_ID)
        self.assertEqual(outcome.prompt_version, DETERMINISTIC_REWRITE_PROMPT_VERSION)

    def test_outcome_traces_back_to_source(self):
        source = _source_example()
        outcome = deterministic_rewrite_training_example(source, "reflective", "batch_1")
        self.assertEqual(outcome.example.synthetic.rewritten_from_example_id, source.metadata.example_id)
        self.assertEqual(outcome.example.synthetic.rewrite_style, "reflective")
        self.assertEqual(outcome.example.synthetic.generator_model, "deterministic-rule-based-v1")

    def test_dimension_and_overall_labels_copied_verbatim(self):
        source = _source_example()
        outcome = deterministic_rewrite_training_example(source, "conversational", "batch_1")
        self.assertEqual(outcome.example.labels.dimension_labels, source.labels.dimension_labels)
        self.assertEqual(outcome.example.labels.overall_label, source.labels.overall_label)

    def test_unsupported_style_propagates_as_value_error(self):
        source = _source_example()
        with self.assertRaises(ValueError):
            deterministic_rewrite_training_example(source, "verbose", "batch_1")


class TestDeterministicRewriteBatch(unittest.TestCase):
    def test_generates_one_outcome_per_unit(self):
        source = _source_example()
        units = (
            RewriteUnit(source_example=source, style="concise"),
            RewriteUnit(source_example=source, style="conversational"),
            RewriteUnit(source_example=source, style="reflective"),
        )
        outcomes = deterministic_rewrite_batch(units, "batch_1")
        self.assertEqual(len(outcomes), 3)
        self.assertEqual({o.style for o in outcomes}, {"concise", "conversational", "reflective"})

    def test_each_outcome_traces_to_its_own_source(self):
        source_a = _source_example(recipe_id="r_a")
        source_b = _source_example(recipe_id="r_b")
        units = (
            RewriteUnit(source_example=source_a, style="concise"),
            RewriteUnit(source_example=source_b, style="concise"),
        )
        outcomes = deterministic_rewrite_batch(units, "batch_1")
        ids = {o.example.synthetic.rewritten_from_example_id for o in outcomes}
        self.assertEqual(ids, {source_a.metadata.example_id, source_b.metadata.example_id})


if __name__ == "__main__":
    unittest.main()
