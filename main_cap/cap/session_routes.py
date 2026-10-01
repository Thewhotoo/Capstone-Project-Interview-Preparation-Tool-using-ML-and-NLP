"""
Session history API — the logged-in user's past and current interviews.

    GET    /api/insights                          home page: stats, score trend, "Focus next"
    GET    /api/sessions                         list, newest first (?type=resume_discussion|technical)
    GET    /api/sessions/<id>                     one session with every turn (question, answer, evaluation)
    DELETE /api/sessions/<id>
    POST   /api/technical-sessions                start a Technical Interview session
    POST   /api/technical-sessions/<id>/end       {attention_metrics, integrity}

Question-bank Technical Interview (tech_interview/):
    POST   /api/tech-interview/start              {mode: standalone (10 questions) | round2 (8)}
    POST   /api/tech-interview/<id>/answer        {answer} -> next prompt (question, clarification
                                                  or follow-up); scores are not shown until the end
    POST   /api/tech-interview/<id>/end           {attention_metrics, integrity} -> report

Resume Discussion sessions are started/recorded/finished by the
/api/resume-discussion-v2/* routes in app.py (see session_history.py).
Another user's session id answers 404, never 403.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

import insights
import session_history
from tech_interview.bank import load_bank
from tech_interview.selector import select_questions
from tech_interview.session import TechInterview
from database import db
from models import SESSION_TYPE_RESUME_DISCUSSION, SESSION_TYPE_TECHNICAL, InterviewSession

sessions_bp = Blueprint("sessions", __name__)

_SESSION_TYPES = {SESSION_TYPE_RESUME_DISCUSSION, SESSION_TYPE_TECHNICAL}


def _own_session(session_id: int) -> InterviewSession | None:
    return db.session.scalar(select(InterviewSession).where(
        InterviewSession.id == session_id, InterviewSession.user_id == current_user.id,
    ))


@sessions_bp.get("/api/sessions")
@login_required
def list_sessions():
    session_history.abandon_stale_sessions(current_user.id)
    query = select(InterviewSession).where(InterviewSession.user_id == current_user.id)
    session_type = request.args.get("type")
    if session_type:
        if session_type not in _SESSION_TYPES:
            return jsonify({"error": f"Unknown session type '{session_type}'."}), 400
        query = query.where(InterviewSession.session_type == session_type)
    sessions = db.session.scalars(query.order_by(InterviewSession.started_at.desc(), InterviewSession.id.desc()))
    return jsonify({"sessions": [s.to_dict() for s in sessions]}), 200


@sessions_bp.get("/api/insights")
@login_required
def get_insights():
    """Home page: stats, score trend, and "Focus next" (insights.py)."""
    session_history.abandon_stale_sessions(current_user.id)
    return jsonify(insights.build_insights(current_user.id)), 200


@sessions_bp.get("/api/sessions/<int:session_id>")
@login_required
def get_session(session_id: int):
    session = _own_session(session_id)
    if session is None:
        return jsonify({"error": "Session not found."}), 404
    return jsonify({"session": session.to_dict(include_turns=True)}), 200


@sessions_bp.delete("/api/sessions/<int:session_id>")
@login_required
def delete_session(session_id: int):
    session = _own_session(session_id)
    if session is None:
        return jsonify({"error": "Session not found."}), 404
    session_history.delete_session(session)
    return jsonify({"status": "deleted"}), 200


@sessions_bp.post("/api/technical-sessions")
@login_required
def start_technical_session():
    session = session_history.begin_technical_session(current_user.id)
    return jsonify({"session": session.to_dict()}), 201


@sessions_bp.post("/api/technical-sessions/<int:session_id>/end")
@login_required
def end_technical_session(session_id: int):
    session = session_history.own_in_progress_technical_session(session_id, current_user.id)
    if session is None:
        return jsonify({"error": "Session not found or already finished."}), 404
    data = request.get_json(silent=True) or {}
    session_history.finish_technical_session(session, data.get("attention_metrics"), data.get("integrity"))
    return jsonify({"session": session.to_dict()}), 200


# ── Question-bank Technical Interview ───────────────────────────────────────

TECH_INTERVIEW_LENGTHS = {"standalone": 10, "round2": 8}
MAX_ANSWER_CHARS = 5000


def _report(session: InterviewSession, interview: TechInterview) -> dict:
    """Shown once the interview ends: per-question scores, what was covered
    and missed, and the reference answer."""
    return {"session": session.to_dict(), "summary": interview.summary(),
            "questions": [{k: r[k] for k in ("number", "subject_label", "topic", "difficulty", "question",
                                             "answer", "score", "covered", "partial", "missing",
                                             "exchanges", "reference_answer")}
                          for r in ({**r, "number": i + 1} for i, r in enumerate(interview.records))]}


@sessions_bp.post("/api/tech-interview/start")
@login_required
def start_tech_interview():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "standalone")
    if mode not in TECH_INTERVIEW_LENGTHS:
        return jsonify({"error": f"Unknown mode '{mode}'."}), 400
    bank = load_bank()
    if not bank:
        return jsonify({"error": "The question bank is not available."}), 503
    seen, topic_scores = session_history.technical_history(current_user.id)
    questions = select_questions(bank, TECH_INTERVIEW_LENGTHS[mode], seen_ids=seen, topic_scores=topic_scores)
    interview = TechInterview(questions, mode=mode)
    session = session_history.begin_tech_interview(current_user.id, interview)
    return jsonify({"session": session.to_dict(), "prompt": interview.prompt()}), 201


@sessions_bp.post("/api/tech-interview/<int:session_id>/answer")
@login_required
def answer_tech_interview(session_id: int):
    live = session_history.live_tech_interview(session_id, current_user.id)
    if live is None:
        return jsonify({"error": "Interview not found or already finished."}), 404
    session, interview = live
    if interview.finished:
        return jsonify({"error": "All questions are answered; end the interview."}), 409
    answer = (request.get_json(silent=True) or {}).get("answer")
    if not isinstance(answer, str):
        return jsonify({"error": "'answer' must be a string."}), 400
    result = interview.submit(answer[:MAX_ANSWER_CHARS])
    if result["record"] is not None:
        session_history.record_tech_interview_turn(session, result["record"])
    return jsonify({"prompt": result["prompt"], "finished": result["finished"],
                    "questions_answered": len(interview.records)}), 200


@sessions_bp.post("/api/tech-interview/<int:session_id>/end")
@login_required
def end_tech_interview(session_id: int):
    """Ends the interview (early or after the last question) and returns the report."""
    live = session_history.live_tech_interview(session_id, current_user.id)
    if live is None:
        return jsonify({"error": "Interview not found or already finished."}), 404
    session, interview = live
    data = request.get_json(silent=True) or {}
    session_history.finish_tech_interview(session, interview.summary(),
                                          data.get("attention_metrics"), data.get("integrity"))
    return jsonify(_report(session, interview)), 200
