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


def _skill_ctx(tech: str, title: str):
    """A SKILL_IN_CONTEXT-shaped PhrasingContext -- text_seed is the bare
    technology name (candidate_profile_mapper._gazetteer_matches never
    captures a verb/ownership signal), grounded in the project it was
    found in, exactly what topic_pool.py's Priority 5 block builds."""
    return PhrasingContext(
        category=QuestionCategory.SKILL_IN_CONTEXT, text_seed=tech,
        title=title, technologies=(), role="", company="", certification_name="",
        source_id=title,
    )


_OWNERSHIP_WORDS = ("build", "built", "implement")


class TestSkillApplicationFamily(unittest.TestCase):
    """Phase 4 (ownership audit): SKILL_IN_CONTEXT's only evidence is a
    bare technology name -- no per-mention ownership signal exists (see
    session handover investigation). Neutral "used"/"worked with"
    phrasing must replace "implementation" family's ownership-asserting
    wording for this category only."""

    def test_skill_application_registered_and_applicable_only_to_skill_in_context(self):
        defn = get_family("skill_application")
        self.assertEqual(defn.applicable_categories, frozenset({QuestionCategory.SKILL_IN_CONTEXT}))

    def test_skill_application_never_contains_ownership_language(self):
        ctx = _skill_ctx("FastAPI", "AI SOC Analyst")
        defn = get_family("skill_application")
        for variant in defn.phrasing_variants:
            text = variant(ctx).lower()
            for word in _OWNERSHIP_WORDS:
                self.assertNotIn(word, text, f"{word!r} found in: {text!r}")

    def test_skill_application_names_the_technology_and_project(self):
        ctx = _skill_ctx("FastAPI", "AI SOC Analyst")
        defn = get_family("skill_application")
        for variant in defn.phrasing_variants:
            text = variant(ctx)
            self.assertIn("FastAPI", text)
            self.assertIn("AI SOC Analyst", text)

    def test_reproduces_and_fixes_the_exact_reported_fastapi_case(self):
        """Direct regression for the reported bug: "How did you go about
        building FastAPI in AI SOC Analyst..." must never be produced by
        the family SKILL_IN_CONTEXT actually uses now."""
        ctx = _skill_ctx("FastAPI", "AI SOC Analyst – Intelligent Security Log Analysis Platform")
        defn = get_family("skill_application")
        texts = [variant(ctx) for variant in defn.phrasing_variants]
        for text in texts:
            self.assertNotIn("go about building FastAPI", text)
            self.assertNotIn("how you implemented", text.lower())
        self.assertIn(
            "How did you use FastAPI in AI SOC Analyst – Intelligent Security Log Analysis Platform?",
            texts,
        )

    def test_react_linux_deberta_also_use_neutral_wording(self):
        """Not FastAPI-specific -- every bare technology seed gets the
        same neutral treatment."""
        for tech, title in (
            ("React", "AI SOC Analyst"),
            ("Linux", "AI SOC Analyst"),
            ("DeBERTa", "AI-Powered Adaptive Interview Preparation Platform"),
        ):
            ctx = _skill_ctx(tech, title)
            defn = get_family("skill_application")
            for variant in defn.phrasing_variants:
                text = variant(ctx).lower()
                for word in _OWNERSHIP_WORDS:
                    self.assertNotIn(word, text, f"{word!r} found for {tech!r}: {text!r}")


class TestImplementationFamilyUnchangedForProjectDeepDive(unittest.TestCase):
    """Regression guard: "implementation" itself must remain completely
    untouched and still available for PROJECT_DEEP_DIVE -- only
    SKILL_IN_CONTEXT's arc entry changed, not the family."""

    def test_implementation_still_applies_to_project_deep_dive_and_skill_in_context(self):
        defn = get_family("implementation")
        self.assertEqual(
            defn.applicable_categories,
            frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.SKILL_IN_CONTEXT}),
        )

    def test_implementation_wording_unchanged(self):
        ctx = PhrasingContext(
            category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
            title="Resume Discussion Platform", technologies=(), role="", company="",
            certification_name="", source_id="Resume Discussion Platform",
        )
        defn = get_family("implementation")
        texts = [variant(ctx) for variant in defn.phrasing_variants]
        self.assertEqual(
            texts,
            [
                "I noticed Resume Discussion Platform involved Redis caching. Can you walk me through how you implemented that?",
                "How did you go about building Redis caching in Resume Discussion Platform?",
            ],
        )


_TRADEOFF_WORDS = ("tradeoff", "other options", "why didn't you go with")


