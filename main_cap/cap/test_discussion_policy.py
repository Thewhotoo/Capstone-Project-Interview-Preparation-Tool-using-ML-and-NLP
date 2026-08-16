"""Tests for discussion_policy.py — Phase 2, Tasks 6 and 8."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discussion_policy
from conversation_memory import ConversationMemory
from discussion_policy import _ARC, select_family, select_transition
from question_families import families_for_category
from question_specification import (
    CertificationGrounding,
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _project_spec(category, source_id="P1", spec_id="topic_0", text_seed=None):
    return QuestionSpecification(
        id=spec_id, category=category, text_seed=text_seed,
        grounding=Grounding(project=ProjectGrounding(title=source_id)),
        source_type=SourceType.PROJECT, source_id=source_id, source_field="x", reason="test",
    )


def _experience_spec(source_id="Engineer at Acme", spec_id="topic_e"):
    return QuestionSpecification(
        id=spec_id, category=QuestionCategory.EXPERIENCE, text_seed=None,
        grounding=Grounding(experience=ExperienceGrounding(role="Engineer", company="Acme")),
        source_type=SourceType.EXPERIENCE, source_id=source_id, source_field="x", reason="test",
    )


def _cert_spec(source_id="AWS", spec_id="topic_c"):
    return QuestionSpecification(
        id=spec_id, category=QuestionCategory.CERTIFICATION, text_seed=None,
        grounding=Grounding(certification=CertificationGrounding(name=source_id)),
        source_type=SourceType.CERTIFICATION, source_id=source_id, source_field="name", reason="test",
    )


class TestArcConsistency(unittest.TestCase):
    """Every family in _ARC must be a real, applicable, registered family —
    this is exactly what discussion_policy.py's own module docstring
    promises is 'verified by a test rather than at import time'."""

    def test_every_arc_family_is_registered_and_applicable(self):
        for category, arc in _ARC.items():
            applicable = set(families_for_category(category))
            for family in arc:
                self.assertIn(family, applicable, f"{family!r} not applicable to {category!r}")


class TestSelectFamily(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()

    def test_first_touch_on_project_overview_spec_is_overview(self):
        spec = _project_spec(QuestionCategory.PROJECT_OVERVIEW)
        self.assertEqual(select_family(spec, self.memory), "overview")

    def test_first_touch_on_project_deep_dive_spec_is_ALSO_overview(self):
        """The documented resolution to the tier-order tension: even though
        this spec is a deep-dive spec, the first-ever turn on this project
        opens with 'overview' framing."""
        spec = _project_spec(QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching")
        self.assertEqual(select_family(spec, self.memory), "overview")

    def test_family_progresses_through_arc_as_touches_accumulate(self):
        spec = _project_spec(QuestionCategory.PROJECT_DEEP_DIVE, text_seed="x")
        seen = []
        for i in range(5):
            family = select_family(spec, self.memory)
            seen.append(family)
            # simulate recording this turn so touch counts advance
            self.memory._source_touch_counts[spec.source_id] = i + 1
            self.memory._source_category_touch_counts[(spec.source_id, spec.category.value)] = i + 1
            self.memory.recent_question_families.append(family)
        self.assertEqual(len(seen), len(set(seen)))  # no immediate repeats across the arc walk

    def test_arc_cycles_instead_of_clamping_on_a_long_tail(self):
        """A category with many more turns than its arc has entries must
        cycle back through the arc, not get stuck repeating its last one or
        two entries (the bug real manual validation caught)."""
        spec = _project_spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="x")
        seen = []
        for i in range(6):  # 2 full cycles of the 3-entry skill_in_context arc
            family = select_family(spec, self.memory)
            seen.append(family)
            self.memory._source_touch_counts[spec.source_id] = i + 1
            self.memory._source_category_touch_counts[(spec.source_id, spec.category.value)] = i + 1
            self.memory.recent_question_families.append(family)
        self.assertEqual(len(set(seen)), 3)  # all 3 arc entries actually get used
        self.assertEqual(seen[0:3], seen[3:6])  # and the cycle repeats identically

    def test_other_categories_touches_on_the_same_project_do_not_advance_this_categorys_arc(self):
        """The bug real manual validation caught: a project touched many
        times by project_deep_dive turns must not make its FIRST
        skill_in_context turn think it's deep into that arc already."""
        project_title = "Shared Project"
        deep_dive_spec = _project_spec(QuestionCategory.PROJECT_DEEP_DIVE, source_id=project_title, spec_id="dd", text_seed="x")
        for i in range(5):
            family = select_family(deep_dive_spec, self.memory)
            self.memory._source_touch_counts[project_title] = i + 1
            self.memory._source_category_touch_counts[(project_title, "project_deep_dive")] = i + 1
            self.memory.recent_question_families.append(family)

        skill_spec = _project_spec(QuestionCategory.SKILL_IN_CONTEXT, source_id=project_title, spec_id="sk", text_seed="y")
        skill_arc = _ARC[QuestionCategory.SKILL_IN_CONTEXT]
        first_skill_family = select_family(skill_spec, self.memory)
        self.assertEqual(first_skill_family, skill_arc[0] if skill_arc[0] != self.memory.last_family() else skill_arc[1])

    def test_project_overview_category_does_not_reopen_with_overview_if_already_used(self):
        """A project_deep_dive spec already framed the project's opening
        as 'overview' — a later project_overview-category spec for the SAME
        project must not repeat that framing."""
        project_title = "Shared Project"
        deep_dive_spec = _project_spec(QuestionCategory.PROJECT_DEEP_DIVE, source_id=project_title, spec_id="dd", text_seed="x")
        family = select_family(deep_dive_spec, self.memory)
        self.assertEqual(family, "overview")
        self.memory._source_touch_counts[project_title] = 1
        self.memory._source_category_touch_counts[(project_title, "project_deep_dive")] = 1
        self.memory.recent_question_families.append(family)
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="dd", source_id=project_title, category="project_deep_dive",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference=project_title,
        ))

        overview_spec = _project_spec(QuestionCategory.PROJECT_OVERVIEW, source_id=project_title, spec_id="ov")
        second_family = select_family(overview_spec, self.memory)
        self.assertNotEqual(second_family, "overview")

    def test_never_repeats_the_immediately_preceding_family(self):
        spec_a = _project_spec(QuestionCategory.PROJECT_OVERVIEW, source_id="A", spec_id="a")
        family_a = select_family(spec_a, self.memory)
        self.memory.recent_question_families.append(family_a)
        self.memory._source_touch_counts["A"] = 1
        self.memory._source_category_touch_counts[("A", "project_overview")] = 1

        spec_b = _project_spec(QuestionCategory.PROJECT_OVERVIEW, source_id="B", spec_id="b")
        family_b = select_family(spec_b, self.memory)
        # B is a fresh project (touch_index 0) so would also want "overview"
        # were it not for the anti-repeat rule against the immediately
        # preceding family.
        if family_a == "overview":
            self.assertNotEqual(family_b, "overview")

    def test_deterministic_for_identical_state(self):
        spec = _project_spec(QuestionCategory.PROJECT_OVERVIEW)
        a = select_family(spec, ConversationMemory())
        b = select_family(spec, ConversationMemory())
        self.assertEqual(a, b)


