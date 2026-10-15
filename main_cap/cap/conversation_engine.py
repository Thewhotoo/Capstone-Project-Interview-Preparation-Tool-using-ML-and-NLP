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

import logging
import uuid as _uuid

import question_realizer
from conversation_memory import ConversationMemory
from evaluation_engine import EvaluationLedger, build_request, evaluate
from evaluation_result import EvaluationResult
from evaluator import Evaluator
from evaluator_registry import UnknownEvaluatorError, get_active_evaluator, get_evaluator, register_evaluator
from heuristic_evaluator import HeuristicEvaluator
from interview_question import InterviewQuestion
from live_store import LocalCache, get_store
from planner import ConversationState, Planner
from question_specification import UnitStatus
from concept_analysis import concept_coverage_percent
from strong_answer import build_improved_answer, coaching_note
from topic_pool import ProfileLike

# Live conversations are kept in the live store (live_store.py: this
# process's memory, or Redis shared by every worker) as a small JSON record:
#
#     {"version", "profile", "evaluator": [name, version],
#      "turns": [{"answer", "evaluation"}], "current_question", "ended"}
#
# The planner, memory and ledger are not stored: they are rebuilt by
# replaying the record (`_rebuild`). That is exact because planning is
# deterministic (no `random`, crc32 not `hash()`; checked across hash seeds)
# and never depends on evaluation results. `_cache` keeps the rebuilt objects
# per process, reused while the stored record's version is unchanged, so a
# single-process server never replays.
_cache = LocalCache()

# Interview budget (session 14, UX milestone): a real technical interview
# doesn't exhaust a candidate's entire topic pool -- capping the number of
# QUESTIONS ASKED (not touching Planner/TopicPool's own priority ordering
# at all) is enough. `TopicPool.select_next` always returns the current
# highest-priority UNASKED unit; simply not calling `plan_next` again once
# this many turns have been recorded means only the top-N priority units
# are ever scheduled -- lower-priority units are silently never asked, with
# zero change to planning heuristics. Single constant, easy to retune.
RESUME_DISCUSSION_QUESTION_BUDGET = 10

logger = logging.getLogger(__name__)

# Session-integrity rules (full screen, no tab/window switching, no
# copy/cut/paste) are enforced in the browser -- a web page can detect a
# violation but never prevent one. The client reports the outcome on
# /end; these are the only violation types it can send.
INTEGRITY_VIOLATION_TYPES = frozenset({
    "tab_switch", "window_switch", "fullscreen_exit", "copy", "cut", "paste", "drop",
})


def sanitize_integrity(raw) -> dict:
    """Keep only known fields of the client-reported integrity record, so a
    malformed or tampered payload can't put arbitrary data into the
    session summary."""
    if not isinstance(raw, dict) or raw.get("terminated") is not True:
        return {"terminated": False}
    violation_type = raw.get("type")
    if violation_type not in INTEGRITY_VIOLATION_TYPES:
        violation_type = "unknown"
    at_turn = raw.get("at_turn")
    if isinstance(at_turn, bool) or not isinstance(at_turn, int) or at_turn < 0:
        at_turn = None
    return {
        "terminated": True,
        "type": violation_type,
        "label": str(raw.get("label") or "")[:120],
        "at_turn": at_turn,
        "occurred_at": str(raw.get("occurred_at") or "")[:40],
    }


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


def _key(conversation_id: str) -> str:
    return f"conv:{conversation_id}"


def _profile_dict(profile: ProfileLike) -> dict:
    return profile.model_dump(mode="json") if hasattr(profile, "model_dump") else profile


def _first_question(planner: Planner, memory: ConversationMemory):
    spec = planner.plan_next(ConversationState())
    if spec is None:
        return None, None, None
    question, variant_idx = question_realizer.realize(spec, memory, turn_number=1)
    return spec, question, variant_idx


def _plan_after_answer(planner: Planner, memory: ConversationMemory, last_category):
    """The next specification once the current one is marked covered, or None
    when the budget is spent or the pool is empty. Shared by live answers and
    by replay, so both always take the same path."""
    # Budget check BEFORE asking the planner for another unit -- this is
    # the only way lower-priority units "never get scheduled" rather than
    # scheduled-then-discarded; select_next() itself is never told to stop
    # early, it simply isn't called again once the budget is spent.
    if memory.turn_count() >= RESUME_DISCUSSION_QUESTION_BUDGET:
        return None
    return planner.plan_next(ConversationState(
        last_category=last_category,
        # soft cooldown so one project/job doesn't take several turns in a row
        recent_source_ids=memory.recent_source_ids(),
    ))


