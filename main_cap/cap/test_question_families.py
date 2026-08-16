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
from question_families import _experience_label, _experience_preposition_label
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


def _ctx(role="", company="", category=QuestionCategory.EXPERIENCE):
    return PhrasingContext(
        category=category, text_seed="a specific detail",
        title="", technologies=(), role=role, company=company, certification_name="",
        source_id="test",
    )


class TestExperienceLabelEmptyRole(unittest.TestCase):
    """Phase 2 companion fix: experience_parser.py's institution-marker
    fallback can leave role="" with a real company (e.g. "CAVE Labs -
    PES University EC Campus"). Labels/phrasing must never fabricate a
    job title in that case."""

    def test_label_is_company_alone_when_role_empty(self):
        ctx = _ctx(role="", company="CAVE Labs – PES University EC Campus")
        self.assertEqual(_experience_label(ctx), "CAVE Labs – PES University EC Campus")

    def test_label_is_role_at_company_when_both_present(self):
        ctx = _ctx(role="Senior Engineer", company="Acme Corp")
        self.assertEqual(_experience_label(ctx), "Senior Engineer at Acme Corp")

    def test_label_is_role_alone_when_company_empty(self):
        ctx = _ctx(role="Senior Engineer", company="")
        self.assertEqual(_experience_label(ctx), "Senior Engineer")

    def test_label_falls_back_to_that_role_when_both_empty(self):
        ctx = _ctx(role="", company="")
        self.assertEqual(_experience_label(ctx), "that role")

    def test_preposition_label_uses_at_not_as_when_role_empty(self):
        ctx = _ctx(role="", company="CAVE Labs – PES University EC Campus")
        phrase = _experience_preposition_label(ctx)
        self.assertEqual(phrase, "at CAVE Labs – PES University EC Campus")
        self.assertNotIn("as ", phrase)

    def test_preposition_label_uses_as_when_role_present(self):
        ctx = _ctx(role="Senior Engineer", company="Acme Corp")
        self.assertEqual(_experience_preposition_label(ctx), "as Senior Engineer at Acme Corp")

    def test_responsibilities_family_never_says_worked_as_company(self):
        """Direct regression for the reported bug: "You worked as CAVE
        Labs at PES University EC Campus" must never be produced again."""
        ctx = _ctx(role="", company="CAVE Labs – PES University EC Campus")
        defn = get_family("responsibilities")
        for variant in defn.phrasing_variants:
            text = variant(ctx)
            self.assertNotIn("as CAVE Labs", text)
            self.assertIn("at CAVE Labs", text)

    def test_team_collaboration_family_never_says_as_company(self):
        ctx = _ctx(role="", company="CAVE Labs – PES University EC Campus")
        defn = get_family("team_collaboration")
        for variant in defn.phrasing_variants:
            text = variant(ctx)
            self.assertNotIn("As CAVE Labs", text)
            self.assertNotIn("as CAVE Labs", text)
            self.assertTrue("At CAVE Labs" in text or "at CAVE Labs" in text)

    def test_responsibilities_family_still_says_worked_as_role_when_role_present(self):
        """Regression guard: normal role+company entries are unaffected."""
        ctx = _ctx(role="Senior Engineer", company="Acme Corp")
        defn = get_family("responsibilities")
        texts = [variant(ctx) for variant in defn.phrasing_variants]
        self.assertTrue(any("as Senior Engineer at Acme Corp" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
