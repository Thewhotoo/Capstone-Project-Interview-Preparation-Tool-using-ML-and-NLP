"""
Session history — writes interviews to the database as they happen.

Both interview types are saved turn by turn, so nothing already answered
is lost if the server restarts or the browser closes:

    Resume Discussion   conversation_engine runs the live session in memory
                        (planner, evaluator, memory); the /api/resume-
                        discussion-v2/* routes in app.py call the
                        `*_resume_discussion` functions below around it.
                        conversation_engine itself stays unaware of the DB.
    Technical Interview /api/technical-sessions starts a session, each
                        /api/evaluate call with a `session_id` records a
                        turn, and .../end finishes it. (Legacy quiz flow.)
    Tech Interview      /api/tech-interview/* (session_routes.py): the
                        question-bank interview (tech_interview/). The live
                        TechInterview is held in memory here; each main
                        question is saved as one turn when it closes
                        (follow-ups inside its evaluation).

Session status:
    in_progress  -> completed   finished normally
                 -> terminated  ended by a session-integrity violation
                 -> abandoned   never finished: the server restarted, the
                                user started another interview, or it sat
                                idle for STALE_AFTER

A user runs one interview at a time — starting a new one abandons any
other still in progress.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select, update

import conversation_engine
from database import db
from models import (
    SESSION_ABANDONED, SESSION_COMPLETED, SESSION_IN_PROGRESS, SESSION_TERMINATED,
    SESSION_TYPE_RESUME_DISCUSSION, SESSION_TYPE_TECHNICAL,
    InterviewSession, SessionTurn, utcnow,
)

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=2)

# Attention metrics come from the browser; keep only these numeric fields.
_ATTENTION_FIELDS = (
    "totalWarnings", "faceAbsentWarnings", "totalDeviationMs",
    "livenessRechecks", "livenessFailures", "sessionMs", "attentionScore",
)


@dataclass
class _LiveConversation:
    """Links a live conversation_engine conversation to its database row,
    and remembers the question on screen (the reply payload only carries
    the *next* question)."""
    session_id: int
    user_id: int
    current_question: dict


# conversation_id -> live link. In memory, like conversation_engine's own
# state: after a restart both are gone and the rows are marked abandoned.
_live: dict[str, _LiveConversation] = {}

# session id -> (user id, live tech_interview.TechInterview). Same lifetime rules.
_live_tech: dict[int, tuple[int, Any]] = {}

TECH_INTERVIEW_EVALUATOR = ("tech_interview_nli", "1")


def session_grade(average_score: Optional[float]) -> Optional[str]:
    """Session-level grade from the mean turn score. Same bands as the
    report screen (`rdOverallGrade` in index.html), so history shows the
    grade the candidate saw."""
    if average_score is None:
        return None
    if average_score >= 0.80:
        return "excellent"
    if average_score >= 0.60:
        return "good"
    if average_score >= 0.40:
        return "adequate"
    if average_score >= 0.25:
        return "weak"
    return "poor"


def _sanitize_attention(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    clean = {}
    for key in _ATTENTION_FIELDS:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            clean[key] = round(float(value), 2)
    return clean or None


def _new_session(user_id: int, session_type: str, resume_id: Optional[int] = None,
                 evaluator: Optional[tuple[str, str]] = None) -> InterviewSession:
    abandon_in_progress_sessions(user_id)
    now = utcnow()
    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        session_type=session_type,
        status=SESSION_IN_PROGRESS,
        started_at=now,
        last_activity_at=now,
        evaluator_name=evaluator[0] if evaluator else None,
        evaluator_version=evaluator[1] if evaluator else None,
    )
    db.session.add(session)
    db.session.commit()
    return session


def _add_turn(session: InterviewSession, turn: SessionTurn) -> None:
    session.turns.append(turn)
    session.questions_answered = len(session.turns)
    session.last_activity_at = turn.answered_at
    db.session.commit()


def _finish(session: InterviewSession, status: str, *, summary: Optional[dict] = None,
            integrity: Optional[dict] = None, attention_metrics: Any = None) -> None:
    scores = [t.overall_score for t in session.turns if t.overall_score is not None]
    session.overall_score = round(sum(scores) / len(scores), 4) if scores else None
    session.overall_grade = session_grade(session.overall_score)
    session.questions_answered = len(session.turns)
    session.status = status
    session.ended_at = session.last_activity_at = utcnow()
    if summary is not None:
        session.summary = summary
    if integrity is not None:
        session.integrity = integrity
    attention = _sanitize_attention(attention_metrics)
    if attention is not None:
        session.attention_metrics = attention
    db.session.commit()


# ── Abandonment ─────────────────────────────────────────────────────────────

def _drop_live_state(session_ids: set[int]) -> None:
    """Forget live conversations for these sessions and free the engine's
    in-memory state for them."""
    for conversation_id, live in list(_live.items()):
        if live.session_id in session_ids:
            del _live[conversation_id]
            conversation_engine.end_conversation(conversation_id)
    for session_id in session_ids:
        _live_tech.pop(session_id, None)


def _mark_abandoned(sessions: list[InterviewSession]) -> None:
    for session in sessions:
        scores = [t.overall_score for t in session.turns if t.overall_score is not None]
        session.overall_score = round(sum(scores) / len(scores), 4) if scores else None
        session.overall_grade = session_grade(session.overall_score)
        session.status = SESSION_ABANDONED
        session.ended_at = session.last_activity_at or session.started_at
    if sessions:
        _drop_live_state({s.id for s in sessions})
        db.session.commit()


def abandon_in_progress_sessions(user_id: int) -> None:
    """A user runs one interview at a time: starting a new one (or
    reloading the page mid-interview and starting again) closes the old."""
    _mark_abandoned(list(db.session.scalars(select(InterviewSession).where(
        InterviewSession.user_id == user_id, InterviewSession.status == SESSION_IN_PROGRESS,
    ))))


def abandon_stale_sessions(user_id: int) -> None:
    cutoff = utcnow() - STALE_AFTER
    _mark_abandoned(list(db.session.scalars(select(InterviewSession).where(
        InterviewSession.user_id == user_id,
        InterviewSession.status == SESSION_IN_PROGRESS,
        InterviewSession.last_activity_at < cutoff,
    ))))


def abandon_all_open_sessions() -> int:
    """At startup: no live interview survives a restart, so every session
    still marked in progress is abandoned. Returns how many."""
    result = db.session.execute(
        update(InterviewSession)
        .where(InterviewSession.status == SESSION_IN_PROGRESS)
        .values(status=SESSION_ABANDONED, ended_at=InterviewSession.last_activity_at)
    )
    db.session.commit()
    return result.rowcount or 0


# ── Resume Discussion ───────────────────────────────────────────────────────

def begin_resume_discussion(conversation_id: str, user_id: int, resume_id: Optional[int],
                            first_question: dict) -> InterviewSession:
    session = _new_session(user_id, SESSION_TYPE_RESUME_DISCUSSION, resume_id,
                           conversation_engine.evaluator_info(conversation_id))
    _live[conversation_id] = _LiveConversation(session.id, user_id, first_question)
    return session


def owns_conversation(conversation_id: str, user_id: int) -> bool:
    live = _live.get(conversation_id)
    return live is not None and live.user_id == user_id


def record_resume_discussion_turn(conversation_id: str, answer: str, reply: dict) -> None:
    """Save the question just answered, the answer, and its evaluation.
    `reply` is conversation_engine.advance_conversation's payload."""
    live = _live.get(conversation_id)
    evaluation = reply.get("evaluation")
    if live is None or evaluation is None:
        return
    session = db.session.get(InterviewSession, live.session_id)
    if session is None:  # deleted mid-interview
        _live.pop(conversation_id, None)
        return

    question = live.current_question
    _add_turn(session, SessionTurn(
        turn_number=question.get("turn_number") or len(session.turns) + 1,
        question_text=question.get("text", ""),
        category=question.get("category"),
        family=question.get("family"),
        reasoning_type=question.get("reasoning_type"),
        project_reference=question.get("project_reference"),
        source_id=question.get("source_id"),
        is_followup=bool(question.get("is_followup")),
        answer_text=answer,
        answered_at=utcnow(),
        overall_score=evaluation.get("overall_score"),
        grade=evaluation.get("grade"),
        evaluation=evaluation,
    ))
    if reply.get("next_question"):
        live.current_question = reply["next_question"]


