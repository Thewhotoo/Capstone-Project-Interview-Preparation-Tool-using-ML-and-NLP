"""Tests for rewrite_generation_pipeline.py — Experiment 4 (Rewrite Augmentation) Stage.

Includes the import-graph assertion mirroring
`test_synthetic_generation_pipeline.py`'s own: this pipeline must never
import the Evaluation Engine or the Conversation Engine either — it only
produces rewritten TrainingExamples, same boundary the original generation
pipeline enforces."""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, FakeGenerationClient, GenerationOutput
from generation_recipe import sample_recipe
from prompt_assembler import AssembledPrompt
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
import rewrite_generation_pipeline as pipeline_module
from rewrite_generation_pipeline import (
    RewriteRejectedError,
    RewriteUnit,
    rewrite_batch,
    rewrite_training_example,
)
from rewrite_verifier_client import FakeSemanticVerifierClient
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


def _source_example(tier=QualityTier.GOOD, concepts=("caching", "eviction policy"), recipe_id="r1") -> TrainingExample:
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING, concepts, tier)
    answer_parts = ["I worked on this directly."]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept}.")
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


class _EchoingRewriteClient:
    """A deterministic fake `GenerationClient` that reproduces the source
    answer with a fixed prefix/suffix per style — passes rewrite validation
    (same concepts, same contradiction state, moderate similarity) without
    depending on FakeGenerationClient's generation-time-only concept parsing
    (which reads recipe-shaped instructions, not rewrite-shaped ones)."""

    model_name = "fake-echo-rewriter-v1"

    def __init__(self, source_example: TrainingExample, suffix: str = "") -> None:
        self._source_example = source_example
        self._suffix = suffix

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        evidence = [
            ConceptEvidenceEntry(concept=t.concept, evidence=f"I discussed {t.concept} in my own way.")
            for t in self._source_example.synthetic.intended_concept_inclusion
            if t.status != ConceptObservationStatus.OMITTED
        ]
        # Light rewording (not a straight prefix/append) so the length ratio
        # stays close to 1.0 (passes every style's band) and the text isn't
        # byte-identical to the source (which would trip the near-duplicate
        # similarity ceiling).
        text = (
            self._source_example.inputs.answer_text
            .replace("worked on this directly", "handled this myself")
            + self._suffix
        )
        return GenerationOutput(answer_text=text, concept_evidence=evidence, contradiction_note="")


class _AlwaysRejectingVerifierClient:
    model_name = "fake-always-reject-v1"

    def verify(self, original_answer: str, rewritten_answer: str):
        from rewrite_verifier_client import SemanticDriftVerdict
        return SemanticDriftVerdict(meaning_changed=True, explanation="forced rejection for test")


class TestRewriteTrainingExample(unittest.TestCase):
    def test_successful_rewrite_returns_outcome(self):
        source = _source_example(concepts=("caching",))
        client = _EchoingRewriteClient(source)
        outcome = rewrite_training_example(source, "concise", client, FakeSemanticVerifierClient(), "rewrite_batch_1")
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(outcome.style, "concise")
        self.assertEqual(outcome.source_example_id, source.metadata.example_id)
        self.assertEqual(outcome.example.synthetic.rewritten_from_example_id, source.metadata.example_id)

    def test_exhausting_attempts_raises_rewrite_rejected_error(self):
        source = _source_example(concepts=("caching",))
        client = _EchoingRewriteClient(source)
        with self.assertRaises(RewriteRejectedError) as ctx:
            rewrite_training_example(
                source, "concise", client, _AlwaysRejectingVerifierClient(), "rewrite_batch_1", max_attempts=2,
            )
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(ctx.exception.style, "concise")

    def test_different_styles_produce_different_rewrite_style_field(self):
        source = _source_example(concepts=("caching",))
        client = _EchoingRewriteClient(source)
        outcome_concise = rewrite_training_example(source, "concise", client, FakeSemanticVerifierClient(), "b1")
        outcome_reflective = rewrite_training_example(source, "reflective", client, FakeSemanticVerifierClient(), "b1")
        self.assertEqual(outcome_concise.example.synthetic.rewrite_style, "concise")
        self.assertEqual(outcome_reflective.example.synthetic.rewrite_style, "reflective")


class TestRewriteBatch(unittest.TestCase):
    def test_generates_one_outcome_per_unit(self):
        source = _source_example(concepts=("caching",))
        client = _EchoingRewriteClient(source)
        units = (
            RewriteUnit(source_example=source, style="concise"),
            RewriteUnit(source_example=source, style="conversational"),
            RewriteUnit(source_example=source, style="reflective"),
        )
        outcomes = rewrite_batch(units, client, FakeSemanticVerifierClient(), "rewrite_batch_1")
        self.assertEqual(len(outcomes), 3)
        self.assertEqual({o.style for o in outcomes}, {"concise", "conversational", "reflective"})

    def test_batch_propagates_rejection_immediately(self):
        source = _source_example(concepts=("caching",))
        client = _EchoingRewriteClient(source)
        units = (RewriteUnit(source_example=source, style="concise"),)
        with self.assertRaises(RewriteRejectedError):
            rewrite_batch(units, client, _AlwaysRejectingVerifierClient(), "rewrite_batch_1", max_attempts=1)

    def test_each_outcome_traces_to_its_own_source(self):
        source_a = _source_example(concepts=("caching",), recipe_id="r_a")
        source_b = _source_example(concepts=("caching",), recipe_id="r_b")
        outcome_a = rewrite_training_example(
            source_a, "concise", _EchoingRewriteClient(source_a), FakeSemanticVerifierClient(), "rewrite_batch_1",
        )
        outcome_b = rewrite_training_example(
            source_b, "concise", _EchoingRewriteClient(source_b), FakeSemanticVerifierClient(), "rewrite_batch_1",
        )
        self.assertEqual(outcome_a.example.synthetic.rewritten_from_example_id, source_a.metadata.example_id)
        self.assertEqual(outcome_b.example.synthetic.rewritten_from_example_id, source_b.metadata.example_id)
        self.assertNotEqual(
            outcome_a.example.synthetic.rewritten_from_example_id,
            outcome_b.example.synthetic.rewritten_from_example_id,
        )


if __name__ == "__main__":
    unittest.main()
