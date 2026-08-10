"""
HeuristicEvaluator — Phase 3 concrete implementation of the Evaluator
interface (RFC Section 7, "Evaluator V1" in the same sense the architecture
already uses that term for the Planning subsystem's Model Registry, Chapter
19.10). Pretrained-off-the-shelf signals only — nothing trained or
fine-tuned here, exactly like the existing Resume Discussion evaluator's
own V1 (discussion_engine.py's `_evaluate_discussion_answer_local`).

DELIBERATE INDEPENDENCE FROM discussion_engine.py: this module does not
import anything from discussion_engine.py, and does not share its lazy
SentenceTransformer/CrossEncoder singletons. That module is the legacy v1
Conversation+Evaluation engine's own evaluator, tightly coupled to its own
(pre-Phase-3) EvaluationResult shape. This module is a fresh implementation
of the NEW, frozen Evaluator interface for the v2 (Planner + Realizer +
Conversation Engine) pipeline. The cost of this independence is a second,
separately-cached copy of the same embedding model in-process if both
engines run simultaneously — an accepted, documented trade-off in favor of
Goal 1 (Conversation Engine and Evaluation Engine must be completely
independent) over micro-optimizing shared model loading.

Every dimension score, gap, and confidence value in this module traces back
to one of three signals:
    1. SBERT cosine similarity  — semantic relevance/alignment to grounding
    2. Lexical marker presence  — cheap, explainable proxies for
       architecture/trade-offs/ownership/debugging/testing/scalability
       discussion (token/phrase presence, not learned)
    3. An NLI cross-encoder     — used ONLY as a contradiction flag, never
       blended into a score (the same lesson the architecture already
       learned and documented — Chapter 19.5 — applied fresh here rather
       than re-learned the hard way).
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from evaluation_request import EvaluationRequest
from evaluation_result import (
    ConceptObservation,
    ConceptObservationStatus,
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
    EvidenceLinkedClaim,
    MissingReasoningCategory,
    MissingReasoningItem,
)
from question_families import ReasoningType
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
    contributes_by_default,
    relevant_dimensions,
)

logger = logging.getLogger(__name__)

_SEM_MODEL_NAME = "all-MiniLM-L6-v2"
_NLI_MODEL_NAME = "cross-encoder/nli-MiniLM2-L6-H768"
_CONTRADICTION_THRESHOLD = 0.5

# Strength/weakness classification thresholds -- named and exported (not
# just local literals) so `hybrid_evaluator.py` can reclassify claims
# against the FINAL (possibly DeBERTa-sourced) dimension scores using this
# exact same rule, rather than a second, independently-chosen threshold
# that could drift out of sync. See `_claims` below and
# `hybrid_evaluator._reclassify_claims`.
STRENGTH_THRESHOLD = 0.65
WEAKNESS_THRESHOLD = 0.35

_OWNERSHIP_MARKERS = (
    "i designed", "i built", "i implemented", "i developed", "i chose",
    "i decided", "my approach", "i was responsible", "i led", "i managed",
    "i created", "i configured", "i set up", "i integrated",
)
_ARCHITECTURE_MARKERS = (
    "architecture", "component", "layer", "service", "module", "structure",
    "data flow", "pipeline", "design",
)
_TRADEOFF_MARKERS = (
    "versus", "vs.", "instead of", "alternative", "trade-off", "tradeoff",
    "compared to", "rather than", "over using", "chose", "considered",
)
_DEBUGGING_MARKERS = (
    "bug", "issue", "broke", "broken", "fixed", "resolved", "debug", "error",
    "failure", "crash", "root cause",
)
_TESTING_MARKERS = (
    "test", "tested", "testing", "verified", "validation", "unit test",
    "integration test",
)
_SCALABILITY_MARKERS = (
    "scale", "scaling", "scalab", "load", "throughput", "performance",
    "grow", "growth", "concurrent", "high traffic",
)


def _marker_score(text_lower: str, markers: tuple[str, ...]) -> float:
    hits = sum(1 for m in markers if m in text_lower)
    return min(1.0, hits / 2.0)  # 2+ distinct markers -> full credit


def _has_ownership_language(text_lower: str) -> bool:
    return any(m in text_lower for m in _OWNERSHIP_MARKERS)


class _LazyModels:
    """Lazy singletons, private to this module — see the module docstring
    for why these are NOT shared with discussion_engine.py's own copies."""

    _sem_model = None
    _nli_model = None

    @classmethod
    def semantic(cls):
        if cls._sem_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._sem_model = SentenceTransformer(_SEM_MODEL_NAME)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("SentenceTransformer unavailable, using fallback: %s", e)
                cls._sem_model = False
        return cls._sem_model if cls._sem_model is not False else None

    @classmethod
    def nli(cls):
        if cls._nli_model is None:
            try:
                from sentence_transformers import CrossEncoder
                cls._nli_model = CrossEncoder(_NLI_MODEL_NAME)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("NLI cross-encoder unavailable, contradiction detection disabled: %s", e)
                cls._nli_model = False
        return cls._nli_model if cls._nli_model is not False else None


