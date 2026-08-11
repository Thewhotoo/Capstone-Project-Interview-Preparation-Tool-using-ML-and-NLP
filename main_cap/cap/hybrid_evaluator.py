"""
HybridEvaluator — Round 3 (DeBERTa-primary policy; supersedes Round 2's
per-dimension agreement-banded BLENDING — see docs/architecture and the
Experiment 4 head-to-head evaluation that motivated this change).

WHY ROUND 2 WAS REPLACED: the Experiment 4 evaluation
(`run_experiment_4_evaluate.py`, `artifacts/experiment_4_evaluation/report.json`)
measured, on the same 362-example held-out test set:
    raw new DeBERTa   QWK = 0.3976
    HeuristicEvaluator QWK = 0.1341
    Round-2 Hybrid     QWK = 0.1814   <- worse than raw DeBERTa by >2x
Round 2's LOW-agreement band made the (much weaker) heuristic FULLY
authoritative for any dimension where the two evaluators disagreed by more
than ~0.40 raw-score points. Because the heuristic is frequently the one
that's wrong (its own QWK is 3x lower than the trained model's), that
"safety" mechanism was routinely overriding a more-accurate DeBERTa
prediction with a less-accurate heuristic one -- the opposite of what a
disagreement-handling policy should do once a trained evaluator has been
shown to be more accurate than the heuristic it was being blended against.

ROUND 3 POLICY (this module, current):
- HeuristicEvaluator still runs on every turn -- required for the fallback
  path, for feedback text, and to compute the SAME agreement/band signal
  as before, now used PURELY for confidence/observability.
- TrainedEvaluator (DeBERTa) still runs on every turn.
- If TrainedEvaluator SUCCEEDS (returns a valid EvaluationResult -- the
  schema's own pydantic validators already reject a malformed one, so
  "returned without raising" already means "valid"): its `dimensions`,
  `overall_score`, `grade`, and `reasoning` are used EXACTLY AS PRODUCED —
  never blended, never overridden, regardless of how much they disagree
  with the heuristic. Disagreement no longer downgrades a valid DeBERTa
  prediction.
- If TrainedEvaluator FAILS (raises): unchanged graceful degradation to a
  pure HeuristicEvaluator result for that turn, exactly as Round 2 did.
- Agreement (heuristic vs. trained, per dimension and overall) is still
  computed and still feeds `confidence` (reusing the SAME, unmodified
  `_agreement_band` / `_compute_confidence` formulas Round 2 already
  established -- no new thresholds, no new confidence model) and the
  diagnostics log -- it is observability/confidence-only now, never a
  score override.
- missing_reasoning, suggested_improvements, recommended_topics remain
  ENTIRELY heuristic-sourced, unchanged from Round 2 -- no new NLP/text
  generation.
- concept_coverage (Concept Evidence Layer follow-up, after Round 3): base
  is still heuristic-sourced, but each concept's status is now reconciled
  DOWNGRADE-ONLY against TrainedEvaluator's own per-concept read (already
  computed above, previously discarded) when DeBERTa succeeded this turn --
  see `_reconcile_concept_coverage`. The heuristic's lexical detector
  unconditionally scores an exact-phrase-in-a-long-enough-sentence hit as
  DEMONSTRATED regardless of what the sentence actually says ("mentioned
  briefly" and "demonstrated with concrete detail" score identically); the
  trained concept head reads that qualifying language and can only ever
  pull an over-credited verdict down, never invent credit the heuristic
  found no lexical evidence for at all (a probe against genuinely novel
  phrasing found the trained head does not yet reliably generalize to
  crediting true zero-keyword-overlap paraphrase, so upgrading was
  deliberately not attempted).
- strengths/weaknesses text is heuristic-sourced but RECLASSIFIED against
  the final dimension scores above (`_reclassify_claims`) -- a fix added
  after a real end-to-end demo caught a dimension displayed at 25% labelled
  "Strong" because the heuristic's own pre-blend score for that dimension
  disagreed with DeBERTa's. Same claim text (still accurate content-wise),
  re-bucketed by the score actually shown to the user.

Satisfies the SAME, unchanged `evaluator.Evaluator` Protocol every other
implementation does -- no registry change, no call-site change anywhere in
conversation_engine.py or downstream, no change to evaluator_registry.py
or deployment_evaluator.py's wiring. The class name, `.name` ("hybrid-v1"),
and constructor signature are all unchanged from Round 2 -- every existing
caller that resolves "hybrid-v1" from the registry keeps working exactly
as before; only what happens INSIDE `.evaluate()` changed.
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from evaluation_request import EvaluationRequest
from evaluation_result import (
    ConceptObservation, ConceptObservationStatus, ConfidenceSource, DimensionScore, EvaluationResult,
    EvidenceLinkedClaim,
)
from heuristic_evaluator import STRENGTH_THRESHOLD, WEAKNESS_THRESHOLD, HeuristicEvaluator
from model_evaluator import TrainedEvaluator

logger = logging.getLogger(__name__)

# Agreement bands -- UNCHANGED from Round 2 (same thresholds, same
# "agreement = 1 - abs(heuristic_raw_score - trained_raw_score)" proxy).
# No longer used to decide WHICH score wins (DeBERTa always wins when
# available) -- only to inform `confidence` and the diagnostics log, i.e.
# still exactly the "confidence/disagreement detection" the production
# wiring is still meant to provide.
_HIGH_AGREEMENT_THRESHOLD = 0.85
_MEDIUM_AGREEMENT_THRESHOLD = 0.60

_DEFAULT_DIAGNOSTICS_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hybrid_diagnostics.jsonl",
)


def _agreement_band(agreement: float) -> str:
    if agreement >= _HIGH_AGREEMENT_THRESHOLD:
        return "high"
    if agreement >= _MEDIUM_AGREEMENT_THRESHOLD:
        return "medium"
    return "low"


def _dimension_agreement(heuristic_dim: DimensionScore, trained_dim: Optional[DimensionScore]) -> Optional[float]:
    """Same agreement proxy Round 2 used, kept for confidence/diagnostics
    only -- no longer produces a blended score (Round 2's `_blend_dimension`
    is retired; DeBERTa's own dimension score is used unmodified when
    available, see module docstring)."""
    if trained_dim is None:
        return None
    return max(0.0, min(1.0, 1.0 - abs(heuristic_dim.raw_score - trained_dim.raw_score)))


# Confidence: agreement is the DOMINANT term (a band ceiling), model
# confidence is a bounded SECONDARY adjustment within that ceiling -- a
# model being confident while disagreeing with an independent measure is
# not, by itself, a reason for extra trust; agreement between two
# independent sources is stronger evidence than either source's own
# self-assessment. UNCHANGED from Round 2 -- this formula was never the
# problem (the blending of the SCORE was); it still legitimately informs
# how much to trust a valid DeBERTa prediction, it just no longer decides
# whether to use that prediction.
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
    """Unchanged from Round 2 (see that docstring's worked examples) --
    combines agreement (via `band`) and the trained model's own analytical
    confidence into a final confidence value. Returns
    (final_confidence, adjusted_multiplier, tier_label)."""
    band_multiplier = _BAND_CONFIDENCE_MULTIPLIER[band]
    model_factor = (1.0 - _MODEL_CONFIDENCE_INFLUENCE) + _MODEL_CONFIDENCE_INFLUENCE * model_confidence
    adjusted_multiplier = max(0.0, min(1.0, band_multiplier * model_factor))
    final_confidence = round(max(0.0, min(1.0, heuristic_confidence * adjusted_multiplier)), 3)
    return final_confidence, adjusted_multiplier, _confidence_tier_label(adjusted_multiplier)


def _record_diagnostics(
    log_path: str, request: EvaluationRequest, heuristic_result: EvaluationResult,
    trained_result: Optional[EvaluationResult], final_overall_score: float,
    overall_agreement: Optional[float], overall_band: Optional[str], final_confidence: float,
    per_dimension: dict[str, dict], trained_error: Optional[str], score_source: str,
) -> None:
    """Appends one JSON line per turn -- heuristic score, DeBERTa score,
    final (Round 3: score_source tells you which one won -- always
    "trained" unless DeBERTa failed this turn), agreement band, and
    evaluator confidence, plus full per-dimension detail for future
    calibration work. Never allowed to affect the live evaluation -- any
    failure here is logged and swallowed, same discipline as before."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request.request_id,
        "reasoning_type": request.reasoning_type.value,
        "heuristic_overall_score": heuristic_result.overall_score,
        "trained_overall_score": trained_result.overall_score if trained_result is not None else None,
        "final_hybrid_overall_score": final_overall_score,
        "score_source": score_source,
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


def _reclassify_claims(
    final_dimensions: tuple[DimensionScore, ...],
    heuristic_strengths: tuple[EvidenceLinkedClaim, ...],
    heuristic_weaknesses: tuple[EvidenceLinkedClaim, ...],
) -> tuple[tuple[EvidenceLinkedClaim, ...], tuple[EvidenceLinkedClaim, ...]]:
    """Rebuilds strengths/weaknesses against the FINAL dimension scores
    (Round 3: DeBERTa's, when available -- the numbers actually shown to
    the user), never the heuristic's own pre-blend view of that dimension.

    Confirmed production bug (real end-to-end demo): `_claims()` classifies
    a dimension as a strength/weakness using the HEURISTIC evaluator's OWN
    `raw_score` for that dimension, computed BEFORE Round 3 potentially
    replaces the whole `dimensions` tuple with DeBERTa's. Carrying those
    claims over unchanged (the prior "heuristic-sourced, unchanged" policy)
    let a dimension DISPLAYED at 25% get labelled "Strong" purely because
    the heuristic's own (unseen, unpublished) score for that same dimension
    happened to be high -- a direct contradiction between the text and the
    number sitting right next to it.

    Uses the exact same `STRENGTH_THRESHOLD`/`WEAKNESS_THRESHOLD` cutpoints
    `HeuristicEvaluator._claims` uses (imported, not re-chosen -- the one
    shared classification rule) so a given raw_score always gets the same
    label regardless of which evaluator produced it. Evidence text is
    reused from the heuristic's ORIGINAL claim for that dimension in the
    SAME bucket only (a strength's evidence for a new strength, a
    weakness's for a new weakness -- `_concrete_evidence` deliberately
    phrases the two differently, e.g. a plain quote for a strength vs.
    "... — not closely aligned..." for a weakness, so citing the wrong
    bucket's text would itself read as self-contradictory) when one
    exists, falling back to a plain "Scored X% on Y" line built from the
    FINAL score otherwise -- never inventing new evaluative text, only
    re-deriving which bucket (strength/weakness/neither) each real score
    belongs in."""
    strength_evidence = {c.dimension: c.evidence for c in heuristic_strengths}
    weakness_evidence = {c.dimension: c.evidence for c in heuristic_weaknesses}

    strengths: list[EvidenceLinkedClaim] = []
    weaknesses: list[EvidenceLinkedClaim] = []
    for d in final_dimensions:
        if d.raw_score >= STRENGTH_THRESHOLD:
            evidence = strength_evidence.get(d.name)
            strengths.append(EvidenceLinkedClaim(
                claim=f"Strong {d.name.replace('_', ' ')}.",
                dimension=d.name,
                evidence=evidence or f"Scored {d.raw_score:.0%} on {d.name.replace('_', ' ')}.",
            ))
        elif d.raw_score < WEAKNESS_THRESHOLD:
            evidence = weakness_evidence.get(d.name)
            weaknesses.append(EvidenceLinkedClaim(
                claim=f"Weak {d.name.replace('_', ' ')}.",
                dimension=d.name,
                evidence=evidence or f"Scored only {d.raw_score:.0%} on {d.name.replace('_', ' ')}.",
            ))

    if not strengths:
        strengths.append(EvidenceLinkedClaim(
            claim="Attempted to address the question.",
            dimension=final_dimensions[0].name,
            evidence=f"Scored {final_dimensions[0].raw_score:.0%} on {final_dimensions[0].name}.",
        ))
    if not weaknesses:
        weaknesses.append(EvidenceLinkedClaim(
            claim="Minor areas for deeper elaboration.",
            dimension=final_dimensions[-1].name,
            evidence=f"Scored {final_dimensions[-1].raw_score:.0%} on {final_dimensions[-1].name}.",
        ))
    return tuple(strengths), tuple(weaknesses)


# Concept evidence reconciliation (Round 3 follow-up: Concept Evidence
# Layer). WHY: HeuristicEvaluator's `_concept_status` is lexical -- an exact
# phrase (or bare token-overlap) hit inside a long-enough sentence is
# unconditionally DEMONSTRATED, blind to what the surrounding words
# actually SAY (a battery of held-out concept-labeled test examples found
# this conflates "X was mentioned briefly" with "X was demonstrated with
# concrete functional detail" every time -- 216/702 genuinely-superficial
# concepts scored as DEMONSTRATED). TrainedEvaluator's concept head is a
# real, already-trained, already-deployed (jointly trained with the promoted
# dimension heads, ALREADY invoked by HybridEvaluator on every turn --
# nothing new to compute) cross-encoder pass over (answer, concept) that
# reads the qualifying language a lexical scan cannot.
#
# WHY DOWNGRADE-ONLY (never upgrade): a manual probe against genuinely
# novel, non-templated phrasing (not the synthetic training distribution)
# found the trained concept head does NOT reliably generalize to crediting
# real paraphrase with zero lexical overlap -- it call a hand-written,
# clearly-demonstrating answer using none of the concept's own words
# OMITTED, same as the heuristic. Letting a model invent DEMONSTRATED/
# SUPERFICIAL credit the heuristic found no lexical evidence for at all
# would violate ConceptObservation's own "never invented" evidence
# discipline on exactly the cases where it's least trustworthy. Only ever
# pulling a lexically-over-credited verdict DOWN to the trained model's more
# conservative read is the smallest change that is monotonically safer than
# the status quo on every case checked (never produces a HIGHER coverage
# number than the pure heuristic would have) while still catching the
# concrete, confirmed over-crediting failure mode above.
_CONCEPT_STATUS_CREDIT = {
    ConceptObservationStatus.DEMONSTRATED: 2,
    ConceptObservationStatus.SUPERFICIAL: 1,
    ConceptObservationStatus.OMITTED: 0,
}


def _reconcile_concept_coverage(
    heuristic_coverage: tuple[ConceptObservation, ...],
    trained_coverage: tuple[ConceptObservation, ...],
) -> tuple[ConceptObservation, ...]:
    """Per-concept minimum of the heuristic's (lexical) and the trained
    model's (semantic) status, matched by concept name, order-preserving
    from `heuristic_coverage` (the same order downstream consumers --
    concept_analysis.py, the dashboard -- already expect). A concept the
    trained model didn't independently score (e.g. `trained_coverage` empty
    because DeBERTa failed this turn, or, defensively, name mismatch) keeps
    its heuristic verdict unchanged -- this function can only ever lower a
    turn's concept coverage, never raise it, and never touches a concept
    pair it can't compare."""
    trained_by_concept = {c.concept.strip().lower(): c for c in trained_coverage}
    reconciled: list[ConceptObservation] = []
    for h_obs in heuristic_coverage:
        t_obs = trained_by_concept.get(h_obs.concept.strip().lower())
        if t_obs is not None and _CONCEPT_STATUS_CREDIT[t_obs.status] < _CONCEPT_STATUS_CREDIT[h_obs.status]:
            reconciled.append(t_obs)
        else:
            reconciled.append(h_obs)
    return tuple(reconciled)


class HybridEvaluator:
    """Evaluator Protocol implementation. Wraps a HeuristicEvaluator
    (feedback text, fallback, and the confidence/disagreement signal) and a
    TrainedEvaluator (the authoritative scorer whenever it succeeds --
    Round 3 policy, see module docstring).

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
        # fallback when DeBERTa fails; a failure here is a genuine bug, not
        # something this module papers over.
        heuristic_result = self.heuristic.evaluate(request)

        # TrainedEvaluator MUST run whenever available -- a runtime failure
        # on THIS specific request degrades gracefully to heuristic-only
        # for this turn, not a session crash.
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
            # ── Fallback path: DeBERTa unavailable this turn ──
            score_source = "heuristic_fallback"
            final_dimensions = heuristic_result.dimensions
            final_overall_score = heuristic_result.overall_score
            final_grade = heuristic_result.grade
            final_confidence = heuristic_result.confidence
            confidence_source = heuristic_result.confidence_source
            confidence_rationale = (
                f"{heuristic_result.confidence_rationale} (No trained-model comparison was available "
                f"for this turn -- DeBERTa failed or was unavailable, so the heuristic result is used "
                f"as-is.)"
            )
            reasoning = heuristic_result.reasoning
            raw_model_output = heuristic_result.raw_model_output
            model_version = heuristic_result.model_version
            overall_agreement: Optional[float] = None
            overall_band: Optional[str] = None
            per_dimension_diag: dict[str, dict] = {}
        else:
            # ── Primary path: DeBERTa succeeded -- its dimensions/overall
            # score/grade/reasoning are used EXACTLY AS PRODUCED, never
            # blended or overridden by the heuristic, regardless of
            # agreement (Round 3 policy -- see module docstring for why). ──
            score_source = "trained"
            final_dimensions = trained_result.dimensions
            final_overall_score = trained_result.overall_score
            final_grade = trained_result.grade
            reasoning = trained_result.reasoning

            # Agreement/band computed for CONFIDENCE and DIAGNOSTICS only --
            # does not touch final_dimensions/final_overall_score/final_grade
            # above.
            heuristic_by_name = {d.name: d for d in heuristic_result.dimensions}
            per_dimension_diag = {}
            agreements: list[float] = []
            for t_dim in trained_result.dimensions:
                h_dim = heuristic_by_name.get(t_dim.name)
                agreement = _dimension_agreement(h_dim, t_dim) if h_dim is not None else None
                per_dimension_diag[t_dim.name] = {
                    "heuristic": h_dim.raw_score if h_dim is not None else None,
                    "trained": t_dim.raw_score,
                    "final": t_dim.raw_score,  # Round 3: final == trained, always, when available
                    "agreement": agreement,
                }
                if agreement is not None:
                    agreements.append(agreement)

            overall_agreement = round(sum(agreements) / len(agreements), 3) if agreements else None
            overall_band = _agreement_band(overall_agreement) if overall_agreement is not None else None

            model_confidence = trained_result.confidence
            if overall_band is not None:
                final_confidence, adjusted_multiplier, tier_label = _compute_confidence(
                    heuristic_result.confidence, overall_band, model_confidence,
                )
                confidence_source = ConfidenceSource.HYBRID
                confidence_rationale = (
                    f"DeBERTa's prediction is used as the authoritative score. An independent "
                    f"heuristic comparison showed {overall_agreement:.0%} agreement ({overall_band} "
                    f"band) with model confidence {model_confidence:.0%}, yielding {tier_label} "
                    f"combined confidence. (Disagreement is recorded for observability; it does not "
                    f"override the DeBERTa prediction.)"
                )
            else:
                # No overlapping dimensions to compare (shouldn't normally
                # happen -- both evaluators mask to the same
                # relevant_dimensions() for a given reasoning_type -- but
                # degrade to the trained model's own confidence rather than
                # inventing a number).
                final_confidence = model_confidence
                confidence_source = ConfidenceSource.MODEL
                confidence_rationale = "DeBERTa's prediction is used as the authoritative score (no heuristic dimensions were available for comparison)."

            raw_model_output = heuristic_result.raw_model_output + tuple(
                (f"trained_{d.name}", d.raw_score) for d in trained_result.dimensions
            ) + (("agreement_score", overall_agreement if overall_agreement is not None else 0.0),)
            model_version = heuristic_result.model_version + trained_result.model_version

        _record_diagnostics(
            self.diagnostics_log_path, request, heuristic_result, trained_result, final_overall_score,
            overall_agreement, overall_band, final_confidence, per_dimension_diag, trained_error, score_source,
        )

        # missing_reasoning, suggested_improvements, recommended_topics,
        # contradiction_* remain heuristic-sourced (base object), unchanged
        # from Round 2. strengths/weaknesses are RECLASSIFIED against
        # final_dimensions (see _reclassify_claims docstring) -- fixed after
        # the real end-to-end demo showed a dimension displayed at 25%
        # labelled "Strong" because the heuristic's own pre-blend score for
        # it disagreed with DeBERTa's.
        final_strengths, final_weaknesses = _reclassify_claims(
            final_dimensions, heuristic_result.strengths, heuristic_result.weaknesses,
        )

        # concept_coverage: heuristic-sourced base, DOWNGRADE-ONLY
        # reconciled against the trained model's own per-concept read when
        # DeBERTa succeeded this turn (see _reconcile_concept_coverage
        # docstring -- Concept Evidence Layer). When DeBERTa failed
        # (trained_result is None), concept_coverage is untouched, exactly
        # the prior "entirely heuristic-sourced" behavior.
        final_concept_coverage = (
            _reconcile_concept_coverage(heuristic_result.concept_coverage, trained_result.concept_coverage)
            if trained_result is not None else heuristic_result.concept_coverage
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
            "strengths": final_strengths,
            "weaknesses": final_weaknesses,
            "concept_coverage": final_concept_coverage,
        })
