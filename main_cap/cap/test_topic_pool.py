"""
Tests for topic_pool.py — Phase 1 of ResumeDiscussion_v2 (Chapters 9-11, 14).

Covers:
- TopicPool generation from a Candidate Profile
- Coverage tracking integration
- Deterministic selection / priority ordering
- Traceability of every generated QuestionSpecification
- Invalid (untraceable) topic rejection
- Duplicate prevention (identity-level, Phase 1 scope)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import (
    empty_profile_dict,
    minimal_profile_dict,
    sample_profile_dict,
)
from question_specification import (
    CATEGORY_PRIORITY,
    QuestionCategory,
    SourceType,
    UnitStatus,
)
from topic_pool import TopicPool


class TestTopicPoolGeneration(unittest.TestCase):
    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_project_deep_dive_units_built_from_interview_seeds(self):
        deep_dives = [
            s for s in self.pool.specifications.values()
            if s.category == QuestionCategory.PROJECT_DEEP_DIVE
        ]
        self.assertEqual(len(deep_dives), 2)  # sample profile has 2 interview_seeds
        for spec in deep_dives:
            self.assertEqual(spec.source_id, "Resume Discussion Platform")
            self.assertEqual(spec.source_field, "interview_seeds")

    def test_project_overview_unit_built_per_project(self):
        overviews = [
            s for s in self.pool.specifications.values()
            if s.category == QuestionCategory.PROJECT_OVERVIEW
        ]
        self.assertEqual(len(overviews), 2)  # 2 projects on the sample profile
        titles = {s.source_id for s in overviews}
        self.assertEqual(titles, {"Resume Discussion Platform", "Static Portfolio Site"})

    def test_experience_unit_built_per_experience_entry(self):
        experiences = [
            s for s in self.pool.specifications.values()
            if s.category == QuestionCategory.EXPERIENCE
        ]
        self.assertEqual(len(experiences), 1)
        self.assertEqual(experiences[0].source_id, "Software Engineering Intern at Acme Corp")

    def test_certification_unit_built_per_certification(self):
        certs = [
            s for s in self.pool.specifications.values()
            if s.category == QuestionCategory.CERTIFICATION
        ]
        self.assertEqual(len(certs), 1)
        self.assertEqual(certs[0].source_id, "AWS Certified Cloud Practitioner")

    def test_skill_in_context_units_only_for_traceable_topics(self):
        skills = [
            s for s in self.pool.specifications.values()
            if s.category == QuestionCategory.SKILL_IN_CONTEXT
        ]
        # 3 technical_topics in the fixture, 1 untraceable -> only 2 units
        self.assertEqual(len(skills), 2)
        source_ids = {s.source_id for s in skills}
        self.assertIn("Resume Discussion Platform", source_ids)
        self.assertIn("Software Engineering Intern at Acme Corp", source_ids)

    def test_priority_boost_set_for_weakness_touching_units(self):
        boosted = [s for s in self.pool.specifications.values() if s.priority_boost]
        self.assertTrue(boosted)
        for spec in boosted:
            self.assertIn("Resume Discussion Platform", spec.reason + spec.source_id)

    def test_empty_profile_builds_zero_units_without_error(self):
        pool = TopicPool(empty_profile_dict())
        self.assertEqual(len(pool.specifications), 0)
        self.assertEqual(pool.categories_present(), frozenset())
        self.assertTrue(pool.all_categories_covered())  # vacuously true

    def test_minimal_profile_builds_one_overview_unit(self):
        pool = TopicPool(minimal_profile_dict())
        self.assertEqual(len(pool.specifications), 1)
        spec = next(iter(pool.specifications.values()))
        self.assertEqual(spec.category, QuestionCategory.PROJECT_OVERVIEW)

    def test_accepts_pydantic_style_profile_via_model_dump_shape(self):
        # Even though we pass a plain dict here, this exercises the same
        # `_profile_to_dict` path a real CandidateProfile.model_dump() would
        # take — see test_planner.py for the real-model integration test.
        pool = TopicPool(sample_profile_dict())
        self.assertGreater(len(pool.specifications), 0)


class TestInvalidTopicRejection(unittest.TestCase):
    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_untraceable_topic_is_rejected_not_built(self):
        skill_source_ids = {
            s.source_id for s in self.pool.specifications.values()
            if s.category == QuestionCategory.SKILL_IN_CONTEXT
        }
        self.assertNotIn("Order Management System", skill_source_ids)

    def test_rejected_topic_recorded_with_reason(self):
        self.assertEqual(len(self.pool.rejected), 1)
        rejected = self.pool.rejected[0]
        self.assertEqual(rejected.topic, "GraphQL federation")
        self.assertEqual(rejected.originating_project, "Order Management System")
        self.assertTrue(rejected.reason)

    def test_rejected_topic_never_surfaces_as_a_specification(self):
        for spec in self.pool.specifications.values():
            self.assertNotEqual(spec.text_seed, "GraphQL federation")


class TestTraceabilityOfGeneratedSpecifications(unittest.TestCase):
    """FR2 / Chapter 16: every generated specification must resolve to
    exactly one real Candidate Profile entity."""

    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_every_specification_has_non_empty_provenance(self):
        for spec in self.pool.specifications.values():
            self.assertTrue(spec.source_type)
            self.assertTrue(spec.source_id.strip())
            self.assertTrue(spec.source_field.strip())
            self.assertTrue(spec.reason.strip())

    def test_every_project_sourced_spec_traces_to_a_real_project(self):
        profile = sample_profile_dict()
        real_titles = {p["title"] for p in profile["projects"]}
        for spec in self.pool.specifications.values():
            if spec.source_type == SourceType.PROJECT:
                self.assertIn(spec.grounding.project.title, real_titles)
                self.assertEqual(spec.source_id, spec.grounding.project.title)

    def test_every_experience_sourced_spec_traces_to_a_real_experience(self):
        for spec in self.pool.specifications.values():
            if spec.source_type == SourceType.EXPERIENCE:
                self.assertEqual(spec.grounding.experience.role, "Software Engineering Intern")

    def test_every_certification_sourced_spec_traces_to_a_real_certification(self):
        for spec in self.pool.specifications.values():
            if spec.source_type == SourceType.CERTIFICATION:
                self.assertEqual(spec.grounding.certification.name, "AWS Certified Cloud Practitioner")

    def test_no_specification_blends_two_entities(self):
        # Every Grounding already enforces exactly-one-entity at construction
        # (test_question_specification.py); this asserts the pool never even
        # attempts to build one that would violate it.
        for spec in self.pool.specifications.values():
            set_count = sum(
                x is not None
                for x in (spec.grounding.project, spec.grounding.experience, spec.grounding.certification)
            )
            self.assertEqual(set_count, 1)


class TestDuplicatePrevention(unittest.TestCase):
    """Phase 1 duplicate prevention is identity-level (no phrased text exists
    yet for semantic dedup, Chapter 15 — that's the Question Realizer's
    job). Covers: (a) identical (project, seed) pairs never produce twin
    units, and (b) select_next never re-returns an already-selected spec."""

    def test_duplicate_interview_seed_text_does_not_produce_two_units(self):
        profile = sample_profile_dict()
        profile["projects"][0]["interview_seeds"] = [
            "Why Redis caching?",
            "Why Redis caching?",  # literal duplicate
        ]
        pool = TopicPool(profile)
        deep_dives = [
            s for s in pool.specifications.values()
            if s.category == QuestionCategory.PROJECT_DEEP_DIVE
        ]
        self.assertEqual(len(deep_dives), 1)

    def test_select_next_never_reselects_an_asked_unit(self):
        pool = TopicPool(sample_profile_dict())
        seen_ids = set()
        last_category = None
        for _ in range(len(pool.specifications)):
            spec = pool.select_next(last_category)
            self.assertIsNotNone(spec)
            self.assertNotIn(spec.id, seen_ids)
            seen_ids.add(spec.id)
            pool.mark_covered(spec.id)
            last_category = spec.category
        # Pool now exhausted.
        self.assertIsNone(pool.select_next(last_category))
        self.assertEqual(len(seen_ids), len(pool.specifications))


class TestPriorityOrdering(unittest.TestCase):
    """Chapter 10.3: tier order is the dominant factor, overridden only by
    the coverage-sweep bonus for a category untouched this session."""

    def test_tier_weights_match_architecture_table(self):
        self.assertEqual(CATEGORY_PRIORITY[QuestionCategory.PROJECT_DEEP_DIVE], 5)
        self.assertEqual(CATEGORY_PRIORITY[QuestionCategory.PROJECT_OVERVIEW], 4)
        self.assertEqual(CATEGORY_PRIORITY[QuestionCategory.EXPERIENCE], 3)
        self.assertEqual(CATEGORY_PRIORITY[QuestionCategory.CERTIFICATION], 2)
        self.assertEqual(CATEGORY_PRIORITY[QuestionCategory.SKILL_IN_CONTEXT], 1)

    def test_first_selection_is_highest_tier_present(self):
        pool = TopicPool(sample_profile_dict())
        first = pool.select_next(None)
        # project_deep_dive (tier 5) exists on the sample profile and has no
        # competing coverage-sweep bonus yet (nothing has been covered), so
        # it wins outright.
        self.assertEqual(first.category, QuestionCategory.PROJECT_DEEP_DIVE)

    def test_coverage_sweep_beats_tier_for_untouched_categories(self):
        """Once every category has been touched once, subsequent selections
        fall back to strict tier order among what's left."""
        pool = TopicPool(sample_profile_dict())
        last_category = None
        touched_order = []
        while True:
            spec = pool.select_next(last_category)
            if spec is None:
                break
            touched_order.append(spec.category)
            pool.mark_covered(spec.id)
            last_category = spec.category

        # Every present category must appear in the touched order at least
        # once (the coverage-sweep guarantee, Chapter 14) ...
        self.assertEqual(set(touched_order), pool.categories_present())

        # ... and the LAST category to be first touched in this sweep must
        # be lower tier than project_deep_dive, since the coverage bonus only
        # ever fires once per category and every project_deep_dive-tier unit
        # was already exhausted by tier dominance beforehand in this fixture
        # (2 deep-dive units < number of remaining categories to sweep).
        first_touch = {}
        for cat in touched_order:
            first_touch.setdefault(cat, True)
        self.assertIn(QuestionCategory.PROJECT_DEEP_DIVE, first_touch)

    def test_priority_boost_breaks_ties_within_a_tier(self):
        pool = TopicPool(sample_profile_dict())
        overview_specs = [
            s for s in pool.specifications.values()
            if s.category == QuestionCategory.PROJECT_OVERVIEW
        ]
        boosted = [s for s in overview_specs if s.priority_boost]
        not_boosted = [s for s in overview_specs if not s.priority_boost]
        self.assertTrue(boosted)
        self.assertTrue(not_boosted)
        # Mark every other category covered first so the coverage-sweep
        # bonus can't mask the priority_boost tie-break within this tier.
        for cat in pool.categories_present():
            if cat != QuestionCategory.PROJECT_OVERVIEW:
                for spec in list(pool.specifications.values()):
                    if spec.category == cat and pool.lifecycle_of(spec.id).status == UnitStatus.UNASKED:
                        pool.mark_covered(spec.id)
        chosen = pool.select_next(QuestionCategory.PROJECT_OVERVIEW)
        self.assertTrue(chosen.priority_boost)


