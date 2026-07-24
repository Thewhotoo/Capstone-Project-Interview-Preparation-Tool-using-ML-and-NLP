"""
Tests for model_evaluator.py — TrainedEvaluator (the Evaluator Protocol
implementation) and promote_trained_model. Includes the import-graph
assertion enforcing this layer's approved dependency boundary. Uses the
tiny random backbone (approved clarification #4) — never a full pretrained
download in unit tests.
"""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluator import Evaluator, check_conformance
import evaluator_registry
import model_evaluator as model_evaluator_module
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_evaluator import TrainedEvaluator, promote_trained_model
from model_heads import MultiTaskModel
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_experimentation import BenchmarkResult, Checkpoint, ExperimentConfig, PromotionDecision, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


def _module_imports(module) -> set:
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestModelEvaluatorStaysWithinItsOwnBoundary(unittest.TestCase):
    FORBIDDEN_MODULES = {
        "synthetic_generation_pipeline", "coverage_strategy",
        "generation_client", "generation_recipe", "generation_validation",
        "prompt_assembler", "prompt_controllers", "labeling_operations", "dataset_manifest",
        "conversation_engine", "conversation_memory", "discussion_policy", "planner", "topic_pool",
        "discussion_engine", "heuristic_evaluator",
    }

    def test_never_imports_forbidden_modules(self):
        self.assertFalse(_module_imports(model_evaluator_module) & self.FORBIDDEN_MODULES)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _request(request_id: str = "r1", expected_concepts: tuple = ("caching",)) -> EvaluationRequest:
    return EvaluationRequest(
        request_id=request_id, requested_at="2026-07-24T00:00:00+00:00",
        specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING,
        answer_text="I worked through a cache invalidation bug using Redis carefully.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=expected_concepts,
    )


def _checkpoint(dataset_version: str = "v1") -> Checkpoint:
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version=dataset_version)
    return assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="in-memory-test-artifact")


def _trained_evaluator() -> TrainedEvaluator:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone)
    return TrainedEvaluator(_checkpoint(), model, _TOKENIZER, BackboneConfig(max_length=32))


class TestTrainedEvaluatorConformance(unittest.TestCase):
    def test_satisfies_evaluator_protocol_structurally(self):
        evaluator = _trained_evaluator()
        self.assertIsInstance(evaluator, Evaluator)

    def test_passes_check_conformance(self):
        evaluator = _trained_evaluator()
        check_conformance(evaluator, _request())  # must not raise

    def test_declares_all_dimensions_and_reasoning_types(self):
        evaluator = _trained_evaluator()
        self.assertEqual(set(evaluator.declared_dimensions), set(TrainedEvaluator.declared_dimensions))
        self.assertEqual(set(evaluator.declared_reasoning_types), set(ReasoningType))
        self.assertFalse(evaluator.requires_network)


class TestTrainedEvaluatorEvaluate(unittest.TestCase):
    def test_produces_valid_result_with_populated_provenance_fields(self):
        evaluator = _trained_evaluator()
        result = evaluator.evaluate(_request())

        self.assertEqual(result.request_id, "r1")
        self.assertTrue(result.dimensions)
        self.assertIn(result.grade, ("poor", "weak", "adequate", "good", "excellent"))
        self.assertEqual(result.dataset_version, "v1")
        self.assertIsNotNone(result.training_date)
        self.assertEqual(result.confidence_source, "model_derived")
        for d in result.dimensions:
            self.assertEqual(d.confidence_source, "model_derived")

    def test_only_relevant_dimensions_are_reported(self):
        from reasoning_dimension_relevance import relevant_dimensions
        evaluator = _trained_evaluator()
        result = evaluator.evaluate(_request())
        expected = relevant_dimensions(ReasoningType.DEBUGGING)
        self.assertEqual({d.name for d in result.dimensions}, set(expected))

    def test_concept_coverage_produced_for_expected_concepts(self):
        evaluator = _trained_evaluator()
        result = evaluator.evaluate(_request(expected_concepts=("caching", "redis")))
        self.assertEqual({c.concept for c in result.concept_coverage}, {"caching", "redis"})
        for observation in result.concept_coverage:
            self.assertEqual(observation.confidence_source, "model_derived")

    def test_no_expected_concepts_yields_empty_concept_coverage(self):
        evaluator = _trained_evaluator()
        result = evaluator.evaluate(_request(expected_concepts=()))
        self.assertEqual(result.concept_coverage, ())

    def test_evaluate_is_stateless_across_calls(self):
        evaluator = _trained_evaluator()
        result_a = evaluator.evaluate(_request(request_id="r1"))
        result_b = evaluator.evaluate(_request(request_id="r1"))
        self.assertEqual(
            [d.raw_score for d in result_a.dimensions], [d.raw_score for d in result_b.dimensions],
        )


class TestPromoteTrainedModel(unittest.TestCase):
    def setUp(self):
        # evaluator_registry is process-global state -- reset between tests
        # so promotion tests don't leak into each other or other test files.
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None

    def test_rejects_unapproved_decision(self):
        checkpoint = _checkpoint()
        decision = PromotionDecision(
            approved=False, rationale="did not clear the bar",
            checkpoint_model_version=checkpoint.model_version, benchmark_id="bench_1",
        )
        with self.assertRaises(ValueError):
            promote_trained_model(checkpoint, decision, _trained_evaluator())

    def test_approved_decision_registers_and_activates(self):
        checkpoint = _checkpoint()
        decision = PromotionDecision(
            approved=True, rationale="cleared the bar",
            checkpoint_model_version=checkpoint.model_version, benchmark_id="bench_1",
        )
        evaluator = _trained_evaluator()
        promote_trained_model(checkpoint, decision, evaluator, sample_request=_request(), make_active=True)

        self.assertEqual(evaluator_registry.get_active_evaluator().name, evaluator.name)
        self.assertIn(evaluator.name, evaluator_registry.registered_evaluator_names())


if __name__ == "__main__":
    unittest.main()
