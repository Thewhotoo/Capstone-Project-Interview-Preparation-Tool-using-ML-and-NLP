"""Tests for reasoning_dimension_relevance.py — Phase 3, RFC Section 6."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from question_families import ReasoningType
from reasoning_dimension_relevance import (
    ALL_DIMENSIONS,
    AUTHENTICITY,
    COMMUNICATION,
    COMPLETENESS,
    RESUME_GROUNDING,
    TECHNICAL_ACCURACY,
    contributes_by_default,
    relevant_dimensions,
)


class TestAlwaysRelevant(unittest.TestCase):
    def test_core_dimensions_relevant_for_every_reasoning_type(self):
        for rt in ReasoningType:
            dims = relevant_dimensions(rt)
            self.assertIn(TECHNICAL_ACCURACY, dims)
            self.assertIn(COMMUNICATION, dims)
            self.assertIn(COMPLETENESS, dims)
            self.assertIn(RESUME_GROUNDING, dims)


class TestReasoningTypeSpecificity(unittest.TestCase):
    def test_every_reasoning_type_has_an_entry(self):
        for rt in ReasoningType:
            self.assertIsInstance(relevant_dimensions(rt), frozenset)

    def test_debugging_reasoning_type_includes_debugging_dimension(self):
        from reasoning_dimension_relevance import DEBUGGING
        self.assertIn(DEBUGGING, relevant_dimensions(ReasoningType.DEBUGGING))

    def test_optimization_reasoning_type_includes_scalability(self):
        from reasoning_dimension_relevance import SCALABILITY
        self.assertIn(SCALABILITY, relevant_dimensions(ReasoningType.OPTIMIZATION))

    def test_trade_off_analysis_includes_tradeoffs_dimension(self):
        from reasoning_dimension_relevance import TRADEOFFS
        self.assertIn(TRADEOFFS, relevant_dimensions(ReasoningType.TRADE_OFF_ANALYSIS))

    def test_different_reasoning_types_can_produce_different_relevance_sets(self):
        recall_dims = relevant_dimensions(ReasoningType.RECALL)
        debugging_dims = relevant_dimensions(ReasoningType.DEBUGGING)
        self.assertNotEqual(recall_dims, debugging_dims)


class TestAuthenticityNeverContributesByDefault(unittest.TestCase):
    def test_authenticity_does_not_contribute_by_default(self):
        self.assertFalse(contributes_by_default(AUTHENTICITY))

    def test_other_dimensions_contribute_by_default(self):
        for dim in ALL_DIMENSIONS:
            if dim != AUTHENTICITY:
                self.assertTrue(contributes_by_default(dim), dim)


class TestDeterminism(unittest.TestCase):
    def test_relevant_dimensions_is_deterministic(self):
        for rt in ReasoningType:
            self.assertEqual(relevant_dimensions(rt), relevant_dimensions(rt))


if __name__ == "__main__":
    unittest.main()
