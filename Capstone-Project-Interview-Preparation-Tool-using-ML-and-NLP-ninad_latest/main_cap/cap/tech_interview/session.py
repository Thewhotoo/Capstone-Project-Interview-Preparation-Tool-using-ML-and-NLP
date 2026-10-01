"""One live technical interview.

    prompt()        what is on screen now: a main question, a clarification
                    request, or a follow-up
    submit(answer)  grade it, decide what comes next; returns the finished
                    main question's record (to be saved) when it closes

Per main question:
  * the answer is graded against the key points (grader.py);
  * after a clarification request, the clarification is appended to the
    original answer and the whole is re-graded;
  * after a follow-up on a key point, a point the candidate now supplies moves
    to covered (or partial). Recovered points earn RECOVERED_CREDIT of a point
    stated unprompted -- prompted recall is worth a little less, as an
    interviewer would judge it;
  * at most MAX_FOLLOWUPS follow-ups (clarifications included), then the next
    main question.
Live state is in memory only; each closed main question is returned as a plain
dict for session_history to store.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from .bank import Question
from .followup import Decision, decide
from .grader import CORE_FLOORS, Grade, combine, followup_covers, grade_answer

RECOVERED_CREDIT = 0.75


@dataclass
class _Current:
    question: Question
    answer: str = ""
    graded: Optional[Grade] = None       # the grader's own result for the answer (+ clarification)
    grade: Optional[Grade] = None        # graded, with points recovered through follow-ups
    first_grade: Optional[dict] = None
    exchanges: list[dict] = field(default_factory=list)
    followups_used: int = 0
    clarified: bool = False
    asked_points: set[str] = field(default_factory=set)
    recovered: dict[str, str] = field(default_factory=dict)   # point -> covered|partial via follow-up
    pending: Optional[Decision] = None


class TechInterview:
    def __init__(self, questions: list[Question], *, mode: str = "standalone",
                 grade_fn: Optional[Callable[..., Grade]] = None,
                 cover_fn: Optional[Callable[..., tuple[str, dict]]] = None):
        if not questions:
            raise ValueError("a technical interview needs at least one question")
        self.questions = questions
        self.mode = mode
        self._grade = grade_fn or (lambda q, a: grade_answer(q, a))
        self._cover = cover_fn or (lambda kp, a: followup_covers(kp, a))
        self.index = 0
        self.clarify_count = 0
        self.records: list[dict] = []
        self.current = _Current(questions[0])

    @property
    def finished(self) -> bool:
        return self.index >= len(self.questions)

    # ── what is on screen ───────────────────────────────────────────────────
    def prompt(self) -> Optional[dict]:
        if self.finished:
            return None
        q, cur = self.current.question, self.current
        base = {"number": self.index + 1, "total": len(self.questions), "subject": q.subject,
                "subject_label": q.subject_label, "topic": q.topic, "difficulty": q.difficulty,
                "question_id": q.id}
        if cur.pending is None:
            return {**base, "kind": "question", "text": q.text}
        return {**base, "kind": "clarify" if cur.pending.kind == "clarify" else "followup",
                "text": cur.pending.text, "main_question": q.text}

    # ── answering ───────────────────────────────────────────────────────────
    def submit(self, answer: str) -> dict:
        """Returns {"record": closed main question or None, "prompt": next prompt or None,
        "finished": bool}."""
        if self.finished:
            raise RuntimeError("the interview is already finished")
        answer = (answer or "").strip()
        cur = self.current
        if cur.pending is None:                                    # the main answer
            cur.answer = answer
            cur.graded = cur.grade = self._grade(cur.question, answer)
            cur.first_grade = cur.grade.to_dict()
        elif cur.pending.kind == "clarify":
            cur.exchanges.append({"kind": "clarify", "prompt": cur.pending.text, "answer": answer})
            cur.clarified = True
            cur.graded = self._grade(cur.question, f"{cur.answer} {answer}".strip())
            self._apply_recovered(cur)
        else:                                                      # a follow-up on a key point
            kp = cur.pending.key_point
            verdict, scores = self._cover(kp, answer)
            cur.exchanges.append({"kind": "followup", "prompt": cur.pending.text, "key_point": kp.point,
                                  "answer": answer, "verdict": verdict, "scores": scores,
                                  "expected": kp.followup_answer})
            if verdict != "missing":
                cur.recovered[kp.point] = verdict
            self._apply_recovered(cur)

        decision = decide(cur.question, cur.grade, followups_used=cur.followups_used,
                          clarified=cur.clarified, asked_points=cur.asked_points,
                          clarify_count=self.clarify_count)
        if decision.kind in ("clarify", "probe"):
            cur.pending = decision
            cur.followups_used += 1
            if decision.kind == "clarify":
                self.clarify_count += 1
            else:
                cur.asked_points.add(decision.key_point.point)
            return {"record": None, "prompt": self.prompt(), "finished": False}

        record = self._close(cur, decision.reason)
        self.index += 1
        if not self.finished:
            self.current = _Current(self.questions[self.index])
        return {"record": record, "prompt": self.prompt(), "finished": self.finished}

    def _apply_recovered(self, cur: _Current) -> None:
        """cur.grade = the grader's result with points recovered through follow-ups
        moved up, and the score recomputed. Always rebuilt from cur.graded."""
        base = cur.graded
        if not cur.recovered:          # keep the grader's own score (and its caps) untouched
            cur.grade = base
            return
        g = replace(base, covered=list(base.covered), partial=list(base.partial), missing=list(base.missing))
        order = {"missing": 0, "partial": 1, "covered": 2}
        status = {p: "covered" for p in g.covered} | {p: "partial" for p in g.partial} | {p: "missing" for p in g.missing}
        credit = {"covered": 1.0, "partial": 0.5, "missing": 0.0}
        points_credit = {p: credit[s] for p, s in status.items()}
        for p, v in cur.recovered.items():
            if p in status and order[v] > order[status[p]]:
                status[p] = v
                points_credit[p] = max(points_credit[p], credit[v] * RECOVERED_CREDIT)
        g.covered = [p for p, s in status.items() if s == "covered"]
        g.partial = [p for p, s in status.items() if s == "partial"]
        g.missing = [p for p, s in status.items() if s == "missing"]
        g.keypoint_score = round(sum(points_credit.values()) / len(points_credit), 3) if points_credit else 0.0
        g.keypoint_score = max(g.keypoint_score, CORE_FLOORS.get(base.core, 0.0))   # main idea stated
        g.score = round(combine(g.keypoint_score, g.reference_similarity), 3)
        if g.clarity.dont_know and not g.covered:
            g.score = min(g.score, 0.1)
        cur.grade = g

    def _close(self, cur: _Current, reason: str) -> dict:
        q, g = cur.question, cur.grade
        record = {
            "question_id": q.id, "subject": q.subject, "subject_label": q.subject_label,
            "topic_id": q.topic_id, "topic": q.topic, "difficulty": q.difficulty,
            "question": q.text, "answer": cur.answer, "score": g.score,
            "covered": g.covered, "partial": g.partial, "missing": g.missing,
            "first_grade": cur.first_grade, "final_grade": g.to_dict(),
            "exchanges": cur.exchanges, "closed_because": reason,
            "reference_answer": q.reference_answer,
            "key_points": [{"point": k.point, "followup": k.followup, "followup_answer": k.followup_answer}
                           for k in q.key_points],
            "source_pages": list(q.source_pages),
        }
        self.records.append(record)
        return record

    # ── summary ─────────────────────────────────────────────────────────────
    def summary(self) -> dict:
        def avg(xs):
            return round(sum(xs) / len(xs), 4) if xs else None
        by_subject, by_difficulty = {}, {}
        for r in self.records:
            by_subject.setdefault(r["subject_label"], []).append(r["score"])
            by_difficulty.setdefault(r["difficulty"], []).append(r["score"])
        return {
            "mode": self.mode,
            "questions_planned": len(self.questions),
            "questions_answered": len(self.records),
            "average_score": avg([r["score"] for r in self.records]),
            "by_subject": {k: avg(v) for k, v in by_subject.items()},
            "by_difficulty": {k: avg(v) for k, v in by_difficulty.items()},
            "followups_asked": sum(len(r["exchanges"]) for r in self.records),
            "weak_topics": sorted({r["topic"] for r in self.records if r["score"] < 0.5}),
        }
