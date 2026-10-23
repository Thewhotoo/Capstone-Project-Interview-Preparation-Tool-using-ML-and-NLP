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
import re
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

# Confirmation (second pass): a flagged claim counts only if an NLI model says the LLM's
# "correction" CONTRADICTS the claim, and the claim isn't a personal statement "corrected" with
# another personal statement ("I didn't trust Gemini" -> "I trusted Gemini"). Measured on the
# benchmark (recorded qwen2.5:3b outputs): same ranking accuracy as asking the LLM itself to
# verify, but false alarms on correct answers fell from 10/22 to 0/22 (original set) and 4/15 to
# 3/15 (held-out). The LLM's own yes/no verdict was unreliable - it called several wrong claims
# "true" - and verifying its restatement of a claim was worse still (it inverted facts).
CONFIRM_CONTRADICTION = 0.5
_NLI_MODEL = "cross-encoder/nli-deberta-v3-small"   # labels: contradiction, entailment, neutral
_PERSONAL = re.compile(r"^\s*(i|we|my|our|the candidate)\b", re.IGNORECASE)
_nli = None


def _default_contradiction(claim: str, correction: str) -> float:
    global _nli
    if _nli is None:
        from sentence_transformers import CrossEncoder
        _nli = CrossEncoder(_NLI_MODEL)
    import numpy as np
    logits = _nli.predict([(claim, correction)])[0]
    probs = np.exp(logits - logits.max())
    return float(probs[0] / probs.sum())


def _is_personal_flip(claim: str, correction: str) -> bool:
    return bool(_PERSONAL.match(claim)) and bool(_PERSONAL.match(correction))


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
    false_claims: tuple[dict, ...] = field(default_factory=tuple)      # confirmed (correction contradicts the claim)
    suspected_claims: tuple[dict, ...] = field(default_factory=tuple)  # everything the LLM flagged (logging only)
    model: str = ""
    detail: str = ""                              # why unavailable, for logs

    @property
    def has_errors(self) -> bool:
        return self.status == "checked" and bool(self.false_claims)

    @property
    def severity(self) -> str:
        """'confirmed' | 'none' (also 'none' when unavailable). Unconfirmed flags are
        not penalised: on the benchmark they hit correct answers as often as wrong ones."""
        return "confirmed" if self.status == "checked" and self.false_claims else "none"


class OllamaFactChecker:
    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float | None = None,
                 contradiction_fn=None):
        self.contradiction_fn = contradiction_fn or _default_contradiction
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
            confirmed = [c for c in candidates[:3]
                         if not _is_personal_flip(c["claim"], c["correction"])
                         and self.contradiction_fn(c["claim"], c["correction"]) >= CONFIRM_CONTRADICTION]
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            logger.info("fact check unavailable: %s", exc)
            return FactCheckResult(status="unavailable", model=self.model, detail=f"{type(exc).__name__}: {exc}")
        return FactCheckResult(status="checked", false_claims=tuple(confirmed),
                               suspected_claims=tuple(candidates), model=self.model)