def finish_resume_discussion(conversation_id: str, end_payload: dict, attention_metrics: Any) -> None:
    """`end_payload` is conversation_engine.end_conversation's summary."""
    live = _live.pop(conversation_id, None)
    if live is None:
        return
    session = db.session.get(InterviewSession, live.session_id)
    if session is None:
        return
    integrity = end_payload.get("integrity") or {"terminated": False}
    # Per-turn evaluations already live in session_turns; keep the rest.
    summary = {k: v for k, v in end_payload.items() if k != "evaluations"}
    _finish(session, SESSION_TERMINATED if integrity.get("terminated") else SESSION_COMPLETED,
            summary=summary, integrity=integrity, attention_metrics=attention_metrics)


# ── Technical Interview ─────────────────────────────────────────────────────

def begin_technical_session(user_id: int) -> InterviewSession:
    return _new_session(user_id, SESSION_TYPE_TECHNICAL)


def own_in_progress_technical_session(session_id: Any, user_id: int) -> Optional[InterviewSession]:
    try:
        session_id = int(session_id)
    except (TypeError, ValueError):
        return None
    return db.session.scalar(select(InterviewSession).where(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id,
        InterviewSession.session_type == SESSION_TYPE_TECHNICAL,
        InterviewSession.status == SESSION_IN_PROGRESS,
    ))