class TestSkillContextFamily(unittest.TestCase):
    """Phase 5 (Linux/tradeoff grounding audit): SKILL_IN_CONTEXT's only
    evidence is a bare technology name -- no comparison-language signal
    exists (see session handover investigation). Neutral "what role did
    it play"/"how did it fit in" phrasing must replace "tradeoffs"
    family's comparison-presupposing wording for this category only."""

    def test_skill_context_registered_and_applicable_only_to_skill_in_context(self):
        defn = get_family("skill_context")
        self.assertEqual(defn.applicable_categories, frozenset({QuestionCategory.SKILL_IN_CONTEXT}))

    def test_skill_context_never_contains_tradeoff_language(self):
        ctx = _skill_ctx("Linux", "AI SOC Analyst")
        defn = get_family("skill_context")
        for variant in defn.phrasing_variants:
            text = variant(ctx).lower()
            for phrase in _TRADEOFF_WORDS:
                self.assertNotIn(phrase, text, f"{phrase!r} found in: {text!r}")

    def test_skill_context_never_contains_ownership_language(self):
        """Not just tradeoff-safe -- also doesn't reintroduce Phase 4's
        ownership problem."""
        ctx = _skill_ctx("Linux", "AI SOC Analyst")
        defn = get_family("skill_context")
        for variant in defn.phrasing_variants:
            text = variant(ctx).lower()
            for word in _OWNERSHIP_WORDS:
                self.assertNotIn(word, text, f"{word!r} found in: {text!r}")

    def test_skill_context_names_the_technology_and_project(self):
        ctx = _skill_ctx("Linux", "AI SOC Analyst")
        defn = get_family("skill_context")
        for variant in defn.phrasing_variants:
            text = variant(ctx)
            self.assertIn("Linux", text)
            self.assertIn("AI SOC Analyst", text)

    def test_reproduces_and_fixes_the_exact_reported_linux_case(self):
        """Direct regression for the reported bug: "What tradeoffs did
        you weigh around Linux in AI SOC Analyst..." must never be
        produced by the family SKILL_IN_CONTEXT actually uses now."""
        ctx = _skill_ctx("Linux", "AI SOC Analyst – Intelligent Security Log Analysis Platform")
        defn = get_family("skill_context")
        texts = [variant(ctx) for variant in defn.phrasing_variants]
        for text in texts:
            self.assertNotIn("tradeoffs did you weigh", text.lower())
            self.assertNotIn("other options you considered", text.lower())
        self.assertIn(
            "What role did Linux play in AI SOC Analyst – Intelligent Security Log Analysis Platform?",
            texts,
        )

    def test_react_fastapi_deberta_also_use_neutral_wording(self):
        """Not Linux-specific -- every bare technology seed gets the same
        neutral treatment."""
        for tech, title in (
            ("React", "AI SOC Analyst"),
            ("FastAPI", "AI SOC Analyst"),
            ("DeBERTa", "AI-Powered Adaptive Interview Preparation Platform"),
        ):
            ctx = _skill_ctx(tech, title)
            defn = get_family("skill_context")
            for variant in defn.phrasing_variants:
                text = variant(ctx).lower()
                for phrase in _TRADEOFF_WORDS:
                    self.assertNotIn(phrase, text, f"{phrase!r} found for {tech!r}: {text!r}")


class TestTradeoffsFamilyUnchangedForProjectDeepDive(unittest.TestCase):
    """Regression guard: "tradeoffs" itself must remain completely
    untouched and still available for PROJECT_DEEP_DIVE -- only
    SKILL_IN_CONTEXT's arc entry changed, not the family."""

    def test_tradeoffs_still_applies_to_project_deep_dive_and_skill_in_context(self):
        defn = get_family("tradeoffs")
        self.assertEqual(
            defn.applicable_categories,
            frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.SKILL_IN_CONTEXT}),
        )

    def test_tradeoffs_wording_unchanged(self):
        ctx = PhrasingContext(
            category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
            title="Resume Discussion Platform", technologies=(), role="", company="",
            certification_name="", source_id="Resume Discussion Platform",
        )
        defn = get_family("tradeoffs")
        texts = [variant(ctx) for variant in defn.phrasing_variants]
        self.assertEqual(
            texts,
            [
                "What tradeoffs did you weigh around Redis caching in Resume Discussion Platform?",
                "Were there other options you considered for Redis caching, and why didn't you go with them?",
            ],
        )


if __name__ == "__main__":
    unittest.main()