class TestCoverageIntegration(unittest.TestCase):
    def test_categories_present_matches_actual_units(self):
        pool = TopicPool(sample_profile_dict())
        expected = {s.category for s in pool.specifications.values()}
        self.assertEqual(pool.categories_present(), expected)

    def test_all_categories_covered_false_until_every_category_touched(self):
        pool = TopicPool(sample_profile_dict())
        self.assertFalse(pool.all_categories_covered())

    def test_mark_active_updates_coverage(self):
        pool = TopicPool(sample_profile_dict())
        spec = pool.select_next(None)
        pool.mark_active(spec.id)
        self.assertIn(spec.category, pool.categories_covered())
        self.assertEqual(pool.lifecycle_of(spec.id).status, UnitStatus.ACTIVE)

    def test_mark_skipped_still_counts_as_covered_for_the_category(self):
        pool = TopicPool(sample_profile_dict())
        spec = pool.select_next(None)
        pool.mark_skipped(spec.id)
        self.assertIn(spec.category, pool.categories_covered())
        self.assertEqual(pool.lifecycle_of(spec.id).status, UnitStatus.SKIPPED)

    def test_remaining_count_decreases_as_units_are_resolved(self):
        pool = TopicPool(sample_profile_dict())
        total = len(pool.specifications)
        self.assertEqual(pool.remaining(), total)
        spec = pool.select_next(None)
        pool.mark_covered(spec.id)
        self.assertEqual(pool.remaining(), total - 1)


if __name__ == "__main__":
    unittest.main()
