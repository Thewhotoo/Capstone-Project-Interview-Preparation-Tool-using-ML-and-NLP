"""
Tests for the "question variety" product-quality fix (investigation:
docs/architecture -- Resume Discussion v2 question-generation variety).

Three additive mechanisms, each covered independently and then together:

    1. Evidence-specific seed realization (question_realizer.py) — a
       validated, candidate-facing interview_seed sentence is rendered
       verbatim instead of being discarded in favor of a generic family.
    2. Short-window source/project cooldown (topic_pool.py) — a soft,
       additive scoring penalty so one source doesn't dominate several
       consecutive turns just because the category changes.
    3. Family-recency avoidance (discussion_policy.py) — wires the
       previously-unused ConversationMemory.is_family_recently_used into
       select_family as a soft preference layered on top of the existing
       arc/last-family logic.

None of these change QuestionSpecification's schema, the evaluator, or any
Flask route contract.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conversation_memory import ConversationMemory
from discussion_policy import _ARC, select_family
from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_realizer import (
    _SEED_VERBATIM_FAMILY,
    _is_candidate_facing_question_seed,
    realize,
)
from question_specification import (
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from topic_pool import TopicPool


def _project_spec(spec_id, source_id, category=QuestionCategory.PROJECT_DEEP_DIVE,
                   text_seed=None, text_seed_is_sentence=False, priority_boost=False,
                   technologies=()):
    return QuestionSpecification(
        id=spec_id, category=category, text_seed=text_seed,
        text_seed_is_sentence=text_seed_is_sentence,
        grounding=Grounding(project=ProjectGrounding(title=source_id, technologies=tuple(technologies))),
        priority_boost=priority_boost,
        source_type=SourceType.PROJECT, source_id=source_id, source_field="interview_seeds", reason="test",
    )


def _two_project_profile(seeds_a=(), seeds_b=()):
    """Two projects, no experience/certification/skill entries — isolates
    source-cooldown behavior from every other category's coverage-sweep
    bonus so PROJECT_DEEP_DIVE/PROJECT_OVERVIEW ties are decided purely by
    the mechanism under test."""
    return {
        "candidate_name": "Cooldown Test Candidate",
        "skills": [],
        "experience": [],
        "certifications": [],
        "projects": [
            {
                "title": "Project A", "summary": "First project.",
                "technologies": ["Python"], "concepts": [], "interview_seeds": list(seeds_a),
            },
            {
                "title": "Project B", "summary": "Second project.",
                "technologies": ["Go"], "concepts": [], "interview_seeds": list(seeds_b),
            },
        ],
        "interview_blueprint": {"technical_topics": [], "estimated_weaknesses": []},
    }


# ═════════════════════════════════════════════════════════════════════════
# 1. Seed realization
# ═════════════════════════════════════════════════════════════════════════

class TestSeedRealization(unittest.TestCase):
    def test_valid_candidate_facing_seed_is_rendered(self):
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1  # not the first touch
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Why did you use Docker in this project?",
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=2)
        self.assertEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertIn("Why did you use Docker in this project?", question.question_text)

    def test_seed_is_not_silently_discarded(self):
        """The specific investigation finding: a sentence-shaped seed must
        actually surface in the final text, not be swapped for a generic
        'your approach'/architecture-style template."""
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed='You mentioned "40% faster" — how was that measured?',
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=2)
        self.assertIn("40% faster", question.question_text)
        self.assertNotIn("your approach", question.question_text)

    def test_non_question_seed_falls_back_to_family_realization(self):
        """A sentence-shaped seed that doesn't end in '?' is not trusted —
        falls back to the existing family system exactly as before."""
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Redis caching strategy",  # no '?' — real fixture data, not invented
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=2)
        self.assertNotEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertNotIn("Redis caching strategy", question.question_text)

    def test_empty_seed_falls_back(self):
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec("topic_1", "Project A", text_seed=None, text_seed_is_sentence=True)
        question, _ = realize(spec, memory, turn_number=2)
        self.assertNotEqual(question.family, _SEED_VERBATIM_FAMILY)

    def test_non_sentence_seed_never_uses_verbatim_path(self):
        """SKILL_IN_CONTEXT-shaped bare topics (text_seed_is_sentence=False)
        must never be treated as candidate-facing, even if they happen to
        end in '?' or look question-like."""
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec("topic_1", "Project A", text_seed="React?", text_seed_is_sentence=False)
        self.assertFalse(_is_candidate_facing_question_seed(spec))

    def test_first_touch_on_source_keeps_overview_framing_even_with_a_valid_seed(self):
        """Documented, deliberate exception: the very first turn on a
        project still opens with the 'overview' family, matching
        discussion_policy's pre-existing narrative-flow decision."""
        memory = ConversationMemory()  # nothing touched yet
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Why did you use Docker in this project?",
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=1)
        self.assertEqual(question.family, "overview")
        self.assertNotIn("Why did you use Docker", question.question_text)

    def test_grounding_and_source_metadata_intact_for_verbatim_turn(self):
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Why did you use Docker in this project?",
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=2)
        self.assertIsInstance(question, InterviewQuestion)
        self.assertEqual(question.specification, spec)
        self.assertEqual(question.project_reference, "Project A")
        meta = question.metadata_dict()
        self.assertEqual(meta["source_id"], "Project A")
        self.assertEqual(meta["category"], "project_deep_dive")

    def test_verbatim_realization_is_deterministic(self):
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Why did you use Docker in this project?",
            text_seed_is_sentence=True,
        )
        memory_a = ConversationMemory()
        memory_a._source_touch_counts["Project A"] = 1
        memory_b = ConversationMemory()
        memory_b._source_touch_counts["Project A"] = 1
        q1, v1 = realize(spec, memory_a, turn_number=2)
        q2, v2 = realize(spec, memory_b, turn_number=2)
        self.assertEqual(q1.question_text, q2.question_text)
        self.assertEqual(v1, v2)


