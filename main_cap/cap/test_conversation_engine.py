"""
Integration tests for conversation_engine.py — Phase 2, Tasks 10-11.

Uses the REAL `CandidateProfile` Pydantic model from
candidate_profile_generator.py (imported read-only), driven through the
complete Conversation Engine: Candidate Profile -> Planner -> Question
Realizer -> InterviewQuestion, exactly the pipeline the live application
uses once a resume has been parsed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conversation_engine as ce
from candidate_profile_generator import (
    CandidateProfile,
    ExperienceEntry,
    InterviewBlueprint,
    ProjectEntry,
    TechnicalTopic,
)


def _real_profile() -> CandidateProfile:
    return CandidateProfile(
        candidate_name="Phase 2 Test Candidate",
        skills=["Python", "Kafka", "PostgreSQL", "Docker"],
        experience=[
            ExperienceEntry(
                company="Globex", role="Backend Engineering Intern",
                duration="Summer 2023", summary="Built billing microservices.",
            )
        ],
        projects=[
            ProjectEntry(
                title="Realtime Analytics Dashboard",
                summary="A streaming analytics dashboard for e-commerce metrics.",
                technologies=["Python", "Kafka", "Postgres"],
                concepts=["Stream processing", "Data modeling"],
                interview_seeds=[
                    "Why Kafka over a simple queue?",
                    "How did you handle late-arriving events?",
                ],
            ),
            ProjectEntry(
                title="CLI Task Manager",
                summary="A command-line task tracker.",
                technologies=["Python"], concepts=["CLI design"],
                interview_seeds=[],
            ),
        ],
        certifications=["Certified Kubernetes Administrator"],
        interview_blueprint=InterviewBlueprint(
            technical_topics=[
                TechnicalTopic(
                    topic="Kafka consumer group rebalancing",
                    originating_project="Realtime Analytics Dashboard",
                    originating_experience="", evidence="uses Kafka",
                ),
            ],
            estimated_weaknesses=["CLI Task Manager"],
        ),
    )


def _run_full_conversation(profile) -> tuple[list[dict], dict]:
    """Drive a complete session, returning (question_payloads, summary)."""
    result, status = ce.start_conversation(profile)
    assert status == 200, result
    questions = [result["question"]]
    conversation_id = result["conversation_id"]
    for _ in range(50):
        reply, status = ce.advance_conversation(
            conversation_id, "I built this myself, handling the core logic in Python and testing it carefully."
        )
        assert status == 200, reply
        if reply.get("is_completed"):
            break
        questions.append(reply["next_question"])
    summary, status = ce.end_conversation(conversation_id)
    assert status == 200
    return questions, summary


class TestFullConversationFlow(unittest.TestCase):
    def setUp(self):
        self.profile = _real_profile().model_dump()

    def test_conversation_completes(self):
        questions, summary = _run_full_conversation(self.profile)
        self.assertGreater(len(questions), 0)
        self.assertGreater(summary["total_questions"], 0)

    def test_every_question_grounded_in_a_real_project_experience_or_cert(self):
        questions, _ = _run_full_conversation(self.profile)
        valid_sources = {
            "Realtime Analytics Dashboard", "CLI Task Manager",
            "Backend Engineering Intern at Globex", "Certified Kubernetes Administrator",
        }
        for q in questions:
            self.assertIn(q["source_id"], valid_sources)

    def test_no_generic_technical_question_without_project_context(self):
        """No question may name a technology without also naming a project/
        experience/certification — enforced structurally here by checking
        every question has a non-empty source_id (Chapter 12.3's
        `_mentions` check is exercised at the text level below)."""
        questions, _ = _run_full_conversation(self.profile)
        for q in questions:
            self.assertTrue(q["source_id"])

    def test_technologies_only_mentioned_in_project_context(self):
        questions, _ = _run_full_conversation(self.profile)
        for q in questions:
            if "Kafka" in q["text"]:
                self.assertIn("Realtime Analytics Dashboard", q["text"])

    def test_no_duplicate_question_text(self):
        questions, _ = _run_full_conversation(self.profile)
        texts = [q["text"] for q in questions]
        self.assertEqual(len(texts), len(set(texts)))

    def test_no_immediately_repeated_family(self):
        questions, _ = _run_full_conversation(self.profile)
        families = [q["family"] for q in questions]
        for a, b in zip(families, families[1:]):
            self.assertNotEqual(a, b)

    def test_no_immediately_repeated_transition_text(self):
        result, status = ce.start_conversation(self.profile)
        conversation_id = result["conversation_id"]
        transitions = []
        for _ in range(50):
            reply, status = ce.advance_conversation(conversation_id, "A reasonably detailed answer.")
            if reply.get("is_completed"):
                break
            # transition text isn't in the public payload; inspect the live session directly
            session = ce._conversations[conversation_id]
            transitions.append(session["current_question"].transition_text)
        for a, b in zip(transitions, transitions[1:]):
            if a and b:
                self.assertNotEqual(a, b)
        ce._conversations.pop(conversation_id, None)

    def test_full_coverage_achieved(self):
        _, summary = _run_full_conversation(self.profile)
        self.assertEqual(
            set(summary["projects_discussed"]),
            {"Realtime Analytics Dashboard", "CLI Task Manager"},
        )

    def test_conversation_memory_derived_summary_fields_stay_evaluation_free(self):
        """Phase 2's approved boundary, unchanged by Phase 3: the
        ConversationMemory-derived fields (projects_discussed,
        technologies_mentioned, timeline, ...) never contain evaluation
        data. Phase 3 legitimately adds a separate, nested "evaluations"
        key (RFC Section 1's Evaluation Ledger) — that key existing is
        expected; these specific top-level, memory-derived fields must
        still never carry a score."""
        _, summary = _run_full_conversation(self.profile)
        forbidden = ("overall_score", "grade", "correctness", "concepts_mastered", "strengths", "weaknesses")
        for key in forbidden:
            self.assertNotIn(key, summary)  # not present at the TOP level
        for turn in summary["timeline"]:
            for key in forbidden:
                self.assertNotIn(key, turn)  # nor inside any individual timeline entry


class TestDeterministicReplay(unittest.TestCase):
    """Section 4 / Section 12: repeated sessions on the same profile must
    remain deterministic."""

    def test_identical_profile_produces_identical_conversation(self):
        profile = _real_profile().model_dump()
        questions_a, _ = _run_full_conversation(profile)
        questions_b, _ = _run_full_conversation(profile)
        texts_a = [q["text"] for q in questions_a]
        texts_b = [q["text"] for q in questions_b]
        self.assertEqual(texts_a, texts_b)

    def test_families_sequence_identical_across_replays(self):
        profile = _real_profile().model_dump()
        questions_a, _ = _run_full_conversation(profile)
        questions_b, _ = _run_full_conversation(profile)
        self.assertEqual([q["family"] for q in questions_a], [q["family"] for q in questions_b])


class TestPlannerIntegration(unittest.TestCase):
    """The Conversation Engine must consume the REAL Planner, not a
    synthetic replacement — verified by checking turn count matches the
    Planner's own specification count."""

    def test_turn_count_matches_planner_specification_count(self):
        from planner import Planner

        profile = _real_profile().model_dump()
        planner = Planner(profile)
        expected_turns = len(planner.pool.specifications)

        questions, summary = _run_full_conversation(profile)
        self.assertEqual(summary["total_questions"], expected_turns)

    def test_untraceable_topics_never_produce_a_question(self):
        profile = _real_profile()
        profile.interview_blueprint.technical_topics.append(
            TechnicalTopic(
                topic="Nonexistent thing", originating_project="Nonexistent Project",
                originating_experience="", evidence="n/a",
            )
        )
        questions, _ = _run_full_conversation(profile.model_dump())
        for q in questions:
            self.assertNotIn("Nonexistent Project", q["text"])


class TestStartAdvanceEndLifecycle(unittest.TestCase):
    def setUp(self):
        self.profile = _real_profile().model_dump()

    def test_start_conversation_returns_valid_shape(self):
        result, status = ce.start_conversation(self.profile)
        self.assertEqual(status, 200)
        self.assertIn("conversation_id", result)
        self.assertIn("question", result)
        ce.end_conversation(result["conversation_id"])

    def test_invalid_conversation_id_returns_404(self):
        result, status = ce.advance_conversation("does-not-exist", "answer")
        self.assertEqual(status, 404)

    def test_advance_after_completion_returns_completed_status(self):
        result, status = ce.start_conversation(self.profile)
        conversation_id = result["conversation_id"]
        for _ in range(50):
            reply, _ = ce.advance_conversation(conversation_id, "answer")
            if reply.get("is_completed"):
                break
        final, status = ce.advance_conversation(conversation_id, "answer")
        self.assertEqual(final.get("status"), "completed")


if __name__ == "__main__":
    unittest.main()
