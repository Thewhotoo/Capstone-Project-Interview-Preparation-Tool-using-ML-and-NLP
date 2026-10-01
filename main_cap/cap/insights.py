"""
Home-page insights — a user's stats, score trend, and "Focus next".

Computed on request from saved sessions (session_history.py); nothing
here is stored.

"Focus next" looks at the user's recent answers and names what keeps
coming up short:
  1. reasoning gaps the evaluator flagged (`missing_reasoning`) — the most
     specific signal ("no trade-offs discussed"), ranked by how often they
     occur, then by total severity;
  2. if fewer than FOCUS_LIMIT gaps recur, scoring dimensions whose average
     is weak (e.g. completeness);
  3. Technical Interview topics averaging below WEAK_SCORE.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import select

from database import db
from models import (
    SESSION_COMPLETED, SESSION_TERMINATED, SESSION_TYPE_RESUME_DISCUSSION, SESSION_TYPE_TECHNICAL,
    InterviewSession, iso_utc,
)

TREND_LENGTH = 10
FOCUS_WINDOW_SESSIONS = 5     # recent sessions of each type that "Focus next" looks at
FOCUS_LIMIT = 3
WEAK_SCORE = 0.55
MIN_RECURRENCE = 2            # a gap must show up in at least this many answers

_FINISHED = (SESSION_COMPLETED, SESSION_TERMINATED)

REASONING_GAP_LABELS = {
    "tradeoff": "Trade-off reasoning",
    "architecture": "Explaining architecture",
    "example": "Concrete examples",
    "testing": "Testing approach",
    "debugging": "Debugging stories",
    "metrics": "Measurable results",
    "edge_case": "Edge cases",
    "scalability": "Scalability",
    "design_decision": "Justifying design decisions",
    "ownership": "Showing ownership",
    "communication": "Structured communication",
}

DIMENSION_LABELS = {
    "technical_accuracy": "Technical accuracy",
    "technical_depth": "Technical depth",
    "completeness": "Complete answers",
    "communication": "Communication",
    "architecture": "Explaining architecture",
    "tradeoffs": "Trade-off reasoning",
    "ownership": "Showing ownership",
    "debugging": "Debugging stories",
    "testing": "Testing approach",
    "scalability": "Scalability",
    "resume_grounding": "Staying specific to your resume",
}


def _finished_sessions(user_id: int) -> list[InterviewSession]:
    return list(db.session.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.status.in_(_FINISHED))
        .order_by(InterviewSession.started_at.desc(), InterviewSession.id.desc())
    ))


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _focus_from_resume_discussions(sessions: list[InterviewSession]) -> list[dict]:
    answers = [t for s in sessions for t in s.turns if t.evaluation]
    if not answers:
        return []

    gap_count: dict[str, int] = defaultdict(int)
    gap_severity: dict[str, float] = defaultdict(float)
    dimension_scores: dict[str, list[float]] = defaultdict(list)
    for turn in answers:
        seen = set()
        for gap in turn.evaluation.get("missing_reasoning") or []:
            category = gap.get("category")
            if category in REASONING_GAP_LABELS and category not in seen:
                seen.add(category)
                gap_count[category] += 1
                gap_severity[category] += float(gap.get("severity") or 0)
        for dim in turn.evaluation.get("dimensions") or []:
            if dim.get("contributes_to_overall", True) and dim.get("name") in DIMENSION_LABELS:
                dimension_scores[dim["name"]].append(float(dim.get("raw_score") or 0))

    focus = []
    recurring = [c for c in gap_count if gap_count[c] >= MIN_RECURRENCE]
    for category in sorted(recurring, key=lambda c: (-gap_count[c], -gap_severity[c]))[:FOCUS_LIMIT]:
        focus.append({
            "key": f"gap:{category}",
            "label": REASONING_GAP_LABELS[category],
            "reason": f"Missing in {gap_count[category]} of your last {_plural(len(answers), 'answer')}",
        })

    labels_used = {item["label"] for item in focus}
    weak_dimensions = sorted(
        ((name, sum(v) / len(v)) for name, v in dimension_scores.items() if sum(v) / len(v) < WEAK_SCORE),
        key=lambda item: item[1],
    )
    for name, average in weak_dimensions:
        if len(focus) >= FOCUS_LIMIT:
            break
        if DIMENSION_LABELS[name] in labels_used:
            continue
        focus.append({
            "key": f"dimension:{name}",
            "label": DIMENSION_LABELS[name],
            "reason": f"Averaging {round(average * 100)}% across your last {_plural(len(answers), 'answer')}",
        })
    return focus


def _focus_from_technical(sessions: list[InterviewSession]) -> list[dict]:
    by_topic: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        for turn in session.turns:
            if turn.category and turn.overall_score is not None:
                by_topic[turn.category].append(turn.overall_score)
    weak = sorted(
        ((topic, sum(v) / len(v), len(v)) for topic, v in by_topic.items() if sum(v) / len(v) < WEAK_SCORE),
        key=lambda item: item[1],
    )
    return [{
        "key": f"topic:{topic}",
        "label": f"{topic} (technical)",
        "reason": f"Averaging {round(average * 100)}% across {_plural(count, 'question')}",
    } for topic, average, count in weak]


def build_insights(user_id: int) -> dict[str, Any]:
    finished = _finished_sessions(user_id)
    scored = [s for s in finished if s.overall_score is not None]
    attention = [
        s.attention_metrics["attentionScore"] for s in finished
        if s.attention_metrics and isinstance(s.attention_metrics.get("attentionScore"), (int, float))
    ]

    last: Optional[InterviewSession] = finished[0] if finished else None
    resume_sessions = [s for s in finished if s.session_type == SESSION_TYPE_RESUME_DISCUSSION]
    technical_sessions = [s for s in finished if s.session_type == SESSION_TYPE_TECHNICAL]
    focus = (_focus_from_resume_discussions(resume_sessions[:FOCUS_WINDOW_SESSIONS])
             + _focus_from_technical(technical_sessions[:FOCUS_WINDOW_SESSIONS]))[:FOCUS_LIMIT]

    return {
        "stats": {
            "sessions_finished": len(finished),
            "average_score": round(sum(s.overall_score for s in scored) / len(scored), 4) if scored else None,
            "best_score": max((s.overall_score for s in scored), default=None),
            "average_attention": round(sum(attention) / len(attention)) if attention else None,
        },
        "last_session": ({
            "id": last.id,
            "session_type": last.session_type,
            "status": last.status,
            "overall_score": last.overall_score,
            "overall_grade": last.overall_grade,
            "started_at": iso_utc(last.started_at),
        } if last else None),
        # Oldest first, so it reads left-to-right as a trend line.
        "trend": [{
            "session_id": s.id,
            "session_type": s.session_type,
            "score": s.overall_score,
            "started_at": iso_utc(s.started_at),
        } for s in reversed(scored[:TREND_LENGTH])],
        "focus": focus,
    }
