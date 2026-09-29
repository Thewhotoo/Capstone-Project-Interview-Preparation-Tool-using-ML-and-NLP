"""
Resume Evidence Evaluator — evidence-based scoring for candidate-specific
resume-interview questions (isolated, additive, NOT DEPLOYED).

WHY (architectural conclusion): the resume interview's 21 question families are
all EXPERIENTIAL ("what did YOU build / decide / learn"), so an answer's factual
technical correctness cannot be established without a per-question answer key,
which cannot be authored without inventing candidate facts. Therefore this
evaluator does NOT claim technical correctness. It scores the evidence that IS
available — relevance, consistency with the résumé grounding, concrete
implementation detail, demonstrated (grounded) ownership, consistency with the
candidate's prior answers this session — and exposes technical correctness only
as a STATUS: "verified" when an AnswerKey exists, otherwise
"not_independently_verified".

REUSE, NOT A PARALLEL FRAMEWORK: every underlying signal is the SAME one the
existing heuristic stack already computes — `_semantic_similarity`,
`_grounding_text`/`_grounding_terms`, `_has_ownership_language`,
`_contradiction_flag`, `_rescale` (imported from `heuristic_evaluator`), the
four diagnostic dimensions (`HeuristicDiagnosticsEngine`, preserved verbatim in
the payload), and the deterministic degeneracy gate (`correctness_nli_scorer.
degeneracy`). What is NEW is only (a) the honest RE-COMPOSITION of those signals
into an overall that never rewards length / first-person-alone / jargon-density /
generic-textbook / confident tone, and (b) the missing evidence signals
(concreteness, non-answer, self-correction, prior-answer consistency).

NOT DEPLOYED: imported by nothing in the live stack; v5_1088 remains the active
production evaluator and rollback. API payload (EvaluationResult) is unchanged;
the four canonical diagnostic dimensions are preserved.
"""

from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from correctness_nli_scorer import degeneracy
from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS, HeuristicDiagnosticsEngine
from heuristic_evaluator import (
    _ACCURACY_SIMILARITY_CEILING,
    _ACCURACY_SIMILARITY_FLOOR,
    _GROUNDING_SIMILARITY_CEILING,
    _GROUNDING_SIMILARITY_FLOOR,
    _contradiction_flag,
    _grounding_terms,
    _grounding_text,
    _has_ownership_language,
    _rescale,
    _semantic_similarity,
)
from question_families import ReasoningType

_CONFIDENCE_SOURCE = "resume_evidence_heuristic"

_NON_ANSWER_MARKERS = (
    "i don't know", "i dont know", "i do not know", "not sure", "no idea",
    "can't remember", "cannot remember", "don't recall", "didn't work on",
    "did not work on", "not familiar", "no clue", "beats me",
)
_SELF_CORRECTION_MARKERS = (
    "actually", "i mean", "to correct", "let me correct", "let me rephrase",
    "on second thought", "i misspoke", "scratch that", "correction,",
    "what i meant", "rather,",
)
# Numeric/quantitative tokens (metrics like "50ms", "2s", "p95", "99.9%").
# Matches digit runs directly — a trailing \b would fail on digit+unit tokens.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _grade_from_score(score: float) -> str:
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


@dataclass(frozen=True)
class EvidenceBreakdown:
    relevance: float            # answer ↔ question topical alignment
    grounding: float            # answer ↔ résumé-grounding consistency (also specificity-to-their-project)
    concreteness: float         # concrete detail: numbers + actual résumé-term use (NOT length)
    ownership: float            # demonstrated ownership, GATED by grounding/concreteness
    tech_correctness_status: str  # "verified" | "not_independently_verified"
    flags: tuple[str, ...]


def _concreteness(answer: str, answer_lower: str, terms: tuple[str, ...]) -> tuple[float, int, int]:
    """Concrete detail WITHOUT rewarding length: quantitative specifics
    (numbers/metrics) + how many of the candidate's ACTUAL résumé technologies/
    concepts they used in the answer. A 15-word answer with a number and a real
    project term scores high; a 200-word answer with neither scores ~0."""
    numbers = len(_NUMBER_RE.findall(answer))
    mentioned = [t for t in terms if t and t.lower() in answer_lower]
    term_cov = (len(mentioned) / len(terms)) if terms else 0.0
    num_signal = min(1.0, numbers / 2.0)
    # weight résumé-term use a bit above raw numbers; both are length-independent.
    score = 0.4 * num_signal + 0.6 * min(1.0, term_cov * 1.5)
    return round(min(1.0, score), 3), numbers, len(mentioned)