class TestSelectTransition(unittest.TestCase):
    def setUp(self):
        self.memory = ConversationMemory()

    def test_first_question_has_no_transition(self):
        spec = _project_spec(QuestionCategory.PROJECT_OVERVIEW)
        self.assertEqual(select_transition(spec, self.memory), "")

    def test_same_source_id_gets_same_topic_transition(self):
        spec_a = _project_spec(QuestionCategory.PROJECT_OVERVIEW, source_id="A", spec_id="a")
        self.memory._source_touch_counts["A"] = 1
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="a", source_id="A", category="project_overview",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference="A",
        ))
        transition = select_transition(spec_a, self.memory)
        self.assertIn(transition, discussion_policy._TRANSITIONS["same_topic"])

    def test_new_project_after_different_project_gets_new_project_transition(self):
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="a", source_id="A", category="project_overview",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference="A",
        ))
        spec_b = _project_spec(QuestionCategory.PROJECT_OVERVIEW, source_id="B", spec_id="b")
        transition = select_transition(spec_b, self.memory)
        self.assertIn(transition, discussion_policy._TRANSITIONS["new_project"])

    def test_returning_to_a_previously_discussed_project_says_so(self):
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory._source_touch_counts["A"] = 1
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="a", source_id="A", category="project_overview",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference="A",
        ))
        # turn 2: a different topic entirely
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=2, spec_id="c", source_id="AWS", category="certification",
            family="motivation", reasoning_type=ReasoningType.REFLECTION, is_followup=False,
            project_reference=None,
        ))
        # turn 3: back to project A
        spec_a_again = _project_spec(QuestionCategory.PROJECT_DEEP_DIVE, source_id="A", spec_id="a2")
        transition = select_transition(spec_a_again, self.memory)
        self.assertIn(transition, discussion_policy._TRANSITIONS["returning_project"])

    def test_experience_gets_experience_transition(self):
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="a", source_id="A", category="project_overview",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference="A",
        ))
        spec_exp = _experience_spec()
        transition = select_transition(spec_exp, self.memory)
        self.assertIn(transition, discussion_policy._TRANSITIONS["new_experience"])

    def test_certification_gets_certification_transition(self):
        from conversation_memory import ConversationTurnRecord
        from question_families import ReasoningType
        self.memory.timeline.append(ConversationTurnRecord(
            turn_number=1, spec_id="a", source_id="A", category="project_overview",
            family="overview", reasoning_type=ReasoningType.RECALL, is_followup=False,
            project_reference="A",
        ))
        spec_cert = _cert_spec()
        transition = select_transition(spec_cert, self.memory)
        self.assertIn(transition, discussion_policy._TRANSITIONS["new_certification"])

    def test_deterministic_for_identical_state(self):
        spec = _project_spec(QuestionCategory.PROJECT_OVERVIEW)
        self.assertEqual(select_transition(spec, ConversationMemory()), select_transition(spec, ConversationMemory()))


