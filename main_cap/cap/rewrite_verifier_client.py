"""
Rewrite Verifier Client — Experiment 4 (Rewrite Augmentation) Stage.

The second LLM call site this milestone introduces (`generation_client.py`
handles the first — generating the rewritten text itself). This module's
job is narrower and different in KIND: not "produce new text," but "judge
whether two already-written texts mean the same thing," per this session's
explicit design decision to add a Gemini-based semantic-drift check as a
safeguard beyond SBERT similarity alone.

Kept independent from `generation_client.py` rather than extending it —
same "deliberate independence between pipeline stages" precedent already
applied repeatedly in this codebase (`generation_validation.py`,
`dataset_relabeling.py`). Concretely: the lazy-singleton `google-genai`
client setup is DUPLICATED here rather than importing
`generation_client._get_genai_client` (a private, underscore-prefixed name)
— the same rule `dataset_relabeling.py`'s docstring already states
explicitly for this codebase.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 1.0


class SemanticDriftVerdict(BaseModel):
    """Whether the rewritten answer's technical meaning materially differs
    from the original's, per an LLM judge's reading of both texts side by
    side — a safeguard beyond SBERT cosine similarity, which measures
    surface-level semantic distance but can miss a subtle but material
    factual drift (e.g. a swapped cause/effect, a reversed claim) that still
    scores as "similar enough" numerically."""

    meaning_changed: bool = False
    explanation: str = Field(default="", description="A brief explanation of the verdict.")


class RewriteVerifierClient(Protocol):
    """What `rewrite_validation.py` needs from a semantic-drift judge —
    nothing more. Mirrors `generation_client.GenerationClient`'s Protocol
    shape exactly, one level removed (judges, doesn't generate)."""

    model_name: str

    def verify(self, original_answer: str, rewritten_answer: str) -> SemanticDriftVerdict:
        ...


# ═════════════════════════════════════════════════════════════════════════════
# Gemini implementation
# ═════════════════════════════════════════════════════════════════════════════

_genai_client = None


def _get_genai_client():
    """Lazy cached google-genai Client — same pattern as
    `generation_client._get_genai_client` and
    `candidate_profile_generator.py`'s `_get_genai_client`, deliberately
    duplicated rather than shared (see module docstring)."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set it to your Google AI Studio API key."
        )

    from google import genai
    _genai_client = genai.Client(api_key=api_key)
    return _genai_client


def _is_retryable_gemini_error(exc: Exception) -> bool:
    error_str = str(exc).lower()
    if any(kw in error_str for kw in ("api_key", "authentication", "permission", "401", "403")):
        return False
    return any(
        kw in error_str
        for kw in ("rate", "limit", "timeout", "deadline", "500", "502", "503", "unavailable")
    )


_VERIFIER_SYSTEM_PROMPT = (
    "You are comparing two versions of the same interview answer: an ORIGINAL and a "
    "REWRITE that was supposed to change communication style only, never technical "
    "meaning. Judge whether the REWRITE's technical meaning has changed from the "
    "ORIGINAL's in any material way — a fact added or dropped, a claim reversed, a "
    "concept's presence/absence flipped, a contradiction added or removed, or a "
    "different technology/outcome implied. Superficial differences in wording, tone, "
    "length, or sentence structure are NOT material changes. Respond with meaning_changed "
    "and a brief explanation."
)


class GeminiSemanticVerifierClient:
    """Production `RewriteVerifierClient` — one Gemini call per verification,
    native structured output enforcing `SemanticDriftVerdict`'s shape."""

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.0) -> None:
        self.model_name = model_name
        self.temperature = temperature

    def verify(self, original_answer: str, rewritten_answer: str) -> SemanticDriftVerdict:
        client = _get_genai_client()
        from google.genai import types

        contents = (
            f"{_VERIFIER_SYSTEM_PROMPT}\n\n"
            f"ORIGINAL:\n{original_answer}\n\nREWRITE:\n{rewritten_answer}"
        )
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=512,
            response_mime_type="application/json",
            response_schema=SemanticDriftVerdict,
        )

        # A successful HTTP call with an unparseable body (response.parsed is
        # None) is NOT an exception `_verify_with_retry`'s except-block would
        # catch — it's a distinct, empirically observed transient failure
        # mode (a pilot run against real Gemini hit this on attempt 1 and
        # crashed the entire batch with no retry at all). Retried here,
        # separately, for exactly that reason.
        last_unparsed = False
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            response = self._verify_with_retry(client, contents=contents, config=config)
            if response.parsed is not None:
                return response.parsed
            last_unparsed = True
            if attempt < _RETRY_MAX_ATTEMPTS - 1:
                delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "Gemini verification call returned no parsed SemanticDriftVerdict "
                    "(attempt %d/%d), retrying in %.1fs.", attempt + 1, _RETRY_MAX_ATTEMPTS, delay,
                )
                time.sleep(delay)
        if last_unparsed:
            raise RuntimeError("Gemini returned no parsed SemanticDriftVerdict after retrying (empty or malformed response).")

    def _verify_with_retry(self, client, contents: str, config):
        last_exc: Optional[Exception] = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                return client.models.generate_content(model=self.model_name, contents=contents, config=config)
            except Exception as e:
                last_exc = e
                if attempt < _RETRY_MAX_ATTEMPTS - 1 and _is_retryable_gemini_error(e):
                    delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                    logger.warning("Gemini verification call failed (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, _RETRY_MAX_ATTEMPTS, delay, e)
                    time.sleep(delay)
                    continue
                break
        raise RuntimeError(f"Gemini verification call failed: {last_exc}") from last_exc


# ═════════════════════════════════════════════════════════════════════════════
# Deterministic fake — network-free, for tests and local pipeline exercises
# ═════════════════════════════════════════════════════════════════════════════

_FAKE_DRIFT_TRIGGER = "DRIFT_TEST_TRIGGER"


class FakeSemanticVerifierClient:
    """Deterministic, network-free `RewriteVerifierClient`. Flags
    `meaning_changed=True` only when the rewritten text contains the literal
    marker `DRIFT_TEST_TRIGGER` (a test fixture's way of exercising the
    rejection path deterministically) — otherwise always reports no drift.
    Never used in production verification; mirrors
    `generation_client.FakeGenerationClient`'s "deterministic stand-in, not
    a quality simulation" role exactly."""

    def __init__(self, model_name: str = "fake-verifier-deterministic-v1") -> None:
        self.model_name = model_name

    def verify(self, original_answer: str, rewritten_answer: str) -> SemanticDriftVerdict:
        if _FAKE_DRIFT_TRIGGER in rewritten_answer:
            return SemanticDriftVerdict(
                meaning_changed=True,
                explanation="Fake verifier: rewritten answer contains the deliberate test drift marker.",
            )
        return SemanticDriftVerdict(meaning_changed=False, explanation="Fake verifier: no drift detected.")
