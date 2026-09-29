"""
Independent Four-Dimension Rubric Judge — Step 3 dataset-labeling infra.

The judge assigns the TRAINING LABELS for the four canonical dimensions
(evaluation_dimensions.py), independently of the generation target. It exists
ONLY to label generated dataset examples; it is NOT the production interview
evaluator (that stays the HybridEvaluator / DeBERTa path) and nothing in the
live evaluation stack imports this module.

Each dimension is judged in ITS OWN call, from the exact Step-1 rubric text
plus the Step-2 contextual input (question + grounding + expected concepts +
answer), so the four scores are as independent as possible and the judge sees
the same context the model will. Production uses a real LLM at temperature 0
for determinism; tests inject a mock judge (no network).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from evaluation_dimensions import (
    CANONICAL_DIMENSIONS,
    NUM_TIERS,
    RUBRICS,
    EvaluationDimension,
)
from model_backbone import build_dimension_input_text

logger = logging.getLogger(__name__)

_MAX_TIER = NUM_TIERS - 1
DEFAULT_AGREEMENT_TOLERANCE = 1


class JudgeVerdict(BaseModel):
    """One dimension's independently judged label for a dataset example."""

    model_config = ConfigDict(frozen=True)

    dimension: str          # canonical EvaluationDimension key
    score: int              # ordinal tier 0..4
    rationale: str = ""     # short, for auditing/debugging only
    judge_version: str

    @model_validator(mode="after")
    def _validate(self) -> "JudgeVerdict":
        if self.dimension not in {d.value for d in EvaluationDimension}:
            raise ValueError(f"unknown dimension key: {self.dimension!r}")
        if not (0 <= self.score <= _MAX_TIER):
            raise ValueError(f"score must be in [0, {_MAX_TIER}], got {self.score}")
        if not self.judge_version.strip():
            raise ValueError("judge_version must not be empty")
        return self


class RubricJudge(Protocol):
    """What the labeling pipeline needs from a judge — nothing more. Any
    implementation (LLM, a future fine-tuned judge, a test mock) satisfies
    this without the pipeline knowing which."""

    judge_version: str

    def judge_dimension(
        self,
        dimension: EvaluationDimension,
        question_text: str,
        answer_text: str,
        grounding_text: str,
        expected_concepts: tuple[str, ...],
    ) -> JudgeVerdict:
        ...


def build_judge_prompt(
    dimension: EvaluationDimension,
    question_text: str,
    answer_text: str,
    grounding_text: str,
    expected_concepts: tuple[str, ...],
) -> tuple[str, str]:
    """Builds (system_text, user_text) for judging ONE dimension. The system
    text is the exact Step-1 rubric (definition + 0-4 tier boundaries +
    evidence up/down + non-overlap); the user text is the Step-2 contextual
    input plus the answer. Deterministic given its inputs."""
    rubric = RUBRICS[dimension]
    tier_lines = "\n".join(f"  {t}: {rubric.tiers[t]}" for t in range(NUM_TIERS))
    increases = "; ".join(rubric.increases)
    decreases = "; ".join(rubric.decreases)
    non_overlap = "; ".join(
        f"vs {other.value}: {reason}" for other, reason in rubric.must_not_overlap_with.items()
    )
    system_text = (
        f"You are an expert interview-answer grader scoring EXACTLY ONE dimension: "
        f"{rubric.display_name} ({dimension.value}).\n\n"
        f"DEFINITION: {rubric.definition}\n\n"
        f"SCORE 0-4 STRICTLY BY THIS RUBRIC:\n{tier_lines}\n\n"
        f"INCREASE the score for: {increases}\n"
        f"DECREASE the score for: {decreases}\n\n"
        f"KEEP THIS DIMENSION DISTINCT — {non_overlap}\n\n"
        "Judge ONLY this dimension; ignore the others. Return an integer score 0-4 and a short rationale."
    )
    context = build_dimension_input_text(question_text, grounding_text, expected_concepts)
    user_text = f"{context}\n\nANSWER:\n{answer_text}"
    return system_text, user_text


