"""Tests for evaluator_registry.py — Phase 3, RFC Section 7 (dependency injection)."""

import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import ConfidenceSource, DimensionScore, EvaluationResult
import evaluator_registry as registry
from evaluator_registry import UnknownEvaluatorError, get_evaluator, register_evaluator, set_active_evaluator
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_OVERVIEW, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title="My Project")),
        source_type=SourceType.PROJECT, source_id="My Project", source_field="summary", reason="test",
    )


def _request():
    return EvaluationRequest(
        request_id="req_1", requested_at="2026-01-01T00:00:00+00:00", specification=_spec(),
        question_text="Tell me about My Project.", reasoning_type=ReasoningType.RECALL,
        answer_text="I built it.", conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


def _make_fake_evaluator(name):
    class FakeEvaluator:
        declared_dimensions = ("technical_accuracy",)
        declared_reasoning_types = tuple(ReasoningType)
        requires_network = False
        version = "1.0.0"

        def __init__(self):
            self.name = name

        def evaluate(self, request):
            return EvaluationResult(
                result_id="eval_1", request_id=request.request_id,
                evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
                specification_id=request.specification.id, source_id=request.specification.source_id,
                category=request.specification.category.value, reasoning_type=request.reasoning_type,
                evaluator_name=self.name, evaluator_version=self.version,
                dimensions=(DimensionScore(
                    name="technical_accuracy", raw_score=0.5, weight_used=1.0,
                    confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
                ),),
                overall_score=0.5, grade="adequate", confidence=0.5,
                confidence_source=ConfidenceSource.HEURISTIC, confidence_rationale="Because reasons.",
                reasoning="technical_accuracy: 50%",
            )
    return FakeEvaluator()


def _unique_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TestRegistration(unittest.TestCase):
    def test_register_and_retrieve(self):
        name = _unique_name("eval")
        evaluator = _make_fake_evaluator(name)
        register_evaluator(evaluator)
        self.assertIs(get_evaluator(name), evaluator)

    def test_register_with_conformance_check_passes_for_valid_evaluator(self):
        name = _unique_name("eval")
        evaluator = _make_fake_evaluator(name)
        register_evaluator(evaluator, sample_request=_request())  # must not raise

    def test_unregistered_name_raises(self):
        with self.assertRaises(UnknownEvaluatorError):
            get_evaluator(_unique_name("never_registered"))

    def test_registered_evaluator_names_includes_registered(self):
        name = _unique_name("eval")
        register_evaluator(_make_fake_evaluator(name))
        self.assertIn(name, registry.registered_evaluator_names())


class TestActiveEvaluatorPinning(unittest.TestCase):
    def test_set_and_get_active(self):
        name = _unique_name("eval")
        register_evaluator(_make_fake_evaluator(name))
        set_active_evaluator(name)
        self.assertIs(registry.get_active_evaluator(), get_evaluator(name))
        self.assertEqual(registry.active_evaluator_name(), name)

    def test_make_active_flag_on_register(self):
        name = _unique_name("eval")
        register_evaluator(_make_fake_evaluator(name), make_active=True)
        self.assertEqual(registry.active_evaluator_name(), name)

    def test_setting_unregistered_name_active_raises(self):
        with self.assertRaises(UnknownEvaluatorError):
            set_active_evaluator(_unique_name("never_registered"))

    def test_resolving_active_evaluator_twice_returns_same_instance(self):
        """Supports the RFC's mid-session-pinning risk mitigation: a caller
        that resolves once and holds the reference is unaffected by any
        LATER registry change."""
        name = _unique_name("eval")
        evaluator = _make_fake_evaluator(name)
        register_evaluator(evaluator, make_active=True)
        pinned = registry.get_active_evaluator()

        other_name = _unique_name("eval_other")
        register_evaluator(_make_fake_evaluator(other_name), make_active=True)

        self.assertIs(pinned, evaluator)  # the earlier reference is untouched
        self.assertIsNot(registry.get_active_evaluator(), pinned)  # but the registry moved on


if __name__ == "__main__":
    unittest.main()
