"""
Generation Client — Stage A Synthetic Dataset Generation Pipeline.

The one place this pipeline actually calls an LLM. `GenerationClient` is a
Protocol so `synthetic_generation_pipeline.py` never depends on a concrete
model provider; `GeminiGenerationClient` is the production implementation
(mirrors `candidate_profile_generator.py`'s lazy-singleton + retry
conventions, this system's one other LLM call site); `FakeGenerationClient`
is a deterministic, network-free implementation for tests.

Strict separation of responsibility: this module produces a `GenerationOutput`
— raw text plus per-concept evidence — and nothing else. It does not decide
whether that output is acceptable (generation_validation.py's job), does not
assemble a TrainingExample (training_example_assembler.py's job), and does
not decide WHAT to generate (generation_recipe.py + prompt_assembler.py's
job).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Protocol

from pydantic import BaseModel, Field

from prompt_assembler import AssembledPrompt

logger = logging.getLogger(__name__)

_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 1.0


class ConceptEvidenceEntry(BaseModel):
    """One concept's supporting evidence in the raw generation output —
    present only for concepts the model actually addressed (demonstrated or
    superficial); a concept with no entry here is treated as omitted."""

    concept: str = ""
    evidence: str = ""


class GenerationOutput(BaseModel):
    """Raw, not-yet-validated model output. Passed directly as
    `response_schema` to the Gemini structured-output API, matching
    `candidate_profile_generator.py`'s pattern exactly."""

    answer_text: str = ""
    concept_evidence: list[ConceptEvidenceEntry] = Field(default_factory=list)
    contradiction_note: str = Field(
        default="",
        description="If a deliberate contradiction was introduced, a short note identifying "
                    "which single claim is the contradictory one. Empty otherwise.",
    )


class GenerationClient(Protocol):
    """What `synthetic_generation_pipeline.py` needs from a model provider —
    nothing more. Any implementation (Gemini, a fake, a future local model)
    satisfies this without the pipeline knowing which."""

    model_name: str

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        ...


# ═════════════════════════════════════════════════════════════════════════════
# Gemini implementation
# ═════════════════════════════════════════════════════════════════════════════

_genai_client = None


def _get_genai_client():
    """Lazy cached google-genai Client — same pattern as
    candidate_profile_generator.py's `_get_genai_client`, deliberately not
    shared with it (this pipeline's calls have a different purpose, volume,
    and failure-handling profile from profile generation)."""
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


class GeminiGenerationClient:
    """Production `GenerationClient` — one Gemini call per generation
    attempt, native structured output enforcing `GenerationOutput`'s shape."""

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.9) -> None:
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        client = _get_genai_client()
        from google.genai import types

        contents = f"{prompt.system_text}\n\n{prompt.user_text}"
        response = self._generate_with_retry(
            client, contents=contents,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=GenerationOutput,
            ),
        )
        if response.parsed is not None:
            return response.parsed
        raise RuntimeError("Gemini returned no parsed GenerationOutput (empty or malformed response).")

    def _generate_with_retry(self, client, contents: str, config):
        last_exc: Optional[Exception] = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                return client.models.generate_content(model=self.model_name, contents=contents, config=config)
            except Exception as e:
                last_exc = e
                if attempt < _RETRY_MAX_ATTEMPTS - 1 and _is_retryable_gemini_error(e):
                    delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                    logger.warning("Gemini generation call failed (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, _RETRY_MAX_ATTEMPTS, delay, e)
                    time.sleep(delay)
                    continue
                break
        raise RuntimeError(f"Gemini generation call failed: {last_exc}") from last_exc


# ═════════════════════════════════════════════════════════════════════════════
# Deterministic fake — network-free, for tests and local pipeline exercises
# ═════════════════════════════════════════════════════════════════════════════


class FakeGenerationClient:
    """Deterministic, network-free `GenerationClient`. Produces plausible
    output purely from the prompt's own structure — used by
    test_synthetic_generation_pipeline.py and by anyone exercising the
    pipeline without incurring a live Gemini call. Never used in production
    generation runs."""

    def __init__(self, model_name: str = "fake-deterministic-v1") -> None:
        self.model_name = model_name

    def generate(self, prompt: AssembledPrompt) -> GenerationOutput:
        user_text = prompt.user_text
        answer_parts = ["I worked on this directly and can walk through what I did."]
        concept_evidence: list[ConceptEvidenceEntry] = []

        for line in user_text.splitlines():
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                concept, instruction = line[2:].split(":", 1)
                concept = concept.strip()
                instruction_lower = instruction.lower()
                if "do not mention" not in instruction_lower and "do not" not in instruction_lower[:12]:
                    detail = "demonstrated with concrete functional detail" if "genuine functional" in instruction_lower else "mentioned briefly"
                    concept_evidence.append(ConceptEvidenceEntry(concept=concept, evidence=f"{concept} was {detail}."))
                    answer_parts.append(f"I used {concept} — {detail}.")

        contradiction_note = ""
        if "introduce exactly one deliberate" in user_text.lower():
            contradiction_note = "Introduced one deliberate contradiction as instructed."
            answer_parts.append("Actually, I want to note something that conflicts with the stated grounding.")

        if "do not meaningfully engage" in user_text.lower():
            answer_parts = ["Actually, let me tell you about a completely different topic instead."]
            concept_evidence = []

        return GenerationOutput(
            answer_text=" ".join(answer_parts),
            concept_evidence=concept_evidence,
            contradiction_note=contradiction_note,
        )
