"""
Tests for evaluation_engine.py — Phase 3, RFC Section 9 (Integration).

Includes the import-graph assertion that backs the architectural claim:
Conversation Engine modules (conversation_memory, question_realizer,
discussion_policy, planner, topic_pool) must remain completely unaware of
evaluation.
"""

import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict
import conversation_memory
import discussion_policy
from evaluation_engine import EvaluationLedger, build_request, evaluate, _lookup_expected_concepts
from heuristic_evaluator import HeuristicEvaluator
from planner import ConversationState, Planner
import question_realizer
import planner as planner_module
import topic_pool
from question_specification import (
    CertificationGrounding,
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
    UnitStatus,
)


def _module_imports(module) -> set:
    import inspect
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestConversationEngineUnawareOfEvaluation(unittest.TestCase):
    """RFC Section 9: Planner/TopicPool/ConversationMemory/Question
    Realizer/Discussion Policy must remain completely unaware of
    evaluation — verified by checking they never import any Evaluation
    Engine module."""

    EVALUATION_MODULES = {
        "evaluation_request", "evaluation_result", "evaluator",
        "evaluator_registry", "heuristic_evaluator", "evaluation_engine",
        "reasoning_dimension_relevance",
    }

    def test_conversation_memory_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(conversation_memory) & self.EVALUATION_MODULES)

    def test_question_realizer_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(question_realizer) & self.EVALUATION_MODULES)

    def test_discussion_policy_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(discussion_policy) & self.EVALUATION_MODULES)

    def test_planner_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(planner_module) & self.EVALUATION_MODULES)

    def test_topic_pool_does_not_import_evaluation(self):
        self.assertFalse(_module_imports(topic_pool) & self.EVALUATION_MODULES)


class TestBuildRequest(unittest.TestCase):
    def setUp(self):
        self.planner = Planner(sample_profile_dict())
        self.memory = conversation_memory.ConversationMemory()
        spec = self.planner.plan_next(ConversationState())
        self.question, self.variant_idx = question_realizer.realize(spec, self.memory, turn_number=1)

    def test_build_request_produces_valid_evaluation_request(self):
        req = build_request(self.question, "I built this myself.", self.memory, self.planner, {})
        self.assertEqual(req.question_text, self.question.question_text)
        self.assertEqual(req.reasoning_type, self.question.reasoning_type)
        self.assertEqual(req.specification, self.question.specification)
        self.assertEqual(req.answer_text, "I built this myself.")

    def test_conversation_context_reflects_memory_state(self):
        self.memory.record_turn(self.question, self.variant_idx, answer_text="An answer.")
        req = build_request(self.question, "Another answer.", self.memory, self.planner, {})
        self.assertEqual(req.conversation_context.turn_number, self.question.turn_number)
        self.assertEqual(
            set(req.conversation_context.projects_discussed_so_far),
            self.memory.projects_discussed,
        )

    def test_followups_used_reflects_planner_lifecycle(self):
        self.planner.pool.mark_active(self.question.specification.id)
        self.planner.pool.mark_followup_used(self.question.specification.id)
        req = build_request(self.question, "An answer.", self.memory, self.planner, {})
        self.assertEqual(req.conversation_context.followups_used_on_this_spec, 1)

    def test_prior_answers_come_from_answer_history_not_memory(self):
        history = {self.question.specification.id: ("earlier answer",)}
        req = build_request(self.question, "new answer", self.memory, self.planner, history)
        self.assertEqual(req.conversation_context.prior_answers_for_this_spec, ("earlier answer",))

    def test_evaluation_focus_passthrough(self):
        req = build_request(self.question, "An answer.", self.memory, self.planner, {}, evaluation_focus="caching TTL")
        self.assertEqual(req.evaluation_focus, "caching TTL")