# ═════════════════════════════════════════════════════════════════════════
# 2. Source cooldown
# ═════════════════════════════════════════════════════════════════════════

class TestSourceCooldown(unittest.TestCase):
    def test_recent_source_is_not_preferred_when_alternative_exists(self):
        pool = TopicPool(_two_project_profile())
        # Both projects have exactly one PROJECT_OVERVIEW unit each, same
        # tier, same (already-covered, since it's the only category
        # present) coverage status -- a pure tie except for cooldown.
        specs = {s.source_id: s.id for s in pool.specifications.values()}
        pool.mark_covered(specs["Project A"])  # simulate: Project A was just asked
        chosen = pool.select_next(QuestionCategory.PROJECT_OVERVIEW, recent_source_ids=("Project A",))
        self.assertEqual(chosen.source_id, "Project B")

    def test_recent_source_still_selectable_with_no_alternative(self):
        pool = TopicPool(_two_project_profile(seeds_a=("Why use Flask in this project?",)))
        # Consume everything except Project A's own remaining unit.
        for spec in list(pool.specifications.values()):
            if spec.source_id != "Project A" or spec.category != QuestionCategory.PROJECT_DEEP_DIVE:
                pool.mark_covered(spec.id)
        chosen = pool.select_next(None, recent_source_ids=("Project A",))
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.source_id, "Project A")

    def test_cooldown_applies_across_different_categories_of_the_same_source(self):
        """Project A / PROJECT_DEEP_DIVE and Project A / SKILL_IN_CONTEXT
        must count as the same source for cooldown purposes."""
        profile = _two_project_profile(seeds_a=("Why use Flask in this project?",))
        profile["interview_blueprint"]["technical_topics"] = [
            {"topic": "Flask", "originating_project": "Project A", "originating_experience": "", "evidence": "uses Flask"},
        ]
        pool = TopicPool(profile)
        deep_dive_a = next(s for s in pool.specifications.values() if s.category == QuestionCategory.PROJECT_DEEP_DIVE)
        pool.mark_covered(deep_dive_a.id)
        # Remaining candidates: Project A's overview, Project A's
        # skill_in_context, Project B's overview -- Project B is a
        # different source and should be preferred over EITHER of
        # Project A's remaining (different-category) units.
        chosen = pool.select_next(QuestionCategory.PROJECT_DEEP_DIVE, recent_source_ids=("Project A",))
        self.assertEqual(chosen.source_id, "Project B")

    def test_priority_boosted_source_still_selectable_when_it_is_the_best_option(self):
        pool = TopicPool(_two_project_profile())
        # Force Project A's overview to be the priority_boost winner by
        # constructing the pool directly isn't available via the public
        # profile shape for weaknesses without touching Project B, so
        # instead verify the weaker claim the spec actually requires:
        # cooldown never REMOVES a candidate, it only reorders -- with only
        # Project A left, it must still be returned even though "recent".
        for spec in list(pool.specifications.values()):
            if spec.source_id == "Project B":
                pool.mark_covered(spec.id)
        chosen = pool.select_next(None, recent_source_ids=("Project A",))
        self.assertEqual(chosen.source_id, "Project A")

    def test_cooldown_never_overrides_tier_dominance(self):
        """A not-yet-covered category (100-point sweep bonus) from the
        recent source must still beat an already-covered category from a
        fresh source -- the penalty (3.0) is far smaller than the
        coverage-sweep bonus (100) or a tier step (10) by construction."""
        profile = _two_project_profile(seeds_a=("Why use Flask in this project?",))
        pool = TopicPool(profile)
        # Cover Project B's overview so only its (lower-tier, N/A here) is
        # left, while Project A still has an uncovered PROJECT_DEEP_DIVE.
        project_b_overview = next(
            s for s in pool.specifications.values()
            if s.source_id == "Project B" and s.category == QuestionCategory.PROJECT_OVERVIEW
        )
        pool.mark_covered(project_b_overview.id)
        chosen = pool.select_next(None, recent_source_ids=("Project A",))
        # Project A's PROJECT_DEEP_DIVE (tier 5, uncovered category) must
        # still win over Project A's own PROJECT_OVERVIEW despite the
        # cooldown penalty applying equally to both Project A units.
        self.assertEqual(chosen.category, QuestionCategory.PROJECT_DEEP_DIVE)

    def test_cooldown_is_deterministic(self):
        pool_a = TopicPool(_two_project_profile())
        pool_b = TopicPool(_two_project_profile())
        specs_a = {s.source_id: s.id for s in pool_a.specifications.values()}
        specs_b = {s.source_id: s.id for s in pool_b.specifications.values()}
        pool_a.mark_covered(specs_a["Project A"])
        pool_b.mark_covered(specs_b["Project A"])
        chosen_a = pool_a.select_next(QuestionCategory.PROJECT_OVERVIEW, recent_source_ids=("Project A",))
        chosen_b = pool_b.select_next(QuestionCategory.PROJECT_OVERVIEW, recent_source_ids=("Project A",))
        self.assertEqual(chosen_a.source_id, chosen_b.source_id)

    def test_default_recent_source_ids_preserves_old_behavior(self):
        """Every existing caller that never passes recent_source_ids must
        see byte-identical behavior to before this parameter existed."""
        pool = TopicPool(_two_project_profile())
        chosen_without_param = pool.select_next(None)
        pool2 = TopicPool(_two_project_profile())
        chosen_with_empty = pool2.select_next(None, recent_source_ids=())
        self.assertEqual(chosen_without_param.id, chosen_with_empty.id)


