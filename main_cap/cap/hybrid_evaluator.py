"""
HybridEvaluator — runs both HeuristicEvaluator and TrainedEvaluator on every
turn, but never blends or averages their scores. Chosen and scoped
deliberately (see docs/architecture -- Hybrid Evaluator design review):

- HeuristicEvaluator remains the ONLY source of every candidate-facing
  field: overall_score, grade, every DimensionScore.raw_score, strengths,
  weaknesses, missing_reasoning, suggested_improvements, recommended_topics,
  concept_coverage, contradiction_detected/explanation. This module never
  overrides any of them.
- TrainedEvaluator runs on every call where a trained model is available
  (never skipped, never sampled) but its output influences exactly ONE
  candidate-facing field: the reported `confidence` (and its rationale) --
  lowered, never raised, when the two evaluators disagree. This is
  "Design B" from the Hybrid Evaluator design review: confidence-modulated,
  not score-blended.
- TrainedEvaluator's raw per-dimension output and the computed agreement
  score are recorded for diagnostics/future retraining (requirement 5) via
  `raw_model_output` (in the returned EvaluationResult, already an
  open/free-form field -- no schema change) and an append-only local JSONL
  log (`hybrid_diagnostics.jsonl`, gitignored) -- deliberately NOT a new
  database/storage subsystem, per "do not redesign the architecture."

Satisfies the SAME, unchanged `evaluator.Evaluator` Protocol every other
implementation does (evaluator.py's own docstring names "HybridEvaluator"
as one of the interchangeable implementations the Protocol was designed
for) -- no registry change, no call-site change anywhere in
conversation_engine.py or downstream.
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from evaluation_request import EvaluationRequest
from evaluation_result import ConfidenceSource, EvaluationResult
from heuristic_evaluator import HeuristicEvaluator
from model_evaluator import TrainedEvaluator

logger = logging.getLogger(__name__)

# Per-turn agreement is a simple, deterministic, explainable proxy -- NOT
# the same thing as the QWK-based offline/promotion metrics from the
# production-promotion roadmap. QWK needs a POPULATION of human-labeled
# examples to mean anything; this is a single live turn, so a bounded
# absolute-difference comparison (both evaluators already report every
# dimension on the same 0..1 scale) is the right-sized signal here, not a
# statistical correlation measure.
_HIGH_AGREEMENT_THRESHOLD = 0.80

# Confidence is dampened, not zeroed, by disagreement: at perfect agreement
# (1.0) the multiplier is 1.0 (heuristic's own confidence, unchanged); at
# total disagreement (0.0) the multiplier is 0.5, not 0.0 -- one noisy
# single-turn comparison against an undertrained checkpoint (documented
# elsewhere as trained on synthetic data only) should not be allowed to
# collapse confidence to nothing on its own.
_MIN_CONFIDENCE_MULTIPLIER = 0.5

_DEFAULT_DIAGNOSTICS_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hybrid_diagnostics.jsonl",
)


def _dimension_agreement(heuristic_result: EvaluationResult, trained_result: EvaluationResult) -> tuple[float, dict[str, float]]:
    """Returns (agreement_score, per_dimension_abs_diff). Agreement is
    1 - mean absolute difference across dimensions BOTH evaluators
    produced for this turn (they consult the same reasoning_type ->
    dimension mapping, so in practice this is normally every dimension
    either produced -- but only the intersection is ever compared,
    defensively, in case a future evaluator implementation diverges)."""
    trained_by_name = {d.name: d for d in trained_result.dimensions}
    diffs: dict[str, float] = {}
    for d in heuristic_result.dimensions:
        match = trained_by_name.get(d.name)
        if match is not None:
            diffs[d.name] = abs(d.raw_score - match.raw_score)
    if not diffs:
        return 1.0, {}
    mean_diff = sum(diffs.values()) / len(diffs)
    agreement = max(0.0, min(1.0, 1.0 - mean_diff))
    return agreement, diffs


def _record_diagnostics(
    log_path: str, request: EvaluationRequest, heuristic_result: EvaluationResult,
    trained_result: Optional[EvaluationResult], agreement_score: Optional[float],
    dimension_diffs: dict[str, float], trained_error: Optional[str],
) -> None:
    """Appends one JSON line with both evaluators' raw output for this
    turn. Never allowed to affect the live evaluation -- any failure here
    (disk full, unwritable path, etc.) is logged and swallowed, exactly
    the same "never crash because of a diagnostic/logging concern"
    discipline deployment_evaluator.py already applies to model loading."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request.request_id,
        "reasoning_type": request.reasoning_type.value,
        "heuristic_overall_score": heuristic_result.overall_score,
        "heuristic_dimensions": {d.name: d.raw_score for d in heuristic_result.dimensions},
        "trained_available": trained_result is not None,
        "trained_overall_score": trained_result.overall_score if trained_result is not None else None,
        "trained_dimensions": (
            {d.name: d.raw_score for d in trained_result.dimensions} if trained_result is not None else None
        ),
        "trained_error": trained_error,
        "agreement_score": agreement_score,
        "dimension_diffs": dimension_diffs,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # pragma: no cover - environment-dependent (disk/permissions)
        logger.warning("HybridEvaluator: could not write diagnostics log to %r: %s", log_path, e)


