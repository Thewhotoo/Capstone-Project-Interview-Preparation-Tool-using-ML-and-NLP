"""
Fact checker — flags technically FALSE general claims in an interview answer,
using a small local LLM served by Ollama (default qwen2.5:3b, 4-bit, ~2 GB on GPU).

WHY: the evidence evaluator can measure relevance, specificity and ownership,
but not whether a confident technical statement is true ("more Kafka
partitions guarantee exactly-once delivery") — that needs world knowledge a
small encoder doesn't have.

SCOPE (deliberately narrow):
  * Only GENERAL technical facts are judged. Claims about the candidate's own
    work ("I used Redis", "it took 40 seconds") can't be verified and are
    explicitly excluded in the prompt.
  * The result can only LOWER a score (see resume_evidence_evaluator); it never
    raises one, so a hallucinating checker can't inflate grades.
  * Optional: if Ollama isn't reachable, the model isn't pulled, or the call
    times out, the result is status="unavailable" and grading proceeds exactly
    as without it ("correctness not verified").

Config (env): CAP_FACT_CHECK_MODEL (default qwen2.5:3b), CAP_OLLAMA_URL
(default http://localhost:11434), CAP_FACT_CHECK_TIMEOUT seconds (default 20).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_URL = "http://localhost:11434"

_SYSTEM_PROMPT = """You are a strict senior software engineer fact-checking a candidate's interview answer.

Find statements in the ANSWER that are technically FALSE as general facts about how software, systems, \
algorithms, protocols, databases, security or tools work.

Rules:
- Only flag a statement if it is clearly and objectively false. When unsure, do NOT flag it.
- Do NOT flag claims about the candidate's own project or experience (what they built, chose, measured, \
or how long something took) - those cannot be checked.
- Do NOT flag vagueness, missing detail, opinions, or bad style. Only false facts.
- Quote the false statement briefly and say in one short sentence what is actually true.

Reply with JSON only: {"false_claims": [{"claim": "...", "correction": "..."}]}
Use {"false_claims": []} when nothing is clearly false."""

# Second pass, one flagged claim at a time: small models are noticeably more reliable on a
# single focused yes/no judgment than on open-ended extraction, and the first pass also
# flags paraphrases ("one schema" vs "a common schema") and personal statements.
_VERIFY_PROMPT = """You check ONE statement from a job candidate's interview answer.

Classify it:
- "false": it states something about how a technology, protocol, algorithm or tool works in general, \
and that is clearly and objectively wrong.
- "true": it is correct, or it is basically the same as the suggested correction (a paraphrase).
- "personal": it only describes the candidate's own project, choices, opinions or results.
- "unsure": anything else.

Reply with JSON only: {"verdict": "false" | "true" | "personal" | "unsure"}"""
# Direct rubric grade (same 0-4 rubric as benchmarks/evaluator/label_answers.py). Blended 50/50 with
# the evidence score: on the held-out benchmark the blend ranked answers better (82%) than either the
# evidence scorer + fact check (80%) or this grade alone (78%) — their errors are complementary.
_GRADE_PROMPT = """You grade a candidate's answer in a technical interview about a project on their resume.
Score 0-4:
4 excellent: correct, specific to THIS project, explains why/how, shows real ownership
3 good: correct and specific, but brief or missing the why
2 partial: on topic and plausible, but vague or only half the answer
1 poor: generic/textbook, a keyword list, or built around things not on the resume
0 worthless: non-answer, off-topic, or technically wrong
Judge correctness and specificity. Do NOT reward length, confidence or jargon.
Reply with JSON only: {"score": <0-4>}"""
_COLD_START_TIMEOUT = 90.0   # first call loads the model into VRAM (~20-40 s on a laptop GPU)


@dataclass(frozen=True)
class FactCheckResult:
    status: str                                   # "checked" | "unavailable"
    false_claims: tuple[dict, ...] = field(default_factory=tuple)      # confirmed by the second pass
    suspected_claims: tuple[dict, ...] = field(default_factory=tuple)  # flagged by the first pass only
    model: str = ""
    detail: str = ""                              # why unavailable, for logs

    @property
    def has_errors(self) -> bool:
        return self.status == "checked" and bool(self.false_claims)

    @property
    def severity(self) -> str:
        """'confirmed' | 'suspected' | 'none' (also 'none' when unavailable)."""
        if self.status != "checked":
            return "none"
        if self.false_claims:
            return "confirmed"
        return "suspected" if self.suspected_claims else "none"


class OllamaFactChecker:
    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float | None = None):
        self.model = model or os.environ.get("CAP_FACT_CHECK_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("CAP_OLLAMA_URL", DEFAULT_URL)).rstrip("/")
        self.timeout = timeout if timeout is not None else float(os.environ.get("CAP_FACT_CHECK_TIMEOUT", "20"))
        self._warm = False

    def _chat(self, system: str, user: str, max_tokens: int) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": max_tokens},
        }
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        timeout = self.timeout if self._warm else max(self.timeout, _COLD_START_TIMEOUT)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        self._warm = True
        return json.loads(body["message"]["content"])

    def grade(self, question: str, answer: str, context: str = "") -> float | None:
        """Direct 0..1 rubric grade, or None when the model is unavailable."""
        user = f"RESUME PROJECT: {context}\nQUESTION: {question}\nANSWER: {answer}"
        try:
            score = float(self._chat(_GRADE_PROMPT, user, 20).get("score"))
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError, TypeError) as exc:
            logger.info("llm grade unavailable: %s", exc)
            return None
        return max(0.0, min(4.0, score)) / 4.0

    def check(self, question: str, answer: str, context: str = "") -> FactCheckResult:
        if not answer or len(answer.split()) < 6:      # nothing to fact-check in a one-liner
            return FactCheckResult(status="checked", model=self.model)
        user = f"QUESTION: {question}\n"
        if context:
            user += f"CANDIDATE'S PROJECT (from their resume, assume true): {context}\n"
        user += f"ANSWER: {answer}"
        try:
            content = self._chat(_SYSTEM_PROMPT, user, 300)
            candidates = []
            for item in content.get("false_claims") or []:
                if isinstance(item, dict) and str(item.get("claim", "")).strip():
                    candidates.append({"claim": str(item["claim"]).strip()[:300],
                                       "correction": str(item.get("correction", "")).strip()[:300]})
            confirmed = []
            for c in candidates[:3]:
                # Verify the QUOTED claim. (Verifying the model's own restatement was tried and
                # failed badly with a 3B model: it often restated a correct claim as its negation.)
                verdict = self._chat(_VERIFY_PROMPT,
                                     f"STATEMENT: {c['claim']}\nSUGGESTED CORRECTION: {c['correction']}", 20)
                if str(verdict.get("verdict", "")).strip().lower() == "false":
                    confirmed.append(c)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            logger.info("fact check unavailable: %s", exc)
            return FactCheckResult(status="unavailable", model=self.model, detail=f"{type(exc).__name__}: {exc}")
        return FactCheckResult(status="checked", false_claims=tuple(confirmed),
                               suspected_claims=tuple(candidates), model=self.model)
