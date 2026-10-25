"""Background LLM re-grade of technical answers (local Ollama, free).

The live interview keeps the fast grader (grader.py): it decides follow-ups instantly.
Once a main question closes, its answer is also judged by a local LLM on ONE worker
thread, while the candidate works on the next question:

    the LLM marks each key point covered / partial / missing, and says whether the
    answer contains a clear factual error ("wrong")
    llm_score   = the same formula as the fast grader (key points + reference
                  similarity), with points recovered through follow-ups credited
                  as in session.py
    final score = 0.5 x fast score + 0.5 x llm_score, capped at WRONG_CAP when "wrong"

Measured 2026-10-25 on 575 human-labelled answers (grader_eval/: llm400, mine40,
team_tune, team_test; never the `fresh` set) with qwen3:8b, ~3-5 s per answer:
                       fast grader   blend (this)
  correlation (r)         0.84          0.93      (team answers: 0.71 -> 0.88)
  mean |diff|             0.14          0.11
  better answer ranked    91%           98%       (pairs of answers to one question)
  confidently wrong avg   0.19          0.16
The "wrong" flag fired on 116 of 186 answers humans scored below 0.3, 3 of 50 in
0.3-0.5 and none of the 339 scored 0.5 or more, so the cap never hit a good answer.

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
LLM_WEIGHT = 0.5
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
    "Do not give credit for words that merely repeat the question.")
USER = ("QUESTION: {q}\n\nREFERENCE ANSWER: {ref}\n\nKEY POINTS:\n{points}\n\nCANDIDATE ANSWER: {a}\n\n"
        "Return a verdict for every key point, in order, and wrong=true if the answer contains "
        "a clear factual error about the question.")


def _schema(n: int) -> dict:
    return {"type": "object", "required": ["verdicts", "wrong"], "properties": {
        "verdicts": {"type": "array", "minItems": n, "maxItems": n,
                     "items": {"type": "string", "enum": ["covered", "partial", "missing"]}},
        "wrong": {"type": "boolean"}}}


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

    def judge(self, question: Question, answer: str) -> dict:
        """{"verdicts": [covered|partial|missing per key point], "wrong": bool}"""
        n = len(question.key_points)
        points = "\n".join(f"{i + 1}. {k.point}" for i, k in enumerate(question.key_points))
        payload = {
            "model": self.model, "stream": False, "format": _schema(n), "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 200},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER.format(q=question.text, ref=question.reference_answer,
                                                                 points=points, a=answer)}],
        }
        if self.model.startswith(("qwen3", "deepseek-r1")):
            payload["think"] = False      # measured without hidden reasoning (and it is much faster)
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT if self._warm else COLD_START_TIMEOUT) as resp:
            out = json.loads(json.loads(resp.read().decode())["message"]["content"])
        self._warm = True
        verdicts = [v if v in CREDIT else "missing" for v in list(out.get("verdicts") or [])[:n]]
        return {"verdicts": verdicts + ["missing"] * (n - len(verdicts)), "wrong": bool(out.get("wrong"))}


def answer_text(record: dict) -> str:
    """The main answer plus any clarification, as the fast grader saw it (session.py)."""
    extra = [e["answer"] for e in record.get("exchanges", []) if e.get("kind") == "clarify"]
    return " ".join([record.get("answer", ""), *extra]).strip()


def blended(record: dict, judged: dict) -> dict:
    """The re-graded score for a closed question record (session.TechInterview._close)."""
    from .session import RECOVERED_CREDIT
    final = record.get("final_grade") or {}
    points = [k["point"] for k in record["key_points"]]
    status = dict(zip(points, judged["verdicts"]))
    credit = {p: CREDIT[s] for p, s in status.items()}
    for e in record.get("exchanges", []):          # points recovered through follow-ups, as in session.py
        p, v = e.get("key_point"), e.get("verdict")
        if e.get("kind") == "followup" and p in credit and v in CREDIT and CREDIT[v] > CREDIT[status[p]]:
            credit[p] = max(credit[p], CREDIT[v] * RECOVERED_CREDIT)
    kp = sum(credit.values()) / len(credit) if credit else 0.0
    kp = max(kp, CORE_FLOORS.get(final.get("core", ""), 0.0))
    llm_score = combine(kp, final.get("reference_similarity", 0.0))
    clarity = final.get("clarity") or {}
    if clarity.get("dont_know") and not final.get("covered"):
        llm_score = min(llm_score, 0.1)
    if clarity.get("too_short"):
        llm_score = min(llm_score, 0.5)
    score = LLM_WEIGHT * llm_score + (1 - LLM_WEIGHT) * record["score"]
    if judged["wrong"] or final.get("contradicts_reference"):
        score = min(score, WRONG_CAP)
    return {"score": round(score, 3), "fast_score": record["score"], "llm_score": round(llm_score, 3),
            "llm_verdicts": status, "llm_wrong": judged["wrong"]}


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
    regrade = blended(record, judge.judge(question, answer_text(record)))
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