class TestExpectedConceptsWiring(unittest.TestCase):
    """Expected Concepts revision (approved): build_request must populate
    `expected_concepts` via the deterministic registry lookup, entirely
    inside evaluation_engine.py — no QuestionSpecification/Planner changes."""

    def _profile_with_fastapi(self) -> dict:
        # A technical_topics entry naming "FastAPI" is required to produce
        # a genuine SKILL_IN_CONTEXT unit for it -- since the
        # question-category-scoped concept pool fix (real-demo audit),
        # merely listing "FastAPI" in the project's technologies no longer
        # gives every question about that project a FastAPI concept pool;
        # only a skill_in_context question actually about FastAPI does.
        profile = sample_profile_dict()
        profile["projects"][0]["technologies"] = ["Python", "FastAPI"]
        profile["interview_blueprint"]["technical_topics"].append({
            "topic": "FastAPI",
            "originating_project": "Resume Discussion Platform",
            "originating_experience": "",
            "evidence": "built the API layer with FastAPI",
        })
        return profile

    def test_expected_concepts_populated_when_technology_matches_registry(self):
        planner = Planner(self._profile_with_fastapi())
        memory = conversation_memory.ConversationMemory()
        state = ConversationState()
        # Walk turns until we find the skill_in_context turn specifically
        # about FastAPI (project_deep_dive/project_overview turns about
        # the same project correctly yield no concepts now).
        req = None
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            question, _ = question_realizer.realize(spec, memory, turn_number=1)
            candidate_req = build_request(question, "An answer.", memory, planner, {})
            if candidate_req.expected_concepts:
                req = candidate_req
                break
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)
        self.assertIsNotNone(req, "expected at least one turn grounded in the FastAPI project")
        self.assertEqual(
            req.expected_concepts,
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity"),
        )

    def test_expected_concepts_empty_when_no_registry_match(self):
        planner = Planner(sample_profile_dict())  # uses Python/Flask/SBERT — no seeded match
        memory = conversation_memory.ConversationMemory()
        spec = planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, memory, turn_number=1)
        req = build_request(question, "An answer.", memory, planner, {})
        self.assertEqual(req.expected_concepts, ())


class TestEvaluateCallThrough(unittest.TestCase):
    def test_evaluate_delegates_to_the_evaluator(self):
        planner = Planner(sample_profile_dict())
        memory = conversation_memory.ConversationMemory()
        spec = planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, memory, turn_number=1)
        req = build_request(question, "I built this myself.", memory, planner, {})
        result = evaluate(HeuristicEvaluator(), req)
        self.assertEqual(result.request_id, req.request_id)


class TestEvaluationLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = EvaluationLedger()
        self.planner = Planner(sample_profile_dict())
        self.memory = conversation_memory.ConversationMemory()

    def _evaluate_next_turn(self, evaluator, turn_number, answer="An answer about this."):
        spec = self.planner.plan_next(ConversationState())
        question, _ = question_realizer.realize(spec, self.memory, turn_number)
        req = build_request(question, answer, self.memory, self.planner, {})
        return evaluate(evaluator, req), spec

    def test_starts_empty(self):
        self.assertEqual(len(self.ledger), 0)
        self.assertEqual(self.ledger.all(), ())

    def test_append_and_all(self):
        evaluator = HeuristicEvaluator()
        result, _ = self._evaluate_next_turn(evaluator, 1)
        self.ledger.append(result)
        self.assertEqual(len(self.ledger), 1)
        self.assertEqual(self.ledger.all(), (result,))

    def test_for_specification_filters_correctly(self):
        evaluator = HeuristicEvaluator()
        result, spec = self._evaluate_next_turn(evaluator, 1)
        self.ledger.append(result)
        self.assertEqual(self.ledger.for_specification(spec.id), (result,))
        self.assertEqual(self.ledger.for_specification("nonexistent_id"), ())