def _semantic_similarity(text_a: str, text_b: str) -> float:
    model = _LazyModels.semantic()
    if model is None or not text_a.strip() or not text_b.strip():
        # Graceful degradation (matches the architecture's established
        # NFR7 pattern): word-overlap ratio if the model can't load.
        words_a, words_b = set(text_a.lower().split()), set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / max(len(words_a | words_b), 1)
    import numpy as np
    embs = model.encode([text_a, text_b])
    dot = np.dot(embs[0], embs[1])
    norm = np.linalg.norm(embs[0]) * np.linalg.norm(embs[1])
    return float(dot / norm) if norm > 0 else 0.0


# Calibration for _semantic_similarity's raw cosine output (Phase 3
# evaluation-fairness fix, round 2). Raw SBERT cosine similarity does NOT
# live on a 0..1 "percent correct" scale, and -- found during the round-2
# calibration battery -- the CHOICE of reference text matters as much as
# the rescale: comparing the answer against the bare QUESTION text is not
# just a weak signal, it is *inversely* correlated with quality for a
# short interrogative question (an empirically measured battery of
# weak/average/good/excellent answers against the same question scored
# 0.56/0.31/0.30/0.27 raw similarity -- backwards). Comparing against the
# GROUNDING text alone (project title/tech/concepts) was, on the same
# battery, perfectly monotonic (0.15/0.21/0.25/0.35). Two conclusions:
#   1. `resume_grounding` uses grounding-only similarity, unchanged in
#      spirit from before.
#   2. `technical_accuracy` needs to stay a DIFFERENT signal from
#      resume_grounding (duplicating one value into two dimensions was
#      exactly the bug the original round-1 fix corrected), but blending
#      in much of the unreliable question-only signal reintroduces noise.
#      A grounding-dominant blend (85% grounding-only, 15% question-only)
#      keeps technical_accuracy numerically distinct while remaining
#      monotonic on the same battery (verified: 0.21/0.23/0.26/0.34).
# Each gets its own floor/ceiling, calibrated against its own observed
# range on the same battery -- using one shared ceiling for both (the
# round-1 approach) systematically under-scored resume_grounding, whose
# natural raw range sits lower than technical_accuracy's blended range.
_GROUNDING_SIMILARITY_FLOOR = 0.08
_GROUNDING_SIMILARITY_CEILING = 0.33

_ACCURACY_SIMILARITY_FLOOR = 0.10
_ACCURACY_SIMILARITY_CEILING = 0.32
_ACCURACY_GROUNDING_WEIGHT = 0.85  # vs. 0.15 question-only, see above


def _rescale(raw: float, floor: float, ceiling: float) -> float:
    """Linearly rescales a raw cosine similarity so the meaningful part of
    its range (see the calibration constants above) maps to 0..1, instead
    of the raw value's own much narrower, much lower natural range being
    read directly as a percentage."""
    if ceiling <= floor:
        return raw
    scaled = (raw - floor) / (ceiling - floor)
    return max(0.0, min(1.0, scaled))


