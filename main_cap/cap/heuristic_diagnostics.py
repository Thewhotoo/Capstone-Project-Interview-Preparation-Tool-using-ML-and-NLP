"""
Heuristic Diagnostics Engine — V3 Single-Overall-Score Architecture
(isolated, additive).

Produces the four canonical DIAGNOSTIC dimensions
(`evaluation_dimensions.CANONICAL_DIMENSIONS`: technical_correctness,
depth_specificity, relevance_completeness, grounding_ownership) as
deterministic, interpretable, evidence-linked scores — completely SEPARATE
from, and NEVER fed into, the learned DeBERTa overall-score prediction (see
`overall_single_evaluator.py`). These are explanatory output only: "here is
why the model's overall score looks the way it does," never additional
DeBERTa heads and never a second vote on the overall number.

REUSE, NOT REINVENTION (read before changing anything): this module does
NOT duplicate `HeuristicEvaluator`'s signal computation — it imports and
calls the SAME private helper functions `heuristic_evaluator.py` already
uses (`_semantic_similarity`, `_rescale`, `_marker_score`,
`_has_ownership_language`, the marker-word tuples, the calibration
floor/ceiling constants) so a given answer gets the exact same underlying
signal whether scored by the legacy 12-dimension HeuristicEvaluator or by
this four-canonical-dimension engine. What's NEW here is only the
GROUPING of those signals into the four canonical dimensions — and that
grouping is not invented either: it is EXACTLY
`evaluation_dimensions.LEGACY_DIMENSION_MAP`, the pure-data compatibility
bridge that module already defines and documents for precisely this
purpose ("this module... exists so later aggregation/relabel code can
translate legacy signal into the canonical four"). `test_heuristic_
diagnostics.py` asserts this module's grouping matches `LEGACY_DIMENSION_MAP`
exactly, so the two can never silently drift apart.

    technical_correctness   <- {technical_accuracy}
    depth_specificity        <- {technical_depth, architecture, tradeoffs,
                                  debugging, testing, scalability}
    relevance_completeness   <- {completeness, communication}
    grounding_ownership       <- {resume_grounding, ownership, authenticity}

Each canonical dimension's raw score is the plain, unweighted MEAN of its
legacy-signal group's raw scores (an explicit, documented, equal-weight
aggregation — same "don't invent arbitrary weights" discipline this
redesign applies everywhere else). No dimension in the mapping needed a
newly-invented heuristic — every legacy signal it groups already exists in
`heuristic_evaluator.py` and is reused here unchanged.

DETERMINISTIC AND INTERPRETABLE: every score is a pure function of the
`EvaluationRequest` (question, answer, grounding) — no learned model, no
randomness, no hidden state. Two calls with the same request always
produce the same four scores.
"""

from __future__ import annotations

from evaluation_dimensions import CANONICAL_DIMENSIONS, LEGACY_DIMENSION_MAP, EvaluationDimension
from evaluation_request import EvaluationRequest
from evaluation_result import ConfidenceSource, DimensionScore, EvidenceLinkedClaim
from heuristic_evaluator import (
    STRENGTH_THRESHOLD,
    WEAKNESS_THRESHOLD,
    _ACCURACY_GROUNDING_WEIGHT,
    _ACCURACY_SIMILARITY_CEILING,
    _ACCURACY_SIMILARITY_FLOOR,
    _ARCHITECTURE_MARKERS,
    _DEBUGGING_MARKERS,
    _GROUNDING_SIMILARITY_CEILING,
    _GROUNDING_SIMILARITY_FLOOR,
    _SCALABILITY_MARKERS,
    _TESTING_MARKERS,
    _TRADEOFF_MARKERS,
    _grounding_text,
    _grounding_terms,
    _has_ownership_language,
    _marker_score,
    _rescale,
    _semantic_similarity,
)
from reasoning_dimension_relevance import (
    ARCHITECTURE,
    AUTHENTICITY,
    COMMUNICATION,
    COMPLETENESS,
    DEBUGGING,
    OWNERSHIP,
    RESUME_GROUNDING,
    SCALABILITY,
    TECHNICAL_ACCURACY,
    TECHNICAL_DEPTH,
    TESTING,
    TRADEOFFS,
)

