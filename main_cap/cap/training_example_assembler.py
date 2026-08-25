"""
Training Example Assembler — Stage A Synthetic Dataset Generation Pipeline
(Dataset Design RFC Section 4/7, Promptbook RFC Section 10 — both APPROVED
AND FROZEN).

Combines a validated `GenerationOutput` with the `GenerationRecipe` that
produced it into a fully populated `TrainingExample`. Every label here is
RECIPE-derived ground truth (`label_source="synthetic_ground_truth"`) — this
module never invents a label the recipe didn't already specify, and never
calls an Evaluator (that would blur the "Evaluation never imports
Generation, Generation never performs evaluation" boundary the architecture
requires).

This module assumes its input has already passed
`generation_validation.validate_generation` — it does not re-validate.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from evaluation_result import ConceptObservationStatus
from generation_client import GenerationOutput
from generation_recipe import GenerationRecipe
from reasoning_dimension_relevance import relevant_dimensions
from training_example import (
    ConceptLabel,
    ContradictionLabel,
    DimensionLabel,
    MissingReasoningLabel,
    OverallLabel,
    ProvenanceSource,
    QualityTier,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
    TrainingExampleSyntheticMeta,
)

# Deterministic dimension-score band per quality tier — the ground-truth
# target every relevant dimension is labeled with for a given tier (Dataset
# Design RFC Section 4's rubric, applied as a label rather than a live
# judgment). Off-topic/contradictory map onto the tier their content was
# actually sampled at (off-topic gets its own floor; contradictory reuses
# GOOD, matching generation_recipe.sample_recipe's own "otherwise
# GOOD-quality" choice for contradictory content).
_TIER_DIMENSION_SCORE: dict[QualityTier, float] = {
    QualityTier.EXCELLENT: 0.90,
    QualityTier.GOOD: 0.70,
    QualityTier.ADEQUATE: 0.50,
    QualityTier.WEAK: 0.30,
    QualityTier.POOR: 0.12,
    QualityTier.OFF_TOPIC: 0.05,
    QualityTier.CONTRADICTORY: 0.70,
}

_TIER_OVERALL_GRADE: dict[QualityTier, str] = {
    QualityTier.EXCELLENT: "excellent",
    QualityTier.GOOD: "good",
    QualityTier.ADEQUATE: "adequate",
    QualityTier.WEAK: "weak",
    QualityTier.POOR: "poor",
    QualityTier.OFF_TOPIC: "off_topic",
    QualityTier.CONTRADICTORY: "contradictory",
}


def _dimension_labels(recipe: GenerationRecipe) -> tuple[DimensionLabel, ...]:
    score = _TIER_DIMENSION_SCORE[recipe.quality_tier]
    dims = relevant_dimensions(recipe.reasoning_type)
    return tuple(DimensionLabel(name=name, score=score) for name in sorted(dims))


def _concept_labels(recipe: GenerationRecipe, output: GenerationOutput) -> tuple[ConceptLabel, ...]:
    evidence_by_concept = {e.concept.strip().lower(): e.evidence for e in output.concept_evidence}
    labels = []
    for target in recipe.concept_targets:
        evidence = evidence_by_concept.get(target.concept.strip().lower())
        labels.append(ConceptLabel(
            concept=target.concept, status=target.status,
            evidence=evidence if target.status != ConceptObservationStatus.OMITTED else None,
        ))
    return tuple(labels)


def _missing_reasoning_labels(recipe: GenerationRecipe) -> tuple[MissingReasoningLabel, ...]:
    labels = []
    for target in recipe.reasoning_targets:
        if not target.present:
            continue
        category_label = target.category.replace("_", " ")
        labels.append(MissingReasoningLabel(
            category=target.category, present=True, severity=target.severity,
            explanation=f"the answer was deliberately generated to under-develop {category_label}",
        ))
    return tuple(labels)


def _contradiction_label(recipe: GenerationRecipe, output: GenerationOutput) -> ContradictionLabel:
    if not recipe.is_contradictory:
        return ContradictionLabel(contradiction_present=False)
    explanation = output.contradiction_note.strip() or f"a deliberate {recipe.contradiction_type.value} contradiction was introduced"
    return ContradictionLabel(
        contradiction_present=True, contradiction_type=recipe.contradiction_type, explanation=explanation,
    )


def _overall_label(recipe: GenerationRecipe) -> OverallLabel:
    score = _TIER_DIMENSION_SCORE[recipe.quality_tier]
    grade = _TIER_OVERALL_GRADE[recipe.quality_tier]
    return OverallLabel(score=score, grade=grade, rationale=f"Generated to target the {grade!r} synthetic quality tier.")


def assemble_training_example(
    recipe: GenerationRecipe,
    output: GenerationOutput,
    generation_prompt_id: str,
    prompt_version: str,
    generator_model: str,
    generation_batch_id: str,
) -> TrainingExample:
    """Assemble one fully-populated, recipe-labeled `TrainingExample`.
    Caller (`synthetic_generation_pipeline.py`) is responsible for having
    already validated `output` via `generation_validation.validate_generation`."""
    now = datetime.now(timezone.utc).isoformat()

    synthetic_meta = TrainingExampleSyntheticMeta(
        generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
        generator_model=generator_model, generation_batch_id=generation_batch_id,
        intended_quality_tier=recipe.quality_tier,
        intended_concept_inclusion=recipe.concept_targets,
        intended_reasoning_category_targets=recipe.reasoning_targets,
        is_off_topic=recipe.is_off_topic, is_contradictory=recipe.is_contradictory,
        contradiction_type=recipe.contradiction_type,
        diversity_seed=recipe.diversity_seed, style_seed=recipe.style_seed,
    )

    labels = TrainingExampleLabels(
        label_source="synthetic_ground_truth",
        dimension_labels=_dimension_labels(recipe),
        missing_reasoning_labels=_missing_reasoning_labels(recipe),
        concept_labels=_concept_labels(recipe, output),
        contradiction_label=_contradiction_label(recipe, output),
        overall_label=_overall_label(recipe),
    )

    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=f"train_{_uuid.uuid4().hex[:16]}", created_at=now),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.SYNTHETIC, collection_batch_id=generation_batch_id),
        inputs=TrainingExampleInputs(
            specification=recipe.specification, question_text=recipe.question_text,
            reasoning_type=recipe.reasoning_type, answer_text=output.answer_text,
            expected_concepts=recipe.expected_concepts,
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        synthetic=synthetic_meta,
        labels=labels,
    )
