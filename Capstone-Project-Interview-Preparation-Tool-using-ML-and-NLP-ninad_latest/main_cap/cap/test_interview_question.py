"""Tests for interview_question.py — Phase 2, Task 2."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_OVERVIEW, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title="My Project")),
        source_type=SourceType.PROJECT, source_id="My Project", source_field="summary", reason="test",
    )


def _question(**overrides):
    defaults = dict(
        question_text="Tell me about My Project.", transition_text="",
        specification=_spec(), family="overview", reasoning_type=ReasoningType.RECALL,
        project_reference="My Project", is_followup=False, turn_number=1,
    )
    defaults.update(overrides)
    return InterviewQuestion(**defaults)


class TestConstruction(unittest.TestCase):
    def test_constructs_with_all_fields(self):
        q = _question()
        self.assertEqual(q.question_text, "Tell me about My Project.")
        self.assertEqual(q.family, "overview")
        self.assertEqual(q.reasoning_type, ReasoningType.RECALL)

    def test_specification_embedded(self):
        spec = _spec()
        q = _question(specification=spec)
        self.assertEqual(q.specification, spec)

    def test_metadata_defaults_empty(self):
        q = _question()
        self.assertEqual(q.metadata, ())
        self.assertEqual(q.metadata_dict(), {})

    def test_metadata_dict_returns_a_copy(self):
        q = _question(metadata=(("k", "v"),))
        d = q.metadata_dict()
        d["k"] = "mutated"
        self.assertEqual(q.metadata_dict()["k"], "v")


class TestImmutability(unittest.TestCase):
    def test_cannot_reassign_question_text(self):
        q = _question()
        with self.assertRaises(pydantic.ValidationError):
            q.question_text = "changed"

    def test_cannot_reassign_specification(self):
        q = _question()
        with self.assertRaises(pydantic.ValidationError):
            q.specification = _spec()

    def test_cannot_reassign_family(self):
        q = _question()
        with self.assertRaises(pydantic.ValidationError):
            q.family = "debugging"

    def test_cannot_reassign_metadata(self):
        q = _question()
        with self.assertRaises(pydantic.ValidationError):
            q.metadata = (("x", "y"),)


class TestNotARawString(unittest.TestCase):
    def test_is_not_a_str_instance(self):
        q = _question()
        self.assertNotIsInstance(q, str)
        self.assertIsInstance(q, InterviewQuestion)


if __name__ == "__main__":
    unittest.main()
