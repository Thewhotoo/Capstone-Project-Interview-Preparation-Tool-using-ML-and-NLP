"""
HybridEvaluator — runs both HeuristicEvaluator and TrainedEvaluator on every
turn. Round 2 (per-dimension agreement-banded decision policy — see
docs/architecture, Hybrid Evaluator design review + round-2 policy update):

- Per DIMENSION, the two evaluators' scores are compared and classified
  into one of three agreement bands:
    HIGH   (agreement >= _HIGH_AGREEMENT_THRESHOLD)   -> DeBERTa trusted;
             the dimension's final score is a LIGHT blend biased toward
             the trained model (not 100% trained -- the heuristic stays a
             small stabilizing anchor even here).
    MEDIUM (>= _MEDIUM_AGREEMENT_THRESHOLD, < HIGH)   -> an even blend of
             both evaluators.
    LOW    (< _MEDIUM_AGREEMENT_THRESHOLD)            -> the heuristic
             becomes fully authoritative for that dimension; DeBERTa is
             logged but does not move the score.
  This lets the trained model genuinely participate wherever it agrees
  with the heuristic, while the heuristic remains the safety mechanism for
  large disagreements -- exactly the requested policy, applied at the
  finest available granularity rather than only on the aggregate score.
- overall_score and grade are RECOMPUTED from the final, per-dimension
  BLENDED scores (using the heuristic's own already-established
  proportional weight_used per dimension -- that weighting scheme itself
  is unchanged), not derived by averaging the two evaluators' own overall
  scores directly.
- confidence combines TWO real, already-available signals: the agreement
  band (how much two independent evaluators concur) and the trained
  model's own analytical self-confidence (`coral_confidence`, already
  computed by TrainedEvaluator -- never approximated, never invented).
  Agreement is the dominant term; model confidence provides a bounded
  secondary adjustment within the band it establishes (see
  _compute_confidence's docstring for the exact formula and worked
  examples).
- strengths, weaknesses, missing_reasoning, suggested_improvements,
  recommended_topics, and concept_coverage remain ENTIRELY
  heuristic-sourced, unchanged -- no new NLP/text generation was added.
  This is a deliberate, documented trade-off: the displayed FEEDBACK TEXT
  may reference a dimension's ORIGINAL heuristic score even though the
  DISPLAYED per-dimension number can now differ slightly after blending.
  Regenerating claims from blended inputs would require new generation
  logic, explicitly out of scope for this round.
- TrainedEvaluator runs on every call where available (never skipped,
  never sampled). Diagnostics (heuristic score, DeBERTa score, final
  hybrid score, agreement band, and final confidence, per dimension and
  overall) are recorded via `raw_model_output` (existing open field) and
  an append-only local JSONL log (`hybrid_diagnostics.jsonl`, gitignored).

Satisfies the SAME, unchanged `evaluator.Evaluator` Protocol every other
implementation does -- no registry change, no call-site change anywhere in
conversation_engine.py or downstream, no change to evaluator_registry.py
or deployment_evaluator.py's wiring.
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from evaluation_request import EvaluationRequest
from evaluation_result import ConfidenceSource, DimensionScore, EvaluationResult
from heuristic_evaluator import HeuristicEvaluator
from model_evaluator import TrainedEvaluator

logger = logging.getLogger(__name__)

# Agreement bands -- per-dimension AND overall use the same thresholds for
# consistency. "Agreement" is 1 - abs(heuristic_raw_score - trained_raw_score);
# both evaluators already report every dimension on the same 0..1 scale, so
# a bounded absolute-difference comparison is a simple, deterministic,
# explainable proxy. This is NOT the same thing as the QWK-based offline/
# promotion metrics from the production-promotion roadmap -- QWK needs a
# labeled POPULATION to mean anything; this is a single live turn.
_HIGH_AGREEMENT_THRESHOLD = 0.85
_MEDIUM_AGREEMENT_THRESHOLD = 0.60

# How much weight the trained model's score gets in each band's blend.
# HIGH is a LIGHT blend biased toward the trained model, not 100% trained
# -- the heuristic stays a small stabilizing anchor even at high agreement,
# so one single-turn measurement never fully displaces the deterministic,
# already-calibrated authoritative scorer. LOW is 0.0: the heuristic is
# fully authoritative when the two evaluators diverge sharply.
_TRAINED_WEIGHT_BY_BAND = {"high": 0.80, "medium": 0.50, "low": 0.0}

_DEFAULT_DIAGNOSTICS_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hybrid_diagnostics.jsonl",
)


def _agreement_band(agreement: float) -> str:
    if agreement >= _HIGH_AGREEMENT_THRESHOLD:
        return "high"
    if agreement >= _MEDIUM_AGREEMENT_THRESHOLD:
        return "medium"
    return "low"


def _blend_dimension(
    heuristic_dim: DimensionScore, trained_dim: Optional[DimensionScore],
) -> tuple[DimensionScore, Optional[str], Optional[float]]:
    """Returns (final_dimension, band, agreement). band/agreement are None
    when no trained score exists for this specific dimension this turn
    (graceful per-dimension degradation to pure heuristic -- the same
    principle as the whole-turn fallback, just at finer granularity)."""
    if trained_dim is None:
        return heuristic_dim, None, None

    agreement = max(0.0, min(1.0, 1.0 - abs(heuristic_dim.raw_score - trained_dim.raw_score)))
    band = _agreement_band(agreement)
    trained_weight = _TRAINED_WEIGHT_BY_BAND[band]

    if trained_weight == 0.0:
        return heuristic_dim, band, agreement

    blended_score = round(
        trained_weight * trained_dim.raw_score + (1.0 - trained_weight) * heuristic_dim.raw_score, 3,
    )
    final_dim = heuristic_dim.model_copy(update={
        "raw_score": blended_score,
        "confidence_source": f"hybrid_{band}_agreement",
    })
    return final_dim, band, agreement


def _recompute_overall(dimensions: tuple[DimensionScore, ...]) -> float:
    """Recomputes overall_score from the FINAL (post-blend) per-dimension
    scores, reusing each dimension's own already-established weight_used
    (the heuristic's proportional always-relevant-vs-extra weighting is
    unchanged) -- never averaging the two evaluators' own overall_score
    values directly."""
    contributing = [d for d in dimensions if d.contributes_to_overall]
    if not contributing:
        return 0.0
    weight_sum = sum(d.weight_used for d in contributing)
    if weight_sum <= 0:
        return 0.0
    total = sum(d.raw_score * d.weight_used for d in contributing)
    return round(max(0.0, min(1.0, total / weight_sum)), 3)


# Confidence: agreement is the DOMINANT term (a band ceiling), model
# confidence is a bounded SECONDARY adjustment within that ceiling -- a
# model being confident while disagreeing with an independent measure is
# not, by itself, a reason for extra trust; agreement between two
# independent sources is stronger evidence than either source's own
# self-assessment. _MODEL_CONFIDENCE_INFLUENCE bounds how much the model's
# own confidence can move the multiplier: at model_confidence=0 the factor
# is (1 - influence); at model_confidence=1 the factor is 1.0.
_BAND_CONFIDENCE_MULTIPLIER = {"high": 1.0, "medium": 0.80, "low": 0.55}
_MODEL_CONFIDENCE_INFLUENCE = 0.30


def _confidence_tier_label(adjusted_multiplier: float) -> str:
    if adjusted_multiplier >= 0.90:
        return "very high"
    if adjusted_multiplier >= 0.70:
        return "high"
    if adjusted_multiplier >= 0.45:
        return "moderate"
    return "low"


def _compute_confidence(heuristic_confidence: float, band: str, model_confidence: float) -> tuple[float, float, str]:
    """Combines agreement (via `band`) and the trained model's own
    analytical confidence (`coral_confidence`, from model_heads.py --
    genuinely computed, never approximated) into a final confidence value.
    Returns (final_confidence, adjusted_multiplier, tier_label).

    Worked examples (matching the requested design):
      high agreement + high model confidence   -> multiplier ~0.97-1.00 ("very high")
      high agreement + low model confidence    -> multiplier ~0.76        ("high")
      medium agreement + high model confidence -> multiplier ~0.78        ("high")
      low agreement + low model confidence     -> multiplier ~0.42        ("low")
      low agreement + high model confidence    -> multiplier ~0.53        ("moderate" at best --
        a confident-but-disagreeing model is still not fully trusted)."""
    band_multiplier = _BAND_CONFIDENCE_MULTIPLIER[band]
    model_factor = (1.0 - _MODEL_CONFIDENCE_INFLUENCE) + _MODEL_CONFIDENCE_INFLUENCE * model_confidence
    adjusted_multiplier = max(0.0, min(1.0, band_multiplier * model_factor))
    final_confidence = round(max(0.0, min(1.0, heuristic_confidence * adjusted_multiplier)), 3)
    return final_confidence, adjusted_multiplier, _confidence_tier_label(adjusted_multiplier)


def _record_diagnostics(
    log_path: str, request: EvaluationRequest, heuristic_result: EvaluationResult,
    trained_result: Optional[EvaluationResult], final_overall_score: float,
    overall_agreement: Optional[float], overall_band: Optional[str], final_confidence: float,
    per_dimension: dict[str, dict], trained_error: Optional[str],
) -> None:
    """Appends one JSON line per turn -- heuristic score, DeBERTa score,
    final hybrid score, agreement band, and evaluator confidence
    (requirement 9), plus full per-dimension detail for future retraining.
    Never allowed to affect the live evaluation -- any failure here is
    logged and swallowed, the same discipline deployment_evaluator.py
    already applies to model loading."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request.request_id,
        "reasoning_type": request.reasoning_type.value,
        "heuristic_overall_score": heuristic_result.overall_score,
        "trained_overall_score": trained_result.overall_score if trained_result is not None else None,
        "final_hybrid_overall_score": final_overall_score,
        "overall_agreement": overall_agreement,
        "overall_agreement_band": overall_band,
        "final_confidence": final_confidence,
        "trained_available": trained_result is not None,
        "trained_error": trained_error,
        "per_dimension": per_dimension,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # pragma: no cover - environment-dependent (disk/permissions)
        logger.warning("HybridEvaluator: could not write diagnostics log to %r: %s", log_path, e)


