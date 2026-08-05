"""
Trained Evaluator — Model-Implementation Layer (see model_backbone.py's
docstring for this layer's overall provenance/approval history).

`TrainedEvaluator` implements the SAME, UNCHANGED `evaluator.Evaluator`
Protocol `HeuristicEvaluator` implements — no base class, no interface
change, no special-casing anywhere in the Evaluation Engine. This is the
whole point of `Evaluator` being a structural Protocol.

Contradiction detection is REUSED, never trained (frozen ML Architecture RFC
decision — same off-the-shelf NLI cross-encoder `heuristic_evaluator.py`
already uses), reimplemented locally rather than imported — same
"deliberate independence between evaluator implementations" precedent
`heuristic_evaluator.py` itself documents relative to `discussion_engine.py`.

PROMOTION: `promote_trained_model` is a thin glue function over the
UNCHANGED `evaluator_registry.register_evaluator` — no new registration
mechanism. It refuses to register a `PromotionDecision` that wasn't
approved.

`confidence_source="model_derived"` (approved value) is used as a raw
string literal, NOT added as a new attribute on `evaluation_result.py`'s
`ConfidenceSource` class — that class's own docstring says new sources are
added "on evaluator implementations," never as an edit to that shared,
frozen module. `_CONFIDENCE_SOURCE_MODEL_DERIVED` below is this module's own
local constant for it.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

import torch

from evaluation_request import EvaluationRequest
from evaluation_result import (
    ConceptObservation,
    ConceptObservationStatus,
    DimensionScore,
    EvaluationResult,
    EvidenceLinkedClaim,
    MissingReasoningItem,
)
from evaluator_registry import register_evaluator
from model_backbone import BackboneConfig, tokenize_pair
from model_heads import _MISSING_REASONING_CATEGORIES, MultiTaskModel, coral_confidence, coral_predict
from question_families import ReasoningType
from reasoning_dimension_relevance import (
    ALL_DIMENSIONS,
    COMMUNICATION,
    COMPLETENESS,
    RESUME_GROUNDING,
    TECHNICAL_ACCURACY,
    contributes_by_default,
    relevant_dimensions,
)
from training_experimentation import Checkpoint, PromotionDecision

logger = logging.getLogger(__name__)

_ORDINAL_GRADES: tuple[str, ...] = ("poor", "weak", "adequate", "good", "excellent")
_CONFIDENCE_SOURCE_MODEL_DERIVED = "model_derived"

# Duplicated locally rather than imported from model_dataset.py (same
# "deliberate independence between modules" precedent used throughout this
# codebase) -- must match ConceptObservationHead's training-time label order.
_CONCEPT_STATUS_ORDER: tuple[ConceptObservationStatus, ...] = (
    ConceptObservationStatus.DEMONSTRATED, ConceptObservationStatus.SUPERFICIAL, ConceptObservationStatus.OMITTED,
)

_NLI_MODEL_NAME = "cross-encoder/nli-MiniLM2-L6-H768"
_CONTRADICTION_THRESHOLD = 0.5


def _grade_from_score(score: float) -> str:
    """Same cutpoints as `HeuristicEvaluator._grade` (duplicated
    intentionally, not imported — see module docstring). Kept in sync with
    that function's Phase 3 heuristic-calibration review update."""
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


class _LazyNliModel:
    """Reuses the same off-the-shelf NLI cross-encoder
    `heuristic_evaluator._contradiction_flag` already uses — frozen ML
    Architecture RFC decision: contradiction detection is reused, never
    fine-tuned."""

    _model = None

    @classmethod
    def get(cls):
        if cls._model is None:
            try:
                from sentence_transformers import CrossEncoder
                cls._model = CrossEncoder(_NLI_MODEL_NAME)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("NLI cross-encoder unavailable, contradiction detection disabled: %s", e)
                cls._model = False
        return cls._model if cls._model is not False else None


def _contradiction_flag(answer: str, grounding_text: str) -> bool:
    model = _LazyNliModel.get()
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


