"""Background LLM re-grade of technical answers (local Ollama, free).

The live interview keeps the fast grader (grader.py): it decides follow-ups instantly.
Once a main question closes, its answer is also judged by a local LLM on ONE worker
thread, while the candidate works on the next question:

    the LLM marks each key point covered / partial / missing, says whether the answer
    contains a clear factual error ("wrong"), and gives an overall score for the whole
    answer ("holistic", 0-1, the way frontier-model judges grade)
    final score = 0.6 x holistic + 0.4 x fast score (which includes follow-up
                  recoveries); points recovered through follow-ups also add to the
                  holistic part; capped at WRONG_CAP when "wrong"

2026-10-28, holistic score added (grader_eval/frontier_eval.py compares with frontier
models). On 412 tuning answers (current bank; stale labels skipped), vs the previous
0.5 fast + 0.5 LLM-point-count blend: move-on decision 88.8% -> 90.3%, r 0.922 -> 0.946,
mean gap 0.107 -> 0.096; once on the never-tuned fresh set: decision 70% -> 80%,
r 0.81 -> 0.85, gap 0.149 -> 0.130 (fast grader alone: 66%, 0.55, 0.235).
The numbers below are the earlier (point-count) blend's.

Measured 2026-10-25 on 575 human-labelled answers (grader_eval/: llm400, mine40,
team_tune, team_test; never the `fresh` set) with qwen3:8b, ~3-5 s per answer:
                       fast grader   blend (this)
  correlation (r)         0.84          0.93      (team answers: 0.71 -> 0.88)
  mean |diff|             0.14          0.11
  better answer ranked    91%           98%       (pairs of answers to one question)
  confidently wrong avg   0.19          0.16
The "wrong" flag fired on 116 of 186 answers humans scored below 0.3, 3 of 50 in
0.3-0.5 and none of the 339 scored 0.5 or more, so the cap never hit a good answer.

The re-grade also replaces, in the report:
  * the covered / partial / missing lists, with the LLM's per-point verdicts
    (per-point agreement with human labels: team_tune 0.69 -> 0.81, team_test
    0.72 -> 0.77, mine40 0.67 -> 0.72);
  * each follow-up verdict: a reply counts only when BOTH the fast grader and the
    LLM accept it (followup_verdict; 183 labelled replies: wrong replies accepted
    17.6% -> 4.1%, accuracy 86.9% -> 89.6%, correct replies rejected 10.1% -> 14.7%).

/end waits up to CAP_REGRADE_WAIT_SECONDS for unfinished re-grades; an unfinished or
failed one keeps the fast score, and without Ollama nothing changes.
Config: CAP_TECH_LLM_GRADE auto (default: only when Ollama has the model) | 1 | 0,
CAP_TECH_JUDGE_MODEL (default: first installed of PREFERRED_MODELS), CAP_OLLAMA_URL.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from .bank import Question
from .grader import CORE_FLOORS, combine

logger = logging.getLogger(__name__)

# Only qwen3:8b was measured; smaller models are untested here, so they are not used by default.
PREFERRED_MODELS = ("qwen3:8b",)
DEFAULT_URL = "http://localhost:11434"
LLM_WEIGHT = 0.6     # weight of the LLM's holistic score; the rest is the fast score
WRONG_CAP = 0.20
TIMEOUT = 60.0
COLD_START_TIMEOUT = 120.0          # the first call loads the model into GPU memory
AVAILABILITY_RECHECK_SECONDS = 300.0
CREDIT = {"covered": 1.0, "partial": 0.5, "missing": 0.0}

SYSTEM = (
    "You are a strict but fair technical interviewer grading a candidate's spoken answer. "
    "For each numbered key point, decide whether the ANSWER itself states it:\n"
    "- covered: the answer states this idea correctly, in any words (paraphrase, example or informal speech is fine)\n"
    "- partial: the answer gets part of it, or gestures at it vaguely without the key mechanism\n"
    "- missing: the answer does not say it, says something different, or says it wrongly\n"
    "Judge only what the candidate said. Talking about the same topic is not stating the point. "
    "A claim that contradicts the reference answer is wrong and earns nothing. "
    "Do not give credit for words that merely repeat the question."
    " Also give an overall score from 0.0 to 1.0 for the whole answer: 1.0 = complete and correct,"
    " about 0.5 = roughly half of what the question needs, near 0 = wrong, off-topic or no real answer."
    " A confident wrong answer scores near 0 even if it uses the right words.")
USER = ("QUESTION: {q}\n\nREFERENCE ANSWER: {ref}\n\nKEY POINTS:\n{points}\n\nCANDIDATE ANSWER: {a}\n\n"
        "Return a verdict for every key point, in order, and wrong=true if the answer contains "
        "a clear factual error about the question. Also return score, the overall score from 0.0 to 1.0.")


FU_SYSTEM = (
    "You are a strict but fair technical interviewer. The candidate missed a point, so you asked a "
    "follow-up question. Decide whether their REPLY answers it correctly:\n"
    "- covered: the reply states the expected idea correctly, however briefly or informally. A terse "
    "reply that matches it is complete: \"nope\" to a yes/no question whose answer is no, \"it becomes "
    "half\", \"left join union right join\".\n"
    "- partial: the reply commits to an answer that is on the right track but incomplete\n"
    "- missing: the reply is wrong, off-topic or says something different; or the candidate does not "
    "commit to an answer (\"not sure, maybe X\", \"I think X but I'm blanking\") -- a hedged guess is "
    "not an answer.\n"
    "Judge only what the reply adds; words that merely repeat the question earn nothing.")
FU_USER = ("FOLLOW-UP QUESTION: {q}\n\nEXPECTED ANSWER: {expected}\n\nTHE POINT BEING CHECKED: {point}\n\n"
           "CANDIDATE REPLY: {a}\n\nReturn the verdict.")
FU_SCHEMA = {"type": "object", "required": ["verdict"], "properties": {
    "verdict": {"type": "string", "enum": ["covered", "partial", "missing"]}}}


def _schema(n: int) -> dict:
    return {"type": "object", "required": ["verdicts", "wrong", "score"], "properties": {
        "verdicts": {"type": "array", "minItems": n, "maxItems": n,
                     "items": {"type": "string", "enum": ["covered", "partial", "missing"]}},
        "wrong": {"type": "boolean"},
        "score": {"type": "number", "minimum": 0, "maximum": 1}}}


class OllamaJudge:
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        explicit = model or os.environ.get("CAP_TECH_JUDGE_MODEL")
        self.model = explicit or PREFERRED_MODELS[0]
        self._resolved = bool(explicit)
        self.base_url = (base_url or os.environ.get("CAP_OLLAMA_URL", DEFAULT_URL)).rstrip("/")
        self._warm = False

    def available(self, timeout: float = 2.0) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=timeout) as resp:
                models = json.loads(resp.read().decode()).get("models") or []
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return False
        installed = {m.get("name", "") for m in models} | {m.get("model", "") for m in models}
        if not self._resolved:
            self.model = next((m for m in PREFERRED_MODELS if m in installed), self.model)
            self._resolved = True
        return self.model in installed

    def _chat(self, system: str, user: str, schema: dict) -> dict:
        payload = {
            "model": self.model, "stream": False, "format": schema, "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 200},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.model.startswith(("qwen3", "deepseek-r1")):
            payload["think"] = False      # measured without hidden reasoning (and it is much faster)
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT if self._warm else COLD_START_TIMEOUT) as resp:
            out = json.loads(json.loads(resp.read().decode())["message"]["content"])
        self._warm = True
        return out

    def judge(self, question: Question, answer: str) -> dict:
        """{"verdicts": [covered|partial|missing per key point], "wrong": bool, "holistic": 0-1}"""
        n = len(question.key_points)
        points = "\n".join(f"{i + 1}. {k.point}" for i, k in enumerate(question.key_points))
        out = self._chat(SYSTEM, USER.format(q=question.text, ref=question.reference_answer,
                                             points=points, a=answer), _schema(n))
        verdicts = [v if v in CREDIT else "missing" for v in list(out.get("verdicts") or [])[:n]]
        try:
            holistic = min(1.0, max(0.0, float(out.get("score"))))
        except (TypeError, ValueError):
            holistic = None
        return {"verdicts": verdicts + ["missing"] * (n - len(verdicts)), "wrong": bool(out.get("wrong")),
                "holistic": holistic}

    def judge_followup(self, followup: str, expected: str, point: str, reply: str) -> str:
        """covered | partial | missing for one reply to a key point's follow-up question."""
        out = self._chat(FU_SYSTEM, FU_USER.format(q=followup, expected=expected or point, point=point, a=reply),
                         FU_SCHEMA)
        v = out.get("verdict")
        return v if v in CREDIT else "missing"


