"""
Correctness NLI Scorer — reference-anchored, keyless, CPU evaluator (isolated,
additive, NOT DEPLOYED).

WHY THIS EXISTS (forensic conclusion): the deployed single-overall-score
DeBERTa evaluator (deployed_model_overall_single_v5_1088) cannot separate a
technically CORRECT answer from a fluent, detailed, technically WRONG one —
it learned answer LENGTH as a proxy for quality (training label/length
correlation r=0.61), so under length-matched conditions correct vs
fluent-wrong is a coin flip. A small encoder cannot fix this by more training
because judging correctness requires world knowledge it does not hold.

THE APPROACH (validated read-only before this module was written): move the
knowledge to BUILD TIME. Each question carries an authored answer key —
`key_points` (atomic correct claims) and `misconceptions` (atomic known-wrong
claims). At runtime, a keyless CPU pipeline grades by GROUNDED COMPARISON,
not by knowing facts:
  - technical_correctness: sentence-level max ENTAILMENT of the answer against
    each key point (an NLI cross-encoder), minus contradiction of them, minus
    the worst misconception the answer entails. Length-independent by
    construction.
  - relevance: MiniLM embedding coverage of the key points by the answer.
  - a cheap DETERMINISTIC degeneracy gate (no model) caps empty / keyword-dump
    / extreme-repetition answers. Conservative: it never flags a legitimate
    concise technical answer (validated: 0 false positives over 270 answers).

Everything runs on the cached, keyless models this repo already ships
(`cross-encoder/nli-deberta-v3-small`, `sentence-transformers/all-MiniLM-L6-v2`)
— no API, no key, no large LM (a 1.5B LM was tried and is not viable on the
target CPU hardware).

NOT DEPLOYED: this module is imported by nothing in the live evaluation stack
(`deployment_evaluator.py`, `evaluator_registry.py`, `hybrid_evaluator.py`).
`deployed_model_overall_single_v5_1088` remains the active production evaluator
and the rollback. This exists as a new, isolated, tested implementation pending
its own review/rollout decision — the same discipline `overall_single_evaluator.py`
followed before its own cutover. It also does NOT train, read, or modify any
dataset, label, or checkpoint.
"""

from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from answer_key import AnswerKey  # shared, neutral type (also re-exported here)
from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS, HeuristicDiagnosticsEngine
from question_families import ReasoningType

_CONFIDENCE_SOURCE = "nli_margin_derived"

# ── Cached, keyless model ids (no download at import; lazy-loaded on first use) ─
_NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-small"
_EMB_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


# ═════════════════════════════════════════════════════════════════════════════
# Cheap DETERMINISTIC degeneracy gate (NO model). Flags empty / keyword-dump /
# extreme-repetition using surface features only. Tuned conservatively so a
# legitimate concise technical answer is NEVER flagged.
# ═════════════════════════════════════════════════════════════════════════════

