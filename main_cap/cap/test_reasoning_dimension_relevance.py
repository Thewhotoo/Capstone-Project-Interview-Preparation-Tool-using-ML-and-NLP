"""Tests for reasoning_dimension_relevance.py — Phase 3, RFC Section 6."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from question_families import ReasoningType
from question_specification import QuestionCategory
from reasoning_dimension_relevance import (
    ALL_DIMENSIONS,
    ARCHITECTURE,
    AUTHENTICITY,
    COMMUNICATION,
    COMPLETENESS,
    RESUME_GROUNDING,
    TECHNICAL_ACCURACY,
    TRADEOFFS,
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


class TestBackwardCompatibilityNoCategory(unittest.TestCase):
    """`category` is optional and defaults to None -- every pre-Phase-6
    call site (and every existing test above) must see EXACTLY today's
    behavior when it isn't supplied."""

    def test_omitting_category_matches_original_behavior_for_every_reasoning_type(self):
        for rt in ReasoningType:
            self.assertEqual(relevant_dimensions(rt), relevant_dimensions(rt, None))

    def test_decision_making_without_category_still_includes_architecture_and_tradeoffs(self):
        dims = relevant_dimensions(ReasoningType.DECISION_MAKING)
        self.assertIn(ARCHITECTURE, dims)
        self.assertIn(TRADEOFFS, dims)


class TestCategoryAwareExclusion(unittest.TestCase):
    """Phase 6: the one evidenced exclusion -- DECISION_MAKING's
    reasoning-type-level architecture/tradeoffs dimensions are not
    meaningful for SKILL_IN_CONTEXT's bare-technology-name evidence (see
    session handover investigation / reasoning_dimension_relevance.py's
    DIMENSION_EXCLUSIONS_BY_CATEGORY docstring)."""

    def test_decision_making_plus_skill_in_context_excludes_architecture_and_tradeoffs(self):
        dims = relevant_dimensions(ReasoningType.DECISION_MAKING, QuestionCategory.SKILL_IN_CONTEXT)
        self.assertNotIn(ARCHITECTURE, dims)
        self.assertNotIn(TRADEOFFS, dims)

    def test_decision_making_plus_skill_in_context_keeps_always_relevant_dimensions(self):
        """Narrowing removes only the two evidenced dimensions -- the
        always-relevant core is untouched."""
        dims = relevant_dimensions(ReasoningType.DECISION_MAKING, QuestionCategory.SKILL_IN_CONTEXT)
        self.assertIn(TECHNICAL_ACCURACY, dims)
        self.assertIn(COMMUNICATION, dims)
        self.assertIn(COMPLETENESS, dims)
        self.assertIn(RESUME_GROUNDING, dims)

    def test_decision_making_plus_project_overview_preserves_architecture_and_tradeoffs(self):
        dims = relevant_dimensions(ReasoningType.DECISION_MAKING, QuestionCategory.PROJECT_OVERVIEW)
        self.assertIn(ARCHITECTURE, dims)
        self.assertIn(TRADEOFFS, dims)

    def test_decision_making_plus_project_deep_dive_preserves_architecture_and_tradeoffs(self):
        dims = relevant_dimensions(ReasoningType.DECISION_MAKING, QuestionCategory.PROJECT_DEEP_DIVE)
        self.assertIn(ARCHITECTURE, dims)
        self.assertIn(TRADEOFFS, dims)

    def test_unrelated_reasoning_type_category_combinations_are_unaffected(self):
        """Every (reasoning_type, category) pair NOT in the exclusion
        table behaves exactly like relevant_dimensions(reasoning_type)
        alone -- for every reasoning type and every category, not just
        a hand-picked few."""
        for rt in ReasoningType:
            for category in QuestionCategory:
                if (rt, category) == (ReasoningType.DECISION_MAKING, QuestionCategory.SKILL_IN_CONTEXT):
                    continue
                self.assertEqual(
                    relevant_dimensions(rt, category), relevant_dimensions(rt),
                    f"{rt}/{category} should be unaffected by category narrowing",
                )

    def test_exclusion_never_widens_the_reasoning_type_set(self):
        """A (reasoning_type, category) pair's result is always a SUBSET
        of relevant_dimensions(reasoning_type) alone -- category can only
        narrow, never add a dimension reasoning_type itself wouldn't."""
        for rt in ReasoningType:
            for category in QuestionCategory:
                self.assertTrue(
                    relevant_dimensions(rt, category) <= relevant_dimensions(rt),
                    f"{rt}/{category} widened the base set",
                )


if __name__ == "__main__":
    unittest.main()