def record_technical_turn(session: InterviewSession, request_data: dict, result: dict) -> None:
    """One quiz question: main answer + fill-in-the-blank, and /api/evaluate's result."""
    _add_turn(session, SessionTurn(
        turn_number=len(session.turns) + 1,
        question_text=str(request_data.get("question", "")),
        category=request_data.get("topic"),
        answer_text=str(request_data.get("user_answer", "")),
        answered_at=utcnow(),
        overall_score=result.get("score"),
        grade=session_grade(result.get("score")),
        evaluation={
            **result,
            "difficulty": request_data.get("difficulty"),
            "fill_question": request_data.get("fill_question"),
            "user_fill_mask": request_data.get("user_fill_mask"),
            "reference_fill_mask": request_data.get("reference_fill_mask"),
            "reference_answer": request_data.get("reference_answer"),
        },
    ))


def finish_technical_session(session: InterviewSession, attention_metrics: Any, integrity: Any = None) -> None:
    """`integrity` is the browser's session-integrity record, sanitized the
    same way as the Resume Discussion's; a violation marks it terminated."""
    clean = conversation_engine.sanitize_integrity(integrity)
    _finish(session, SESSION_TERMINATED if clean["terminated"] else SESSION_COMPLETED,
            integrity=clean, attention_metrics=attention_metrics)


# ── Tech Interview (question bank) ──────────────────────────────────────────

def technical_history(user_id: int) -> tuple[set[str], dict[str, float]]:
    """Question ids this user has already been asked, and their mean score
    per bank topic id -- the selector avoids repeats and leans towards weak
    topics. Only turns from the question-bank interview carry a source_id."""
    rows = db.session.execute(
        select(SessionTurn.source_id, SessionTurn.overall_score, SessionTurn.evaluation)
        .join(InterviewSession)
        .where(InterviewSession.user_id == user_id,
               InterviewSession.session_type == SESSION_TYPE_TECHNICAL,
               SessionTurn.source_id.is_not(None))
    ).all()
    seen, per_topic = set(), {}
    for source_id, score, evaluation in rows:
        seen.add(source_id)
        topic_id = (evaluation or {}).get("topic_id")
        if topic_id and score is not None:
            per_topic.setdefault(topic_id, []).append(score)
    return seen, {t: sum(v) / len(v) for t, v in per_topic.items()}


def begin_tech_interview(user_id: int, interview: Any) -> InterviewSession:
    session = _new_session(user_id, SESSION_TYPE_TECHNICAL, evaluator=TECH_INTERVIEW_EVALUATOR)
    _live_tech[session.id] = (user_id, interview)
    return session


def live_tech_interview(session_id: Any, user_id: int) -> Optional[tuple[InterviewSession, Any]]:
    """The user's in-progress question-bank interview and its live state."""
    session = own_in_progress_technical_session(session_id, user_id)
    live = _live_tech.get(session.id) if session is not None else None
    if live is None or live[0] != user_id:
        return None
    return session, live[1]


def record_tech_interview_turn(session: InterviewSession, record: dict) -> None:
    """One closed main question (answer, follow-ups, grade) from TechInterview.submit."""
    _add_turn(session, SessionTurn(
        turn_number=len(session.turns) + 1,
        question_text=record["question"],
        category=record["topic"],
        family=record["subject"],
        reasoning_type=record["difficulty"],
        source_id=record["question_id"],
        answer_text=record["answer"],
        answered_at=utcnow(),
        overall_score=record["score"],
        grade=session_grade(record["score"]),
        evaluation=record,
    ))


def finish_tech_interview(session: InterviewSession, summary: dict, attention_metrics: Any,
                          integrity: Any = None) -> None:
    clean = conversation_engine.sanitize_integrity(integrity)
    _live_tech.pop(session.id, None)
    _finish(session, SESSION_TERMINATED if clean["terminated"] else SESSION_COMPLETED,
            summary=summary, integrity=clean, attention_metrics=attention_metrics)


# ── Deletion ────────────────────────────────────────────────────────────────

def delete_session(session: InterviewSession) -> None:
    _drop_live_state({session.id})
    db.session.delete(session)
    db.session.commit()
