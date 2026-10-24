"""Tests for tech_consistency_flag.py — the informational, score-free side
channel that checks a described tech stack against the resume's own listed
technologies for a project. Model-free: the NLI/embedding calls are injected
as deterministic fakes (same discipline as test_correctness_nli_scorer.py)."""

from __future__ import annotations

import hashlib
import re

import numpy as np

import tech_consistency_flag as tcf
from correctness_nli_scorer import CoverageNLIScorer
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def fake_nli(pairs):
    out = []
    for premise, hyp in pairs:
        # "irrelevant-topic" simulates the real model's observed quirk: an
        # answer that says nothing about the project ALSO reads as a high-
        # contradiction/low-support pair against the tech key points, same
        # shape as a genuinely fabricated claim (see the module's 2nd
        # calibration note) -- this is what _engages_with_project must catch.
        if "fabricated-tech" in premise.lower() or "irrelevant-topic" in premise.lower():
            out.append([5.0, 0.0, 0.0])  # [contradiction, entailment, neutral]
        elif hyp.lower() in premise.lower():
            out.append([0.0, 5.0, 0.0])
        else:
            out.append([0.0, 0.0, 3.0])
    return out


def _stable_hash(word: str, dim: int) -> int:
    # deterministic across processes (unlike builtin hash(), which is salted
    # per-run) and spread over a large enough space to avoid spurious
    # bag-of-words collisions between unrelated vocabularies in these tests.
    return int(hashlib.md5(word.encode()).hexdigest(), 16) % dim


def fake_embed(texts, dim=4096):
    arr = np.zeros((len(texts), dim))
    for i, t in enumerate(texts):
        for w in re.findall(r"[a-z]+", t.lower()):
            if len(w) > 2:  # skip tiny stopword-ish tokens that inflate collisions
                arr[i, _stable_hash(w, dim)] += 1.0
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _spec(category=QuestionCategory.PROJECT_DEEP_DIVE, technologies=("Postgres", "FastAPI")):
    grounding = Grounding(project=ProjectGrounding(title="Chronos", summary="task orchestrator", technologies=technologies))
    return QuestionSpecification(
        id="spec-1", category=category, grounding=grounding,
        source_type=SourceType.PROJECT, source_id="proj-1", source_field="technologies",
        reason="test",
    )


