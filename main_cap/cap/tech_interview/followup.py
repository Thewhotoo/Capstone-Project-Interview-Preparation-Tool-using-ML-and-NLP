"""After each answer: move on, ask for clarification, or ask a prepared follow-up.

    "I don't know"                       -> next question (no pressure)
    follow-ups used up (MAX_FOLLOWUPS)   -> next question
    good answer (score >= GOOD_SCORE)    -> next question
    unclear (hesitant / vague / repetitive), not yet clarified
                                         -> clarification request (template)
    a key point missing or only partly covered, with a prepared follow-up
    not yet asked                        -> that follow-up (most important first:
                                            missing before partial, in key-point order)
    otherwise                            -> next question

Follow-up texts come from the question bank; clarification requests are
templates, varied by how many have been asked in the session.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .bank import KeyPoint, Question
from .grader import Grade

MAX_FOLLOWUPS = 2
GOOD_SCORE = 0.70

CLARIFY_TEMPLATES = (
    "I didn't quite follow that. Could you explain it again, more precisely?",
    "Could you walk me through that step by step?",
    "Can you say that more concretely? What exactly happens?",
)


@dataclass(frozen=True)
class Decision:
    kind: str                       # "next" | "clarify" | "probe"
    text: str = ""
    key_point: Optional[KeyPoint] = None
    reason: str = ""


def decide(question: Question, grade: Grade, *, followups_used: int, clarified: bool,
           asked_points: set[str], clarify_count: int = 0) -> Decision:
    if grade.clarity.dont_know:
        return Decision("next", reason="dont_know")
    if followups_used >= MAX_FOLLOWUPS:
        return Decision("next", reason="followup_limit")
    if grade.score >= GOOD_SCORE and not grade.clarity.unclear:
        return Decision("next", reason="good_answer")
    if grade.clarity.unclear and not clarified:
        return Decision("clarify", CLARIFY_TEMPLATES[clarify_count % len(CLARIFY_TEMPLATES)],
                        reason="unclear")
    by_point = {k.point: k for k in question.key_points}
    for point in grade.missing + grade.partial:
        kp = by_point.get(point)
        if kp and kp.followup and point not in asked_points:
            return Decision("probe", kp.followup, kp, reason="missing_key_point")
    return Decision("next", reason="nothing_to_probe")
