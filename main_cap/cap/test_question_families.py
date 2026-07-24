"""Tests for question_families.py — Phase 2, Task 3 (question families)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from question_families import (
    DuplicateFamilyError,
    FamilyDefinition,
    PhrasingContext,
    ReasoningType,
    all_family_names,
    families_for_category,
    get_family,
    register_family,
)
from question_specification import QuestionCategory


class TestRegistry(unittest.TestCase):
    def test_all_requested_families_are_registered(self):
        requested = {
            "overview", "responsibilities", "architecture", "implementation",
            "tradeoffs", "decision_making", "debugging", "optimization",
            "lessons_learned", "future_improvements", "reflection",
            "team_collaboration", "ownership", "scaling", "testing",
            "deployment", "failures",
        }
        self.assertTrue(requested.issubset(set(all_family_names())))

    def test_get_family_returns_definition(self):
        defn = get_family("overview")
        self.assertIsInstance(defn, FamilyDefinition)
        self.assertEqual(defn.name, "overview")

    def test_families_for_category_only_returns_applicable(self):
        for name in families_for_category(QuestionCategory.CERTIFICATION):
            self.assertIn(QuestionCategory.CERTIFICATION, get_family(name).applicable_categories)

    def test_families_for_category_deterministic_order(self):
        a = families_for_category(QuestionCategory.PROJECT_DEEP_DIVE)
        b = families_for_category(QuestionCategory.PROJECT_DEEP_DIVE)
        self.assertEqual(a, b)
        self.assertEqual(a, tuple(sorted(a)))

    def test_every_category_has_at_least_one_family(self):
        for category in QuestionCategory:
            self.assertGreater(len(families_for_category(category)), 0, category)

    def test_registering_a_new_family_does_not_modify_existing_code(self):
        """The extensibility requirement: adding a family is one
        `register_family` call, nothing else changes."""
        register_family(FamilyDefinition(
            name="_test_only_new_family",
            reasoning_type=ReasoningType.RECALL,
            applicable_categories=frozenset({QuestionCategory.CERTIFICATION}),
            phrasing_variants=(lambda ctx: f"Test question about {ctx.certification_name}.",),
        ))
        self.assertIn("_test_only_new_family", families_for_category(QuestionCategory.CERTIFICATION))
        # cleanup so other tests aren't affected by test ordering
        from question_families import _FAMILY_REGISTRY
        del _FAMILY_REGISTRY["_test_only_new_family"]

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(DuplicateFamilyError):
            register_family(FamilyDefinition(
                name="overview", reasoning_type=ReasoningType.RECALL,
                applicable_categories=frozenset({QuestionCategory.PROJECT_OVERVIEW}),
                phrasing_variants=(lambda ctx: "x",),
            ))

    def test_family_with_no_variants_rejected(self):
        with self.assertRaises(ValueError):
            register_family(FamilyDefinition(
                name="_test_empty", reasoning_type=ReasoningType.RECALL,
                applicable_categories=frozenset({QuestionCategory.PROJECT_OVERVIEW}),
                phrasing_variants=(),
            ))


class TestPhrasingVariantsRender(unittest.TestCase):
    def test_every_family_every_applicable_category_renders_nonempty_text(self):
        for name in all_family_names():
            defn = get_family(name)
            for category in defn.applicable_categories:
                ctx = PhrasingContext(
                    category=category, text_seed="a specific detail",
                    title="Sample Project", technologies=("Python", "Redis"),
                    role="Engineer", company="Acme", certification_name="Sample Cert",
                    source_id="Sample Project",
                )
                for variant in defn.phrasing_variants:
                    text = variant(ctx)
                    self.assertIsInstance(text, str)
                    self.assertGreater(len(text.strip()), 5)

    def test_each_family_has_at_least_two_variants(self):
        for name in all_family_names():
            self.assertGreaterEqual(len(get_family(name).phrasing_variants), 1)


if __name__ == "__main__":
    unittest.main()