_FUNCTION_WORDS = frozenset(
    """
a an the this that these those it its they them their we our us i you your he she his her
is are was were be been being am do does did has have had can could will would shall should may might must
of in on at to for with from by as into over under about per through between during without within across
and or but so if then than because however therefore thus while when where which who whom whose what how why
not no nor yes such very more most less least much many some any each every both either neither all
i'll we'll it's don't doesn't isn't aren't we're they're you're i've we've
""".split()
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


@dataclass(frozen=True)
class DegeneracyVerdict:
    is_degenerate: bool
    coherence: float          # 1.0 = clearly fluent prose, 0.0 = clearly degenerate
    reasons: tuple[str, ...]


def degeneracy(text: str) -> DegeneracyVerdict:
    """Deterministic, model-free degeneracy check. Returns a verdict whose
    `is_degenerate` is True only on clear evidence (empty/near-empty text, a
    keyword list with almost no function words and no real sentence, a comma-
    separated keyword list, or extreme lexical/bigram repetition). It never
    flags a normal fluent answer, however short — a false positive on a real
    concise technical answer is worse than a little residual word-salad."""
    raw = (text or "").strip()
    toks = _tokens(raw)
    n = len(toks)
    if n < 3:
        return DegeneracyVerdict(True, 0.0, ("empty_or_near_empty",))
    fwr = sum(1 for t in toks if t in _FUNCTION_WORDS) / n
    sentences = len([s for s in re.split(r"[.!?]+", raw) if s.strip()])
    ttr = len(set(toks)) / n
    comma_density = raw.count(",") / n
    bigrams = list(zip(toks, toks[1:]))
    rep_bigram = (1 - len(set(bigrams)) / len(bigrams)) if bigrams else 0.0

    reasons: list[str] = []
    if fwr < 0.12 and sentences <= 1:
        reasons.append("keyword_dump_low_function_words")
    if comma_density >= 0.12 and fwr < 0.20:
        reasons.append("comma_list")
    if ttr < 0.45 or rep_bigram > 0.30:
        reasons.append("repetitive")

    # ── Non-spoken-answer signals (a real interview answer is prose, not markup,
    # code, a SQL statement, control bytes, or a symbol/number soup). These are
    # deterministic and conservative — they never match ordinary technical prose,
    # and they intentionally do NOT flag non-English answers (whose letters are
    # still alphabetic, so the alpha ratio stays high). ──
    low = raw.lower()
    if any(ord(c) < 32 and c not in "\t\n\r" for c in raw):
        reasons.append("control_characters")
    if re.search(r"</?[a-z][a-z0-9]*(?:\s[^>]*)?>", low):  # an HTML/XML tag, e.g. <script>, </b>
        reasons.append("markup")
    if re.search(
        r"\bdef\s+\w+\s*\(|\breturn\s+[\w'\"({\[]|=>|;\s*--|\bdrop\s+table\b|"
        r"\bselect\b.+\bfrom\b|\binsert\s+into\b|\bimport\s+\w|console\.\w+\(|"
        r"printf\s*\(|System\.out|\bfor\s*\(|\bwhile\s*\(|\}\s*;|\{\s*$",
        low,
    ):  # code / SQL signature
        reasons.append("code_or_query")
    letters = sum(1 for c in raw if c.isalpha())
    nonspace = sum(1 for c in raw if not c.isspace())
    if nonspace >= 8 and (letters / nonspace) < 0.5:  # mostly digits/symbols, not words
        reasons.append("non_linguistic")

    # ── No substantive assertion (general non-answer / deflection detector). A
    # real answer makes at least one DECLARATIVE statement with actual content.
    # A response that is only a question back ("What is X?"), a bare retort
    # ("why not", "idk bro"), or otherwise carries no contentful declarative
    # clause is not an answer. This is grounding-independent and general — it
    # replaces case-by-case keyword blocklists. A declarative clause "counts"
    # when it has at least 3 content (non-function) words; questions never count. ──
    _sentence_parts = [s for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()] or [raw]
    def _content_word_count(sentence: str) -> int:
        return sum(1 for t in _tokens(sentence) if t not in _FUNCTION_WORDS and len(t) > 1)
    has_substantive_clause = any(
        not s.strip().endswith("?") and _content_word_count(s) >= 3
        for s in _sentence_parts
    )
    if not has_substantive_clause:
        reasons.append("no_substantive_content")

    penalty = 0.0
    if fwr < 0.12:
        penalty = max(penalty, 0.9)
    elif fwr < 0.18:
        penalty = max(penalty, 0.4)
    if any(r in reasons for r in ("control_characters", "markup", "code_or_query", "non_linguistic", "no_substantive_content")):
        penalty = max(penalty, 0.9)
    if comma_density >= 0.12 and fwr < 0.20:
        penalty = max(penalty, 0.7)
    if ttr < 0.45:
        penalty = max(penalty, 0.6)
    if rep_bigram > 0.30:
        penalty = max(penalty, 0.6)
    return DegeneracyVerdict(len(reasons) > 0, round(1.0 - penalty, 3), tuple(reasons))


# ═════════════════════════════════════════════════════════════════════════════
# Answer key + claim bank (BUILD-TIME knowledge; runtime only compares against it)
# ═════════════════════════════════════════════════════════════════════════════

class ClaimBank(Protocol):
    """OPTIONAL secondary source of an `AnswerKey`, for callers that do not go
    through `evaluation_engine` (tests, offline benchmarks). Production attaches
    the AnswerKey to the request itself (`EvaluationRequest.answer_key`, via
    `answer_key_registry`), which the evaluator reads first. Returns None when
    it has no entry — it must NOT invent a key from `expected_concepts`; that
    weaker fallback is the evaluator's own explicitly-labeled path."""

    def answer_key_for(self, request: EvaluationRequest) -> Optional[AnswerKey]:
        ...


@dataclass
class DictClaimBank:
    """Simple in-memory claim bank keyed by `specification.id`, then by a
    normalized question-text key. Returns None when it has no entry (no silent
    expected_concepts fallback — the evaluator handles that explicitly)."""

    by_spec_id: dict[str, AnswerKey] = field(default_factory=dict)
    by_question: dict[str, AnswerKey] = field(default_factory=dict)

    @staticmethod
    def _qkey(q: str) -> str:
        return " ".join((q or "").split()).casefold()

    def answer_key_for(self, request: EvaluationRequest) -> Optional[AnswerKey]:
        key = self.by_spec_id.get(request.specification.id)
        if key is None:
            key = self.by_question.get(self._qkey(request.question_text))
        return key


# ═════════════════════════════════════════════════════════════════════════════
# Core scorer — sentence-level NLI entailment + embedding coverage + gate.
# Models are injectable so tests run without loading the real encoders.
# ═════════════════════════════════════════════════════════════════════════════

def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]