def _claims(dimensions: list[DimensionScore]) -> tuple[tuple[EvidenceLinkedClaim, ...], tuple[EvidenceLinkedClaim, ...]]:
    strengths, weaknesses = [], []
    for d in dimensions:
        if d.raw_score >= 0.65:
            strengths.append(EvidenceLinkedClaim(
                claim=f"Strong {d.name.replace('_', ' ')}.", dimension=d.name,
                evidence=f"Model-predicted tier {d.raw_score:.0%}.",
            ))
        elif d.raw_score < 0.35:
            weaknesses.append(EvidenceLinkedClaim(
                claim=f"Weak {d.name.replace('_', ' ')}.", dimension=d.name,
                evidence=f"Model-predicted tier only {d.raw_score:.0%}.",
            ))
    if not strengths and dimensions:
        strengths.append(EvidenceLinkedClaim(
            claim="Attempted to address the question.", dimension=dimensions[0].name,
            evidence=f"Model-predicted tier {dimensions[0].raw_score:.0%} on {dimensions[0].name}.",
        ))
    if not weaknesses and dimensions:
        weaknesses.append(EvidenceLinkedClaim(
            claim="Minor areas for deeper elaboration.", dimension=dimensions[-1].name,
            evidence=f"Model-predicted tier {dimensions[-1].raw_score:.0%} on {dimensions[-1].name}.",
        ))
    return tuple(strengths), tuple(weaknesses)


