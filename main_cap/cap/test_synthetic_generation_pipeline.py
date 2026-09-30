"""
Tests for synthetic_generation_pipeline.py — Dataset Generation RFC Section
1/8. Includes the import-graph assertion backing Implementation requirement
11: this pipeline must never import the Evaluation Engine, the Conversation
Engine, or DatasetManifest/benchmarking code — it only produces
TrainingExamples.
"""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generation_client import ConceptEvidenceEntry, FakeGenerationClient, GenerationOutput
from prompt_assembler import AssembledPrompt
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import QualityTier
import synthetic_generation_pipeline as pipeline_module
from synthetic_generation_pipeline import (
    BatchUnit,
    DEFAULT_TIER_CYCLE,
    GenerationRejectedError,
    generate_batch,
    generate_training_example,
)


def _module_imports(module) -> set:
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestPipelineStaysWithinItsOwnBoundary(unittest.TestCase):
    FORBIDDEN_MODULES = {
        "evaluator", "evaluator_registry", "heuristic_evaluator", "evaluation_engine",
        "conversation_engine", "conversation_memory", "discussion_policy", "planner", "topic_pool",
    }

    def test_pipeline_never_imports_evaluation_or_conversation_modules(self):
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


class TestGenerateTrainingExample(unittest.TestCase):
    def test_produces_a_valid_example_with_the_fake_client(self):
        outcome = generate_training_example(
            recipe_id="r1", specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            quality_tier=QualityTier.GOOD, client=FakeGenerationClient(), generation_batch_id="batch_1",
        )
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(outcome.example.provenance.collection_batch_id, "batch_1")
        self.assertEqual(outcome.example.synthetic.intended_quality_tier, QualityTier.GOOD)

    def test_off_topic_tier_produces_off_topic_example(self):
        outcome = generate_training_example(
            recipe_id="r1", specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=(),
            quality_tier=QualityTier.OFF_TOPIC, client=FakeGenerationClient(), generation_batch_id="batch_1",
        )
        self.assertTrue(outcome.example.synthetic.is_off_topic)

    def test_contradictory_tier_produces_contradiction_label(self):
        outcome = generate_training_example(
            recipe_id="r1", specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            quality_tier=QualityTier.CONTRADICTORY, client=FakeGenerationClient(), generation_batch_id="batch_1",
        )
        self.assertTrue(outcome.example.labels.contradiction_label.contradiction_present)


class _AlwaysRejectingClient:
    """Deterministically produces output that always fails malformed-output
    validation — used to exercise the reject-and-regenerate path without
    ever accidentally passing."""

    model_name = "always-rejecting"

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        return GenerationOutput(answer_text="")


class _SucceedsOnSecondAttemptClient:
    """Fails attempt 1 (empty answer), succeeds attempt 2 — proves each
    retry samples a genuinely fresh recipe/prompt rather than patching the
    previous failed output (Implementation requirement 10)."""

    model_name = "succeeds-second"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        self.calls += 1
        if self.calls == 1:
            return GenerationOutput(answer_text="")
        return GenerationOutput(
            answer_text="I worked directly on this and used caching extensively for the project.",
            concept_evidence=[ConceptEvidenceEntry(concept="caching", evidence="Used caching extensively.")],
        )


class TestRejectAndRegenerate(unittest.TestCase):
    def test_exhausting_attempts_raises_with_reasons(self):
        with self.assertRaises(GenerationRejectedError) as ctx:
            generate_training_example(
                recipe_id="r1", specification=_spec(), question_text="Q?",
                reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
                quality_tier=QualityTier.GOOD, client=_AlwaysRejectingClient(), generation_batch_id="batch_1",
                max_attempts=2,
            )
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertTrue(ctx.exception.last_reasons)

    def test_succeeds_after_one_retry(self):
        client = _SucceedsOnSecondAttemptClient()
        outcome = generate_training_example(
            recipe_id="r1", specification=_spec(), question_text="Q?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            quality_tier=QualityTier.GOOD, client=client, generation_batch_id="batch_1", max_attempts=3,
        )
        self.assertEqual(outcome.attempts, 2)
        self.assertEqual(client.calls, 2)

    def test_each_attempt_uses_a_distinct_recipe(self):
        """A rejected attempt must never be patched in place — verified by
        confirming attempt 2's diversity_seed differs from attempt 1's
        (different recipe_id salt -> different deterministic seed)."""
        client = _SucceedsOnSecondAttemptClient()
        outcome = generate_training_example(
            recipe_id="r_seed_test", specification=_spec(), question_text="Q?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            quality_tier=QualityTier.GOOD, client=client, generation_batch_id="batch_1", max_attempts=3,
        )
        from generation_recipe import sample_recipe
        first_attempt_recipe = sample_recipe(
            "r_seed_test", _spec(), "Q?", ReasoningType.DEBUGGING, ("caching",), QualityTier.GOOD,
        )
        self.assertNotEqual(outcome.example.synthetic.diversity_seed, first_attempt_recipe.diversity_seed)


class TestGenerateBatch(unittest.TestCase):
    def test_batch_cycles_through_tiers(self):
        units = tuple(
            BatchUnit(
                recipe_id=f"unit_{i}", specification=_spec(), question_text="Q?",
                reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            )
            for i in range(len(DEFAULT_TIER_CYCLE))
        )
        outcomes = generate_batch(units, client=FakeGenerationClient(), generation_batch_id="batch_1")
        tiers = [o.example.synthetic.intended_quality_tier for o in outcomes]
        self.assertEqual(tiers, list(DEFAULT_TIER_CYCLE))

    def test_batch_propagates_rejection_immediately(self):
        units = (
            BatchUnit(recipe_id="unit_0", specification=_spec(), question_text="Q?",
                      reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",)),
        )
        with self.assertRaises(GenerationRejectedError):
            generate_batch(units, client=_AlwaysRejectingClient(), generation_batch_id="batch_1", max_attempts=1)


if __name__ == "__main__":
    unittest.main()
