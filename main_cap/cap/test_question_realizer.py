"""Tests for question_realizer.py — Phase 2, Tasks 1, 2, 4, 7, 9."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import question_realizer
from conversation_memory import ConversationMemory
from interview_question import InterviewQuestion
from question_realizer import FOLLOWUP_ANGLES, realize, realize_followup
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _spec(spec_id="topic_0", title="My Project", text_seed="Redis caching strategy",
          category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed_is_sentence=False):
    return QuestionSpecification(
        id=spec_id, category=category, text_seed=text_seed,
        text_seed_is_sentence=text_seed_is_sentence,
        grounding=Grounding(project=ProjectGrounding(title=title, technologies=("Python", "Redis"))),
        source_type=SourceType.PROJECT, source_id=title, source_field="interview_seeds", reason="test",
    )


class TestRealizeReturnsInterviewQuestion(unittest.TestCase):
    def test_returns_interview_question_not_a_raw_string(self):
        question, variant_idx = realize(_spec(), ConversationMemory(), turn_number=1)
        self.assertIsInstance(question, InterviewQuestion)
        self.assertIsInstance(variant_idx, int)

    def test_question_mentions_its_source(self):
        question, _ = realize(_spec(title="Resume Discussion Platform"), ConversationMemory(), 1)
        self.assertIn("Resume Discussion Platform", question.question_text)

    def test_project_reference_set_for_project_grounded_spec(self):
        question, _ = realize(_spec(title="My Project"), ConversationMemory(), 1)
        self.assertEqual(question.project_reference, "My Project")

    def test_is_followup_false_for_fresh_turn(self):
        question, _ = realize(_spec(), ConversationMemory(), 1)
        self.assertFalse(question.is_followup)

    def test_turn_number_propagates(self):
        question, _ = realize(_spec(), ConversationMemory(), turn_number=7)
        self.assertEqual(question.turn_number, 7)

    def test_metadata_contains_provenance(self):
        question, _ = realize(_spec(), ConversationMemory(), 1)
        meta = question.metadata_dict()
        self.assertEqual(meta["source_id"], "My Project")
        self.assertEqual(meta["category"], "project_deep_dive")

    def test_realizer_never_mutates_memory(self):
        memory = ConversationMemory()
        realize(_spec(), memory, 1)
        self.assertEqual(memory.turn_count(), 0)  # only record_turn() mutates memory

    def test_specification_embedded_unchanged(self):
        spec = _spec()
        question, _ = realize(spec, ConversationMemory(), 1)
        self.assertEqual(question.specification, spec)


class TestDeterminism(unittest.TestCase):
    """Section 4: the same specification + same conversation history must
    always produce identical output — no `random`, ever."""

    def test_identical_spec_and_memory_state_produce_identical_question(self):
        q1, v1 = realize(_spec(), ConversationMemory(), 1)
        q2, v2 = realize(_spec(), ConversationMemory(), 1)
        self.assertEqual(q1.question_text, q2.question_text)
        self.assertEqual(v1, v2)

    def test_different_spec_ids_can_produce_different_variants(self):
        """Not a strict requirement, but confirms variant selection is
        actually spec-id-sensitive rather than a constant."""
        variants_seen = set()
        for i in range(10):
            _, v = realize(_spec(spec_id=f"topic_{i}"), ConversationMemory(), 1)
            variants_seen.add(v)
        self.assertGreater(len(variants_seen), 1)

    def test_no_python_random_module_used(self):
        import question_realizer as qr
        import inspect
        source = inspect.getsource(qr)
        self.assertNotIn("import random", source)
        self.assertNotIn("random.", source)


class TestVariantRotation(unittest.TestCase):
    def test_immediately_repeating_style_is_avoided(self):
        """If the deterministic base index would exactly repeat the last
        phrasing style used, the realizer must flip to the other variant."""
        memory = ConversationMemory()
        spec = _spec()
        q1, v1 = realize(spec, memory, 1)
        memory.record_turn(q1, v1)
        # Force the "last style" to look exactly like what a second call to
        # the same spec+family would compute, to exercise the flip branch.
        family = q1.family
        memory.recent_phrasing_styles[-1] = (family, question_realizer._stable_index(spec.id, family, modulus=2))
        q2, v2 = realize(spec, memory, 2)
        if q2.family == family:
            self.assertNotEqual(v1, v2)


class TestFollowupInfrastructure(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()
        self.spec = _spec(text_seed="Redis caching strategy")

    def test_realize_followup_returns_interview_question(self):
        question, _ = realize_followup(self.spec, self.memory, turn_number=2)
        self.assertIsInstance(question, InterviewQuestion)
        self.assertTrue(question.is_followup)

    def test_followup_stays_on_same_specification(self):
        question, _ = realize_followup(self.spec, self.memory, turn_number=2)
        self.assertEqual(question.specification.id, self.spec.id)

    def test_followup_has_no_transition(self):
        question, _ = realize_followup(self.spec, self.memory, turn_number=2)
        self.assertEqual(question.transition_text, "")

    def test_followup_grounded_in_text_seed_when_no_focus_hint(self):
        question, _ = realize_followup(self.spec, self.memory, turn_number=2, angle="clarification")
        self.assertIn("Redis caching strategy", question.question_text)

    def test_followup_uses_focus_hint_when_provided(self):
        question, _ = realize_followup(
            self.spec, self.memory, turn_number=2, angle="clarification", focus_hint="the caching TTL"
        )
        self.assertIn("the caching TTL", question.question_text)

    def test_all_documented_followup_angles_are_selectable(self):
        expected = {
            "clarification", "more_detail", "tradeoff_probing", "design_justification",
            "debugging_decisions", "alternative_approaches", "ownership", "reflection",
        }
        self.assertTrue(expected.issubset(set(FOLLOWUP_ANGLES)))

    def test_followup_angle_selection_is_deterministic(self):
        a = question_realizer.select_followup_angle(self.spec, ConversationMemory(), 0)
        b = question_realizer.select_followup_angle(self.spec, ConversationMemory(), 0)
        self.assertEqual(a, b)

    def test_followup_infrastructure_does_not_require_evaluation(self):
        """Phase 2 explicitly does not implement answer-based adaptation —
        realize_followup must work with zero knowledge of answer quality."""
        question, _ = realize_followup(self.spec, self.memory, turn_number=2)
        self.assertIsInstance(question, InterviewQuestion)


class TestFollowupAngleCategoryAwareness(unittest.TestCase):
    """Phase 5 follow-up fix (session handover): a follow-up on a
    SKILL_IN_CONTEXT spec must never select "tradeoff_probing" -- the
    same evidence gap discussion_policy._ARC[SKILL_IN_CONTEXT] was
    already fixed to avoid for fresh turns (Phase 5), reproduced live via
    this SEPARATE, previously-unaudited selection path."""

    def setUp(self):
        self.memory = ConversationMemory()
        self.linux_spec = _spec(
            spec_id="topic_linux", title="AI SOC Analyst – Intelligent Security Log Analysis Platform",
            text_seed="Linux", category=QuestionCategory.SKILL_IN_CONTEXT,
        )

    def test_auto_selection_never_picks_tradeoff_probing_for_skill_in_context(self):
        """Direct regression for the reported bug: walking several
        follow-up positions on the real Linux SKILL_IN_CONTEXT spec must
        never land on tradeoff_probing."""
        seen = []
        for followups_used in range(6):
            angle = question_realizer.select_followup_angle(self.linux_spec, self.memory, followups_used)
            seen.append(angle)
        self.assertNotIn("tradeoff_probing", seen)

    def test_explicit_tradeoff_probing_request_is_reassigned_for_skill_in_context(self):
        """Even an EXPLICITLY requested unavailable angle (bypassing
        select_followup_angle entirely) must never render the
        unsupported tradeoff question -- realize_followup itself must
        refuse and fall back to a category-appropriate angle."""
        question, _ = realize_followup(self.linux_spec, self.memory, turn_number=2, angle="tradeoff_probing")
        self.assertNotEqual(question.family, "tradeoff_probing")
        self.assertNotIn("tradeoffs did you weigh", question.question_text.lower())
        self.assertNotIn("other options you considered", question.question_text.lower())

    def test_reproduces_and_fixes_the_exact_reported_linux_followup_case(self):
        question, _ = realize_followup(self.linux_spec, self.memory, turn_number=2, angle="tradeoff_probing")
        self.assertNotEqual(
            question.question_text,
            "What tradeoffs did you weigh around Linux in AI SOC Analyst – Intelligent Security Log Analysis Platform?",
        )

    def test_project_deep_dive_tradeoff_probing_remains_available(self):
        """Positive control: the exclusion is scoped to SKILL_IN_CONTEXT
        only -- PROJECT_DEEP_DIVE (where seed_synthesis.py's own
        tradeoff_probe precondition already governs real evidence) can
        still explicitly select tradeoff_probing."""
        deep_dive_spec = _spec(
            spec_id="topic_dd", title="RD Platform", text_seed="Redis vs Memcached",
            category=QuestionCategory.PROJECT_DEEP_DIVE,
        )
        question, _ = realize_followup(deep_dive_spec, self.memory, turn_number=2, angle="tradeoff_probing")
        self.assertEqual(question.family, "tradeoff_probing")
        self.assertIn("tradeoffs did you weigh", question.question_text.lower())

    def test_project_deep_dive_auto_selection_can_still_reach_tradeoff_probing(self):
        deep_dive_spec = _spec(
            spec_id="topic_dd2", title="RD Platform", text_seed="Redis vs Memcached",
            category=QuestionCategory.PROJECT_DEEP_DIVE,
        )
        memory = ConversationMemory()
        seen = [
            question_realizer.select_followup_angle(deep_dive_spec, memory, i)
            for i in range(len(FOLLOWUP_ANGLES))
        ]
        self.assertIn("tradeoff_probing", seen)


class TestFollowupSentenceShapedSeedProtection(unittest.TestCase):
    """Fix #2 (seed-substitution / garbled-question investigation):
    realize_followup shares question_families._seed_clause with fresh
    turns via _render() -- confirmed live that a sentence-shaped text_seed
    reaches _FOLLOWUP_ANGLE_FAMILY-mapped angles ("tradeoff_probing" ->
    "tradeoffs", etc.) through this exact path, reproducing the identical
    doubly-nested garble a fresh PROJECT_DEEP_DIVE turn would. Both the
    family-mapped angles (excluded via _angle_available) and the
    template-only angles (protected via _followup_focus's own fallback)
    need coverage here."""

    def setUp(self):
        self.memory = ConversationMemory()
        self.sentence_spec = _spec(
            spec_id="topic_agno", title="Patient OS v2",
            text_seed="Why did you use Agno in this project?",
            category=QuestionCategory.PROJECT_DEEP_DIVE,
            text_seed_is_sentence=True,
        )

    def test_auto_selection_never_picks_a_seed_clause_dependent_angle_for_a_sentence_seed(self):
        from question_families import family_requires_short_seed
        seen = []
        for followups_used in range(8):
            angle = question_realizer.select_followup_angle(self.sentence_spec, self.memory, followups_used)
            seen.append(angle)
        for angle in seen:
            mapped_family = question_realizer._FOLLOWUP_ANGLE_FAMILY.get(angle)
            if mapped_family is not None:
                self.assertFalse(
                    family_requires_short_seed(mapped_family),
                    f"selected angle {angle!r} -> unsafe family {mapped_family!r} for a sentence-shaped seed",
                )

    def test_explicit_family_mapped_angle_request_is_reassigned_for_a_sentence_seed(self):
        """Direct reproduction of the exact reported failure shape, via an
        explicitly-requested angle (bypassing select_followup_angle),
        mirroring test_explicit_tradeoff_probing_request_is_reassigned_
        for_skill_in_context above but for seed SHAPE instead of category."""
        question, _ = realize_followup(self.sentence_spec, self.memory, turn_number=2, angle="tradeoff_probing")
        self.assertNotEqual(question.family, "tradeoff_probing")
        self.assertNotIn("why did you use agno in this project", question.question_text.lower())
        self.assertNotIn("were there other options you considered for why", question.question_text.lower())

    def test_template_only_angle_does_not_embed_the_raw_sentence(self):
        """_FOLLOWUP_TEMPLATES angles (clarification/more_detail/
        alternative_approaches) use _followup_focus, a DIFFERENT function
        than _seed_clause with the identical garbling risk -- e.g.
        "Could you clarify what you mean by Why did you use Agno in this
        project?" -- must not occur."""
        question, _ = realize_followup(
            self.sentence_spec, self.memory, turn_number=2, angle="clarification",
        )
        self.assertNotIn("why did you use agno in this project?", question.question_text.lower())

    def test_short_clause_seed_still_reaches_family_mapped_angles(self):
        """Regression guard: correctly-shaped (short) seeds keep their
        existing follow-up behavior -- this is exactly
        test_project_deep_dive_auto_selection_can_still_reach_tradeoff_
        probing above, re-asserted here for clarity of what this fix must
        NOT change."""
        short_spec = _spec(
            spec_id="topic_short", title="RD Platform", text_seed="Redis vs Memcached",
            category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed_is_sentence=False,
        )
        memory = ConversationMemory()
        seen = [
            question_realizer.select_followup_angle(short_spec, memory, i)
            for i in range(len(FOLLOWUP_ANGLES))
        ]
        self.assertIn("tradeoff_probing", seen)

    def test_short_clause_seed_template_only_angle_unaffected(self):
        short_spec = _spec(
            spec_id="topic_short2", title="RD Platform", text_seed="Redis caching",
            category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed_is_sentence=False,
        )
        question, _ = realize_followup(short_spec, self.memory, turn_number=2, angle="clarification")
        self.assertIn("redis caching", question.question_text.lower())


if __name__ == "__main__":
    unittest.main()