class TestQuestionCategoryScopedConceptPool(unittest.TestCase):
    """Direct regression for the real-demo audit: `_lookup_expected_concepts`
    used to build its candidates from `spec.grounding.project`'s ENTIRE
    technology list for every project-grounded category alike, so a
    project_deep_dive/project_overview question (and any skill_in_context
    question about an unrelated technology in the same project) inherited
    concepts that had nothing to do with what was actually asked. Fixed by
    branching on `spec.category`, using the skill name already threaded
    through as `spec.text_seed` for SKILL_IN_CONTEXT. Never touches
    `_concept_status`, the credit formula, the registry contents, or the
    aggregate percentage."""

    @staticmethod
    def _multi_tech_project_grounding() -> ProjectGrounding:
        return ProjectGrounding(
            title="AI SOC Analyst", technologies=("React", "FastAPI", "Linux"), concepts=(), summary="",
        )

    def _spec(self, category, text_seed=None, grounding=None) -> QuestionSpecification:
        grounding = grounding or Grounding(project=self._multi_tech_project_grounding())
        if grounding.project is not None:
            source_type = SourceType.PROJECT
        elif grounding.experience is not None:
            source_type = SourceType.EXPERIENCE
        else:
            source_type = SourceType.CERTIFICATION
        return QuestionSpecification(
            id="t", category=category, text_seed=text_seed, grounding=grounding,
            source_type=source_type, source_id="AI SOC Analyst", source_field="test", reason="test",
        )

    def test_project_deep_dive_does_not_receive_the_project_technology_pool(self):
        # A project_deep_dive's text_seed is an interview-seed QUESTION
        # STRING (e.g. "Why did you use FastAPI in this project?"), never a
        # bare skill name -- confirming this category gets no pool
        # regardless of what its text_seed happens to contain.
        spec = self._spec(QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Why did you use FastAPI in this project?")
        self.assertEqual(_lookup_expected_concepts(spec), ())

    def test_project_overview_does_not_receive_the_project_technology_pool(self):
        spec = self._spec(QuestionCategory.PROJECT_OVERVIEW, text_seed=None)
        self.assertEqual(_lookup_expected_concepts(spec), ())

    def test_skill_in_context_fastapi_receives_only_fastapi_concepts(self):
        spec = self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="FastAPI")
        self.assertEqual(
            _lookup_expected_concepts(spec),
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity"),
        )

    def test_linux_targeted_question_does_not_receive_fastapi_concepts(self):
        # The exact real-demo bug: a Linux tradeoffs question, in a project
        # that also uses FastAPI, used to be graded against FastAPI's
        # concept pool. Linux has no registry entry (registry contents
        # deliberately untouched) -- correct graceful degradation is an
        # empty pool, never someone else's technology's concepts.
        spec = self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="Linux")
        concepts = _lookup_expected_concepts(spec)
        self.assertEqual(concepts, ())
        self.assertNotIn("ASGI", concepts)
        self.assertNotIn("dependency injection", concepts)

    def test_langgraph_targeted_question_receives_langgraph_concepts(self):
        spec = self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="LangGraph")
        self.assertEqual(
            _lookup_expected_concepts(spec),
            ("graph nodes", "state transitions", "orchestration", "agents", "workflow execution"),
        )

    def test_multi_technology_project_does_not_leak_across_skill_in_context_questions(self):
        # Same multi-tech project (React + FastAPI + Linux) grounds three
        # different skill_in_context specs -- each must receive ONLY its
        # own named skill's concepts, never the union of all three.
        fastapi_concepts = _lookup_expected_concepts(self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="FastAPI"))
        react_concepts = _lookup_expected_concepts(self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="React"))
        linux_concepts = _lookup_expected_concepts(self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed="Linux"))
        self.assertEqual(len(fastapi_concepts), 5)
        self.assertEqual(react_concepts, ())  # React has no registry entry either
        self.assertEqual(linux_concepts, ())
        self.assertTrue(set(fastapi_concepts).isdisjoint(react_concepts))
        self.assertTrue(set(fastapi_concepts).isdisjoint(linux_concepts))

    def test_experience_still_receives_no_concept_pool(self):
        spec = self._spec(
            QuestionCategory.EXPERIENCE, text_seed=None,
            grounding=Grounding(experience=ExperienceGrounding(role="Engineer", company="Acme")),
        )
        self.assertEqual(_lookup_expected_concepts(spec), ())

    def test_certification_lookup_is_unchanged(self):
        spec = self._spec(
            QuestionCategory.CERTIFICATION, text_seed=None,
            grounding=Grounding(certification=CertificationGrounding(name="AWS Certified Cloud Practitioner")),
        )
        # No registry entry for this cert name -- graceful degradation,
        # same as before this fix (certification lookup logic untouched).
        self.assertEqual(_lookup_expected_concepts(spec), ())

    def test_skill_in_context_with_no_text_seed_degrades_to_no_pool(self):
        """Defensive: a SKILL_IN_CONTEXT spec should never lack a
        text_seed in practice (topic_pool.py always supplies one), but if
        it somehow did, this must degrade gracefully to no pool rather
        than raise or fall back to the project's full technology list."""
        spec = self._spec(QuestionCategory.SKILL_IN_CONTEXT, text_seed=None)
        self.assertEqual(_lookup_expected_concepts(spec), ())