def _contradiction_flag(answer: str, grounding_text: str) -> bool:
    """NLI used ONLY as a contradiction flag, never blended into a score —
    see this module's docstring and architecture Chapter 19.5 for why."""
    model = _LazyModels.nli()
    if model is None or not answer.strip() or not grounding_text.strip():
        return False
    import numpy as np
    logits = model.predict([(answer, grounding_text)])[0]
    exp = np.exp(logits - np.max(logits))
    probs = exp / exp.sum()
    return float(probs[0]) >= _CONTRADICTION_THRESHOLD  # id2label: 0=contradiction


def _grounding_text(spec) -> str:
    g = spec.grounding
    if g.project is not None:
        return " ".join(filter(None, [g.project.title, g.project.summary, *g.project.technologies, *g.project.concepts]))
    if g.experience is not None:
        return " ".join(filter(None, [g.experience.role, g.experience.company, g.experience.summary]))
    return g.certification.name


def _grounding_terms(spec) -> tuple[str, ...]:
    g = spec.grounding
    if g.project is not None:
        return tuple(g.project.technologies) + tuple(g.project.concepts)
    return ()


class HeuristicEvaluator:
    """Evaluator interface implementation — Evaluator V1 for the Phase 3
    Evaluation Engine. Stateless: every `evaluate()` call is a pure
    function of its `EvaluationRequest`; no session state is held here."""

    name = "heuristic-v1"
    version = "1.0.0"
    declared_dimensions = (
        TECHNICAL_ACCURACY, TECHNICAL_DEPTH, COMMUNICATION, COMPLETENESS,
        ARCHITECTURE, TRADEOFFS, OWNERSHIP, DEBUGGING, TESTING, SCALABILITY,
        RESUME_GROUNDING, AUTHENTICITY,
    )
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        answer = request.answer_text.strip()
        answer_lower = answer.lower()
        word_count = len(answer.split())
        sentences = [s.strip() for s in answer.replace("!", ".").replace("?", ".").split(".") if s.strip()]

        grounding_text = _grounding_text(request.specification)
        # technical_accuracy and resume_grounding are deliberately different
        # comparisons, not the same value twice (the round-1 fix) -- but
        # both are now grounding-DOMINANT (see the calibration constants'
        # docstring above for why question-only similarity was dropped: it
        # measured empirically as inversely correlated with answer
        # quality, not just weak). resume_grounding is grounding-only;
        # technical_accuracy blends in a small, non-dominant amount of
        # question-similarity so the two remain numerically distinct
        # signals without reintroducing that noise as the dominant term.
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
        contradiction = _contradiction_flag(answer, grounding_text) if grounding_text else False

        terms = _grounding_terms(request.specification)
        mentioned_terms = [t for t in terms if t.lower() in answer_lower]
        missing_terms = [t for t in terms if t.lower() not in answer_lower]
        # A BONUS for mentioning resume-declared technologies/concepts, not
        # the base score: a specific, narrowly-scoped question naturally
        # won't touch every technology the project's grounding happens to
        # list, and shouldn't be penalized as if it should have (Phase 3
        # evaluation-fairness fix -- "missing an optional concept the
        # question didn't ask about" must be a small deduction, not the
        # dominant factor).
        term_coverage_bonus = (len(mentioned_terms) / len(terms)) if terms else 0.5

        has_ownership = _has_ownership_language(answer_lower)

        # Completeness calibration (Phase 3 evaluation-fairness fix,
        # round 2): the old buckets treated word count as a direct proxy
        # for coverage-of-the-point, capping the realistic bulk of solid,
        # appropriately-concise spoken interview answers (25-119 words) at
        # 0.5-0.7 regardless of how complete the content actually was --
        # a checklist-completion bias, not a coverage measure. Recalibrated
        # so a genuinely complete concise answer lands in the range a real
        # interviewer would call "solid" (see docs/architecture -- Hybrid
        # Evaluator + heuristic calibration review for the target bands
        # this was checked against).
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

        # Communication calibration: no longer requires first-person
        # ownership phrasing for full credit -- `ownership` is already its
        # own dedicated dimension (contributes for OWNERSHIP/REFLECTION
        # reasoning types), so a RECALL/EXPLANATION-type answer that has no
        # legitimate reason to say "I built/designed" was being docked 15
        # points of communication credit for a quality it was never asked
        # to demonstrate. Communication is now scored purely on structure/
        # clarity signals (sentence count, connective words, length).
        communication_raw = 0.5
        if len(sentences) >= 2:
            communication_raw += 0.2
        if any(w in answer_lower for w in ("first", "then", "also", "because", "therefore", "however")):
            communication_raw += 0.15
        if word_count > 30:
            communication_raw += 0.15
        communication_raw = min(1.0, communication_raw)

        # Confidence proxy: longer, more structured answers give the
        # heuristic more signal to work with. Always confidence_source=
        # HEURISTIC — this evaluator makes no claim to a calibrated estimate.
        base_confidence = min(1.0, 0.3 + 0.1 * min(len(sentences), 5) + 0.02 * min(word_count, 20))

        # Marker-word dimensions (architecture/trade-offs/debugging/testing/
        # scalability) are blended with a FLOOR derived from how on-topic
        # and correct the answer already looks (accuracy_similarity),
        # instead of being purely 0 when the answer doesn't happen to use
        # one of a small fixed set of literal phrases. A candidate who
        # clearly reasons about a trade-off without ever typing the word
        # "trade-off" must not be scored as if they said nothing at all
        # (Phase 3 evaluation-fairness fix). The literal-marker signal
        # still matters -- it can only raise the score above the floor,
        # never lower it -- so an answer that DOES use explicit,
        # unambiguous language still earns visibly more credit than one
        # that doesn't.
        #
        # Round 2 note: this floor's multiplier (and technical_depth's,
        # below) was raised from round 1's 0.65/0.8 to 0.90/0.95. These
        # "bonus" dimensions are ALREADY down-weighted relative to the
        # always-relevant ones (proportional weighting, below) -- also
        # discounting their VALUE on top of discounting their WEIGHT was
        # compounding the same intent twice and dragging genuinely solid
        # answers below the calibration review's target bands. The weight
        # mechanism alone is enough to express "this matters less for a
        # question that didn't explicitly ask about it."
        _marker_floor = 0.90 * accuracy_similarity

        def _floored_marker_score(markers: tuple[str, ...]) -> float:
            return max(_marker_floor, _marker_score(answer_lower, markers))

        raw_by_dimension: dict[str, float] = {
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

        wanted = relevant_dimensions(request.reasoning_type)
        # Proportional, not uniform, weighting (Phase 3 evaluation-fairness
        # fix). The four ALWAYS-relevant dimensions -- did they address what
        # was actually asked, communicate clearly, answer completely, and
        # stay consistent with the resume -- are what every answer is
        # fundamentally judged on. The 1-2 EXTRA dimensions a reasoning_type
        # pulls in on top (e.g. "architecture" for an EXPLANATION question)
        # are real, relevant signals worth measuring, but this specific
        # question didn't necessarily ask about them explicitly, so they
        # must not carry equal weight to "did you actually answer the
        # question" -- see relevant_dimensions' own module docstring for
        # why this coarse, reasoning_type-level (not per-question) mapping
        # is the accepted trade-off. _ALWAYS_WEIGHT/_EXTRA_WEIGHT are
        # relative shares, not absolute weights; normalized below by
        # dividing every dimension's weight_used by their sum, same as
        # the pre-fix uniform scheme already did.
        always_relevant = {TECHNICAL_ACCURACY, COMMUNICATION, COMPLETENESS, RESUME_GROUNDING}
        _ALWAYS_WEIGHT = 1.5
        _EXTRA_WEIGHT = 1.0
        raw_weights = {
            dim_name: (_ALWAYS_WEIGHT if dim_name in always_relevant else _EXTRA_WEIGHT)
            for dim_name in wanted
        }
        weight_total = sum(raw_weights.values())

        dimensions: list[DimensionScore] = []
        for dim_name in wanted:
            dimensions.append(DimensionScore(
                name=dim_name,
                raw_score=round(raw_by_dimension[dim_name], 3),
                weight_used=round(raw_weights[dim_name] / weight_total, 4),
                confidence=round(base_confidence, 3),
                confidence_source=ConfidenceSource.HEURISTIC,
                contributes_to_overall=contributes_by_default(dim_name),
                evidence_refs=(request.specification.source_id,),
            ))

        contributing = [d for d in dimensions if d.contributes_to_overall]
        overall_score = (
            sum(d.raw_score * d.weight_used for d in contributing) / sum(d.weight_used for d in contributing)
            if contributing else 0.0
        )
        overall_score = round(max(0.0, min(1.0, overall_score)), 3)
        grade = self._grade(overall_score)

        strengths, weaknesses = self._claims(
            dimensions, request, answer=answer, sentences=sentences,
            mentioned_terms=mentioned_terms, missing_terms=missing_terms, has_ownership=has_ownership,
        )
        missing_reasoning = self._missing_reasoning(dimensions, missing_terms, request)
        suggested_improvements = tuple(
            f"Discuss {item.explanation.rstrip('.').lower()}." for item in missing_reasoning[:3]
        )
        recommended_topics = tuple(dict.fromkeys(missing_terms))[:3]

        overall_confidence = round(sum(d.confidence for d in dimensions) / len(dimensions), 3)
        confidence_rationale = (
            f"Based on a {word_count}-word, {len(sentences)}-sentence answer — "
            f"{'substantial enough for reasonable signal' if word_count >= 20 else 'short, so this judgment carries meaningfully less certainty'}."
        )

        reasoning = "\n".join(f"{d.name}: {d.raw_score:.0%}" for d in dimensions)

        concept_coverage = tuple(
            ConceptObservation(
                concept=concept,
                status=status,
                evidence=evidence,
                confidence=round(base_confidence, 3),
                confidence_source=ConfidenceSource.HEURISTIC,
            )
            for concept in request.expected_concepts
            for status, evidence in (self._concept_status(concept, answer, answer_lower, sentences),)
        )

        return EvaluationResult(
            result_id=f"eval_{_uuid.uuid4().hex[:12]}",
            request_id=request.request_id,
            evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
            specification_id=request.specification.id,
            source_id=request.specification.source_id,
            category=request.specification.category.value,
            project_reference=(
                request.specification.grounding.project.title
                if request.specification.grounding.project is not None else None
            ),
            reasoning_type=request.reasoning_type,
            evaluator_name=self.name,
            evaluator_version=self.version,
            model_version=(
                ("semantic_similarity", _SEM_MODEL_NAME),
                ("contradiction", _NLI_MODEL_NAME),
            ),
            dataset_version=None,
            training_date=None,
            dimensions=tuple(dimensions),
            overall_score=overall_score,
            grade=grade,
            confidence=overall_confidence,
            confidence_source=ConfidenceSource.HEURISTIC,
            confidence_rationale=confidence_rationale,
            reasoning=reasoning,
            strengths=strengths,
            weaknesses=weaknesses,
            missing_reasoning=missing_reasoning,
            concept_coverage=concept_coverage,
            suggested_improvements=suggested_improvements,
            recommended_topics=recommended_topics,
            contradiction_detected=contradiction,
            contradiction_explanation=(
                "The answer may conflict with what the resume/grounding states." if contradiction else None
            ),
            resume_grounding_score=round(grounding_similarity, 3),
            raw_model_output=tuple((d.name, d.raw_score) for d in dimensions),
            calibration_version=None,
            recommended_action=self._recommended_action(overall_score, missing_reasoning),
        )

    @staticmethod
    def _grade(overall_score: float) -> str:
        # Cutpoints re-derived (Phase 3 heuristic-calibration review) to
        # match stated real-interviewer expectations rather than the
        # original round-number guesses: weak ~30-45%, average/adequate
        # ~55-70%, good ~75-85%, excellent ~90-100%. Verified empirically
        # against realistic answer examples, not chosen blind -- see the
        # calibration review's battery-test results.
        if overall_score >= 0.90:
            return "excellent"
        if overall_score >= 0.75:
            return "good"
        if overall_score >= 0.55:
            return "adequate"
        if overall_score >= 0.30:
            return "weak"
        return "poor"

    @staticmethod
    def _recommended_action(overall_score: float, missing_reasoning: tuple) -> Optional[str]:
        # A SUGGESTION only — the future Adaptive Controller decides
        # independently whether to act on it (measurement/decision split,
        # architecture Chapter 18.1, preserved).
        if overall_score < 0.15:
            return "skip"
        if overall_score >= 0.55 and missing_reasoning:
            return "probe_deeper"
        if 0.25 <= overall_score < 0.55:
            return "clarify"
        return "move_on"

    # Which literal markers back each marker-scored dimension — used to name
    # the actual matched phrase in a claim's evidence, instead of the bare
    # dimension name (Phase 3 evaluation-fairness fix: feedback should cite
    # concrete parts of the answer, not restate the score).
    _MARKERS_BY_DIMENSION = {
        ARCHITECTURE: _ARCHITECTURE_MARKERS,
        TRADEOFFS: _TRADEOFF_MARKERS,
        DEBUGGING: _DEBUGGING_MARKERS,
        TESTING: _TESTING_MARKERS,
        SCALABILITY: _SCALABILITY_MARKERS,
    }

    @classmethod
    def _concrete_evidence(
        cls, dim_name: str, *, answer: str, sentences: list[str],
        mentioned_terms: list[str], missing_terms: list[str], has_ownership: bool,
    ) -> tuple[Optional[str], Optional[str]]:
        """Best-effort concrete evidence for one dimension: (strength_evidence,
        weakness_evidence), either of which may be None if nothing concrete
        is available for that side. Always a real fragment of the answer or
        a real term from the grounding — never invented content."""
        answer_lower = answer.lower()
        first_sentence = sentences[0] if sentences else answer[:120]

        if dim_name in cls._MARKERS_BY_DIMENSION:
            hit = next((m for m in cls._MARKERS_BY_DIMENSION[dim_name] if m in answer_lower), None)
            if hit is not None:
                containing = next((s for s in sentences if hit in s.lower()), first_sentence)
                return f'Referenced "{hit}" — "{containing.strip()[:160]}"', None
            return None, "The answer doesn't name this explicitly, though it may still be implied."

        if dim_name == TECHNICAL_DEPTH:
            if mentioned_terms:
                return f"Specifically mentioned {', '.join(mentioned_terms[:3])}.", None
            if missing_terms:
                return None, f"Didn't reference {', '.join(missing_terms[:3])} from this project."
            return None, None

        if dim_name == OWNERSHIP:
            if has_ownership:
                hit = next((m for m in _OWNERSHIP_MARKERS if m in answer_lower), None)
                if hit is not None:
                    return f'Used first-person ownership language ("{hit}").', None
            return None, "Described the work without first-person ownership language (e.g. \"I designed\", \"I built\")."

        if dim_name in (TECHNICAL_ACCURACY, RESUME_GROUNDING):
            return f'"{first_sentence.strip()[:160]}"', f'"{first_sentence.strip()[:160]}" — not closely aligned with the project as described.'

        if dim_name == COMPLETENESS:
            return f"Answered in {len(sentences)} sentence(s) covering multiple points.", "The answer was quite short — consider adding another sentence or two of detail."

        if dim_name == COMMUNICATION:
            return None, "The answer could be structured more clearly (e.g. a brief sequence of steps)."

        return None, None

    @classmethod
    def _claims(
        cls, dimensions: list[DimensionScore], request: EvaluationRequest, *,
        answer: str, sentences: list[str], mentioned_terms: list[str],
        missing_terms: list[str], has_ownership: bool,
    ) -> tuple[tuple, tuple]:
        strengths, weaknesses = [], []
        for d in dimensions:
            strength_evidence, weakness_evidence = cls._concrete_evidence(
                d.name, answer=answer, sentences=sentences, mentioned_terms=mentioned_terms,
                missing_terms=missing_terms, has_ownership=has_ownership,
            )
            if d.raw_score >= STRENGTH_THRESHOLD:
                strengths.append(EvidenceLinkedClaim(
                    claim=f"Strong {d.name.replace('_', ' ')}.",
                    dimension=d.name,
                    evidence=strength_evidence or f"Scored {d.raw_score:.0%} on {d.name.replace('_', ' ')}.",
                ))
            elif d.raw_score < WEAKNESS_THRESHOLD:
                weaknesses.append(EvidenceLinkedClaim(
                    claim=f"Weak {d.name.replace('_', ' ')}.",
                    dimension=d.name,
                    evidence=weakness_evidence or f"Scored only {d.raw_score:.0%} on {d.name.replace('_', ' ')}.",
                ))
        if not strengths:
            strengths.append(EvidenceLinkedClaim(
                claim="Attempted to address the question.",
                dimension=dimensions[0].name,
                evidence=f"Scored {dimensions[0].raw_score:.0%} on {dimensions[0].name}.",
            ))
        if not weaknesses:
            weaknesses.append(EvidenceLinkedClaim(
                claim="Minor areas for deeper elaboration.",
                dimension=dimensions[-1].name,
                evidence=f"Scored {dimensions[-1].raw_score:.0%} on {dimensions[-1].name}.",
            ))
        return tuple(strengths), tuple(weaknesses)

    @staticmethod
    def _missing_reasoning(dimensions: list[DimensionScore], missing_terms: list[str],
                            request: EvaluationRequest) -> tuple[MissingReasoningItem, ...]:
        category_by_dimension = {
            ARCHITECTURE: MissingReasoningCategory.ARCHITECTURE,
            TRADEOFFS: MissingReasoningCategory.TRADEOFF,
            OWNERSHIP: MissingReasoningCategory.OWNERSHIP,
            DEBUGGING: MissingReasoningCategory.DEBUGGING,
            TESTING: MissingReasoningCategory.TESTING,
            SCALABILITY: MissingReasoningCategory.SCALABILITY,
            COMMUNICATION: MissingReasoningCategory.COMMUNICATION,
        }
        items = []
        for d in dimensions:
            if d.name in category_by_dimension and d.raw_score < 0.4:
                items.append(MissingReasoningItem(
                    category=category_by_dimension[d.name],
                    explanation=f"the {d.name.replace('_', ' ')} behind this answer",
                    expected_because=(
                        f"the question targeted {request.reasoning_type.value} reasoning, which typically "
                        f"involves {d.name.replace('_', ' ')}"
                    ),
                    evidence=f"no {d.name.replace('_', ' ')} markers found in the answer",
                    severity=round(1.0 - d.raw_score, 3),
                ))
        if missing_terms:
            items.append(MissingReasoningItem(
                category=MissingReasoningCategory.EXAMPLE,
                explanation=f"specific mention of {', '.join(missing_terms[:2])}",
                expected_because=f"{request.specification.source_id!r} is described as using these technologies",
                evidence=f"{', '.join(missing_terms[:2])} not found in the answer",
                severity=0.5,
            ))
        return tuple(sorted(items, key=lambda i: -i.severity))

    @staticmethod
    def _concept_status(
        concept: str, answer: str, answer_lower: str, sentences: list[str],
    ) -> tuple[ConceptObservationStatus, Optional[str]]:
        """
        Approved reference-implementation heuristic for `concept_coverage`
        (Expected Concepts revision). Deliberately simple term/sentence
        matching — the same class of proxy this evaluator already uses
        elsewhere, and explicitly acknowledged in the approved RFC as
        insufficient ALONE for the long-term, fine-tuned evaluator (which
        will genuinely learn the demonstrated/superficial distinction
        rather than approximate it via sentence length). This is a
        temporary reference implementation, not the final answer.

        Never returns `evidence=None` for a non-OMITTED status — every
        DEMONSTRATED/SUPERFICIAL claim must cite where the concept was
        found (ConceptObservation's own "never invented" validator would
        reject a violation of this before it ever reached a caller).
        """
        concept_lower = concept.lower()
        containing = next((s for s in sentences if concept_lower in s.lower()), None)
        if containing is not None:
            extra_words = max(0, len(containing.split()) - len(concept_lower.split()))
            if extra_words >= 4:
                return ConceptObservationStatus.DEMONSTRATED, containing.strip()
            return ConceptObservationStatus.SUPERFICIAL, containing.strip()

        # Exact phrase not found in any single sentence — fall back to
        # token overlap (paraphrase tolerance), same idea as the legacy
        # discussion_engine._keyphrase_covers_term fallback.
        concept_tokens = set(concept_lower.split())
        answer_tokens = set(answer_lower.split())
        if concept_tokens and (concept_tokens & answer_tokens):
            return (
                ConceptObservationStatus.SUPERFICIAL,
                "related terminology found in the answer (not an exact phrase match)",
            )
        return ConceptObservationStatus.OMITTED, None