def _request(answer_text: str, spec=None) -> EvaluationRequest:
    return EvaluationRequest(
        request_id="r1", requested_at="2026-01-01T00:00:00+00:00",
        specification=spec or _spec(), question_text="Tell me about Chronos.",
        reasoning_type=ReasoningType.DESIGN, answer_text=answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


def setup_module(_module):
    tcf._scorer = CoverageNLIScorer(nli_predict=fake_nli, embed=fake_embed)
    tcf._embed = fake_embed  # same hash-based bag-of-words fake drives the project-engagement check too


class TestNotApplicable:
    def test_non_project_category(self):
        req = _request(
            "I used it a lot and it was great honestly, learned so much from it overall.",
            spec=_spec(category=QuestionCategory.SKILL_IN_CONTEXT),
        )
        assert tcf.check_tech_consistency(req) is None

    def test_no_technologies_listed(self):
        req = _request(
            "I used it a lot and it was great honestly, learned so much from it overall.",
            spec=_spec(technologies=()),
        )
        assert tcf.check_tech_consistency(req) is None

    def test_answer_too_short(self):
        req = _request("Used Postgres and FastAPI.")
        assert tcf.check_tech_consistency(req) is None

    def test_degenerate_answer_not_flagged(self):
        req = _request("cache cache cache cache cache cache cache cache cache cache cache cache")
        assert tcf.check_tech_consistency(req) is None


class TestFlagging:
    def test_fabricated_stack_flags_possible_mismatch(self):
        # Must engage with the project (mentions Chronos / task orchestrator)
        # so it clears the new project-engagement gate, same as a real
        # candidate answering "tell me about Chronos" would.
        req = _request(
            "For Chronos, this task orchestrator project, I personally built everything using "
            "fabricated-tech Django and MongoDB, deciding on that stack because it fit requirements."
        )
        assert tcf.check_tech_consistency(req) == tcf.POSSIBLE_MISMATCH

    def test_no_unlisted_technology_named_means_no_mismatch_warning(self):
        # Same high-contradiction NLI signal (the "fabricated-tech" marker), but the only
        # technology named is Postgres, which the resume lists: nothing to warn about.
        req = _request(
            "For Chronos, this task orchestrator, fabricated-tech leases live in Postgres with heartbeats "
            "every ten seconds, and the reaper re-queues a task when its lease expires."
        )
        assert tcf.check_tech_consistency(req) == tcf.NOT_INDEPENDENTLY_VERIFIED

    def test_grounded_answer_is_not_flagged_as_mismatch(self):
        req = _request(
            "For this project I personally built the core using Postgres and FastAPI, "
            "deciding on that stack because it fit the project's relational data needs."
        )
        result = tcf.check_tech_consistency(req)
        assert result != tcf.POSSIBLE_MISMATCH
        assert result == tcf.NOT_INDEPENDENTLY_VERIFIED

    def test_vague_unrelated_answer_is_not_verified_not_mismatch(self):
        # Says nothing about tech at all -- no confident contradiction signal,
        # must not be accused of a mismatch (should fall to not_independently_verified).
        req = _request(
            "It was a good project overall, I learned a lot and contributed to many "
            "parts of it alongside the team throughout the semester."
        )
        assert tcf.check_tech_consistency(req) == tcf.NOT_INDEPENDENTLY_VERIFIED

    def test_off_topic_answer_is_not_flagged_despite_high_contradiction(self):
        # Regression test for the real false positive found in manual testing:
        # an answer that never engages with the project at all (no shared
        # vocabulary with its title/summary) must NOT be flagged as a resume
        # mismatch, even though the underlying NLI signal looks identical to a
        # fabricated-tech claim (see "irrelevant-topic" in fake_nli above).
        req = _request(
            "Honestly my favorite irrelevant-topic hobby is rock climbing and hiking on "
            "weekends, it has nothing to do with any of this at all really."
        )
        assert tcf.check_tech_consistency(req) == tcf.NOT_INDEPENDENTLY_VERIFIED


class TestProjectEngagementGate:
    def test_engages_true_when_answer_shares_project_vocabulary(self):
        project = ProjectGrounding(title="Chronos", summary="task orchestrator", technologies=())
        assert tcf._engages_with_project("I built Chronos as a task orchestrator for my team.", project)

    def test_engages_false_when_answer_is_unrelated(self):
        project = ProjectGrounding(title="Chronos", summary="task orchestrator", technologies=())
        assert not tcf._engages_with_project("I enjoy hiking and rock climbing on weekends.", project)

    def test_engagement_check_fails_closed_on_embedding_error(self):
        project = ProjectGrounding(title="Chronos", summary="task orchestrator", technologies=())

        def broken_embed(_texts):
            raise RuntimeError("model unavailable")

        original = tcf._embed
        tcf._embed = broken_embed
        try:
            assert not tcf._engages_with_project("I built Chronos.", project)
        finally:
            tcf._embed = original


class TestEndToEndInConversationEngine:
    """Through the real Round 1 path (conversation_engine -> end_conversation ->
    interview_feedback.build_feedback), with the REAL (small, cached) NLI/
    embedding models -- same convention as TestEngagementInRound1 in
    test_answer_engagement.py. setup_module (above) already swapped the
    module to fakes for the rest of this file, so this class must explicitly
    swap in real instances rather than just "restoring" whatever is current,
    and restores the fakes again afterward so this doesn't leak into other
    tests in the same process."""

    def setup_method(self, _method):
        self._saved_scorer = tcf._scorer
        self._saved_embed = tcf._embed
        tcf._scorer = CoverageNLIScorer()
        tcf._embed = tcf._lazy_embed

    def teardown_method(self, _method):
        tcf._scorer = self._saved_scorer
        tcf._embed = self._saved_embed

    def test_fabricated_stack_surfaces_in_end_of_session_feedback(self):
        import evaluator_registry
        from heuristic_evaluator import HeuristicEvaluator
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None
        evaluator_registry.register_evaluator(HeuristicEvaluator(), make_active=True)

        import conversation_engine
        from candidate_profile_generator import CandidateProfile, ProjectEntry

        profile = CandidateProfile(
            candidate_name="Test", skills=["Python", "Flask", "PostgreSQL"],
            projects=[ProjectEntry(title="Interview Coach", summary="A Flask app that runs mock interviews.",
                                   technologies=["Python", "Flask", "PostgreSQL"])],
        ).model_dump()
        payload, _ = conversation_engine.start_conversation(profile)
        cid = payload["conversation_id"]
        turn_payload, _ = conversation_engine.advance_conversation(
            cid,
            "For this project I personally built everything using COBOL and mainframe JCL scripts, "
            "deciding on that stack because it fit the project's requirements and I implemented the "
            "main logic myself end to end.",
        )
        # The per-turn flag must be applicable here (project question, resume lists
        # real technologies, answer is long enough) -- it must land on one of the
        # two real verdicts, never silently None.
        flag = turn_payload["evaluation"]["tech_consistency"]
        assert flag in (tcf.POSSIBLE_MISMATCH, tcf.NOT_INDEPENDENTLY_VERIFIED)

        summary, status = conversation_engine.end_conversation(cid)
        assert status == 200
        assert "tech_mismatch_flagged" in summary["feedback"]["stats"]
        if flag == tcf.POSSIBLE_MISMATCH:
            focus_dims = [f["dimension"] for f in summary["feedback"]["focus_areas"]]
            assert "tech_consistency" in focus_dims
            assert summary["feedback"]["stats"]["tech_mismatch_flagged"] is True
