"""
Tests for `overall_single_evaluator.py` (V3 Single-Overall-Score
Architecture) covering:
  Test 6:  DeBERTa overall score is not overwritten by heuristics.
  Test 8:  production EvaluationResult schema.
  Test 9:  existing conversation/evaluation flow remains compatible.
  Test 10: old legacy evaluator remains available for rollback.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_dimensions import CANONICAL_DIMENSIONS
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import DimensionScore, EvaluationResult
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from overall_score_model import OverallScoreModel
from overall_single_evaluator import OverallSingleEvaluator
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_experimentation import ExperimentConfig, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="spec1", category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(
            title="CloudScaler", summary="An autoscaling platform.", technologies=("Kubernetes",),
        )),
        source_type=SourceType.PROJECT, source_id="proj1", source_field="projects", reason="test",
    )


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        request_id="req1", requested_at="2026-01-01T00:00:00+00:00",
        specification=_spec(), question_text="How did you scale it?", reasoning_type=ReasoningType.EXPLANATION,
        answer_text="I designed and built a Redis-based caching layer to reduce database load.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


def _build_evaluator() -> OverallSingleEvaluator:
    backbone = build_tiny_random_encoder(_TOKENIZER)
    backbone_config = BackboneConfig()
    model = OverallScoreModel(backbone_config, backbone=backbone)
    experiment_config = ExperimentConfig(
        backbone_name=backbone_config.hf_model_id, random_seed=42, dataset_version="test_dataset",
    )
    checkpoint = assemble_checkpoint(
        model_version="overall_single_v3_test", experiment_config=experiment_config, artifact_uri="mem://test",
    )
    return OverallSingleEvaluator(checkpoint, model, _TOKENIZER, backbone_config)


class TestOverallScoreNotOverwrittenByHeuristics(unittest.TestCase):
    """Test 6: DeBERTa overall score is not overwritten by heuristics."""

    def test_overall_score_unchanged_when_heuristic_diagnostics_are_extreme(self):
        evaluator = _build_evaluator()
        baseline = evaluator.evaluate(_request())

        # Monkeypatch the diagnostics engine to return four maximally
        # LOW diagnostic scores -- if overall_score were derived from a
        # weighted average of dimensions (like HeuristicEvaluator/
        # TrainedEvaluator do), this would crater overall_score. It must
        # not move at all.
        extreme_low_dims = tuple(
            DimensionScore(
                name=d.value, raw_score=0.0, weight_used=0.25, confidence=0.9,
                confidence_source="heuristic", contributes_to_overall=False,
            )
            for d in CANONICAL_DIMENSIONS
        )
        with mock.patch.object(evaluator.diagnostics_engine, "compute", return_value=extreme_low_dims):
            result_low = evaluator.evaluate(_request())

        extreme_high_dims = tuple(
            DimensionScore(
                name=d.value, raw_score=1.0, weight_used=0.25, confidence=0.9,
                confidence_source="heuristic", contributes_to_overall=False,
            )
            for d in CANONICAL_DIMENSIONS
        )
        with mock.patch.object(evaluator.diagnostics_engine, "compute", return_value=extreme_high_dims):
            result_high = evaluator.evaluate(_request())

        self.assertEqual(baseline.overall_score, result_low.overall_score)
        self.assertEqual(baseline.overall_score, result_high.overall_score)
        self.assertEqual(baseline.grade, result_low.grade)
        self.assertEqual(baseline.grade, result_high.grade)

    def test_all_returned_dimensions_have_contributes_to_overall_false(self):
        evaluator = _build_evaluator()
        result = evaluator.evaluate(_request())
        for d in result.dimensions:
            self.assertFalse(d.contributes_to_overall)

    def test_overall_score_evaluator_never_computes_a_weighted_dimension_average(self):
        # Static guarantee: unlike TrainedEvaluator/HeuristicEvaluator,
        # this evaluator's source never sums raw_score * weight_used.
        import inspect
        source = inspect.getsource(OverallSingleEvaluator.evaluate)
        self.assertNotIn("weight_used", source)


class TestProductionEvaluationResultSchema(unittest.TestCase):
    """Test 8: production EvaluationResult schema."""

    def test_evaluate_returns_a_valid_evaluation_result(self):
        evaluator = _build_evaluator()
        result = evaluator.evaluate(_request())
        self.assertIsInstance(result, EvaluationResult)

    def test_result_exposes_overall_score_grade_and_four_diagnostic_dimensions(self):
        evaluator = _build_evaluator()
        result = evaluator.evaluate(_request())
        self.assertIsInstance(result.overall_score, float)
        self.assertIn(result.grade, ("poor", "weak", "adequate", "good", "excellent"))
        self.assertEqual(len(result.dimensions), 4)
        self.assertEqual({d.name for d in result.dimensions}, {d.value for d in CANONICAL_DIMENSIONS})

    def test_result_has_strengths_weaknesses_and_confidence_info(self):
        evaluator = _build_evaluator()
        result = evaluator.evaluate(_request())
        self.assertGreater(len(result.strengths), 0)
        self.assertGreater(len(result.weaknesses), 0)
        self.assertEqual(result.confidence_source, "model_derived")
        self.assertTrue(result.confidence_rationale)

    def test_result_request_and_specification_identity_are_preserved(self):
        evaluator = _build_evaluator()
        request = _request()
        result = evaluator.evaluate(request)
        self.assertEqual(result.request_id, request.request_id)
        self.assertEqual(result.specification_id, request.specification.id)
        self.assertEqual(result.reasoning_type, request.reasoning_type)


class TestConversationEvaluationFlowCompatibility(unittest.TestCase):
    """Test 9: existing conversation/evaluation flow remains compatible."""

    def test_implements_the_same_evaluator_protocol_shape_as_every_other_evaluator(self):
        from heuristic_evaluator import HeuristicEvaluator
        evaluator = _build_evaluator()
        for attr in ("name", "version", "declared_dimensions", "declared_reasoning_types", "requires_network"):
            self.assertTrue(hasattr(evaluator, attr))
            self.assertTrue(hasattr(HeuristicEvaluator, attr))
        self.assertTrue(callable(evaluator.evaluate))

    def test_evaluate_accepts_a_request_built_the_standard_way(self):
        # Uses the exact same EvaluationRequest shape evaluation_engine.
        # build_request() produces (ConversationContextSnapshot,
        # QuestionSpecification, expected_concepts) -- no special-casing.
        evaluator = _build_evaluator()
        request = EvaluationRequest(
            request_id="req2", requested_at="2026-01-01T00:00:00+00:00",
            specification=_spec(), question_text="What technologies did you use?",
            reasoning_type=ReasoningType.RECALL, answer_text="Kubernetes and Redis.",
            conversation_context=ConversationContextSnapshot(turn_number=2, is_followup=True),
            expected_concepts=("autoscaling",),
        )
        result = evaluator.evaluate(request)
        self.assertIsInstance(result, EvaluationResult)


class TestLegacyEvaluatorRollbackAvailability(unittest.TestCase):
    """Test 10: old legacy evaluator remains available for rollback."""

    def test_heuristic_evaluator_still_importable_and_unchanged_in_shape(self):
        from heuristic_evaluator import HeuristicEvaluator
        evaluator = HeuristicEvaluator()
        self.assertEqual(evaluator.name, "heuristic-v1")
        self.assertEqual(len(evaluator.declared_dimensions), 12)

    def test_trained_evaluator_and_hybrid_evaluator_still_importable(self):
        import model_evaluator  # noqa: F401
        import hybrid_evaluator  # noqa: F401
        self.assertTrue(hasattr(model_evaluator, "TrainedEvaluator"))
        self.assertTrue(hasattr(hybrid_evaluator, "HybridEvaluator"))

    def test_deployment_evaluator_still_targets_a2_as_the_rollback_tier(self):
        # V3 single-overall-score integration (later session): A2 is no
        # longer the sole/primary deployment target, but it MUST remain a
        # fully intact, reachable rollback tier -- see
        # deployment_evaluator.py's three-tier fallback chain and
        # test_deployment_evaluator_overall_single_v3.py's dedicated
        # coverage of that chain end-to-end. This test only asserts A2's
        # own paths/constants are still exactly where they were.
        import deployment_evaluator
        self.assertTrue(deployment_evaluator.DEPLOYED_MODEL_DIR.replace("\\", "/").endswith("deployed_model_a2"))
        self.assertTrue(
            deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR.replace("\\", "/").endswith("deployed_model")
        )
        self.assertTrue(hasattr(deployment_evaluator, "activate_a2_rollback"))

    def test_overall_single_evaluator_is_now_wired_as_the_primary_deployment_tier(self):
        # Superseded expectation from before integration (this evaluator
        # used to be explicitly NOT deployed). Integration is now done --
        # deployment_evaluator.py DOES import and register it (tier 1 of
        # the fallback chain), while A2 (tier 2) and HeuristicEvaluator
        # (tier 3) remain fully intact and reachable.
        import ast
        import inspect
        import deployment_evaluator
        source = inspect.getsource(deployment_evaluator)
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        self.assertIn("overall_single_evaluator", imported_modules)
        self.assertIn("overall_score_model", imported_modules)
        # And A2's own wiring (model_evaluator/hybrid_evaluator) is still present too.
        self.assertIn("model_evaluator", imported_modules)
        self.assertIn("hybrid_evaluator", imported_modules)


if __name__ == "__main__":
    unittest.main()
