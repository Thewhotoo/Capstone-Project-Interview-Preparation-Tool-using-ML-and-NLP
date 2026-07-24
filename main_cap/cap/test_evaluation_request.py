"""Tests for evaluation_request.py — Phase 3."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_OVERVIEW, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title="My Project")),
        source_type=SourceType.PROJECT, source_id="My Project", source_field="summary", reason="test",
    )


def _context(**overrides):
    defaults = dict(turn_number=1, is_followup=False)
    defaults.update(overrides)
    return ConversationContextSnapshot(**defaults)


def _request(**overrides):
    defaults = dict(
        request_id="req_1", requested_at="2026-01-01T00:00:00+00:00",
        specification=_spec(), question_text="Tell me about My Project.",
        reasoning_type=ReasoningType.RECALL, answer_text="I built it with Python.",
        conversation_context=_context(),
    )
    defaults.update(overrides)
    return EvaluationRequest(**defaults)


class TestConversationContextSnapshot(unittest.TestCase):
    def test_construction_with_defaults(self):
        ctx = _context()
        self.assertEqual(ctx.prior_answers_for_this_spec, ())
        self.assertEqual(ctx.followups_used_on_this_spec, 0)

    def test_turn_number_must_be_positive(self):
        with self.assertRaises(pydantic.ValidationError):
            _context(turn_number=0)

    def test_followups_used_cannot_be_negative(self):
        with self.assertRaises(pydantic.ValidationError):
            _context(followups_used_on_this_spec=-1)

    def test_frozen(self):
        ctx = _context()
        with self.assertRaises(pydantic.ValidationError):
            ctx.turn_number = 2


class TestEvaluationRequestConstruction(unittest.TestCase):
    def test_constructs_with_all_fields(self):
        req = _request()
        self.assertEqual(req.answer_text, "I built it with Python.")
        self.assertEqual(req.reasoning_type, ReasoningType.RECALL)

    def test_answer_text_may_be_empty(self):
        """A candidate submitting nothing is still a valid, evaluable case
        — very low score, not a malformed request."""
        req = _request(answer_text="")
        self.assertEqual(req.answer_text, "")

    def test_question_text_must_not_be_empty(self):
        with self.assertRaises(pydantic.ValidationError):
            _request(question_text="")

    def test_request_id_must_not_be_empty(self):
        with self.assertRaises(pydantic.ValidationError):
            _request(request_id="")

    def test_schema_version_default(self):
        """Bumped v1 -> v2 for the approved Expected Concepts revision
        (additive field, backward-compatible per Chapter 8.5's discipline)."""
        req = _request()
        self.assertEqual(req.schema_version, "v2")

    def test_expected_concepts_defaults_empty(self):
        req = _request()
        self.assertEqual(req.expected_concepts, ())

    def test_expected_concepts_accepts_values(self):
        req = _request(expected_concepts=("ASGI", "dependency injection"))
        self.assertEqual(req.expected_concepts, ("ASGI", "dependency injection"))

    def test_expected_concepts_is_immutable(self):
        req = _request()
        import pydantic as _pydantic
        with self.assertRaises(_pydantic.ValidationError):
            req.expected_concepts = ("x",)

    def test_evaluation_focus_optional(self):
        self.assertIsNone(_request().evaluation_focus)
        self.assertEqual(_request(evaluation_focus="caching TTL").evaluation_focus, "caching TTL")


class TestEvaluationRequestImmutability(unittest.TestCase):
    def test_cannot_reassign_answer_text(self):
        req = _request()
        with self.assertRaises(pydantic.ValidationError):
            req.answer_text = "changed"

    def test_cannot_reassign_specification(self):
        req = _request()
        with self.assertRaises(pydantic.ValidationError):
            req.specification = _spec()

    def test_cannot_reassign_conversation_context(self):
        req = _request()
        with self.assertRaises(pydantic.ValidationError):
            req.conversation_context = _context(turn_number=2)


class TestNoConversationEngineTypeDependency(unittest.TestCase):
    """The refinement from RFC Revision 2 Section 2: EvaluationRequest must
    not depend on InterviewQuestion."""

    def test_module_does_not_import_interview_question(self):
        """Checks actual bindings in the module namespace, not prose in the
        docstring (which legitimately explains why these are NOT imported)."""
        import evaluation_request as mod
        self.assertFalse(hasattr(mod, "InterviewQuestion"))

    def test_module_does_not_import_conversation_memory(self):
        import evaluation_request as mod
        self.assertFalse(hasattr(mod, "ConversationMemory"))


if __name__ == "__main__":
    unittest.main()