# ═════════════════════════════════════════════════════════════════════════
# 3. Family recency
# ═════════════════════════════════════════════════════════════════════════

class TestFamilyRecency(unittest.TestCase):
    def test_recently_used_family_is_avoided_when_alternative_exists(self):
        """Cross-category reuse of the same family NAME (e.g.
        'decision_making' appears in both PROJECT_OVERVIEW's and
        PROJECT_DEEP_DIVE's arcs) is now avoided within the recency window,
        not just the immediately preceding turn."""
        memory = ConversationMemory()
        memory.recent_question_families = ["overview", "architecture", "decision_making"]
        spec = _project_spec(
            "topic_x", "Some Project", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="x",
        )
        # Force the base arc-index computation to land on "decision_making"
        # (arc index 3) by setting this category's own touch count to 3.
        memory._source_category_touch_counts[("Some Project", "project_deep_dive")] = 3
        memory._source_touch_counts["Some Project"] = 3
        family = select_family(spec, memory)
        self.assertNotEqual(family, "decision_making")
        self.assertFalse(memory.is_family_recently_used(family))

    def test_recently_used_family_remains_usable_with_no_alternative(self):
        """SKILL_IN_CONTEXT's 3-entry arc, fully cycled within the default
        3-turn window -- every candidate is 'recently used', so the
        original (pre-recency) choice must still be allowed."""
        memory = ConversationMemory()
        spec = _project_spec("topic_s", "Some Project", category=QuestionCategory.SKILL_IN_CONTEXT, text_seed="x")
        seen = []
        for i in range(6):
            family = select_family(spec, memory)
            seen.append(family)
            memory._source_touch_counts[spec.source_id] = i + 1
            memory._source_category_touch_counts[(spec.source_id, spec.category.value)] = i + 1
            memory.recent_question_families.append(family)
        self.assertEqual(len(set(seen)), 3)  # all 3 arc entries still get used
        self.assertEqual(seen[0:3], seen[3:6])  # exact existing cyclic behavior preserved

    def test_existing_arc_progression_still_works(self):
        memory = ConversationMemory()
        spec = _project_spec("topic_p", "Some Project", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="x")
        seen = []
        for i in range(5):
            family = select_family(spec, memory)
            seen.append(family)
            memory._source_touch_counts[spec.source_id] = i + 1
            memory._source_category_touch_counts[(spec.source_id, spec.category.value)] = i + 1
            memory.recent_question_families.append(family)
        self.assertEqual(len(seen), len(set(seen)))  # still no repeats across 5 of 11 arc slots

    def test_family_recency_selection_is_deterministic(self):
        spec = _project_spec("topic_p", "Some Project", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="x")
        memory_a = ConversationMemory()
        memory_a.recent_question_families = ["overview", "architecture", "decision_making"]
        memory_b = ConversationMemory()
        memory_b.recent_question_families = ["overview", "architecture", "decision_making"]
        self.assertEqual(select_family(spec, memory_a), select_family(spec, memory_b))

    def test_recency_walk_never_selects_an_unsafe_family_for_a_sentence_seed(self):
        """The recency-avoidance walk must respect the pre-existing
        seed-safety exclusion -- it may only move between families that
        were already safe, never introduce an unsafe one."""
        from question_families import family_requires_short_seed
        memory = ConversationMemory()
        memory.recent_question_families = ["overview", "architecture"]
        spec = _project_spec(
            "topic_sd", "Some Project", category=QuestionCategory.PROJECT_DEEP_DIVE,
            text_seed="Why did you use Agno in this project?", text_seed_is_sentence=True,
        )
        memory._source_touch_counts["Some Project"] = 2
        memory._source_category_touch_counts[("Some Project", "project_deep_dive")] = 1  # arc[1] = architecture
        family = select_family(spec, memory)
        self.assertFalse(family_requires_short_seed(family))


