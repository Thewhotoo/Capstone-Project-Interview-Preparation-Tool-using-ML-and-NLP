"""
Conversation Engine — Phase 2 integration, extended in Phase 3 with the
Evaluation Engine's ONE integration point
(docs/architecture/ResumeDiscussion_v2.md, Chapters 7, 9-14; Phase 3 RFC —
AI Evaluation Engine, Revision 2, APPROVED AND FROZEN, Sections 1 and 9).

Wires the Phase 1/1.5 planning subsystem (`Planner`) together with Phase
2's Question Realizer and ConversationMemory, and now Phase 3's Evaluation
Engine, into a complete Resume Discussion session:

    Candidate Profile -> Planner -> QuestionRealizer -> InterviewQuestion
        -> Candidate Answer -> EvaluationRequest -> Evaluator
        -> EvaluationResult -> Evaluation Ledger

one turn per QuestionSpecification, in the Planner's own deterministic
order — nothing here reorders, filters, or second-guesses what the Planner
produces, and nothing here lets an evaluation outcome influence which
specification comes next (that remains the Adaptive Controller's future
job, still out of scope — see below).

STRICT SEPARATION (per this phase's explicit instruction): this module is
the ONE place in the whole system permitted to import both Conversation
Engine types (`ConversationMemory`, `Planner`, `InterviewQuestion`) and
Evaluation Engine types (`Evaluator`, `EvaluationRequest`,
`EvaluationResult`, the registry). `conversation_memory.py`,
`question_realizer.py`, `discussion_policy.py`, `planner.py`, and
`topic_pool.py` import NONE of the Evaluation Engine modules — verified by
test_evaluation_engine.py's import-graph assertions — so none of them ever
become "aware" that evaluation exists.

Scope boundary UNCHANGED from Phase 2 (Phase 3 does not implement the
Adaptive Controller): a live session here still never probes or follows up
automatically. Evaluation now genuinely happens on every turn, but its
result is recorded to the Evaluation Ledger and otherwise NOT acted upon —
`planner.advance(..., UnitStatus.COVERED)` remains unconditional, exactly
as before. Follow-up infrastructure (`question_realizer.realize_followup`)
still exists and is directly callable by a future phase; nothing in this
module invokes it on its own, and nothing here lets an `EvaluationResult`
change what happens next.
"""

from __future__ import annotations

import uuid as _uuid

import question_realizer
from conversation_memory import ConversationMemory
from evaluation_engine import EvaluationLedger, build_request, evaluate
from evaluator import Evaluator
from evaluator_registry import UnknownEvaluatorError, get_active_evaluator, register_evaluator
from heuristic_evaluator import HeuristicEvaluator
from interview_question import InterviewQuestion
from planner import ConversationState, Planner
from question_specification import UnitStatus
from concept_analysis import concept_coverage_percent
from strong_answer import build_improved_answer
from topic_pool import ProfileLike

_conversations: dict[str, dict] = {}

# Interview budget (session 14, UX milestone): a real technical interview
# doesn't exhaust a candidate's entire topic pool -- capping the number of
# QUESTIONS ASKED (not touching Planner/TopicPool's own priority ordering
# at all) is enough. `TopicPool.select_next` always returns the current
# highest-priority UNASKED unit; simply not calling `plan_next` again once
# this many turns have been recorded means only the top-N priority units
# are ever scheduled -- lower-priority units are silently never asked, with
# zero change to planning heuristics. Single constant, easy to retune.
RESUME_DISCUSSION_QUESTION_BUDGET = 10


def _question_payload(question: InterviewQuestion) -> dict:
    return {
        "text": question.question_text,
        "family": question.family,
        "reasoning_type": question.reasoning_type.value,
        "project_reference": question.project_reference,
        "is_followup": question.is_followup,
        "turn_number": question.turn_number,
        "category": question.specification.category.value,
        "source_id": question.specification.source_id,
    }