class HybridEvaluator:
    """Evaluator Protocol implementation. Wraps a HeuristicEvaluator
    (authoritative for every candidate-facing field) and a TrainedEvaluator
    (runs every call, influences only reported confidence + diagnostics).

    Stateless per call, same contract as both wrapped evaluators: a fresh
    HeuristicEvaluator/TrainedEvaluator call each time, no session state
    held here."""

    name = "hybrid-v1"
    version = "1.0.0"

    def __init__(
        self, heuristic: HeuristicEvaluator, trained: TrainedEvaluator,
        diagnostics_log_path: str = _DEFAULT_DIAGNOSTICS_LOG_PATH,
    ) -> None:
        self.heuristic = heuristic
        self.trained = trained
        self.diagnostics_log_path = diagnostics_log_path
        self.declared_dimensions = heuristic.declared_dimensions
        self.declared_reasoning_types = heuristic.declared_reasoning_types
        self.requires_network = heuristic.requires_network or trained.requires_network

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        # HeuristicEvaluator is authoritative and always runs; a failure
        # here is a genuine bug, not something this module papers over --
        # same as every other Evaluator implementation, nothing protects
        # against the primary scorer itself failing.
        heuristic_result = self.heuristic.evaluate(request)

        # TrainedEvaluator MUST run whenever available (requirement 1) --
        # but a runtime failure on THIS specific request (a malformed
        # input, a transient resource issue) must degrade gracefully to
        # heuristic-only for this turn, not crash the session. This is
        # distinct from deployment_evaluator.py's startup-time fallback:
        # that decides whether a HybridEvaluator exists AT ALL; this
        # protects one call of an already-constructed one.
        trained_result: Optional[EvaluationResult] = None
        trained_error: Optional[str] = None
        try:
            trained_result = self.trained.evaluate(request)
        except Exception as e:  # noqa: BLE001 -- deliberately broad, see docstring above
            trained_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "HybridEvaluator: TrainedEvaluator failed for request_id=%r (%s) -- "
                "falling back to heuristic-only confidence for this turn.",
                request.request_id, trained_error,
            )

        agreement_score: Optional[float] = None
        dimension_diffs: dict[str, float] = {}
        confidence = heuristic_result.confidence
        confidence_source = heuristic_result.confidence_source
        confidence_rationale = heuristic_result.confidence_rationale
        raw_model_output = heuristic_result.raw_model_output
        model_version = heuristic_result.model_version

        if trained_result is not None:
            agreement_score, dimension_diffs = _dimension_agreement(heuristic_result, trained_result)

            if agreement_score < _HIGH_AGREEMENT_THRESHOLD:
                multiplier = _MIN_CONFIDENCE_MULTIPLIER + (1.0 - _MIN_CONFIDENCE_MULTIPLIER) * agreement_score
                confidence = round(heuristic_result.confidence * multiplier, 3)
                confidence_source = ConfidenceSource.HYBRID
                confidence_rationale = (
                    f"{heuristic_result.confidence_rationale} An independent trained-model comparison "
                    f"showed only {agreement_score:.0%} agreement on this turn, so confidence has been "
                    f"reduced accordingly."
                )
            else:
                confidence_rationale = (
                    f"{heuristic_result.confidence_rationale} Confirmed by {agreement_score:.0%} agreement "
                    f"with an independent trained-model comparison."
                )

            # Built from trained_result.dimensions, NOT trained_result.
            # raw_model_output -- TrainedEvaluator doesn't populate that
            # field itself (EvaluationResult defaults it to an empty
            # tuple), so sourcing from raw_model_output would silently
            # produce nothing. dimensions is always populated.
            raw_model_output = heuristic_result.raw_model_output + tuple(
                (f"trained_{d.name}", d.raw_score) for d in trained_result.dimensions
            ) + (("agreement_score", round(agreement_score, 3)),)
            model_version = heuristic_result.model_version + trained_result.model_version
        else:
            confidence_rationale = (
                f"{heuristic_result.confidence_rationale} (No trained-model comparison was available "
                f"for this turn.)"
            )

        _record_diagnostics(
            self.diagnostics_log_path, request, heuristic_result, trained_result,
            agreement_score, dimension_diffs, trained_error,
        )

        return heuristic_result.model_copy(update={
            "result_id": f"eval_{_uuid.uuid4().hex[:12]}",
            "evaluator_name": self.name,
            "evaluator_version": self.version,
            "confidence": confidence,
            "confidence_source": confidence_source,
            "confidence_rationale": confidence_rationale,
            "raw_model_output": raw_model_output,
            "model_version": model_version,
        })
