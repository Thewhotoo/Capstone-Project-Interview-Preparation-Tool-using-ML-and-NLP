"""Persist user session scores and topic progress."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

TRACKING_DIR = Path(__file__).resolve().parent / "user_progress"

# ---- Original functions (unchanged) ----

def _user_file(user_id: str) -> Path:
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    return TRACKING_DIR / f"{safe}.json"


def load_progress(user_id: str) -> dict:
    path = _user_file(user_id)
    if not path.exists():
        return {"user_id": user_id, "sessions": [], "topics": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_progress(user_id: str, data: dict) -> None:
    with open(_user_file(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_attempt(
    user_id: str,
    subject: str,
    topic: str,
    score: float,
    question_type: str = "open",
    grade: str = "",
) -> dict:
    data = load_progress(user_id)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "subject": subject,
        "topic": topic,
        "score": score,
        "question_type": question_type,
        "grade": grade,
    }
    data["sessions"].append(entry)
    topics = data.setdefault("topics", {})
    bucket = topics.setdefault(topic, {"scores": [], "subject": subject})
    bucket["scores"].append(score)
    bucket["average"] = round(sum(bucket["scores"]) / len(bucket["scores"]), 1)
    bucket["attempts"] = len(bucket["scores"])
    save_progress(user_id, data)
    return data


def get_recommendations(user_id: str, threshold: float = 70.0) -> list[str]:
    data = load_progress(user_id)
    weak = [
        topic
        for topic, info in data.get("topics", {}).items()
        if info.get("average", 100) < threshold
    ]
    return sorted(weak, key=lambda t: data["topics"][t]["average"])


# ---- Wrapper functions for main.py (using default user "default") ----

_DEFAULT_USER = "default"


def log_evaluation(topic: str, difficulty: str, qtype: str, score: float, grade: str) -> None:
    """
    Record an evaluation using the default user.
    Difficulty is stored as a custom field in the session entry.
    """
    # Use record_attempt (subject is left empty – can be set later if needed)
    record_attempt(_DEFAULT_USER, "", topic, score, qtype, grade)
    # Add difficulty to the newly created session
    data = load_progress(_DEFAULT_USER)
    if data["sessions"]:
        data["sessions"][-1]["difficulty"] = difficulty
        save_progress(_DEFAULT_USER, data)


def get_stats() -> dict | None:
    """Compute summary statistics for the default user."""
    data = load_progress(_DEFAULT_USER)
    sessions = data.get("sessions", [])
    if not sessions:
        return None
    scores = [s["score"] for s in sessions]
    grades = [s.get("grade", "") for s in sessions]
    grade_dist = {}
    for g in grades:
        if g:
            grade_dist[g] = grade_dist.get(g, 0) + 1
    return {
        "total_attempts": len(sessions),
        "avg_score": sum(scores) / len(scores),
        "max_score": max(scores),
        "min_score": min(scores),
        "grade_dist": grade_dist,
    }


def get_history(limit: int = 10) -> list[dict]:
    """Return the most recent sessions for the default user (newest first)."""
    data = load_progress(_DEFAULT_USER)
    sessions = data.get("sessions", [])
    return sessions[::-1][:limit]