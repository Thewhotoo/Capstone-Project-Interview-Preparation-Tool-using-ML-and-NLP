"""
AnswerKey — the authored, per-question knowledge the reference-anchored
evaluator (`correctness_nli_scorer.CoverageNLIScorer`) grades against.

Deliberately a NEUTRAL, dependency-light type in its own module so BOTH the
Conversation/Evaluation boundary (`evaluation_request.EvaluationRequest`, which
carries it) and the evaluator (`correctness_nli_scorer`, which consumes it) can
import it with no import cycle and with no coupling of the request schema to the
evaluator implementation.

An AnswerKey is knowable BEFORE the candidate answers — it is a property of the
question/grounding, not of the answer — exactly like `expected_concepts`. It is
therefore looked up deterministically at request-assembly time
(`answer_key_registry`), never generated at answer time, never model-derived,
never invented (same discipline as `expected_concepts_registry`).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnswerKey(BaseModel):
    """Authored knowledge for one question: atomic correct claims, atomic
    known-wrong claims, and an optional human reference answer. All fields are
    plain text authored offline. Frozen and hashable-shaped (tuples, not lists)
    so it is safe to carry on the immutable `EvaluationRequest`."""

    model_config = ConfigDict(frozen=True)

    key_points: tuple[str, ...] = ()
    misconceptions: tuple[str, ...] = ()
    reference_answer: Optional[str] = None

    @property
    def has_key_points(self) -> bool:
        return any(p and p.strip() for p in self.key_points)

    @property
    def is_empty(self) -> bool:
        return not self.has_key_points and not any(m and m.strip() for m in self.misconceptions)