def _save(conversation_id: str, session: dict) -> None:
    record = session["record"]
    record["version"] += 1
    get_store().put(_key(conversation_id), record)
    _cache.put(conversation_id, record["version"], session)


def _pinned_evaluator(name: str) -> Evaluator:
    try:
        return get_evaluator(name)
    except UnknownEvaluatorError:
        logger.warning("Evaluator %r pinned to a live conversation is not registered in this "
                       "process; using the active one", name)
        return _resolve_session_evaluator()


def _rebuild(record: dict) -> dict | None:
    """Recreate a conversation's live objects from its record by replaying
    every answered turn through the same planning steps the live session took.
    Evaluations are restored from the record, never recomputed. Returns None
    if the replay doesn't reach the question the candidate is looking at
    (the profile or planning code changed since the record was written)."""
    planner = Planner(record["profile"])
    memory = ConversationMemory()
    ledger = EvaluationLedger()
    answer_history: dict[str, tuple[str, ...]] = {}

    spec, question, variant_idx = _first_question(planner, memory)
    for turn in record["turns"]:
        if spec is None:
            return None
        spec_id = question.specification.id
        ledger.append(EvaluationResult.model_validate(turn["evaluation"]))
        answer_history[spec_id] = answer_history.get(spec_id, ()) + (turn["answer"],)
        memory.record_turn(question, variant_idx, answer_text=turn["answer"])
        planner.advance(spec_id, UnitStatus.COVERED)
        spec = _plan_after_answer(planner, memory, spec.category)
        if spec is not None:
            question, variant_idx = question_realizer.realize(spec, memory, memory.turn_count() + 1)

    if not record["ended"] and (spec is None or question.question_text != record["current_question"]["text"]):
        logger.error("Replaying a live conversation did not reach its current question; dropping it")
        return None
    return {
        "planner": planner,
        "memory": memory,
        "current_question": question,
        "current_variant_idx": variant_idx,
        "last_category": spec.category if spec is not None else None,
        "ended": record["ended"],
        "evaluator": _pinned_evaluator(record["evaluator"][0]),
        "evaluation_ledger": ledger,
        "answer_history": answer_history,
        "record": record,
    }


def _load(conversation_id: str) -> dict | None:
    """The live conversation's objects, from this process's cache when the
    stored record is unchanged, otherwise rebuilt from the record."""
    record = get_store().get(_key(conversation_id))
    if record is None:
        _cache.drop(conversation_id)
        return None
    session = _cache.get(conversation_id, record["version"])
    if session is None:
        session = _rebuild(record)
        if session is None:
            return None
        _cache.put(conversation_id, record["version"], session)
    return session


def start_conversation(profile: ProfileLike) -> tuple[dict, int]:
    """Start a new Resume Discussion conversation from a Candidate Profile
    (the real Pydantic model or its `.model_dump()` dict form). Planning runs
    on the dict form, the same form a replay starts from."""
    profile = _profile_dict(profile)
    planner = Planner(profile)
    memory = ConversationMemory()
    session_evaluator = _resolve_session_evaluator()

    spec, question, variant_idx = _first_question(planner, memory)
    if spec is None:
        return {"error": "No discussion questions could be generated from this profile."}, 400

    conversation_id = f"conv_{_uuid.uuid4().hex[:12]}"
    session = {
        "planner": planner,
        "memory": memory,
        "current_question": question,
        "current_variant_idx": variant_idx,
        "last_category": spec.category,
        "ended": False,
        "evaluator": session_evaluator,
        "evaluation_ledger": EvaluationLedger(),
        "answer_history": {},  # spec_id -> tuple[str, ...] of raw answers given (Phase 3)
        "record": {
            "version": 0,
            "profile": profile,
            "evaluator": [session_evaluator.name, session_evaluator.version],
            "turns": [],
            "current_question": _question_payload(question),
            "ended": False,
        },
    }
    _save(conversation_id, session)
    return {
        "status": "success",
        "conversation_id": conversation_id,
        "question": _question_payload(question),
        "total_questions": min(planner.total(), RESUME_DISCUSSION_QUESTION_BUDGET),
    }, 200


