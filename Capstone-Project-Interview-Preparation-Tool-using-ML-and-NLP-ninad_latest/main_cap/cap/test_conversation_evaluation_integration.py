"""
Integration tests for Phase 3's wiring into conversation_engine.py — the
ONE integration point the frozen RFC (Section 9) names.

Uses the real CandidateProfile model, exactly like test_conversation_engine.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conversation_engine as ce
import evaluator_registry
from candidate_profile_generator import (
    CandidateProfile,
    ExperienceEntry,
    InterviewBlueprint,
    ProjectEntry,
    TechnicalTopic,
)
from heuristic_evaluator import HeuristicEvaluator


def _real_profile() -> dict:
    return CandidateProfile(
        candidate_name="Phase 3 Test Candidate",
        skills=["Python", "Kafka", "PostgreSQL"],
        experience=[
            ExperienceEntry(company="Globex", role="Backend Engineering Intern",
                             duration="Summer 2023", summary="Built billing microservices."),
        ],
        projects=[
            ProjectEntry(
                title="Realtime Analytics Dashboard",
                summary="A streaming analytics dashboard for e-commerce metrics.",
                technologies=["Python", "Kafka", "Postgres"],
                concepts=["Stream processing"],
                interview_seeds=["Why Kafka over a simple queue?", "How did you handle late-arriving events?"],
            ),
        ],
        certifications=["Certified Kubernetes Administrator"],
        interview_blueprint=InterviewBlueprint(
            technical_topics=[
                TechnicalTopic(topic="Kafka consumer group rebalancing",
                                originating_project="Realtime Analytics Dashboard",
                                originating_experience="", evidence="uses Kafka"),
            ],
            estimated_weaknesses=[],
        ),
    ).model_dump()


class TestEvaluationHappensPerTurn(unittest.TestCase):
    def setUp(self):
        self.profile = _real_profile()

    def test_advance_conversation_response_includes_evaluation(self):
        result, status = ce.start_conversation(self.profile)
        conversation_id = result["conversation_id"]
        reply, status = ce.advance_conversation(conversation_id, "I built this myself using Kafka and Python.")
        self.assertEqual(status, 200)
        self.assertIn("evaluation", reply)
        self.assertIn("overall_score", reply["evaluation"])
        self.assertIn("dimensions", reply["evaluation"])
        ce.end_conversation(conversation_id)

    def test_end_conversation_includes_full_evaluation_ledger(self):
        result, _ = ce.start_conversation(self.profile)
        conversation_id = result["conversation_id"]
        turn_count = 1
        while True:
            reply, _ = ce.advance_conversation(conversation_id, "I built this myself, handling every part carefully.")
            if reply.get("is_completed"):
                break
            turn_count += 1
        summary, status = ce.end_conversation(conversation_id)
        self.assertEqual(status, 200)
        self.assertEqual(len(summary["evaluations"]), turn_count)

    def test_evaluation_never_influences_next_question_selection(self):
        """Phase 3 explicitly does not implement the Adaptive Controller —
        a weak, generic answer must not change which spec comes next."""
        result, _ = ce.start_conversation(self.profile)
        conversation_id = result["conversation_id"]
        first_next_category = None
        reply, _ = ce.advance_conversation(conversation_id, "no")  # deliberately weak/unhelpful answer
        if not reply.get("is_completed"):
            first_next_category = reply["next_question"]["category"]
        ce.end_conversation(conversation_id)

        # Re-run with a strong answer instead — the SEQUENCE of categories
        # visited must be identical either way, since selection is driven
        # entirely by the deterministic Planner, never by evaluation.
        result2, _ = ce.start_conversation(self.profile)
        conversation_id2 = result2["conversation_id"]
        reply2, _ = ce.advance_conversation(
            conversation_id2, "I designed the whole Kafka pipeline myself, handling consumer rebalancing and schema evolution."
        )
        second_next_category = reply2["next_question"]["category"] if not reply2.get("is_completed") else None
        ce.end_conversation(conversation_id2)

        self.assertEqual(first_next_category, second_next_category)


class TestEvaluatorPinnedPerSession(unittest.TestCase):
    def test_session_evaluator_is_pinned_at_start(self):
        profile = _real_profile()
        result, _ = ce.start_conversation(profile)
        conversation_id = result["conversation_id"]
        pinned = ce._conversations[conversation_id]["evaluator"]

        # Registering and activating a DIFFERENT evaluator mid-session must
        # not affect this already-started session (RFC Section 10 risk
        # mitigation: no mid-session evaluator swap).
        class OtherEvaluator(HeuristicEvaluator):
            name = "other-test-evaluator"
        evaluator_registry.register_evaluator(OtherEvaluator(), make_active=True)

        self.assertIs(ce._conversations[conversation_id]["evaluator"], pinned)
        ce.end_conversation(conversation_id)


if __name__ == "__main__":
    unittest.main()
