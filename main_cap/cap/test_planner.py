"""
Tests for planner.py — Phase 1 of ResumeDiscussion_v2 (Chapters 9, 10).

Covers:
- Candidate Profile parsing (plain dict AND the real Pydantic CandidateProfile
  model from candidate_profile_generator.py, imported read-only)
- Planner determinism: identical Candidate Profiles must produce identical
  QuestionSpecification sequences when driven through the same advance() calls
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict, sample_profile_dict_copy
from planner import ConversationState, Planner
from question_specification import QuestionCategory, UnitStatus

# Imported read-only from the existing production module — Phase 1 does not
# modify candidate_profile_generator.py, it only consumes the CandidateProfile
# schema it already defines (Chapter 8.2/8.3).
from candidate_profile_generator import (
    CandidateProfile,
    ExperienceEntry,
    InterviewBlueprint,
    ProjectEntry,
    TechnicalTopic,
)


def _sample_candidate_profile_model() -> CandidateProfile:
    """The same fixture data as `sample_profile_dict()`, constructed through
    the REAL Pydantic CandidateProfile model rather than a plain dict."""
    return CandidateProfile(
        candidate_name="Test Candidate",
        skills=["Python", "Docker", "Redis"],
        experience=[
            ExperienceEntry(
                company="Acme Corp",
                role="Software Engineering Intern",
                duration="Summer 2024",
                summary="Built internal tooling for the data platform team.",
            )
        ],
        projects=[
            ProjectEntry(
                title="Resume Discussion Platform",
                summary="An adaptive interview platform grounded in a candidate's resume.",
                technologies=["Python", "Flask", "SBERT"],
                concepts=["Semantic similarity", "Traceability"],
                interview_seeds=["Why SBERT for answer scoring?", "Redis caching strategy"],
            ),
            ProjectEntry(
                title="Static Portfolio Site",
                summary="A simple static site built with a template engine.",
                technologies=["HTML", "CSS"],
                concepts=["Static site generation"],
                interview_seeds=[],
            ),
        ],
        certifications=["AWS Certified Cloud Practitioner"],
        interview_blueprint=InterviewBlueprint(
            technical_topics=[
                TechnicalTopic(
                    topic="SBERT semantic similarity for answer scoring",
                    originating_project="Resume Discussion Platform",
                    originating_experience="",
                    evidence="uses SBERT to score candidate answers during discussion",
                ),
                TechnicalTopic(
                    topic="Internal data tooling",
                    originating_project="",
                    originating_experience="Software Engineering Intern",
                    evidence="built internal tooling for the data platform team",
                ),
                TechnicalTopic(
                    topic="GraphQL federation",
                    originating_project="Order Management System",
                    originating_experience="",
                    evidence="irrelevant — this project does not exist on this profile",
                ),
            ],
            estimated_weaknesses=["Resume Discussion Platform"],
        ),
    )


class TestCandidateProfileParsing(unittest.TestCase):
    def test_planner_accepts_plain_dict_profile(self):
        planner = Planner(sample_profile_dict())
        self.assertGreater(len(planner.pool.specifications), 0)

    def test_planner_accepts_real_pydantic_candidate_profile_model(self):
        planner = Planner(_sample_candidate_profile_model())
        self.assertGreater(len(planner.pool.specifications), 0)

    def test_dict_and_model_inputs_produce_equivalent_pools(self):
        planner_from_dict = Planner(sample_profile_dict())
        planner_from_model = Planner(_sample_candidate_profile_model())

        def signature(planner):
            return sorted(
                (s.category.value, s.source_type.value, s.source_id, s.source_field)
                for s in planner.pool.specifications.values()
            )

        self.assertEqual(signature(planner_from_dict), signature(planner_from_model))

    def test_rejects_untraceable_topic_identically_regardless_of_input_shape(self):
        planner_from_dict = Planner(sample_profile_dict())
        planner_from_model = Planner(_sample_candidate_profile_model())
        self.assertEqual(len(planner_from_dict.pool.rejected), 1)
        self.assertEqual(len(planner_from_model.pool.rejected), 1)
        self.assertEqual(
            planner_from_dict.pool.rejected[0].topic,
            planner_from_model.pool.rejected[0].topic,
        )


class TestPlannerCoverageState(unittest.TestCase):
    def test_categories_present_delegates_to_pool(self):
        planner = Planner(sample_profile_dict())
        self.assertEqual(planner.categories_present(), planner.pool.categories_present())

    def test_all_categories_covered_false_at_start(self):
        planner = Planner(sample_profile_dict())
        self.assertFalse(planner.all_categories_covered())

    def test_advance_rejects_unasked_as_an_outcome(self):
        planner = Planner(sample_profile_dict())
        spec = planner.plan_next(ConversationState())
        with self.assertRaises(ValueError):
            planner.advance(spec.id, UnitStatus.UNASKED)


class TestPlannerDeterminism(unittest.TestCase):
    """The Planner must produce identical QuestionSpecification sequences for
    identical Candidate Profiles — no LLM, no Gemini, no randomness beyond
    the deterministic tie-breaking already implemented in TopicPool."""

    def _run_full_session(self, profile) -> list[tuple]:
        planner = Planner(profile)
        state = ConversationState()
        signatures = []
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            signatures.append(
                (
                    spec.id,
                    spec.category.value,
                    spec.text_seed,
                    spec.source_type.value,
                    spec.source_id,
                    spec.source_field,
                    spec.reason,
                    spec.priority_boost,
                )
            )
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        return signatures

    def test_identical_profiles_produce_identical_specification_sequences(self):
        run_a = self._run_full_session(sample_profile_dict())
        run_b = self._run_full_session(sample_profile_dict_copy())
        self.assertEqual(run_a, run_b)

    def test_determinism_holds_across_many_independent_planner_instances(self):
        baseline = self._run_full_session(sample_profile_dict())
        for _ in range(5):
            self.assertEqual(baseline, self._run_full_session(sample_profile_dict_copy()))

    def test_full_session_covers_every_present_category(self):
        planner = Planner(sample_profile_dict())
        state = ConversationState()
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertTrue(planner.all_categories_covered())

    def test_full_session_visits_every_specification_exactly_once(self):
        planner = Planner(sample_profile_dict())
        state = ConversationState()
        visited_ids = []
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            visited_ids.append(spec.id)
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertEqual(len(visited_ids), len(set(visited_ids)))
        self.assertEqual(set(visited_ids), set(planner.pool.specifications.keys()))


if __name__ == "__main__":
    unittest.main()