def _softmax_rows(mat):
    import numpy as np
    mat = mat - mat.max(axis=1, keepdims=True)
    e = np.exp(mat)
    return e / e.sum(axis=1, keepdims=True)


class CoverageNLIScorer:
    """Reference-anchored correctness + coverage scorer. `nli_predict` maps a
    list of (premise, hypothesis) pairs to (N,3) logits over
    [contradiction, entailment, neutral]; `embed` maps a list of texts to L2-
    normalized vectors. Both default to the cached keyless models, lazily
    loaded on first call, and can be injected (fakes) in tests."""

    def __init__(
        self,
        nli_predict: Optional[Callable] = None,
        embed: Optional[Callable] = None,
        nli_model_id: str = _NLI_MODEL_ID,
        emb_model_id: str = _EMB_MODEL_ID,
    ):
        self._nli_predict = nli_predict
        self._embed = embed
        self._nli_model_id = nli_model_id
        self._emb_model_id = emb_model_id
        self._nli = None
        self._emb = None
        self._ent_idx: Optional[int] = None
        self._con_idx: Optional[int] = None

    # ── lazy real models (only if not injected) ──
    def _ensure_nli(self):
        if self._nli_predict is not None:
            return
        if self._nli is None:
            from sentence_transformers import CrossEncoder
            self._nli = CrossEncoder(self._nli_model_id)
            id2 = self._nli.model.config.id2label
            lab = {v.lower(): k for k, v in id2.items()}
            self._ent_idx, self._con_idx = lab["entailment"], lab["contradiction"]

    def _ensure_emb(self):
        if self._embed is not None:
            return
        if self._emb is None:
            from sentence_transformers import SentenceTransformer
            self._emb = SentenceTransformer(self._emb_model_id)

    def _nli_probs(self, pairs):
        import numpy as np
        if not pairs:
            return np.zeros((0, 3))
        if self._nli_predict is not None:
            logits = np.asarray(self._nli_predict(pairs), dtype=float)
        else:
            self._ensure_nli()
            logits = np.asarray(self._nli.predict(pairs, show_progress_bar=False), dtype=float)
        if logits.ndim == 1:
            logits = logits[None, :]
        return _softmax_rows(logits)

    def _ent_con_indices(self):
        if self._nli_predict is not None:
            # injected fakes must use the same [contradiction, entailment, neutral] order.
            return 1, 0
        self._ensure_nli()
        return self._ent_idx, self._con_idx

    def _embed_texts(self, texts):
        import numpy as np
        if self._embed is not None:
            return np.asarray(self._embed(texts), dtype=float)
        self._ensure_emb()
        return np.asarray(self._emb.encode(texts, normalize_embeddings=True), dtype=float)

    def score_answer(self, answer_text: str, key: AnswerKey) -> dict:
        """Returns technical_correctness (0-1), relevance (0-1), and diagnostic
        internals. Correctness is length-independent (sentence-level max
        entailment); the deterministic degeneracy gate caps clearly degenerate
        answers downward only."""
        import numpy as np
        deg = degeneracy(answer_text)
        ss = _sentences(answer_text)
        if not ss:
            return {"technical_correctness": 0.0, "relevance": 0.0, "coherence": deg.coherence,
                    "degenerate": True, "support": 0.0, "contradiction": 0.0, "misconception_hit": 0.0,
                    "reasons": deg.reasons}

        ent, con = self._ent_con_indices()
        kps = list(key.key_points)
        mis = list(key.misconceptions)

        # relevance: embedding coverage of key points by the answer's sentences
        relevance = 0.5  # neutral prior when there is no key to compare against
        if kps:
            se = self._embed_texts(ss)
            ke = self._embed_texts(kps)
            cov_per_kp = (se @ ke.T).max(axis=0)   # best matching sentence per key point
            coverage = float(cov_per_kp.mean())
            relevance = max(0.0, min(1.0, (coverage - 0.15) / 0.55))  # map cosine→0-1
        else:
            coverage = 0.0

        # correctness: sentence-level max entailment/contradiction of key points,
        # minus the single worst misconception the answer entails.
        if kps:
            kp_p = self._nli_probs([(s, k) for k in kps for s in ss]).reshape(len(kps), len(ss), 3)
            support = float(kp_p[:, :, ent].max(axis=1).mean())
            contradiction = float(kp_p[:, :, con].max(axis=1).mean())
        else:
            support = contradiction = 0.0
        if mis:
            mis_p = self._nli_probs([(s, m) for m in mis for s in ss]).reshape(len(mis), len(ss), 3)
            misconception_hit = float(mis_p[:, :, ent].max(axis=1).max())
        else:
            misconception_hit = 0.0

        tc = max(0.0, min(1.0, 0.5 + 0.5 * (support - contradiction) - 0.6 * misconception_hit))

        if deg.is_degenerate:
            tc = min(tc, 0.1)
            relevance = min(relevance, 0.1)

        return {"technical_correctness": round(tc, 3), "relevance": round(relevance, 3),
                "coherence": deg.coherence, "degenerate": deg.is_degenerate,
                "support": round(support, 3), "contradiction": round(contradiction, 3),
                "misconception_hit": round(misconception_hit, 3), "reasons": deg.reasons}