class TrainedEvaluator:
    """`Evaluator` Protocol implementation backed by a real, loaded
    `MultiTaskModel`. Stateless per call (the model is in `eval()` mode and
    never mutated by `.evaluate()`), same statelessness contract
    `HeuristicEvaluator` satisfies."""

    declared_dimensions = ALL_DIMENSIONS
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def __init__(self, checkpoint: Checkpoint, model: MultiTaskModel, tokenizer, backbone_config: BackboneConfig):
        self.checkpoint = checkpoint
        self.model = model
        self.tokenizer = tokenizer
        self.backbone_config = backbone_config
        self.name = f"trained-{checkpoint.model_version}"
        self.version = checkpoint.schema_version
        # Portability (Colab/GPU vs local/CPU, session 10): inferred from
        # the model itself rather than a separate constructor argument, so
        # there is no way to pass a device that disagrees with where the
        # model actually lives. Whatever device train_model / the caller
        # already moved the model to (cpu locally, cuda on Colab) is what
        # this evaluator's own tensors are moved to before every forward
        # pass -- no caller-side wiring required either way.
        self.device = next(model.parameters()).device

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.model.eval()
        with torch.no_grad():
            main_encoding = tokenize_pair(
                self.tokenizer, request.question_text, request.answer_text, self.backbone_config.max_length,
            )
            main_batch = self.tokenizer.pad([main_encoding], return_tensors="pt")
            main_input_ids = main_batch["input_ids"].to(self.device)
            main_attention_mask = main_batch["attention_mask"].to(self.device)
            outputs = self.model.forward_dimensions(main_input_ids, main_attention_mask)

            relevant = relevant_dimensions(request.reasoning_type)
            # Proportional, not uniform, weighting -- same Phase 3
            # evaluation-fairness fix as heuristic_evaluator.py's `evaluate()`
            # (see that module for the full rationale). The four
            # ALWAYS-relevant dimensions carry more weight than the 1-2 extra
            # dimensions a reasoning_type pulls in on top, since those extras
            # weren't necessarily what THIS specific question asked about.
            always_relevant = {TECHNICAL_ACCURACY, COMMUNICATION, COMPLETENESS, RESUME_GROUNDING}
            _ALWAYS_WEIGHT = 1.5
            _EXTRA_WEIGHT = 1.0
            raw_weights = {
                name: (_ALWAYS_WEIGHT if name in always_relevant else _EXTRA_WEIGHT)
                for name in relevant
            }
            weight_total = sum(raw_weights.values())

            dimensions: list[DimensionScore] = []
            for name in ALL_DIMENSIONS:
                if name not in relevant:
                    continue
                logits = outputs["dimension_logits"][name]
                ordinal = int(coral_predict(logits)[0].item())
                confidence = float(coral_confidence(logits)[0].item())
                raw_score = ordinal / (self.model.num_ordinal_classes - 1)
                dimensions.append(DimensionScore(
                    name=name, raw_score=round(raw_score, 3),
                    weight_used=round(raw_weights[name] / weight_total, 4),
                    confidence=round(confidence, 3), confidence_source=_CONFIDENCE_SOURCE_MODEL_DERIVED,
                    contributes_to_overall=contributes_by_default(name),
                    evidence_refs=(request.specification.source_id,),
                ))

            contributing = [d for d in dimensions if d.contributes_to_overall]
            overall_score = (
                sum(d.raw_score * d.weight_used for d in contributing) / sum(d.weight_used for d in contributing)
                if contributing else 0.0
            )
            overall_score = round(max(0.0, min(1.0, overall_score)), 3)
            grade = _grade_from_score(overall_score)

            concept_coverage = []
            for concept in request.expected_concepts:
                concept_encoding = tokenize_pair(
                    self.tokenizer, request.answer_text, concept, self.backbone_config.max_length,
                )
                concept_batch = self.tokenizer.pad([concept_encoding], return_tensors="pt")
                concept_input_ids = concept_batch["input_ids"].to(self.device)
                concept_attention_mask = concept_batch["attention_mask"].to(self.device)
                concept_logits = self.model.forward_concept(concept_input_ids, concept_attention_mask)
                probs = torch.softmax(concept_logits, dim=1)[0]
                predicted_index = int(torch.argmax(probs).item())
                status = _CONCEPT_STATUS_ORDER[predicted_index]
                confidence = float(probs[predicted_index].item())
                evidence = None if status == ConceptObservationStatus.OMITTED else f"model-derived observation for {concept!r}"
                concept_coverage.append(ConceptObservation(
                    concept=concept, status=status, evidence=evidence,
                    confidence=round(confidence, 3), confidence_source=_CONFIDENCE_SOURCE_MODEL_DERIVED,
                ))

            presence_probs = torch.sigmoid(outputs["presence_logits"])[0]
            severity_pred = outputs["severity_pred"][0]
            missing_reasoning = []
            for j, category in enumerate(_MISSING_REASONING_CATEGORIES):
                if float(presence_probs[j].item()) > 0.5:
                    severity = float(max(0.0, min(1.0, severity_pred[j].item())))
                    missing_reasoning.append(MissingReasoningItem(
                        category=category,
                        explanation=f"the model predicts {category.replace('_', ' ')} is under-addressed",
                        expected_because=(
                            f"reasoning_type={request.reasoning_type.value} typically involves "
                            f"{category.replace('_', ' ')}"
                        ),
                        evidence="model-derived prediction from the shared missing-reasoning head",
                        severity=round(severity, 3),
                    ))
            missing_reasoning.sort(key=lambda i: -i.severity)

            contradiction = _contradiction_flag(request.answer_text, _grounding_text(request.specification))

            overall_confidence = round(sum(d.confidence for d in dimensions) / len(dimensions), 3) if dimensions else 0.0
            strengths, weaknesses = _claims(dimensions)
            reasoning = "\n".join(f"{d.name}: {d.raw_score:.0%}" for d in dimensions)

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
                dimensions=tuple(dimensions),
                overall_score=overall_score, grade=grade,
                confidence=overall_confidence, confidence_source=_CONFIDENCE_SOURCE_MODEL_DERIVED,
                confidence_rationale=(
                    f"Derived from CORAL logit entropy across {len(dimensions)} relevant dimensions."
                ),
                reasoning=reasoning,
                strengths=strengths, weaknesses=weaknesses,
                missing_reasoning=tuple(missing_reasoning),
                concept_coverage=tuple(concept_coverage),
                contradiction_detected=contradiction,
                contradiction_explanation=(
                    "The answer may conflict with what the resume/grounding states." if contradiction else None
                ),
                resume_grounding_score=0.0,
                calibration_version=None,
            )


def promote_trained_model(
    checkpoint: Checkpoint,
    decision: PromotionDecision,
    trained_evaluator: TrainedEvaluator,
    sample_request: Optional[EvaluationRequest] = None,
    make_active: bool = True,
) -> None:
    """
    Thin glue over the UNCHANGED `evaluator_registry.register_evaluator` —
    no new registration mechanism. Refuses to register a rejected
    `PromotionDecision`.
    """
    if not decision.approved:
        raise ValueError(
            f"cannot promote checkpoint {checkpoint.model_version!r}: promotion decision was not approved "
            f"({decision.rationale})"
        )
    register_evaluator(trained_evaluator, sample_request=sample_request, make_active=make_active)
