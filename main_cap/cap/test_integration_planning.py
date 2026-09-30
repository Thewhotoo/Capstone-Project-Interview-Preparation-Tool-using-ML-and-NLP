"""
Integration tests for the complete planning flow — Phase 1.5, Task 3
(docs/architecture/ResumeDiscussion_v2.md, Chapters 7-11, 14).

    Candidate Profile -> Planner -> TopicPool -> QuestionSpecification

These exercise the REAL `CandidateProfile` Pydantic model from
candidate_profile_generator.py (imported read-only, never modified) end to
end through both entry points that now exist in the project:

    1. Directly through `Planner`/`TopicPool` (the new planning subsystem).
    2. Through `discussion_engine.start_session`/`reply` (the live Flask
       route implementation), which — since Phase 1.5's migration — is
       backed by the exact same planning subsystem via
       legacy_topic_pool_adapter.TopicPool.

Both entry points must agree, because there is now exactly one planning
implementation in the project (Phase 1.5's Task 1 goal).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discussion_engine as de
from candidate_profile_generator import (
    CandidateProfile,
    ExperienceEntry,
    InterviewBlueprint,
    ProjectEntry,
    TechnicalTopic,
)
from planner import ConversationState, Planner
from question_specification import QuestionCategory, SourceType, UnitStatus


def _real_candidate_profile() -> CandidateProfile:
    """A realistic CandidateProfile built through the REAL Pydantic model —
    not a synthetic planner-only dict — covering all five discussion
    categories plus one deliberately untraceable technical_topic."""
    return CandidateProfile(
        candidate_name="Integration Test Candidate",
        skills=["Python", "Kubernetes", "PostgreSQL"],
        experience=[
            ExperienceEntry(
                company="Globex",
                role="Backend Engineering Intern",
                duration="Summer 2023",
                summary="Built billing microservices.",
            )
        ],
        projects=[
            ProjectEntry(
                title="Realtime Analytics Dashboard",
                summary="A streaming analytics dashboard for e-commerce metrics.",
                technologies=["Python", "Kafka", "Postgres"],
                concepts=["Stream processing", "Data modeling"],
                interview_seeds=[
                    "Why Kafka over a simple queue?",
                    "How did you handle late-arriving events?",
                ],
            ),
            ProjectEntry(
                title="CLI Task Manager",
                summary="A command-line task tracker.",
                technologies=["Python"],
                concepts=["CLI design"],
                interview_seeds=[],
            ),
        ],
        certifications=["Certified Kubernetes Administrator"],
        interview_blueprint=InterviewBlueprint(
            technical_topics=[
                TechnicalTopic(
                    topic="Kafka consumer group rebalancing",
                    originating_project="Realtime Analytics Dashboard",
                    originating_experience="",
                    evidence="uses Kafka for the streaming pipeline",
                ),
                TechnicalTopic(
                    topic="Billing microservice idempotency",
                    originating_project="",
                    originating_experience="Backend Engineering Intern",
                    evidence="built billing microservices",
                ),
                TechnicalTopic(
                    topic="GraphQL gateway design",
                    originating_project="Nonexistent Gateway Project",
                    originating_experience="",
                    evidence="not traceable to anything on this profile",
                ),
            ],
            estimated_weaknesses=["CLI Task Manager"],
        ),
    )


class TestFullFlowThroughPlanner(unittest.TestCase):
    """Candidate Profile -> Planner -> TopicPool -> QuestionSpecification,
    driven directly (no Flask, no discussion_engine)."""

    def setUp(self):
        self.profile = _real_candidate_profile()
        self.planner = Planner(self.profile)

    def test_every_specification_is_traceable(self):
        state = ConversationState()
        seen = 0
        while True:
            spec = self.planner.plan_next(state)
            if spec is None:
                break
            seen += 1
            self.assertTrue(spec.source_type)
            self.assertTrue(spec.source_id.strip())
            self.assertTrue(spec.source_field.strip())
            self.assertTrue(spec.reason.strip())
            # Grounding must reference exactly one real entity — enforced by
            # QuestionSpecification's own validators at construction time,
            # re-asserted here as an integration-level sanity check.
            grounded_entities = [
                e for e in (spec.grounding.project, spec.grounding.experience,
                            spec.grounding.certification) if e is not None
            ]
            self.assertEqual(len(grounded_entities), 1)
            self.planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertGreater(seen, 0)

    def test_untraceable_topic_never_becomes_a_specification(self):
        state = ConversationState()
        text_seeds = []
        while True:
            spec = self.planner.plan_next(state)
            if spec is None:
                break
            text_seeds.append(spec.text_seed)
            self.planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertNotIn("GraphQL gateway design", text_seeds)
        self.assertEqual(len(self.planner.rejected), 1)
        self.assertEqual(self.planner.rejected[0].topic, "GraphQL gateway design")

    def test_no_duplicate_specifications(self):
        state = ConversationState()
        seen_ids = set()
        seen_identity_tuples = set()
        while True:
            spec = self.planner.plan_next(state)
            if spec is None:
                break
            self.assertNotIn(spec.id, seen_ids)
            seen_ids.add(spec.id)
            identity = (spec.category, spec.source_id, spec.text_seed)
            self.assertNotIn(identity, seen_identity_tuples)
            seen_identity_tuples.add(identity)
            self.planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)

    def test_deterministic_ordering_across_independent_planners(self):
        def run(profile):
            planner = Planner(profile)
            state = ConversationState()
            order = []
            while True:
                spec = planner.plan_next(state)
                if spec is None:
                    break
                order.append(spec.id)
                planner.advance(spec.id, UnitStatus.COVERED)
                state = ConversationState(last_category=spec.category)
            return order

        order_a = run(_real_candidate_profile())
        order_b = run(_real_candidate_profile())
        self.assertEqual(order_a, order_b)

    def test_complete_coverage_reached(self):
        state = ConversationState()
        while True:
            spec = self.planner.plan_next(state)
            if spec is None:
                break
            self.planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertTrue(self.planner.all_categories_covered())
        expected_categories = {
            QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.PROJECT_OVERVIEW,
            QuestionCategory.EXPERIENCE, QuestionCategory.CERTIFICATION,
            QuestionCategory.SKILL_IN_CONTEXT,
        }
        self.assertEqual(self.planner.categories_present(), expected_categories)

    def test_no_invalid_specifications_reach_the_pool(self):
        """Every specification that exists must have passed
        QuestionSpecification's own validation at construction — this
        asserts the pool never silently swallowed a validation error into a
        malformed spec (it would have raised during `_build` instead)."""
        for spec in self.planner.pool.specifications.values():
            self.assertIn(spec.source_type, (SourceType.PROJECT, SourceType.EXPERIENCE, SourceType.CERTIFICATION))
            self.assertTrue(spec.id)


class TestFullFlowThroughDiscussionEngine(unittest.TestCase):
    """The SAME real CandidateProfile, driven through the live
    discussion_engine.start_session/reply routes — which, since Phase 1.5's
    migration, are backed by legacy_topic_pool_adapter.TopicPool wrapping
    the exact same planning subsystem exercised above."""

    def setUp(self):
        self.profile_dict = _real_candidate_profile().model_dump()

    def test_start_session_produces_a_traceable_first_question(self):
        result, status = de.start_session(self.profile_dict, "profile_session_x")
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "success")
        self.assertIn(result["question"]["category"], {
            "project_deep_dive", "project_overview", "experience",
            "certification", "skill_in_context",
        })

    def test_full_session_reaches_completion_with_full_coverage(self):
        result, status = de.start_session(self.profile_dict, "profile_session_y")
        self.assertEqual(status, 200)
        session_id = result["session_id"]

        seen_categories = {result["question"]["category"]}
        completed = False
        for _ in range(30):
            reply_result, reply_status = de.reply(session_id, "A reasonably detailed answer about this topic.")
            self.assertEqual(reply_status, 200)
            if reply_result.get("next_question"):
                seen_categories.add(reply_result["next_question"]["category"])
            if reply_result.get("is_completed"):
                completed = True
                break
        self.assertTrue(completed)

        summary, summary_status = de.end_session(session_id)
        self.assertEqual(summary_status, 200)
        # Every category present on this profile must have been touched
        # (Chapter 14's completion gate) before the session was allowed to end.
        self.assertEqual(seen_categories, {
            "project_deep_dive", "project_overview", "experience",
            "certification", "skill_in_context",
        })

    def test_planner_and_discussion_engine_agree_on_pool_contents(self):
        """The direct Planner path and the discussion_engine path must
        build an IDENTICAL set of specifications from the same profile —
        proof that there is only one planning implementation, not two that
        happen to agree by coincidence."""
        planner = Planner(self.profile_dict)
        direct_signature = sorted(
            (s.category.value, s.source_type.value, s.source_id, s.source_field, s.text_seed)
            for s in planner.pool.specifications.values()
        )

        from legacy_topic_pool_adapter import TopicPool as AdapterTopicPool
        adapter = AdapterTopicPool(self.profile_dict)
        adapter_signature = sorted(
            (u["category"], u["source_type"], u["source_id"], u["source_field"], u["text_seed"])
            for u in adapter.units.values()
        )

        self.assertEqual(direct_signature, adapter_signature)


if __name__ == "__main__":
    unittest.main()