# The four canonical dimension keys, in canonical order — the ONLY four
# dimensions this engine ever produces (never more, never fewer).
CANONICAL_DIMENSION_KEYS: tuple[str, ...] = tuple(d.value for d in CANONICAL_DIMENSIONS)

# `LEGACY_DIMENSION_MAP` keys are `EvaluationDimension` enum members; this
# module works with plain string keys throughout (matching `DimensionScore.
# name`'s own convention) — this is the one place the enum -> string
# translation happens.
_LEGACY_GROUP_BY_CANONICAL: dict[str, tuple[str, ...]] = {
    dim.value: LEGACY_DIMENSION_MAP[dim] for dim in CANONICAL_DIMENSIONS
}


def _raw_legacy_signals(request: EvaluationRequest) -> dict[str, float]:
    """Computes every legacy-named raw signal this engine needs, using the
    SAME formulas `HeuristicEvaluator.evaluate()` uses (reused helper
    functions, not reimplemented math) — see module docstring."""
    answer = request.answer_text.strip()
    answer_lower = answer.lower()

    grounding_text = _grounding_text(request.specification)
    grounding_similarity_raw = _semantic_similarity(answer, grounding_text) if grounding_text else 0.0
    question_similarity_raw = _semantic_similarity(answer, request.question_text)
    accuracy_blend_raw = (
        _ACCURACY_GROUNDING_WEIGHT * grounding_similarity_raw
        + (1.0 - _ACCURACY_GROUNDING_WEIGHT) * question_similarity_raw
    ) if grounding_text else question_similarity_raw

    accuracy_similarity = _rescale(accuracy_blend_raw, _ACCURACY_SIMILARITY_FLOOR, _ACCURACY_SIMILARITY_CEILING)
    grounding_similarity = (
        _rescale(grounding_similarity_raw, _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING)
        if grounding_text else accuracy_similarity
    )

    terms = _grounding_terms(request.specification)
    mentioned_terms = [t for t in terms if t.lower() in answer_lower]
    term_coverage_bonus = (len(mentioned_terms) / len(terms)) if terms else 0.5

    has_ownership = _has_ownership_language(answer_lower)

    word_count = len(answer.split())
    sentences = [s.strip() for s in answer.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    completeness_raw = 0.0
    if word_count < 8:
        completeness_raw = 0.15
    elif word_count < 25:
        completeness_raw = 0.45
    elif word_count < 60:
        completeness_raw = 0.75
    elif word_count < 120:
        completeness_raw = 0.88
    else:
        completeness_raw = 0.95
    if len(sentences) >= 3:
        completeness_raw = min(1.0, completeness_raw + 0.05)

    communication_raw = 0.5
    if len(sentences) >= 2:
        communication_raw += 0.2
    if any(w in answer_lower for w in ("first", "then", "also", "because", "therefore", "however")):
        communication_raw += 0.15
    if word_count > 30:
        communication_raw += 0.15
    communication_raw = min(1.0, communication_raw)

    marker_floor = 0.90 * accuracy_similarity

    def _floored_marker_score(markers: tuple[str, ...]) -> float:
        return max(marker_floor, _marker_score(answer_lower, markers))

    return {
        TECHNICAL_ACCURACY: accuracy_similarity,
        TECHNICAL_DEPTH: min(1.0, 0.95 * accuracy_similarity + 0.05 * term_coverage_bonus),
        COMMUNICATION: communication_raw,
        COMPLETENESS: completeness_raw,
        ARCHITECTURE: _floored_marker_score(_ARCHITECTURE_MARKERS),
        TRADEOFFS: _floored_marker_score(_TRADEOFF_MARKERS),
        OWNERSHIP: 1.0 if has_ownership else 0.2,
        DEBUGGING: _floored_marker_score(_DEBUGGING_MARKERS),
        TESTING: _floored_marker_score(_TESTING_MARKERS),
        SCALABILITY: _floored_marker_score(_SCALABILITY_MARKERS),
        RESUME_GROUNDING: grounding_similarity,
        AUTHENTICITY: 1.0 if has_ownership else 0.3,
    }


class HeuristicDiagnosticsEngine:
    """Deterministic, model-free engine producing exactly the four
    canonical diagnostic dimensions. Stateless: `compute()` is a pure
    function of its `EvaluationRequest` argument."""

    declared_dimensions: tuple[str, ...] = CANONICAL_DIMENSION_KEYS

    def compute(self, request: EvaluationRequest) -> tuple[DimensionScore, ...]:
        """Returns exactly `len(CANONICAL_DIMENSION_KEYS)` (four)
        `DimensionScore`s, in canonical order. `contributes_to_overall` is
        `False` on every one of them — these are diagnostic/explanatory
        output only; see module docstring and
        `overall_single_evaluator.py` for the enforced separation from the
        learned overall score."""
        raw_by_legacy_signal = _raw_legacy_signals(request)
        answer = request.answer_text.strip()
        word_count = len(answer.split())
        sentences = [s.strip() for s in answer.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        confidence = min(1.0, 0.3 + 0.1 * min(len(sentences), 5) + 0.02 * min(word_count, 20))

        dimensions: list[DimensionScore] = []
        for canonical_name in CANONICAL_DIMENSION_KEYS:
            legacy_group = _LEGACY_GROUP_BY_CANONICAL[canonical_name]
            group_scores = [raw_by_legacy_signal[legacy_name] for legacy_name in legacy_group]
            raw_score = sum(group_scores) / len(group_scores)
            dimensions.append(DimensionScore(
                name=canonical_name,
                raw_score=round(max(0.0, min(1.0, raw_score)), 3),
                weight_used=round(1.0 / len(CANONICAL_DIMENSION_KEYS), 4),
                confidence=round(confidence, 3),
                confidence_source=ConfidenceSource.HEURISTIC,
                # Diagnostic only — must never contribute to the overall
                # score (that comes solely from the learned CORAL head, see
                # overall_single_evaluator.py).
                contributes_to_overall=False,
                evidence_refs=(request.specification.source_id,),
            ))
        return tuple(dimensions)

    @staticmethod
    def claims(dimensions: tuple[DimensionScore, ...]) -> tuple[tuple[EvidenceLinkedClaim, ...], tuple[EvidenceLinkedClaim, ...]]:
        """Strengths/weaknesses text consistent with the four diagnostic
        dimensions — same threshold-based classification convention
        (`STRENGTH_THRESHOLD`/`WEAKNESS_THRESHOLD`, imported not
        re-chosen) every other evaluator in this codebase already uses."""
        strengths: list[EvidenceLinkedClaim] = []
        weaknesses: list[EvidenceLinkedClaim] = []
        for d in dimensions:
            label = d.name.replace("_", " ")
            if d.raw_score >= STRENGTH_THRESHOLD:
                strengths.append(EvidenceLinkedClaim(
                    claim=f"Strong {label}.", dimension=d.name,
                    evidence=f"Heuristic diagnostic scored {d.raw_score:.0%} on {label}.",
                ))
            elif d.raw_score < WEAKNESS_THRESHOLD:
                weaknesses.append(EvidenceLinkedClaim(
                    claim=f"Weak {label}.", dimension=d.name,
                    evidence=f"Heuristic diagnostic scored only {d.raw_score:.0%} on {label}.",
                ))
        if not strengths and dimensions:
            strengths.append(EvidenceLinkedClaim(
                claim="Attempted to address the question.", dimension=dimensions[0].name,
                evidence=f"Scored {dimensions[0].raw_score:.0%} on {dimensions[0].name}.",
            ))
        if not weaknesses and dimensions:
            weaknesses.append(EvidenceLinkedClaim(
                claim="Minor areas for deeper elaboration.", dimension=dimensions[-1].name,
                evidence=f"Scored {dimensions[-1].raw_score:.0%} on {dimensions[-1].name}.",
            ))
        return tuple(strengths), tuple(weaknesses)