class TestQuestionCategoryScopingEndToEnd(unittest.TestCase):
    """The real pipeline (topic_pool -> planner -> question_realizer ->
    build_request), not just direct `_lookup_expected_concepts` calls --
    proves the skill name genuinely survives the full trip from
    TopicPool's own construction through to the EvaluationRequest."""

    def _multi_tech_profile(self) -> dict:
        return {
            "candidate_name": "Test Candidate",
            "contact_details": {"email": "test@example.com"},
            "skills": ["Python"],
            "education": [],
            "experience": [],
            "projects": [
                {
                    "title": "AI SOC Analyst",
                    "summary": "A security log analysis platform.",
                    "technologies": ["React", "FastAPI", "Linux"],
                    "concepts": [],
                    "interview_seeds": [],
                }
            ],
            "certifications": [],
            "predicted_domain": "Software Engineering",
            "experience_level": "Intermediate",
            "confidence": 0.8,
            "resume_summary": "A software engineering candidate.",
            "interview_blueprint": {
                "resume_verification_topics": [],
                "technical_topics": [
                    {"topic": "React", "originating_project": "AI SOC Analyst", "originating_experience": "",
                     "evidence": "used React for the frontend"},
                    {"topic": "FastAPI", "originating_project": "AI SOC Analyst", "originating_experience": "",
                     "evidence": "used FastAPI for the backend"},
                    {"topic": "Linux", "originating_project": "AI SOC Analyst", "originating_experience": "",
                     "evidence": "deployed on Linux servers"},
                ],
                "starting_difficulty": "intermediate",
                "estimated_strengths": [],
                "estimated_weaknesses": [],
            },
        }

    def test_each_skill_in_context_turn_gets_only_its_own_technology_end_to_end(self):
        planner = Planner(self._multi_tech_profile())
        memory = conversation_memory.ConversationMemory()
        state = ConversationState()

        seen: dict[str, tuple] = {}
        for _ in range(20):
            spec = planner.plan_next(state)
            if spec is None:
                break
            question, _ = question_realizer.realize(spec, memory, turn_number=1)
            req = build_request(question, "An answer.", memory, planner, {})
            if spec.category == QuestionCategory.SKILL_IN_CONTEXT:
                seen[spec.text_seed] = req.expected_concepts
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)

        self.assertIn("FastAPI", seen)
        self.assertEqual(
            seen["FastAPI"],
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity"),
        )
        if "Linux" in seen:
            self.assertEqual(seen["Linux"], ())
        if "React" in seen:
            self.assertEqual(seen["React"], ())
        # No skill's pool ever contains another skill's concepts.
        for skill, concepts in seen.items():
            if skill != "FastAPI":
                self.assertTrue(set(concepts).isdisjoint({"ASGI", "dependency injection", "routing"}))


if __name__ == "__main__":
    unittest.main()