def answer_text(record: dict) -> str:
    """The main answer plus any clarification, as the fast grader saw it (session.py)."""
    extra = [e["answer"] for e in record.get("exchanges", []) if e.get("kind") == "clarify"]
    return " ".join([record.get("answer", ""), *extra]).strip()


def followup_verdict(fast: str, llm: Optional[str]) -> str:
    """A follow-up reply counts only when BOTH graders accept it (then the less generous verdict).
    Measured on 183 labelled replies: wrong replies accepted 17.6% -> 4.1%, accuracy 86.9% ->
    89.6%, at the cost of correct replies rejected 10.1% -> 14.7%."""
    if llm is None:
        return fast
    if fast == "missing" or llm == "missing":
        return "missing"
    return "partial" if "partial" in (fast, llm) else "covered"


def blended(record: dict, judged: dict) -> dict:
    """The re-graded score for a closed question record (session.TechInterview._close).
    `judged` may carry "followups": {exchange index: LLM verdict} for its follow-up replies."""
    from .session import RECOVERED_CREDIT
    final = record.get("final_grade") or {}
    points = [k["point"] for k in record["key_points"]]
    status = dict(zip(points, judged["verdicts"]))
    credit = {p: CREDIT[s] for p, s in status.items()}
    kp_main = sum(credit.values()) / len(credit) if credit else 0.0   # before follow-up recoveries
    fu_llm = judged.get("followups") or {}
    for i, e in enumerate(record.get("exchanges", [])):   # points recovered through follow-ups, as in session.py
        if e.get("kind") != "followup":
            continue
        p = e.get("key_point")
        v = followup_verdict(e.get("verdict", "missing"), fu_llm.get(i, fu_llm.get(str(i))))
        if p in credit and CREDIT[v] > CREDIT[status[p]]:
            credit[p] = max(credit[p], CREDIT[v] * RECOVERED_CREDIT)
            status[p] = v
    kp = sum(credit.values()) / len(credit) if credit else 0.0
    kp = max(kp, CORE_FLOORS.get(final.get("core", ""), 0.0))
    llm_score = combine(kp, final.get("reference_similarity", 0.0))
    clarity = final.get("clarity") or {}
    if clarity.get("dont_know") and not final.get("covered"):
        llm_score = min(llm_score, 0.1)
    if clarity.get("too_short"):
        llm_score = min(llm_score, 0.5)
    holistic = judged.get("holistic")
    if holistic is None:      # an older or malformed verdict: fall back to the point count
        holistic = llm_score
    else:                     # points recovered through follow-ups count on top of the main answer
        holistic = min(1.0, holistic + 0.85 * max(0.0, kp - max(kp_main, CORE_FLOORS.get(final.get("core", ""), 0.0))))
        if clarity.get("dont_know") and not final.get("covered"):
            holistic = min(holistic, 0.1)
        if clarity.get("too_short"):
            holistic = min(holistic, 0.5)
    score = LLM_WEIGHT * holistic + (1 - LLM_WEIGHT) * record["score"]
    if judged["wrong"] or final.get("contradicts_reference"):
        score = min(score, WRONG_CAP)
    return {"score": round(score, 3), "fast_score": record["score"], "llm_score": round(llm_score, 3),
            "llm_holistic": None if judged.get("holistic") is None else round(holistic, 3),
            "llm_verdicts": status, "llm_wrong": judged["wrong"],
            "followup_verdicts": {str(i): v for i, v in fu_llm.items()},
            # what the report lists: the LLM's per-point verdicts (with follow-up recoveries);
            # measured per-point agreement with humans 0.69/0.72/0.67 -> 0.81/0.77/0.72
            "covered": [p for p in points if status[p] == "covered"],
            "partial": [p for p in points if status[p] == "partial"],
            "missing": [p for p in points if status[p] == "missing"]}