def compute_evidence(request: EvaluationRequest) -> EvidenceBreakdown:
    """Pure evidence extraction from AVAILABLE signals (reused helpers). No
    length term anywhere; first-person and jargon are never rewarded on their
    own."""
    answer = (request.answer_text or "").strip()
    answer_lower = answer.lower()
    flags: list[str] = []

    gtext = _grounding_text(request.specification)
    relevance = _rescale(_semantic_similarity(answer, request.question_text) if answer else 0.0,
                         _ACCURACY_SIMILARITY_FLOOR, _ACCURACY_SIMILARITY_CEILING)
    grounding = _rescale(_semantic_similarity(answer, gtext) if (answer and gtext) else 0.0,
                        _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING)
    terms = _grounding_terms(request.specification)
    concreteness, n_numbers, n_terms = _concreteness(answer, answer_lower, terms)

    has_ownership = _has_ownership_language(answer_lower)
    self_correction = any(m in answer_lower for m in _SELF_CORRECTION_MARKERS)
    non_answer = (not answer) or any(m in answer_lower for m in _NON_ANSWER_MARKERS)
    deg = degeneracy(answer)
    contradiction = _contradiction_flag(answer, gtext) if (answer and gtext) else False

    # Ownership is EVIDENCE-GATED: first-person language alone is not rewarded.
    if not has_ownership:
        ownership = 0.2
    else:
        support = max(grounding, concreteness)          # is the ownership claim backed by anything?
        if contradiction and not self_correction:
            ownership = 0.15                            # ownership claim conflicts with the résumé → caution
            flags.append("unsupported_or_conflicting_ownership")
        else:
            ownership = round(0.30 + 0.70 * support, 3)  # grounded/specific ownership earns credit; bare "I" ~0.30
            if support < 0.2:
                flags.append("first_person_without_supporting_evidence")

    # generic-textbook: on-topic but not about THEIR project and no concrete detail
    if relevance >= 0.55 and grounding < 0.35 and n_terms == 0 and concreteness < 0.25 and not has_ownership:
        flags.append("generic_textbook")
    if non_answer:
        flags.append("non_answer")
    if deg.is_degenerate:
        flags.append("degenerate:" + ",".join(deg.reasons))
    if self_correction:
        flags.append("self_correction")

    # prior-answer consistency (reuses the NLI contradiction helper)
    prior = getattr(request.conversation_context, "prior_answers_for_this_spec", ())
    if prior and answer:
        if _contradiction_flag(answer, " ".join(prior)) and not self_correction:
            flags.append("contradicts_prior_answer")

    verified = request.answer_key is not None and request.answer_key.has_key_points
    return EvidenceBreakdown(
        relevance=round(relevance, 3), grounding=round(grounding, 3),
        concreteness=concreteness, ownership=ownership,
        tech_correctness_status="verified" if verified else "not_independently_verified",
        flags=tuple(flags),
    )


def _compose_overall(ev: EvidenceBreakdown) -> float:
    """Weighted evidence overall (length-independent), then gates/penalties.
    Weights sum to 1.0; correctness is NOT a term (unverified for résumé Qs)."""
    overall = (0.30 * ev.relevance + 0.30 * ev.grounding
               + 0.25 * ev.concreteness + 0.15 * ev.ownership)
    if "generic_textbook" in ev.flags:
        overall *= 0.75
    if "unsupported_or_conflicting_ownership" in ev.flags:
        overall *= 0.75
    if "contradicts_prior_answer" in ev.flags:
        overall *= 0.85
    # hard caps for non-answers / degenerate text (never rescued by other signals)
    if "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
        overall = min(overall, 0.10)
    return round(max(0.0, min(1.0, overall)), 3)


class ResumeEvidenceEvaluator:
    """`Evaluator`-Protocol evaluator for candidate-specific résumé questions.
    Scores available evidence; never claims unverified technical correctness.
    Diagnostic dimensions come unchanged from `HeuristicDiagnosticsEngine`
    (payload compatibility). NOT deployed; v5_1088 stays active/rollback."""

    declared_dimensions = CANONICAL_DIMENSION_KEYS
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False
    version = "v1"

    def __init__(self, diagnostics_engine: Optional[HeuristicDiagnosticsEngine] = None,
                 name: str = "resume-evidence-evaluator-v1"):
        self.diagnostics_engine = diagnostics_engine or HeuristicDiagnosticsEngine()
        self.name = name

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        ev = compute_evidence(request)
        overall_score = _compose_overall(ev)
        grade = _grade_from_score(overall_score)

        dimensions = self.diagnostics_engine.compute(request)          # preserved verbatim
        strengths, weaknesses = self.diagnostics_engine.claims(dimensions)

        # confidence reflects how much EVIDENCE we had, not how confident the answer sounded.
        confidence = round(max(0.15, min(1.0, 0.25 + 0.4 * ev.grounding + 0.35 * ev.concreteness)), 3)
        if "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
            confidence = 0.2

        reasoning = (
            f"Evidence-based score (résumé-specific question). Technical correctness: "
            f"{ev.tech_correctness_status.upper().replace('_', ' ')} — no answer key, so factual correctness of "
            f"claims was NOT judged; this score reflects only available evidence. "
            f"relevance {ev.relevance:.0%}, résumé-consistency {ev.grounding:.0%}, "
            f"concreteness {ev.concreteness:.0%}, ownership-evidence {ev.ownership:.0%}"
            + (f"; flags: {', '.join(ev.flags)}" if ev.flags else "")
            + ".\nDiagnostic breakdown (heuristic, does NOT drive this score):\n"
            + "\n".join(f"{d.name}: {d.raw_score:.0%}" for d in dimensions)
        )

        return EvaluationResult(
            result_id=f"eval_{_uuid.uuid4().hex[:12]}", request_id=request.request_id,
            evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
            specification_id=request.specification.id, source_id=request.specification.source_id,
            category=request.specification.category.value,
            project_reference=(
                request.specification.grounding.project.title
                if request.specification.grounding.project is not None else None
            ),
            reasoning_type=request.reasoning_type,
            evaluator_name=self.name, evaluator_version=self.version,
            model_version=(("similarity", "all-MiniLM-L6-v2"), ("contradiction", "cross-encoder/nli-MiniLM2-L6-H768")),
            dataset_version=None, training_date=None,
            dimensions=dimensions,
            overall_score=overall_score, grade=grade,
            confidence=confidence, confidence_source=_CONFIDENCE_SOURCE,
            confidence_rationale=(
                "Reflects the strength of the available EVIDENCE (résumé grounding + concrete detail), not the "
                f"answer's tone or length. Technical correctness is {ev.tech_correctness_status} "
                "(no answer key for this experiential question)."
            ),
            reasoning=reasoning,
            strengths=strengths, weaknesses=weaknesses,
            resume_grounding_score=ev.grounding,
            calibration_version=None,
        )