class HybridEvaluator:
    """Evaluator Protocol implementation. Wraps a HeuristicEvaluator
    (authoritative for all feedback text; the safety mechanism for
    per-dimension low agreement) and a TrainedEvaluator (runs every call;
    genuinely participates in scoring wherever it agrees with the
    heuristic, via per-dimension agreement-banded blending).

    Stateless per call, same contract as both wrapped evaluators."""

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
        # HeuristicEvaluator is authoritative for feedback text and is the
        # safety mechanism for disagreement; a failure here is a genuine
        # bug, not something this module papers over.
        heuristic_result = self.heuristic.evaluate(request)

        # TrainedEvaluator MUST run whenever available -- but a runtime
        # failure on THIS specific request degrades gracefully to
        # heuristic-only for this turn, not a session crash.
        trained_result: Optional[EvaluationResult] = None
        trained_error: Optional[str] = None
        try:
            trained_result = self.trained.evaluate(request)
        except Exception as e:  # noqa: BLE001 -- deliberately broad, see docstring above
            trained_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "HybridEvaluator: TrainedEvaluator failed for request_id=%r (%s) -- "
                "falling back to heuristic-only scoring for this turn.",
                request.request_id, trained_error,
            )

        if trained_result is None:
            final_dimensions = heuristic_result.dimensions
            final_overall_score = heuristic_result.overall_score
            final_grade = heuristic_result.grade
            final_confidence = heuristic_result.confidence
            confidence_source = heuristic_result.confidence_source
            confidence_rationale = (
                f"{heuristic_result.confidence_rationale} (No trained-model comparison was available "
                f"for this turn.)"
            )
            reasoning = heuristic_result.reasoning
            raw_model_output = heuristic_result.raw_model_output
            model_version = heuristic_result.model_version
            overall_agreement: Optional[float] = None
            overall_band: Optional[str] = None
            per_dimension_diag: dict[str, dict] = {}
        else:
            trained_by_name = {d.name: d for d in trained_result.dimensions}
            final_dimensions_list: list[DimensionScore] = []
            per_dimension_diag = {}
            agreements: list[float] = []

            for h_dim in heuristic_result.dimensions:
                t_dim = trained_by_name.get(h_dim.name)
                final_dim, band, agreement = _blend_dimension(h_dim, t_dim)
                final_dimensions_list.append(final_dim)
                per_dimension_diag[h_dim.name] = {
                    "heuristic": h_dim.raw_score,
                    "trained": t_dim.raw_score if t_dim is not None else None,
                    "final": final_dim.raw_score,
                    "band": band,
                    "agreement": agreement,
                }
                if agreement is not None:
                    agreements.append(agreement)

            final_dimensions = tuple(final_dimensions_list)
            final_overall_score = _recompute_overall(final_dimensions)
            final_grade = HeuristicEvaluator._grade(final_overall_score)
            reasoning = "\n".join(f"{d.name}: {d.raw_score:.0%}" for d in final_dimensions)

            overall_agreement = round(sum(agreements) / len(agreements), 3) if agreements else None
            overall_band = _agreement_band(overall_agreement) if overall_agreement is not None else None

            model_confidence = trained_result.confidence
            if overall_band is not None:
                final_confidence, adjusted_multiplier, tier_label = _compute_confidence(
                    heuristic_result.confidence, overall_band, model_confidence,
                )
                # Always HYBRID when a trained comparison was available --
                # even a "high agreement" result had its confidence
                # genuinely derived from both signals (band + model
                # confidence), not just copied from the heuristic.
                confidence_source = ConfidenceSource.HYBRID
                confidence_rationale = (
                    f"{heuristic_result.confidence_rationale} An independent trained-model comparison showed "
                    f"{overall_agreement:.0%} agreement ({overall_band} band) with model confidence "
                    f"{model_confidence:.0%}, yielding {tier_label} combined confidence."
                )
            else:
                final_confidence = heuristic_result.confidence
                confidence_source = heuristic_result.confidence_source
                confidence_rationale = heuristic_result.confidence_rationale

            raw_model_output = heuristic_result.raw_model_output + tuple(
                (f"trained_{d.name}", d.raw_score) for d in trained_result.dimensions
            ) + tuple(
                (f"final_{name}", diag["final"]) for name, diag in per_dimension_diag.items()
            ) + (("agreement_score", overall_agreement if overall_agreement is not None else 0.0),)
            model_version = heuristic_result.model_version + trained_result.model_version

        _record_diagnostics(
            self.diagnostics_log_path, request, heuristic_result, trained_result, final_overall_score,
            overall_agreement, overall_band, final_confidence, per_dimension_diag, trained_error,
        )

        return heuristic_result.model_copy(update={
            "result_id": f"eval_{_uuid.uuid4().hex[:12]}",
            "evaluator_name": self.name,
            "evaluator_version": self.version,
            "dimensions": final_dimensions,
            "overall_score": final_overall_score,
            "grade": final_grade,
            "confidence": final_confidence,
            "confidence_source": confidence_source,
            "confidence_rationale": confidence_rationale,
            "reasoning": reasoning,
            "raw_model_output": raw_model_output,
            "model_version": model_version,
        })