def evaluator_info(conversation_id: str) -> tuple[str, str] | None:
    """(name, version) of the evaluator pinned to this conversation, for
    session history — scores from different evaluators aren't comparable."""
    record = get_store().get(_key(conversation_id))
    if record is None:
        return None
    name, version = record["evaluator"]
    return name, version


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
    with get_store().lock(_key(conversation_id)):
        session = _load(conversation_id)
        if session is None:
            return {"error": "Invalid or expired conversation"}, 404
        if session["ended"]:
            return {"status": "completed"}, 200
        try:
            return _advance(conversation_id, session, answer)
        except Exception:
            _cache.drop(conversation_id)   # objects may be half-updated; rebuild from the record next time
            raise


def _advance(conversation_id: str, session: dict, answer: str) -> tuple[dict, int]:

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
    record = session["record"]
    record["turns"].append({"answer": answer, "evaluation": result.model_dump(mode="json")})

    next_spec = _plan_after_answer(planner, memory, session["last_category"])
    # Improved Answer / Coaching Note are derived here, at the one site
    # where the EvaluationResult, the InterviewQuestion (its grounding) AND
    # the raw candidate `answer` are all in scope. `_result_payload` stays a
    # pure field-selector and the ledger (results only) is untouched. See
    # strong_answer.py.
    #
    # UI-honesty fix (post-demo forensic investigation): `improved_answer`
    # (the candidate's own answer + one appended coaching sentence,
    # concatenated) is kept for any existing consumer, but the report now
    # additionally receives `coaching_note` -- that same appended sentence
    # on its own -- computed from the identical shared logic
    # (strong_answer._compute), so it can never disagree with what
    # `improved_answer` would have embedded. This lets the report show
    # "Your Answer" (the candidate's real, unmodified `answer`, already
    # available on this payload) and "Coaching Note" as two honest, separate
    # pieces instead of one blob under a label implying a rewritten answer.
    turn_evaluation = _result_payload(result)
    turn_evaluation["improved_answer"] = build_improved_answer(current_question, result, answer)
    turn_evaluation["coaching_note"] = coaching_note(current_question, result, answer)
    # Concept Coverage % for the dashboard, derived directly from
    # result.concept_coverage's own per-concept statuses (never a separate
    # re-scan of the answer text -- see concept_analysis.py's module
    # docstring for the bug this fixed). None when the turn has no concept
    # pool (e.g. experience/certification) — the dashboard averages only
    # non-null turns.
    turn_evaluation["concept_coverage_pct"] = concept_coverage_percent(result)

    if next_spec is None:
        session["ended"] = record["ended"] = True
        _save(conversation_id, session)
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
    record["current_question"] = _question_payload(next_question)
    _save(conversation_id, session)

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


def end_conversation(conversation_id: str, integrity: dict | None = None) -> tuple[dict, int]:
    """End a conversation and return a structured summary: Chapter 13's
    evaluation-free memory contents, PLUS (Phase 3) the full Evaluation
    Ledger — kept as two clearly separate sections of the payload, never
    merged, so the ConversationMemory-derived fields stay exactly as
    evaluation-free as Phase 2 approved.

    `integrity` is the client's session-integrity record (see
    `sanitize_integrity`); a terminated session is ended exactly like a
    completed one -- the session is discarded, so no further replies are
    accepted -- and the termination is recorded in the summary."""
    with get_store().lock(_key(conversation_id)):
        session = _load(conversation_id)
        if session is None:
            return {"error": "Invalid or expired conversation"}, 404
        get_store().delete(_key(conversation_id))
        _cache.drop(conversation_id)

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
        "integrity": sanitize_integrity(integrity),
    }
    # Data-driven end-of-session feedback (interview_feedback.py): pure
    # summarization of the results above, no evaluation logic. Saved with the
    # session (session_history keeps everything but "evaluations").
    from interview_feedback import build_feedback
    summary["feedback"] = build_feedback(summary["evaluations"], summary["timeline"])
    if summary["integrity"]["terminated"]:
        logger.warning(
            "Conversation %s terminated for an integrity violation: %s at turn %s",
            conversation_id, summary["integrity"]["type"], summary["integrity"]["at_turn"],
        )
    return summary, 200
