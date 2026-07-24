"""
Tests for evaluation_engine.py — Phase 3, RFC Section 9 (Integration).

Includes the import-graph assertion that backs the architectural claim:
Conversation Engine modules (conversation_memory, question_realizer,
discussion_policy, planner, topic_pool) must remain completely unaware of
evaluation.
"""

import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict
import conversation_memory
import discussion_policy
from evaluation_engine import EvaluationLedger, build_request, evaluate
from heuristic_evaluator import HeuristicEvaluator
from planner import ConversationState, Planner
import question_realizer
import planner as planner_module
import topic_pool
from question_specification import UnitStatus


def _module_imports(module) -> set:
    import inspect
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestConversationEngineUnawareOfEvaluation(unittest.TestCase):
    """RFC Section 9: Planner/TopicPool/ConversationMemory/Question
    Realizer/Discussion Policy must remain completely unaware of
    evaluation — verified by checking they never import any Evaluation
    Engine module."""

    EVALUATION_MODULES = {
        "evaluation_request", "evaluation_result", "evaluator",
        "evaluator_registry", "heuristic_evaluator", "evaluation_engine",
        "reasoning_dimension_relevance",
    }

    def test_conversation_memory_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(conversation_memory) & self.EVALUATION_MODULES)

    def test_question_realizer_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(question_realizer) & self.EVALUATION_MODULES)

    def test_discussion_policy_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(discussion_policy) & self.EVALUATION_MODULES)

    def test_planner_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(planner_module) & self.EVALUATION_MODULES)

    def test_topic_pool_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(topic_pool) & self.EVALUATION_MODULES)


class TestBuildRequest(unittest.TestCase):
    def setUp(self):
        self.planner = Planner(sample_profile_dict())
        self.memory = conversation_memory.ConversationMemory()
        spec = self.planner.plan_next(ConversationState())
        self.question, self.variant_idx = question_realizer.realize(spec, self.memory, turn_number=1)

    def test_build_request_produces_valid_evaluation_request(self):
        req = build_request(self.question, "I built this myself.", self.memory, self.planner, {})
        self.assertEqual(req.question_text, self.question.question_text)
        self.assertEqual(req.reasoning_type, self.question.reasoning_type)
        self.assertEqual(req.specification, self.question.specification)
        self.assertEqual(req.answer_text, "I built this myself.")

    def test_conversation_context_reflects_memory_state(self):
        self.memory.record_turn(self.question, self.variant_idx, answer_text="An answer.")
        req = build_request(self.question, "Another answer.", self.memory, self.planner, {})
        self.assertEqual(req.conversation_context.turn_number, self.question.turn_number)
        self.assertEqual(
            set(req.conversation_context.projects_discussed_so_far),
            self.memory.projects_discussed,
        )

    def test_followups_used_reflects_planner_lifecycle(self):
        self.planner.pool.mark_active(self.question.specification.id)
        self.planner.pool.mark_followup_used(self.question.specification.id)
        req = build_request(self.question, "An answer.", self.memory, self.planner, {})
        self.assertEqual(req.conversation_context.followups_used_on_this_spec, 1)

    def test_prior_answers_come_from_answer_history_not_memory(self):
        history = {self.question.specification.id: ("earlier answer",)}
        req = build_request(self.question, "new answer", self.memory, self.planner, history)
        self.assertEqual(req.conversation_context.prior_answers_for_this_spec, ("earlier answer",))

    def test_evaluation_focus_passthrough(self):
        req = build_request(self.question, "An answer.", self.memory, self.planner, {}, evaluation_focus="caching TTL")
        self.assertEqual(req.evaluation_focus, "caching TTL")


class TestExpectedConceptsWiring(unittest.TestCase):
    """Expected Concepts revision (approved): build_request must populate
    `expected_concepts` via the deterministic registry lookup, entirely
    inside evaluation_engine.py — no QuestionSpecification/Planner changes."""

    def _profile_with_fastapi(self) -> dict:
        profile = sample_profile_dict()
        profile["projects"][0]["technologies"] = ["Python", "FastAPI"]
        return profile

    def test_expected_concepts_populated_when_technology_matches_registry(self):
        planner = Planner(self._profile_with_fastapi())
        memory = conversation_memory.ConversationMemory()
        state = ConversationState()
        # Walk turns until we find one grounded in the FastAPI project.
        req = None
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            question, _ = question_realizer.realize(spec, memory, turn_number=1)
            candidate_req = build_request(question, "An answer.", memory, planner, {})
            if candidate_req.expected_concepts:
                req = candidate_req
                break
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertIsNotNone(req, "expected at least one turn grounded in the FastAPI project")
        self.assertEqual(
            req.expected_concepts,
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity"),
        )

    def test_expected_concepts_empty_when_no_registry_match(self):
        planner = Planner(sample_profile_dict())  # uses Python/Flask/SBERT — no seeded match
        memory = conversation_memory.ConversationMemory()
        spec = planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, memory, turn_number=1)
        req = build_request(question, "An answer.", memory, planner, {})
        self.assertEqual(req.expected_concepts, ())


class TestEvaluateCallThrough(unittest.TestCase):
    def test_evaluate_delegates_to_the_evaluator(self):
        planner = Planner(sample_profile_dict())
        memory = conversation_memory.ConversationMemory()
        spec = planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, memory, turn_number=1)
        req = build_request(question, "I built this myself.", memory, planner, {})
        result = evaluate(HeuristicEvaluator(), req)
        self.assertEqual(result.request_id, req.request_id)


class TestEvaluationLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = EvaluationLedger()
        self.planner = Planner(sample_profile_dict())
        self.memory = conversation_memory.ConversationMemory()

    def _evaluate_next_turn(self, evaluator, turn_number, answer="An answer about this."):
        spec = self.planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, self.memory, turn_number)
        req = build_request(question, answer, self.memory, self.planner, {})
        return evaluate(evaluator, req), spec

    def test_starts_empty(self):
        self.assertEqual(len(self.ledger), 0)
        self.assertEqual(self.ledger.all(), ())

    def test_append_and_all(self):
        evaluator = HeuristicEvaluator()
        result, _ = self._evaluate_next_turn(evaluator, 1)
        self.ledger.append(result)
        self.assertEqual(len(self.ledger), 1)
        self.assertEqual(self.ledger.all(), (result,))

    def test_for_specification_filters_correctly(self):
        evaluator = HeuristicEvaluator()
        result, spec = self._evaluate_next_turn(evaluator, 1)
        self.ledger.append(result)
        self.assertEqual(self.ledger.for_specification(spec.id), (result,))
        self.assertEqual(self.ledger.for_specification("nonexistent_id"), ())


if __name__ == "__main__":
    unittest.main()
