"""Tests for conversation_memory.py — Phase 2, Task 5."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conversation_memory import ConversationMemory
from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _make_question(spec_id="topic_0", title="My Project", family="overview",
                    reasoning_type=ReasoningType.RECALL, turn_number=1,
                    is_followup=False, transition_text=""):
    spec = QuestionSpecification(
        id=spec_id, category=QuestionCategory.PROJECT_OVERVIEW, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title=title, technologies=("Python", "Redis"))),
        source_type=SourceType.PROJECT, source_id=title, source_field="summary",
        reason="test",
    )
    return InterviewQuestion(
        question_text=f"{transition_text}Tell me about {title}.",
        transition_text=transition_text, specification=spec, family=family,
        reasoning_type=reasoning_type, project_reference=title,
        is_followup=is_followup, turn_number=turn_number,
    )


class TestRecordTurn(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()

    def test_project_discussed_tracked(self):
        q = _make_question()
        self.memory.record_turn(q, variant_index=0)
        self.assertIn("My Project", self.memory.projects_discussed)

    def test_technologies_and_skills_tracked(self):
        q = _make_question()
        self.memory.record_turn(q, variant_index=0)
        self.assertIn("Python", self.memory.technologies_mentioned)
        self.assertIn("Redis", self.memory.skills_discussed)

    def test_reasoning_type_tracked(self):
        q = _make_question(reasoning_type=ReasoningType.TRADE_OFF_ANALYSIS)
        self.memory.record_turn(q, variant_index=0)
        self.assertIn(ReasoningType.TRADE_OFF_ANALYSIS, self.memory.reasoning_types_covered)

    def test_recent_families_and_styles_updated(self):
        q = _make_question(family="architecture")
        self.memory.record_turn(q, variant_index=1)
        self.assertEqual(self.memory.recent_question_families[-1], "architecture")
        self.assertEqual(self.memory.recent_phrasing_styles[-1], ("architecture", 1))

    def test_recent_transitions_updated_only_when_nonempty(self):
        q1 = _make_question(spec_id="topic_0", transition_text="")
        self.memory.record_turn(q1, variant_index=0)
        self.assertEqual(self.memory.recent_transitions, [])
        q2 = _make_question(spec_id="topic_1", transition_text="Moving on — ")
        self.memory.record_turn(q2, variant_index=0)
        self.assertEqual(self.memory.recent_transitions, ["Moving on — "])

    def test_timeline_records_every_turn_in_order(self):
        for i in range(3):
            self.memory.record_turn(_make_question(spec_id=f"topic_{i}", turn_number=i + 1), variant_index=0)
        self.assertEqual([t.turn_number for t in self.memory.timeline], [1, 2, 3])

    def test_answer_metadata_is_shape_only_not_content(self):
        q = _make_question()
        self.memory.record_turn(q, variant_index=0, answer_text="I built this using Python and Flask. It was fun.")
        answer = self.memory.timeline[-1].answer
        self.assertIsNotNone(answer)
        self.assertGreater(answer.word_count, 0)
        self.assertGreater(answer.sentence_count, 0)
        # Must NOT store the raw text or anything resembling a score.
        self.assertFalse(hasattr(answer, "text"))
        self.assertFalse(hasattr(answer, "score"))
        self.assertFalse(hasattr(answer, "overall_score"))

    def test_no_answer_text_means_no_answer_metadata(self):
        q = _make_question()
        self.memory.record_turn(q, variant_index=0)
        self.assertIsNone(self.memory.timeline[-1].answer)

    def test_never_stores_evaluation_fields(self):
        """ConversationMemory must not store evaluation — verified by
        asserting none of the evaluation-shaped attribute names exist
        anywhere on the object."""
        forbidden = ("concepts_mastered", "concepts_needing_clarification",
                     "overall_score", "grade", "correctness", "current_difficulty")
        for name in forbidden:
            self.assertFalse(hasattr(self.memory, name), name)


class TestTouchCounting(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()

    def test_times_source_touched_starts_at_zero(self):
        self.assertEqual(self.memory.times_source_touched("My Project"), 0)

    def test_times_source_touched_increments(self):
        self.memory.record_turn(_make_question(spec_id="a"), variant_index=0)
        self.memory.record_turn(_make_question(spec_id="b"), variant_index=0)
        self.assertEqual(self.memory.times_source_touched("My Project"), 2)

    def test_different_source_ids_tracked_independently(self):
        self.memory.record_turn(_make_question(spec_id="a", title="Project A"), variant_index=0)
        self.assertEqual(self.memory.times_source_touched("Project A"), 1)
        self.assertEqual(self.memory.times_source_touched("Project B"), 0)


class TestQueries(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()

    def test_last_source_id_and_family(self):
        self.memory.record_turn(_make_question(spec_id="a", title="P1", family="overview"), variant_index=0)
        self.assertEqual(self.memory.last_source_id(), "P1")
        self.assertEqual(self.memory.last_family(), "overview")

    def test_is_family_recently_used_within_window(self):
        self.memory.record_turn(_make_question(spec_id="a", family="overview"), variant_index=0)
        self.assertTrue(self.memory.is_family_recently_used("overview"))
        self.assertFalse(self.memory.is_family_recently_used("debugging"))

    def test_turn_count(self):
        self.assertEqual(self.memory.turn_count(), 0)
        self.memory.record_turn(_make_question(spec_id="a"), variant_index=0)
        self.assertEqual(self.memory.turn_count(), 1)


if __name__ == "__main__":
    unittest.main()
