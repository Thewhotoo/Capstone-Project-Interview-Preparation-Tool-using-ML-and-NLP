"""
Overall Single Evaluator — V3 Single-Overall-Score Architecture (isolated,
additive, NOT DEPLOYED).

`OverallSingleEvaluator` implements the SAME, UNCHANGED `evaluator.Evaluator`
Protocol every other evaluator in this codebase does (`HeuristicEvaluator`,
`TrainedEvaluator`, `HybridEvaluator`) — structural typing, no base class,
no special-casing anywhere in the Evaluation Engine.

WHAT IT COMBINES (per this redesign's spec):
  - `overall_score` / `grade` / `confidence` come EXCLUSIVELY from
    `overall_score_model.OverallScoreModel`'s single CORAL head — the
    learned ML prediction. Never touched by the heuristic diagnostics.
  - `dimensions` are the four canonical diagnostic scores from
    `heuristic_diagnostics.HeuristicDiagnosticsEngine` — explanatory only.
    Every one of them is constructed with `contributes_to_overall=False`
    (enforced by `HeuristicDiagnosticsEngine` itself) and this evaluator
    NEVER recomputes `overall_score` from them (no weighted-dimension-
    average formula here at all, unlike `TrainedEvaluator`/
    `HeuristicEvaluator` — see module docstring difference below). This is
    the explicit, tested guarantee that "heuristic scores must not be fed
    back into the DeBERTa prediction" and "must not overwrite the learned
    overall score."
  - `strengths`/`weaknesses` are built from those same four diagnostic
    dimensions (`HeuristicDiagnosticsEngine.claims`), so the feedback text
    a candidate sees is consistent with the dimension breakdown they see.

NOT DEPLOYED: this evaluator is not registered anywhere, not imported by
`deployment_evaluator.py`, `hybrid_evaluator.py`, or `evaluator_registry.py`,
and does not change which evaluator is currently active in production (A2
via `HybridEvaluator`, see `deployment_evaluator.py`). It exists purely as a
new, isolated, fully-tested implementation pending its own review/rollout
decision — same discipline `model_evaluator.TrainedEvaluator` followed
before A2's own cutover.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

import torch

from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS, HeuristicDiagnosticsEngine
from correctness_nli_scorer import degeneracy
from model_backbone import BackboneConfig, build_dimension_pair, bounded_grounding_to_text, tokenize_pair
from model_heads import coral_confidence, coral_predict
from overall_score_model import OverallScoreModel
from question_families import ReasoningType
from training_experimentation import Checkpoint

_CONFIDENCE_SOURCE_MODEL_DERIVED = "model_derived"

# ── Non-answer fairness gate ────────────────────────────────────────────────
# FORENSIC FIX (real-résumé test): on project questions with rich grounding, the
# CORAL head is answer-insensitive enough that a NON-ANSWER ("idk", "not sure",
# a one-word reply) rides the grounding to a middling/good score (observed
# "idk" scoring 0.5-0.75 across real résumés). A learned score must never let an
# empty or evasive answer inherit the question's context. This deterministic,
# model-free gate caps such answers to a poor score. It is conservative: it only
# fires on an explicit non-answer phrase, a <3-token reply, or text the
# deterministic `degeneracy` check flags (empty / keyword-dump / gibberish) — it
# never flags a normal, on-topic technical answer, however concise.
_NON_ANSWER_MARKERS = (
    "idk", "i don't know", "i dont know", "i do not know", "don't know", "dont know",
    "not sure", "no idea", "no clue", "can't remember", "cannot remember", "don't recall",
    "not familiar", "didn't work on", "did not work on", "beats me", "pass",
)


def _is_non_answer(answer_text: str) -> bool:
    raw = (answer_text or "").strip()
    if len(raw.split()) < 3:
        return True  # empty / one- or two-word reply is a non-answer to a technical question
    low = raw.lower()
    return any(m in low for m in _NON_ANSWER_MARKERS)


def _grade_from_score(score: float) -> str:
    """Same cutpoints every other evaluator in this codebase uses
    (`HeuristicEvaluator._grade`, `model_evaluator._grade_from_score`) —
    duplicated locally rather than imported, the same "deliberate
    independence between evaluator implementations" precedent already
    established throughout this codebase."""
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


class OverallSingleEvaluator:
    """`Evaluator` Protocol implementation backed by `OverallScoreModel`
    (learned overall score) + `HeuristicDiagnosticsEngine` (diagnostic
    dimension breakdown). Stateless per call, same contract every other
    evaluator implementation satisfies."""

    declared_dimensions = CANONICAL_DIMENSION_KEYS
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def __init__(
        self,
        checkpoint: Checkpoint,
        model: OverallScoreModel,
        tokenizer,
        backbone_config: BackboneConfig,
        diagnostics_engine: Optional[HeuristicDiagnosticsEngine] = None,
    ):
        self.checkpoint = checkpoint
        self.model = model
        self.tokenizer = tokenizer
        self.backbone_config = backbone_config
        self.diagnostics_engine = diagnostics_engine or HeuristicDiagnosticsEngine()
        self.name = f"overall-single-{checkpoint.model_version}"
        self.version = checkpoint.schema_version
        self.device = next(model.parameters()).device

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.model.eval()
        with torch.no_grad():
            # Phase 1 production input correction: use `bounded_grounding_to_text`
            # (NOT `grounding_to_text`) so the RELEVANT CONTEXT block stays inside
            # the short-grounding length distribution this deployed checkpoint was
            # trained on. A full résumé summary (~85-92 words) is ~4-6x longer than
            # anything in training and was shown to dominate the representation and
            # collapse answer sensitivity; bounding the free-text summary restores
            # it without retraining. Title/technologies/concepts/role/company are
            # preserved in full; only the free-text summary is capped. Everything
            # else about this input pair (question, expected_concepts, answer,
            # tokenization, model call) is unchanged. See model_backbone.py's
            # `bounded_grounding_to_text` note for the full forensic rationale.
            context_text, answer_text = build_dimension_pair(
                request.question_text,
                bounded_grounding_to_text(request.specification.grounding),
                request.expected_concepts,
                request.answer_text,
            )
            encoding = tokenize_pair(self.tokenizer, context_text, answer_text, self.backbone_config.max_length)
            padded = self.tokenizer.pad([encoding], return_tensors="pt")
            input_ids = padded["input_ids"].to(self.device)
            attention_mask = padded["attention_mask"].to(self.device)

            logits = self.model(input_ids, attention_mask)
            ordinal = int(coral_predict(logits)[0].item())
            model_confidence = float(coral_confidence(logits)[0].item())

            # ── The learned overall score — EXCLUSIVELY from the CORAL
            # head, never touched or recomputed from the heuristic
            # diagnostics below. ──
            overall_score = round(ordinal / (self.model.num_ordinal_classes - 1), 3)

            # Non-answer fairness gate (deterministic): a non-answer / degenerate
            # reply must not ride the grounding to a decent score. Downward-only;
            # never rescues or raises a real answer's learned score.
            gated_non_answer = _is_non_answer(request.answer_text) or degeneracy(request.answer_text).is_degenerate
            if gated_non_answer:
                overall_score = min(overall_score, 0.1)

            grade = _grade_from_score(overall_score)

            # ── Diagnostic dimensions — heuristic, explanatory only. Every
            # DimensionScore here is contributes_to_overall=False (enforced
            # by HeuristicDiagnosticsEngine itself); nothing below this
            # point is allowed to change overall_score/grade. ──
            dimensions = self.diagnostics_engine.compute(request)
            strengths, weaknesses = self.diagnostics_engine.claims(dimensions)

            reasoning = (
                f"Learned overall score: tier {ordinal}/4 ({overall_score:.0%}). "
                "Diagnostic breakdown (heuristic, does not affect this score):\n"
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
                model_version=(("backbone", self.backbone_config.hf_model_id),),
                dataset_version=self.checkpoint.dataset_version,
                training_date=self.checkpoint.created_at,
                dimensions=dimensions,
                overall_score=overall_score, grade=grade,
                confidence=round(model_confidence, 3), confidence_source=_CONFIDENCE_SOURCE_MODEL_DERIVED,
                confidence_rationale=(
                    "Derived from the single CORAL head's own logit entropy — the diagnostic "
                    "dimensions below are heuristic and explanatory only, and do not factor into "
                    "this confidence value."
                ),
                reasoning=reasoning,
                strengths=strengths, weaknesses=weaknesses,
                resume_grounding_score=0.0,
                calibration_version=None,
            )
