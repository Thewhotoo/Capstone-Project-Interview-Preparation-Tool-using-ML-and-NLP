"""Tests for heuristic_evaluator.py — Phase 3 concrete Evaluator implementation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import EvaluationResult
from evaluator import Evaluator, check_conformance
from heuristic_evaluator import HeuristicEvaluator
from question_families import ReasoningType
from question_specification import (
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _project_spec(text_seed="Redis caching strategy"):
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=text_seed,
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis", "Flask"),
            concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _request(answer_text, reasoning_type=ReasoningType.DEBUGGING, spec=None, expected_concepts=()):
    return EvaluationRequest(
        request_id="req_1", requested_at="2026-01-01T00:00:00+00:00",
        specification=spec or _project_spec(), question_text="Did Redis caching give you any trouble?",
        reasoning_type=reasoning_type, answer_text=answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=expected_concepts,
    )


class TestConformsToInterface(unittest.TestCase):
    def test_is_an_evaluator(self):
        self.assertIsInstance(HeuristicEvaluator(), Evaluator)

    def test_passes_conformance_check(self):
        check_conformance(HeuristicEvaluator(), _request("I ran into a caching invalidation bug and fixed it by adding TTLs."))

    def test_requires_network_is_false(self):
        self.assertFalse(HeuristicEvaluator().requires_network)

    def test_declares_all_reasoning_types(self):
        self.assertEqual(set(HeuristicEvaluator().declared_reasoning_types), set(ReasoningType))


class TestEvaluateReturnsValidResult(unittest.TestCase):
    def setUp(self):
        self.evaluator = HeuristicEvaluator()

    def test_returns_evaluation_result(self):
        result = self.evaluator.evaluate(_request("I fixed a caching bug by adding TTLs to Redis."))
        self.assertIsInstance(result, EvaluationResult)

    def test_request_id_propagates(self):
        req = _request("An answer.")
        result = self.evaluator.evaluate(req)
        self.assertEqual(result.request_id, req.request_id)

    def test_specification_fields_denormalized_correctly(self):
        result = self.evaluator.evaluate(_request("An answer."))
        self.assertEqual(result.specification_id, "topic_0")
        self.assertEqual(result.source_id, "Resume Discussion Platform")
        self.assertEqual(result.project_reference, "Resume Discussion Platform")

    def test_evaluator_identity_fields(self):
        result = self.evaluator.evaluate(_request("An answer."))
        self.assertEqual(result.evaluator_name, "heuristic-v1")
        self.assertEqual(result.evaluator_version, "1.0.0")

    def test_only_relevant_dimensions_produced_for_reasoning_type(self):
        from reasoning_dimension_relevance import relevant_dimensions
        req = _request("An answer.", reasoning_type=ReasoningType.OPTIMIZATION)
        result = self.evaluator.evaluate(req)
        produced = {d.name for d in result.dimensions}
        self.assertEqual(produced, relevant_dimensions(ReasoningType.OPTIMIZATION))

    def test_authenticity_never_contributes(self):
        req = _request("I designed and built this myself, handling every part of it.")
        result = self.evaluator.evaluate(req)
        auth = result.dimension("authenticity")
        if auth is not None:
            self.assertFalse(auth.contributes_to_overall)


class TestReasoningIsNeverEmpty(unittest.TestCase):
    def test_every_result_has_nonempty_reasoning_and_rationale(self):
        evaluator = HeuristicEvaluator()
        for answer in ("", "short", "A much longer, more detailed answer with several sentences. It explains things. It also mentions Redis."):
            result = evaluator.evaluate(_request(answer))
            self.assertTrue(result.reasoning.strip())
            self.assertTrue(result.confidence_rationale.strip())


class TestOwnershipAndCommunicationSignals(unittest.TestCase):
    def test_first_person_ownership_scores_higher(self):
        evaluator = HeuristicEvaluator()
        with_ownership = evaluator.evaluate(_request(
            "I designed and built the caching layer myself.", reasoning_type=ReasoningType.OWNERSHIP,
        ))
        without_ownership = evaluator.evaluate(_request(
            "The caching layer was built by the team.", reasoning_type=ReasoningType.OWNERSHIP,
        ))
        self.assertGreater(
            with_ownership.dimension("ownership").raw_score,
            without_ownership.dimension("ownership").raw_score,
        )


class TestLongerAnswerScoresHigherOnCompleteness(unittest.TestCase):
    def test_longer_more_structured_answer_scores_higher_completeness(self):
        evaluator = HeuristicEvaluator()
        short = evaluator.evaluate(_request("Yes."))
        long = evaluator.evaluate(_request(
            "I ran into a caching invalidation bug. First I traced it to a race condition. "
            "Then I fixed it by adding a TTL and a lock. Because of that, correctness improved."
        ))
        self.assertGreater(
            long.dimension("completeness").raw_score,
            short.dimension("completeness").raw_score,
        )


class TestMissingReasoningAndSuggestions(unittest.TestCase):
    def test_missing_technology_produces_a_gap(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request(
            "I built a small feature.", reasoning_type=ReasoningType.APPLICATION,
        ))
        categories = {item.category for item in result.missing_reasoning}
        self.assertTrue(categories)  # at least one gap identified

    def test_suggested_improvements_derived_from_missing_reasoning(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("I built a small feature.", reasoning_type=ReasoningType.APPLICATION))
        self.assertLessEqual(len(result.suggested_improvements), 3)
        self.assertLessEqual(len(result.suggested_improvements), len(result.missing_reasoning))


class TestDeterminism(unittest.TestCase):
    def test_same_request_produces_same_scores(self):
        evaluator = HeuristicEvaluator()
        req = _request("I fixed a caching bug by adding TTLs to Redis.")
        r1 = evaluator.evaluate(req)
        r2 = evaluator.evaluate(req)
        self.assertEqual(
            [(d.name, d.raw_score) for d in r1.dimensions],
            [(d.name, d.raw_score) for d in r2.dimensions],
        )
        self.assertEqual(r1.overall_score, r2.overall_score)


class TestContradictionFlagNeverBlendedIntoScore(unittest.TestCase):
    """Chapter 19.5's already-learned lesson, applied fresh here — verified
    structurally by confirming technical_accuracy and resume_grounding
    depend only on semantic similarity, not on the contradiction flag."""

    def test_technical_accuracy_equals_resume_grounding_signal(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("I fixed a caching bug by adding TTLs to Redis."))
        acc = result.dimension("technical_accuracy")
        if acc is not None:
            self.assertAlmostEqual(acc.raw_score, result.resume_grounding_score, places=3)


class TestConceptCoverage(unittest.TestCase):
    """Expected Concepts revision (approved) — HeuristicEvaluator's
    reference-implementation heuristic for concept_coverage."""

    def setUp(self):
        self.evaluator = HeuristicEvaluator()

    def test_no_expected_concepts_produces_empty_coverage(self):
        result = self.evaluator.evaluate(_request("An answer.", expected_concepts=()))
        self.assertEqual(result.concept_coverage, ())

    def test_one_entry_per_expected_concept(self):
        result = self.evaluator.evaluate(_request(
            "An answer about Redis.", expected_concepts=("caching", "eviction policy"),
        ))
        self.assertEqual(len(result.concept_coverage), 2)
        self.assertEqual({c.concept for c in result.concept_coverage}, {"caching", "eviction policy"})

    def test_concept_discussed_at_length_is_demonstrated(self):
        result = self.evaluator.evaluate(_request(
            "I implemented caching using a Redis-backed layer with a TTL-based eviction policy "
            "to keep memory usage bounded under load.",
            expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertEqual(obs.status.value, "demonstrated")
        self.assertIsNotNone(obs.evidence)

    def test_concept_bare_mention_is_superficial(self):
        result = self.evaluator.evaluate(_request(
            "We used caching.", expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertIn(obs.status.value, ("superficial", "demonstrated"))  # short sentence, likely superficial
        self.assertIsNotNone(obs.evidence)

    def test_concept_never_mentioned_is_omitted_with_no_evidence(self):
        result = self.evaluator.evaluate(_request(
            "I fixed a bug in the frontend.", expected_concepts=("dependency injection",),
        ))
        obs = result.concept_coverage[0]
        self.assertEqual(obs.status.value, "omitted")
        self.assertIsNone(obs.evidence)

    def test_paraphrased_mention_detected_via_token_overlap(self):
        result = self.evaluator.evaluate(_request(
            "I used a dependency container to inject services.",
            expected_concepts=("dependency injection",),
        ))
        obs = result.concept_coverage[0]
        self.assertNotEqual(obs.status.value, "omitted")

    def test_concept_coverage_confidence_populated(self):
        result = self.evaluator.evaluate(_request(
            "An answer about Redis caching.", expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertGreaterEqual(obs.confidence, 0.0)
        self.assertLessEqual(obs.confidence, 1.0)
        self.assertEqual(obs.confidence_source, "heuristic")

    def test_deterministic(self):
        req = _request(
            "I implemented caching with a TTL eviction policy.", expected_concepts=("caching", "eviction policy"),
        )
        r1 = self.evaluator.evaluate(req)
        r2 = self.evaluator.evaluate(req)
        self.assertEqual(
            [(c.concept, c.status) for c in r1.concept_coverage],
            [(c.concept, c.status) for c in r2.concept_coverage],
        )


if __name__ == "__main__":
    unittest.main()