# ── background worker ───────────────────────────────────────────────────────

_pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
_judge: Optional[OllamaJudge] = None
_futures: dict[tuple[int, int], concurrent.futures.Future] = {}
_lock = threading.Lock()
_availability = {"checked_at": None, "available": False}


def _get_judge() -> OllamaJudge:
    global _judge, _pool
    if _judge is None:
        _judge = OllamaJudge()
        _pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="tech-llm-grade")
    return _judge


def enabled() -> bool:
    mode = os.environ.get("CAP_TECH_LLM_GRADE", "auto").strip().lower()
    if mode in ("1", "true", "on"):
        return True
    if mode != "auto":
        return False
    now = time.monotonic()
    if _availability["checked_at"] is None or now - _availability["checked_at"] > AVAILABILITY_RECHECK_SECONDS:
        try:
            _availability["available"] = _get_judge().available()
        except Exception:
            _availability["available"] = False
        _availability["checked_at"] = now
        logger.info("technical LLM re-grade %s", "on" if _availability["available"] else "off")
    return _availability["available"]


def _key(session_id: int, index: int) -> str:
    return f"techregrade:{session_id}:{index}"


def _run(judge: OllamaJudge, question: Question, record: dict, session_id: int, index: int) -> None:
    from live_store import get_store
    judged = judge.judge(question, answer_text(record))
    judged["followups"] = {i: judge.judge_followup(e.get("prompt", ""), e.get("expected", ""),
                                                   e.get("key_point", ""), e.get("answer", ""))
                           for i, e in enumerate(record.get("exchanges", []))
                           if e.get("kind") == "followup" and (e.get("answer") or "").strip()}
    regrade = blended(record, judged)
    get_store().put(_key(session_id, index), regrade)


def queue(session_id: int, index: int, question: Question, record: dict) -> None:
    """Re-grade closed question `index` in the background (never breaks the interview)."""
    if not answer_text(record) or not enabled():
        return
    try:
        judge = _get_judge()
        future = _pool.submit(_run, judge, question, dict(record), session_id, index)
        with _lock:
            _futures[(session_id, index)] = future
    except Exception:
        logger.warning("could not queue the technical LLM re-grade", exc_info=True)


def collect(session_id: int, count: int, wait_seconds: float) -> dict[int, dict]:
    """Finished re-grades for questions 0..count-1 (this process's pending ones get up
    to wait_seconds in total); removes them from the live store."""
    from live_store import get_store
    with _lock:
        mine = [_futures.pop((session_id, i)) for i in range(count) if (session_id, i) in _futures]
    deadline = time.monotonic() + wait_seconds
    for future in mine:
        try:
            future.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:   # timeout or failure: that question keeps its fast score
            future.cancel()
    store, out = get_store(), {}
    for i in range(count):
        stored = store.get(_key(session_id, i))
        if stored is not None:
            store.delete(_key(session_id, i))
            out[i] = stored
    return out