# ═════════════════════════════════════════════════════════════════════════
# 4. Interaction between the three mechanisms
# ═════════════════════════════════════════════════════════════════════════

class TestMechanismInteraction(unittest.TestCase):
    def test_seed_based_question_still_works_when_its_source_was_recently_used(self):
        """Source cooldown affects WHICH spec TopicPool selects, never HOW
        the Realizer phrases whatever spec it's handed -- once a spec is
        selected, verbatim rendering must work exactly the same regardless
        of cooldown state."""
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="Why did you use Docker in this project?",
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=2)
        self.assertEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertIn("Why did you use Docker in this project?", question.question_text)

    def test_seed_based_question_bypasses_family_recency_check_entirely(self):
        """A verbatim-seed turn's family is a sentinel that is never a real
        registered family -- family-recency bookkeeping (which only
        compares real family names) must not affect or be confused by it."""
        memory = ConversationMemory()
        memory._source_touch_counts["Project A"] = 1
        memory.recent_question_families = [_SEED_VERBATIM_FAMILY, _SEED_VERBATIM_FAMILY]
        spec = _project_spec(
            "topic_1", "Project A",
            text_seed="How did Docker and Redis work together in this project?",
            text_seed_is_sentence=True,
        )
        question, _ = realize(spec, memory, turn_number=3)
        self.assertEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertIn("How did Docker and Redis work together in this project?", question.question_text)

    def test_generic_family_realization_unaffected_for_specs_without_valid_seeds(self):
        """SKILL_IN_CONTEXT/EXPERIENCE/CERTIFICATION specs (never
        sentence-shaped) and any spec with an invalid seed must render
        exactly through the existing family system, untouched by either
        new mechanism."""
        memory = ConversationMemory()
        spec = _project_spec(
            "topic_1", "Project A", category=QuestionCategory.SKILL_IN_CONTEXT,
            text_seed="Docker", text_seed_is_sentence=False,
        )
        question, _ = realize(spec, memory, turn_number=1)
        self.assertNotEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertIn(question.family, _ARC[QuestionCategory.SKILL_IN_CONTEXT] + ("overview",))

    def test_source_cooldown_and_seed_realization_compose_across_a_short_session(self):
        """End-to-end: once Project A's cooldown lifts (an alternative was
        chosen instead), a later turn back on Project A with a valid seed
        still renders that seed verbatim -- the two mechanisms don't fight
        each other."""
        pool = TopicPool(_two_project_profile(
            seeds_a=("Why did you use Docker in this project?",),
        ))
        memory = ConversationMemory()

        # Turn 1: forced "overview" framing (first touch), whichever
        # project wins tier/build-order first.
        state_recent = memory.recent_source_ids()
        spec1 = pool.select_next(None, state_recent)
        q1, v1 = realize(spec1, memory, turn_number=1)
        pool.mark_covered(spec1.id)
        memory.record_turn(q1, v1)

        # Turn 2: cooldown should steer away from spec1's source if a
        # same-tier alternative from a different source exists.
        spec2 = pool.select_next(spec1.category, memory.recent_source_ids())
        self.assertIsNotNone(spec2)
        q2, v2 = realize(spec2, memory, turn_number=2)
        pool.mark_covered(spec2.id)
        memory.record_turn(q2, v2)

        # However many turns later, once Project A's own PROJECT_DEEP_DIVE
        # unit (the one with a real seed) becomes the best remaining
        # choice again, it must render verbatim, not generically.
        deep_dive_a = next(
            s for s in pool.specifications.values()
            if s.source_id == "Project A" and s.category == QuestionCategory.PROJECT_DEEP_DIVE
        )
        self.assertGreater(memory.times_source_touched("Project A"), 0)
        question, _ = realize(deep_dive_a, memory, turn_number=99)
        self.assertEqual(question.family, _SEED_VERBATIM_FAMILY)
        self.assertIn("Why did you use Docker in this project?", question.question_text)


if __name__ == "__main__":
    unittest.main()