def _resolve_session_evaluator() -> Evaluator:
    """
    Resolve the evaluator ONCE, at session start, and the caller pins it
    for that session's full duration by storing the returned reference in
    session state — never re-resolving mid-session. This is the explicit
    risk mitigation from the frozen RFC (Section 10, "model-replacement-
    mid-session risk"): a session must never end up with turns scored by
    two different evaluator versions because the registry's active entry
    changed while the session was in flight.

    If nothing has been registered yet (a fresh process — e.g. the first
    call in a test run, or before any explicit app-startup wiring), a
    `HeuristicEvaluator` is registered and activated as the bootstrap
    default. This is NOT a hidden default that silently overrides an
    intentional choice — `evaluator_registry.register_evaluator(...,
    make_active=True)` called anywhere before this point (e.g. at
    application startup) always wins, since this function only runs the
    bootstrap path when the registry reports no active evaluator at all.
    """
    try:
        return get_active_evaluator()
    except UnknownEvaluatorError:
        default = HeuristicEvaluator()
        register_evaluator(default, make_active=True)
        return default


def start_conversation(profile: ProfileLike) -> tuple[dict, int]:
    """Start a new Resume Discussion conversation from a Candidate Profile
    (the real Pydantic model or its `.model_dump()` dict form — Planner
    already accepts either)."""
    planner = Planner(profile)
    memory = ConversationMemory()
    session_evaluator = _resolve_session_evaluator()

    spec = planner.plan_next(ConversationState())
    if spec is None:
        return {"error": "No discussion questions could be generated from this profile."}, 400

    question, variant_idx = question_realizer.realize(spec, memory, turn_number=1)

    conversation_id = f"conv_{_uuid.uuid4().hex[:12]}"
    _conversations[conversation_id] = {
        "planner": planner,
        "memory": memory,
        "current_question": question,
        "current_variant_idx": variant_idx,
        "last_category": spec.category,
        "ended": False,
        "evaluator": session_evaluator,
        "evaluation_ledger": EvaluationLedger(),
        "answer_history": {},  # spec_id -> tuple[str, ...] of raw answers given (Phase 3)
    }
    return {
        "status": "success",
        "conversation_id": conversation_id,
        "question": _question_payload(question),
        "total_questions": min(planner.total(), RESUME_DISCUSSION_QUESTION_BUDGET),
    }, 200


def advance_conversation(conversation_id: str, answer: str) -> tuple[dict, int]:
    """
    Submit an answer for the current question and receive the next one (or
    completion). Phase 3 addition: the answer is now evaluated — an
    `EvaluationRequest` is assembled (evaluation_engine.build_request) and
    passed to the session's pinned `Evaluator`, and the resulting
    `EvaluationResult` is appended to the session's Evaluation Ledger.

    This does NOT change the conversation's control flow: the current
    specification is still unconditionally marked COVERED regardless of
    what the evaluation found (no adaptive probing/skipping yet — that
    remains the Adaptive Controller's job, still out of scope), and
    `ConversationMemory` still only ever receives answer-length metadata,
    never a score (Phase 2's approved boundary, untouched).
    """
    session = _conversations.get(conversation_id)
    if session is None:
        return {"error": "Invalid or expired conversation"}, 404
    if session["ended"]:
        return {"status": "completed"}, 200

    planner: Planner = session["planner"]
    memory: ConversationMemory = session["memory"]
    current_question: InterviewQuestion = session["current_question"]
    variant_idx: int = session["current_variant_idx"]
    session_evaluator: Evaluator = session["evaluator"]
    ledger: EvaluationLedger = session["evaluation_ledger"]
    answer_history: dict[str, tuple[str, ...]] = session["answer_history"]

    spec_id = current_question.specification.id

    # Evaluate BEFORE recording turn metadata, so build_request sees this
    # spec's PRIOR answers only (not the one currently being evaluated).
    request = build_request(current_question, answer, memory, planner, answer_history)
    result = evaluate(session_evaluator, request)
    ledger.append(result)
    answer_history[spec_id] = answer_history.get(spec_id, ()) + (answer,)

    memory.record_turn(current_question, variant_idx, answer_text=answer)
    planner.advance(spec_id, UnitStatus.COVERED)

    # Budget check BEFORE asking the planner for another unit -- this is
    # the only way lower-priority units "never get scheduled" rather than
    # scheduled-then-discarded; select_next() itself is never told to stop
    # early, it simply isn't called again once the budget is spent.
    if memory.turn_count() >= RESUME_DISCUSSION_QUESTION_BUDGET:
        next_spec = None
    else:
        next_spec = planner.plan_next(ConversationState(last_category=session["last_category"]))
    # Improved Answer is derived here, at the one site where the
    # EvaluationResult, the InterviewQuestion (its grounding) AND the raw
    # candidate `answer` are all in scope — the candidate answer is the input
    # that makes this an *improvement* of their own response rather than a
    # fresh one. `_result_payload` stays a pure field-selector and the ledger
    # (results only) is untouched. See strong_answer.py.
    turn_evaluation = _result_payload(result)
    turn_evaluation["improved_answer"] = build_improved_answer(current_question, result, answer)
    # Concept Coverage % for the dashboard, derived directly from
    # result.concept_coverage's own per-concept statuses (never a separate
    # re-scan of the answer text -- see concept_analysis.py's module
    # docstring for the bug this fixed). None when the turn has no concept
    # pool (e.g. experience/certification) — the dashboard averages only
    # non-null turns.
    turn_evaluation["concept_coverage_pct"] = concept_coverage_percent(result)

    if next_spec is None:
        session["ended"] = True
        return {
            "status": "success", "next_question": None, "is_completed": True,
            "turn_number": memory.turn_count(),
            "evaluation": turn_evaluation,
        }, 200

    next_turn_number = memory.turn_count() + 1
    next_question, next_variant_idx = question_realizer.realize(next_spec, memory, next_turn_number)
    session["current_question"] = next_question
    session["current_variant_idx"] = next_variant_idx
    session["last_category"] = next_spec.category

    return {
        "status": "success",
        "next_question": _question_payload(next_question),
        "is_completed": False,
        "turn_number": next_turn_number,
        "evaluation": turn_evaluation,
    }, 200


