"""Model-free tests for the optional local-LLM assist (fact_checker.py) and how
resume_evidence_evaluator uses it: downgrade on false claims, 50/50 blend with the
rubric grade, and unchanged grading whenever the checker is unavailable."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fact_checker import FactCheckResult, OllamaFactChecker  # noqa: E402
from resume_evidence_evaluator import (  # noqa: E402
    EvidenceBreakdown, ResumeEvidenceEvaluator, _compose_overall_v2,
)

NV = "not_independently_verified"


def _ev(flags=()):
    return EvidenceBreakdown(0.8, 0.8, 0.5, 0.5, NV, tuple(flags), substance=1.0, specificity=1.0)


def test_severity_levels():
    assert FactCheckResult(status="unavailable").severity == "none"
    assert FactCheckResult(status="checked").severity == "none"
    assert FactCheckResult(status="checked", suspected_claims=({"claim": "x"},)).severity == "suspected"
    both = FactCheckResult(status="checked", false_claims=({"claim": "x"},), suspected_claims=({"claim": "x"},))
    assert both.severity == "confirmed"


def test_confirmed_error_penalised_more_than_suspected():
    clean = _compose_overall_v2(_ev())
    suspected = _compose_overall_v2(_ev(("factual_error_suspected",)))
    confirmed = _compose_overall_v2(_ev(("factual_error_confirmed",)))
    assert clean > suspected > confirmed


def test_unreachable_ollama_is_unavailable_not_an_error():
    checker = OllamaFactChecker(base_url="http://127.0.0.1:9", timeout=0.5)
    checker._warm = True
    result = checker.check("Why bcrypt?", "Because it is the fastest hash and is reversible with the key.")
    assert result.status == "unavailable" and result.severity == "none"
    assert checker.grade("Why bcrypt?", "because") is None


class _FakeChecker:
    def __init__(self, result: FactCheckResult, grade):
        self._result, self._grade, self.calls = result, grade, 0

    def check(self, question, answer, context=""):
        self.calls += 1
        return self._result

    def grade(self, question, answer, context=""):
        return self._grade


def _request(answer: str):
    from evaluation_request import ConversationContextSnapshot, EvaluationRequest
    from question_families import ReasoningType
    from question_specification import (Grounding, ProjectGrounding, QuestionCategory,
                                        QuestionSpecification, SourceType)
    project = ProjectGrounding(title="Secure Login Service", summary="Flask auth service with bcrypt.",
                               technologies=("Flask", "bcrypt"), concepts=("Password hashing",))
    spec = QuestionSpecification(id="t", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="x",
                                 grounding=Grounding(project=project), source_type=SourceType.PROJECT,
                                 source_id="Secure Login Service", source_field="interview_seeds", reason="test")
    return EvaluationRequest(request_id="r", requested_at="2026-10-23T00:00:00+00:00", specification=spec,
                             question_text="Why did you choose bcrypt?", reasoning_type=ReasoningType.TRADE_OFF_ANALYSIS,
                             answer_text=answer, conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False))


def _patch_evidence(monkeypatch):
    import resume_evidence_evaluator as ree
    monkeypatch.setattr(ree, "compute_evidence", lambda request: _ev())


def test_evaluator_blends_llm_grade_and_applies_fact_penalty(monkeypatch):
    _patch_evidence(monkeypatch)
    base = ResumeEvidenceEvaluator(scoring="v2").evaluate(_request("a")).overall_score
    wrong = FactCheckResult(status="checked", false_claims=({"claim": "bcrypt is reversible", "correction": "it is a one-way hash"},),
                            suspected_claims=({"claim": "bcrypt is reversible", "correction": "it is a one-way hash"},))
    result = ResumeEvidenceEvaluator(scoring="v2", fact_checker=_FakeChecker(wrong, 0.0)).evaluate(_request("a"))
    assert result.overall_score < base
    assert "bcrypt is reversible" in result.reasoning


def test_evaluator_unchanged_when_checker_unavailable(monkeypatch):
    _patch_evidence(monkeypatch)
    base = ResumeEvidenceEvaluator(scoring="v2").evaluate(_request("a")).overall_score
    down = ResumeEvidenceEvaluator(scoring="v2", fact_checker=_FakeChecker(FactCheckResult(status="unavailable"), None))
    assert down.evaluate(_request("a")).overall_score == base


def test_non_answers_never_reach_the_llm():
    fake = _FakeChecker(FactCheckResult(status="checked"), 1.0)
    result = ResumeEvidenceEvaluator(scoring="v2", fact_checker=fake).evaluate(_request("I don't know"))
    assert fake.calls == 0 and result.overall_score <= 0.10