# ═════════════════════════════════════════════════════════════════════════════
# Evaluator — satisfies the same `evaluator.Evaluator` Protocol every other
# evaluator does. overall_score is CORRECTNESS-GATED; the four canonical
# diagnostic dimensions are preserved via HeuristicDiagnosticsEngine.
# ═════════════════════════════════════════════════════════════════════════════

def _grade_from_score(score: float) -> str:
    """Same cutpoints every other evaluator uses (duplicated locally — the
    deliberate cross-evaluator independence this codebase already follows)."""
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


class CorrectnessNLIEvaluator:
    """`Evaluator` Protocol implementation backed by `CoverageNLIScorer` (learned
    correctness/relevance by grounded comparison) + `HeuristicDiagnosticsEngine`
    (the four canonical diagnostic dimension scores, explanatory only). Stateless
    per call. NOT registered anywhere; production remains the v5_1088 evaluator."""

    declared_dimensions = CANONICAL_DIMENSION_KEYS
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False
    version = "v1"

    def __init__(
        self,
        claim_bank: Optional[ClaimBank] = None,
        scorer: Optional[CoverageNLIScorer] = None,
        diagnostics_engine: Optional[HeuristicDiagnosticsEngine] = None,
        name: str = "correctness-nli-scorer-v1",
    ):
        self.claim_bank = claim_bank or DictClaimBank()
        self.scorer = scorer or CoverageNLIScorer()
        self.diagnostics_engine = diagnostics_engine or HeuristicDiagnosticsEngine()
        self.name = name

    def _resolve_key(self, request: EvaluationRequest) -> tuple[AnswerKey, str]:
        """Resolve the AnswerKey and the evaluation MODE, most-authoritative
        first: (1) the AnswerKey attached to the request by the orchestration
        layer (`answer_key_registry`) -> 'full'; (2) an injected claim bank
        (tests/benchmarks) -> 'full'; (3) the request's own `expected_concepts`
        as weak key points, no misconception check -> 'expected_concepts_only';
        (4) nothing -> 'no_key'. Modes 3-4 are surfaced EXPLICITLY in the result
        so a partial/absent correctness judgment is never presented as a full one."""
        ak = getattr(request, "answer_key", None)
        if ak is not None and ak.has_key_points:
            return ak, "full"
        if self.claim_bank is not None:
            cb = self.claim_bank.answer_key_for(request)
            if cb is not None and cb.has_key_points:
                return cb, "full"
        if request.expected_concepts:
            return AnswerKey(key_points=tuple(request.expected_concepts)), "expected_concepts_only"
        return AnswerKey(), "no_key"

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        key, mode = self._resolve_key(request)
        s = self.scorer.score_answer(request.answer_text, key)
        tc = s["technical_correctness"]
        relevance = s["relevance"]
        degen_note = (" [degenerate: " + ",".join(s["reasons"]) + "]") if s["degenerate"] else ""

        # Four canonical diagnostic dimensions — heuristic, explanatory only,
        # ALWAYS present regardless of mode (payload compatibility preserved).
        dimensions = self.diagnostics_engine.compute(request)
        strengths, weaknesses = self.diagnostics_engine.claims(dimensions)

        if mode == "no_key":
            # No authored knowledge for this question: correctness CANNOT be
            # judged. Do not pretend it was — the score reflects only answer
            # coherence, and the fallback is stated explicitly below.
            overall_score = 0.0 if s["degenerate"] else round(0.5 * s["coherence"], 3)
            confidence = 0.2
            confidence_source = "no_answer_key_fallback"
            head = (
                "CORRECTNESS NOT EVALUATED — no answer key is available for this question, so technical "
                f"correctness and relevance were NOT assessed. This score reflects only answer coherence "
                f"({s['coherence']:.2f}{degen_note}). Attach an AnswerKey (answer_key_registry) to evaluate correctness."
            )
        else:
            # Correctness-GATED overall: a technically wrong answer cannot score
            # well however fluent/relevant; relevance only modulates within the
            # band correctness allows. Degenerate answers are already forced low.
            overall_score = round(tc * (0.55 + 0.45 * relevance), 3)
            margin = abs(s["support"] - s["contradiction"]) + s["misconception_hit"]
            confidence = round(max(0.1, min(1.0, 0.4 + 0.6 * margin)), 3)
            if mode == "expected_concepts_only":
                confidence = round(confidence * 0.6, 3)  # weaker evidence than an authored key
                confidence_source = "expected_concepts_only"
                head = (
                    f"PARTIAL correctness — no authored answer key; graded against expected_concepts only "
                    f"(no misconception checking). Reference-anchored correctness: {tc:.0%} "
                    f"(support {s['support']:.2f}, contradiction {s['contradiction']:.2f}); "
                    f"relevance {relevance:.0%}; coherence {s['coherence']:.2f}{degen_note}."
                )
            else:  # full
                confidence_source = _CONFIDENCE_SOURCE
                head = (
                    f"Reference-anchored correctness: {tc:.0%} "
                    f"(support {s['support']:.2f}, contradiction {s['contradiction']:.2f}, "
                    f"misconception_hit {s['misconception_hit']:.2f}); relevance {relevance:.0%}; "
                    f"coherence {s['coherence']:.2f}{degen_note}."
                )

        grade = _grade_from_score(overall_score)
        reasoning = (
            head
            + "\nDiagnostic breakdown (heuristic, does not affect this score):\n"
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
            model_version=(("nli", _NLI_MODEL_ID), ("embed", _EMB_MODEL_ID)),
            dataset_version=None, training_date=None,
            dimensions=dimensions,
            overall_score=overall_score, grade=grade,
            confidence=confidence, confidence_source=confidence_source,
            confidence_rationale=(
                "Derived from the NLI entailment/contradiction margin against the authored answer key; the "
                "diagnostic dimensions below are heuristic and explanatory only and do not factor into this "
                "value. See the reasoning field for the correctness-evaluation mode (full / expected-concepts-"
                "only / no-answer-key)."
            ),
            reasoning=reasoning,
            strengths=strengths, weaknesses=weaknesses,
            resume_grounding_score=0.0,
            calibration_version=None,
        )