def _result_payload(result) -> dict:
    """Renders `EvaluationResult` fields directly — no evaluation logic
    lives here, only field selection (Goal 2: the UI/API layer must never
    contain evaluation logic, only render the result)."""
    return {
        "overall_score": result.overall_score,
        "grade": result.grade,
        "confidence": result.confidence,
        "confidence_rationale": result.confidence_rationale,
        "reasoning": result.reasoning,
        "dimensions": [
            {"name": d.name, "raw_score": d.raw_score, "confidence": d.confidence,
             "contributes_to_overall": d.contributes_to_overall}
            for d in result.dimensions
        ],
        "strengths": [c.claim for c in result.strengths],
        "weaknesses": [c.claim for c in result.weaknesses],
        "missing_reasoning": [
            {"category": m.category, "explanation": m.explanation, "severity": m.severity}
            for m in result.missing_reasoning
        ],
        # Session 15: already computed by every Evaluator implementation
        # (TrainedEvaluator.evaluate() populates this per turn from
        # EvaluationRequest.expected_concepts) but never previously rendered
        # here -- this is the only per-turn field that names the SPECIFIC
        # technical concepts (not a fixed reasoning-category taxonomy) this
        # question was actually grounded in, needed for a question-specific
        # Improved Answer. Pure field selection, no new evaluation logic.
        "concept_coverage": [
            {"concept": c.concept, "status": c.status.value, "evidence": c.evidence}
            for c in result.concept_coverage
        ],
        "suggested_improvements": list(result.suggested_improvements),
        "recommended_topics": list(result.recommended_topics),
        "contradiction_detected": result.contradiction_detected,
    }


def end_conversation(conversation_id: str) -> tuple[dict, int]:
    """End a conversation and return a structured summary: Chapter 13's
    evaluation-free memory contents, PLUS (Phase 3) the full Evaluation
    Ledger — kept as two clearly separate sections of the payload, never
    merged, so the ConversationMemory-derived fields stay exactly as
    evaluation-free as Phase 2 approved."""
    session = _conversations.get(conversation_id)
    if session is None:
        return {"error": "Invalid or expired conversation"}, 404

    memory: ConversationMemory = session["memory"]
    ledger: EvaluationLedger = session["evaluation_ledger"]

    summary = {
        "status": "success",
        "total_questions": memory.turn_count(),
        "projects_discussed": sorted(memory.projects_discussed),
        "skills_discussed": sorted(memory.skills_discussed),
        "technologies_mentioned": sorted(memory.technologies_mentioned),
        "reasoning_types_covered": sorted(rt.value for rt in memory.reasoning_types_covered),
        "timeline": [
            {
                "turn_number": t.turn_number,
                "category": t.category,
                "family": t.family,
                "reasoning_type": t.reasoning_type.value,
                "is_followup": t.is_followup,
                "project_reference": t.project_reference,
            }
            for t in memory.timeline
        ],
        "evaluations": [_result_payload(r) for r in ledger.all()],
    }
    _conversations.pop(conversation_id, None)
    return summary, 200