def judge_all_dimensions(
    judge: RubricJudge,
    question_text: str,
    answer_text: str,
    grounding_text: str,
    expected_concepts: tuple[str, ...],
) -> dict[EvaluationDimension, JudgeVerdict]:
    """Judge all four canonical dimensions, each in its own call, so the
    scores stay independent. Returns a verdict per canonical dimension."""
    verdicts: dict[EvaluationDimension, JudgeVerdict] = {}
    for dimension in CANONICAL_DIMENSIONS:
        verdict = judge.judge_dimension(
            dimension, question_text, answer_text, grounding_text, expected_concepts,
        )
        if verdict.dimension != dimension.value:
            raise ValueError(
                f"judge returned dimension {verdict.dimension!r} for requested {dimension.value!r}"
            )
        verdicts[dimension] = verdict
    return verdicts


# ── Target-vs-judge agreement ────────────────────────────────────────────────

class MismatchPolicy(str, Enum):
    """What to do when the judged label disagrees with the generation target
    by more than the tolerance on any dimension. DISCARD (the conservative
    default) drops the example; RELABEL_KEEP keeps it with the judged labels.
    In BOTH cases the final labels come from the judge, never the target —
    the policy only decides whether to KEEP the example at all."""

    DISCARD = "discard"
    RELABEL_KEEP = "relabel_keep"


class DimensionAgreement(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    target_tier: int
    judged_tier: int
    delta: int
    acceptable: bool


class AgreementReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    tolerance: int
    per_dimension: tuple[DimensionAgreement, ...]

    @property
    def all_acceptable(self) -> bool:
        return all(d.acceptable for d in self.per_dimension)

    @property
    def max_delta(self) -> int:
        return max((d.delta for d in self.per_dimension), default=0)


def compute_agreement(
    profile,  # dimension_profiles.DimensionProfile (duck-typed to avoid import cycle risk)
    verdicts: dict[EvaluationDimension, JudgeVerdict],
    tolerance: int = DEFAULT_AGREEMENT_TOLERANCE,
) -> AgreementReport:
    """Per-dimension |judged - target| <= tolerance check. Used only to
    decide KEEP vs DISCARD; the labels themselves always come from
    `verdicts`."""
    rows = []
    for dimension in CANONICAL_DIMENSIONS:
        target = profile.tier_for(dimension)
        judged = verdicts[dimension].score
        delta = abs(judged - target)
        rows.append(DimensionAgreement(
            dimension=dimension.value, target_tier=target, judged_tier=judged,
            delta=delta, acceptable=delta <= tolerance,
        ))
    return AgreementReport(tolerance=tolerance, per_dimension=tuple(rows))


# ═════════════════════════════════════════════════════════════════════════════
# Production LLM judge (temperature 0). Never called in tests.
# ═════════════════════════════════════════════════════════════════════════════

_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is not None:
        return _genai_client
    import os
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set; the rubric judge requires it for labeling.")
    from google import genai
    _genai_client = genai.Client(api_key=api_key)
    return _genai_client


class _JudgeResponse(BaseModel):
    score: int
    rationale: str = ""


class GeminiRubricJudge:
    """Production `RubricJudge` — one Gemini call per dimension, temperature 0
    for determinism, native structured output. Mirrors the lazy-client
    conventions of generation_client.py / rubric labeling is a distinct call
    site from answer generation, so it keeps its own client accessor."""

    def __init__(self, model_name: str = "gemini-2.5-flash", judge_version: str = "gemini-rubric-judge-v1") -> None:
        self.model_name = model_name
        self.judge_version = judge_version

    def judge_dimension(
        self,
        dimension: EvaluationDimension,
        question_text: str,
        answer_text: str,
        grounding_text: str,
        expected_concepts: tuple[str, ...],
    ) -> JudgeVerdict:
        client = _get_genai_client()
        from google.genai import types

        system_text, user_text = build_judge_prompt(
            dimension, question_text, answer_text, grounding_text, expected_concepts,
        )
        response = client.models.generate_content(
            model=self.model_name,
            contents=f"{system_text}\n\n{user_text}",
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
                response_mime_type="application/json",
                response_schema=_JudgeResponse,
            ),
        )
        parsed: Optional[_JudgeResponse] = response.parsed
        if parsed is None:
            raise RuntimeError(f"rubric judge returned no parsed verdict for {dimension.value!r}")
        score = max(0, min(_MAX_TIER, int(parsed.score)))
        return JudgeVerdict(
            dimension=dimension.value, score=score,
            rationale=parsed.rationale.strip(), judge_version=self.judge_version,
        )
