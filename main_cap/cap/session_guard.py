"""
Immediate session termination when scripted/prompted answers are detected.
Deliberately a hard stop, not a soft flag — per the requirement that this
end the interview session immediately, not just log a warning.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json

TERMINATION_LOG_DIR = Path(__file__).resolve().parent / "session_terminations"


class SessionTerminated(Exception):
    """Raised to unwind the interview loop immediately on a confirmed scripted-answer flag."""
    def __init__(self, reason: str, details: dict):
        self.reason = reason
        self.details = details
        super().__init__(reason)


def check_and_enforce(audio_result: dict, user_id: str, question: str, topic: str) -> None:
    """
    Call this right after InterviewAudioProcessor.process(). Raises
    SessionTerminated if the answer is flagged as scripted — caller
    (main.py) should catch this at the top of the interview loop and
    end the session, not just the current question.
    """
    if not audio_result.get("is_scripted"):
        return

    details = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "topic": topic,
        "question": question,
        "scripted_score": audio_result.get("scripted_score"),
        "metrics": audio_result.get("metrics", {}),
        "transcript": audio_result.get("transcript", ""),
    }
    _log_termination(user_id, details)
    raise SessionTerminated(
        reason="Scripted/prompted answer detected — session ended.",
        details=details,
    )


def _log_termination(user_id: str, details: dict) -> None:
    TERMINATION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    path = TERMINATION_LOG_DIR / f"{safe}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(details) + "\n")