class TestSkillInContextArcOwnershipFix(unittest.TestCase):
    """Phase 4 (ownership audit): SKILL_IN_CONTEXT's arc must use
    "skill_application", never "implementation" -- the latter asserts
    ownership ("building X") the category's bare-technology-name evidence
    never supports. PROJECT_DEEP_DIVE's own arc must be untouched."""

    def test_skill_in_context_arc_uses_skill_application_not_implementation(self):
        arc = _ARC[QuestionCategory.SKILL_IN_CONTEXT]
        self.assertIn("skill_application", arc)
        self.assertNotIn("implementation", arc)

    def test_skill_in_context_arc_length_and_other_entries_unchanged(self):
        """Only the one entry changed -- same length, same
        decision_making/tradeoffs neighbors, same position."""
        self.assertEqual(
            _ARC[QuestionCategory.SKILL_IN_CONTEXT],
            ("decision_making", "skill_application", "tradeoffs"),
        )

    def test_project_deep_dive_arc_still_uses_implementation(self):
        """Regression guard: the swap is scoped to SKILL_IN_CONTEXT only."""
        self.assertIn("implementation", _ARC[QuestionCategory.PROJECT_DEEP_DIVE])

    def test_second_skill_in_context_touch_selects_skill_application(self):
        """End-to-end through select_family: the second touch on a
        skill_in_context spec (arc index 1) must resolve to
        skill_application, not implementation."""
        memory = ConversationMemory()
        spec = _project_spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="FastAPI")
        first = select_family(spec, memory)
        memory._source_touch_counts[spec.source_id] = 1
        memory._source_category_touch_counts[(spec.source_id, spec.category.value)] = 1
        memory.recent_question_families.append(first)
        second = select_family(spec, memory)
        self.assertEqual(second, "skill_application")


if __name__ == "__main__":
    unittest.main()
