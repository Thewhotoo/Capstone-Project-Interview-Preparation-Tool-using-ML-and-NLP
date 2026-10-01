"""Tests for evaluator.py — Phase 3, RFC Section 7 (interface + conformance)."""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import ConfidenceSource, DimensionScore, EvaluationResult
from evaluator import Evaluator, EvaluatorConformanceError, check_conformance
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_OVERVIEW, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title="My Project")),
        source_type=SourceType.PROJECT, source_id="My Project", source_field="summary", reason="test",
    )


def _request(request_id="req_1"):
    return EvaluationRequest(
        request_id=request_id, requested_at="2026-01-01T00:00:00+00:00", specification=_spec(),
        question_text="Tell me about My Project.", reasoning_type=ReasoningType.RECALL,
        answer_text="I built it.", conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


class _ConformantEvaluator:
    name = "test-conformant"
    version = "1.0.0"
    declared_dimensions = ("technical_accuracy",)
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        return EvaluationResult(
            result_id="eval_1", request_id=request.request_id,
            evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
            specification_id=request.specification.id, source_id=request.specification.source_id,
            category=request.specification.category.value, reasoning_type=request.reasoning_type,
            evaluator_name=self.name, evaluator_version=self.version,
            dimensions=(DimensionScore(
                name="technical_accuracy", raw_score=0.7, weight_used=1.0,
                confidence=0.6, confidence_source=ConfidenceSource.HEURISTIC,
            ),),
            overall_score=0.7, grade="good", confidence=0.6,
            confidence_source=ConfidenceSource.HEURISTIC, confidence_rationale="Because reasons.",
            reasoning="technical_accuracy: 70%",
        )


class TestEvaluatorProtocol(unittest.TestCase):
    def test_conformant_evaluator_satisfies_protocol(self):
        self.assertIsInstance(_ConformantEvaluator(), Evaluator)

    def test_object_missing_evaluate_does_not_satisfy_protocol(self):
        class NotAnEvaluator:
            name = "x"
        self.assertNotIsInstance(NotAnEvaluator(), Evaluator)


class TestCheckConformance(unittest.TestCase):
    def test_conformant_evaluator_passes(self):
        check_conformance(_ConformantEvaluator(), _request())  # must not raise

    def test_result_request_id_mismatch_rejected(self):
        class BadEvaluator(_ConformantEvaluator):
            def evaluate(self, request):
                result = super().evaluate(request)
                return result.model_copy(update={"request_id": "totally_different"})
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(BadEvaluator(), _request())

    def test_evaluator_producing_undeclared_dimension_rejected(self):
        class BadEvaluator(_ConformantEvaluator):
            declared_dimensions = ("communication",)  # doesn't match what evaluate() produces
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(BadEvaluator(), _request())

    def test_evaluator_missing_reasoning_type_declaration_rejected(self):
        class BadEvaluator(_ConformantEvaluator):
            declared_reasoning_types = (ReasoningType.DEBUGGING,)  # request uses RECALL
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(BadEvaluator(), _request())

    def test_empty_declared_dimensions_rejected(self):
        class BadEvaluator(_ConformantEvaluator):
            declared_dimensions = ()
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(BadEvaluator(), _request())

    def test_evaluator_name_mismatch_with_result_rejected(self):
        class BadEvaluator(_ConformantEvaluator):
            name = "declared-name"

            def evaluate(self, request):
                # Deliberately returns a result stamped with a DIFFERENT
                # evaluator_name than this instance's own .name attribute.
                return super().evaluate(request).model_copy(update={"evaluator_name": "some-other-name"})
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(BadEvaluator(), _request())

    def test_missing_required_attribute_rejected(self):
        class Incomplete:
            name = "incomplete"
            version = "1.0.0"
            declared_dimensions = ("technical_accuracy",)
            declared_reasoning_types = tuple(ReasoningType)
            # requires_network intentionally missing

            def evaluate(self, request):
                return _ConformantEvaluator().evaluate(request)
        with self.assertRaises(EvaluatorConformanceError):
            check_conformance(Incomplete(), _request())


if __name__ == "__main__":
    unittest.main()
