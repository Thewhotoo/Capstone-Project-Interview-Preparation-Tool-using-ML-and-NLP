"""
Tests for coverage_tracker.py — Phase 1 of ResumeDiscussion_v2 (Chapter 14).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coverage_tracker import CoverageTracker
from question_specification import QuestionCategory


class TestCoverageTracker(unittest.TestCase):
    def setUp(self):
        self.present = {
            QuestionCategory.PROJECT_DEEP_DIVE,
            QuestionCategory.PROJECT_OVERVIEW,
            QuestionCategory.EXPERIENCE,
        }
        self.tracker = CoverageTracker(self.present)

    def test_present_matches_constructor_input(self):
        self.assertEqual(self.tracker.present(), frozenset(self.present))

    def test_nothing_covered_initially(self):
        self.assertEqual(self.tracker.covered(), frozenset())
        self.assertFalse(self.tracker.all_covered())

    def test_uncovered_equals_present_initially(self):
        self.assertEqual(self.tracker.uncovered(), frozenset(self.present))

    def test_mark_covered_adds_to_covered_set(self):
        self.tracker.mark_covered(QuestionCategory.PROJECT_OVERVIEW)
        self.assertIn(QuestionCategory.PROJECT_OVERVIEW, self.tracker.covered())

    def test_mark_covered_removes_from_uncovered(self):
        self.tracker.mark_covered(QuestionCategory.PROJECT_OVERVIEW)
        self.assertNotIn(QuestionCategory.PROJECT_OVERVIEW, self.tracker.uncovered())

    def test_mark_covered_absent_category_raises(self):
        with self.assertRaises(ValueError):
            self.tracker.mark_covered(QuestionCategory.CERTIFICATION)

    def test_all_covered_false_until_every_present_category_touched(self):
        self.tracker.mark_covered(QuestionCategory.PROJECT_DEEP_DIVE)
        self.assertFalse(self.tracker.all_covered())
        self.tracker.mark_covered(QuestionCategory.PROJECT_OVERVIEW)
        self.assertFalse(self.tracker.all_covered())
        self.tracker.mark_covered(QuestionCategory.EXPERIENCE)
        self.assertTrue(self.tracker.all_covered())

    def test_marking_same_category_twice_is_idempotent(self):
        self.tracker.mark_covered(QuestionCategory.PROJECT_OVERVIEW)
        self.tracker.mark_covered(QuestionCategory.PROJECT_OVERVIEW)
        self.assertEqual(len(self.tracker.covered()), 1)

    def test_empty_present_set_is_trivially_all_covered(self):
        tracker = CoverageTracker(set())
        self.assertTrue(tracker.all_covered())


if __name__ == "__main__":
    unittest.main()
