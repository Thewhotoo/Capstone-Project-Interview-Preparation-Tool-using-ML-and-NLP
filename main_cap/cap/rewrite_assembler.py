"""
Rewrite Assembler — Experiment 4 (Rewrite Augmentation) Stage.

Mirrors `training_example_assembler.py`'s role (combine a validated output
with its recipe into a fully populated `TrainingExample`) but for a rewrite:
combines a validated rewrite `GenerationOutput` with its SOURCE
`TrainingExample` into a NEW `TrainingExample` that inherits every label
from the source and only replaces `answer_text` plus adds provenance.

This module assumes its input has already passed
`rewrite_validation.validate_rewrite` — it does not re-validate (same
"assembler trusts its caller's validation" contract
`training_example_assembler.py` already establishes).

WHAT IS COPIED VERBATIM from the source example (never recomputed, since
none of it depends on wording): `labels.dimension_labels`,
`labels.missing_reasoning_labels`, `labels.overall_label`,
`inputs.specification`, `inputs.question_text`, `inputs.reasoning_type`,
`inputs.expected_concepts`, `privacy`.

WHAT IS REBUILT from the rewrite's own output (so evidence/explanation text
stays grounded in what the rewrite actually says, not stale text from a
different answer — same "evidence must reflect the actual text" discipline
`training_example_assembler.py` already applies to freshly generated
examples): `labels.concept_labels`, `labels.contradiction_label`,
`inputs.answer_text`.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from evaluation_result import ConceptObservationStatus
from generation_client import GenerationOutput
from rewrite_validation import recipe_from_source_example
from training_example import (
    ConceptLabel,
    ContradictionLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExampleProvenance,
    TrainingExampleSyntheticMeta,
)


def _concept_labels_for_rewrite(recipe, output: GenerationOutput) -> tuple[ConceptLabel, ...]:
    """Rebuilt from the REWRITE's own `concept_evidence`, not copied from
    the source — same construction `training_example_assembler._concept_labels`
    already uses for freshly generated examples, duplicated locally per this
    codebase's "deliberate independence between pipeline stages" precedent
    rather than importing that private function."""
    evidence_by_concept = {e.concept.strip().lower(): e.evidence for e in output.concept_evidence}
    labels = []
    for target in recipe.concept_targets:
        evidence = evidence_by_concept.get(target.concept.strip().lower())
        labels.append(ConceptLabel(
            concept=target.concept, status=target.status,
            evidence=evidence if target.status != ConceptObservationStatus.OMITTED else None,
        ))
    return tuple(labels)


def _contradiction_label_for_rewrite(recipe, output: GenerationOutput) -> ContradictionLabel:
    """Rebuilt from the REWRITE's own `contradiction_note`, same rationale
    as `_concept_labels_for_rewrite` above."""
    if not recipe.is_contradictory:
        return ContradictionLabel(contradiction_present=False)
    explanation = output.contradiction_note.strip() or f"a deliberate {recipe.contradiction_type.value} contradiction was introduced"
    return ContradictionLabel(
        contradiction_present=True, contradiction_type=recipe.contradiction_type, explanation=explanation,
    )


def assemble_rewritten_example(
    source_example: TrainingExample,
    output: GenerationOutput,
    style: str,
    generation_prompt_id: str,
    prompt_version: str,
    generator_model: str,
    generation_batch_id: str,
) -> TrainingExample:
    """Assemble one fully-populated `TrainingExample` for a validated
    rewrite. Caller (`rewrite_generation_pipeline.py`) is responsible for
    having already validated `output` via
    `rewrite_validation.validate_rewrite`."""
    if source_example.synthetic is None:
        raise ValueError("cannot assemble a rewrite from a non-synthetic source example")
    recipe = recipe_from_source_example(source_example)
    now = datetime.now(timezone.utc).isoformat()
    source_synthetic = source_example.synthetic

    synthetic_meta = TrainingExampleSyntheticMeta(
        generation_prompt_id=generation_prompt_id, prompt_version=prompt_version,
        generator_model=generator_model, generation_batch_id=generation_batch_id,
        intended_quality_tier=source_synthetic.intended_quality_tier,
        intended_concept_inclusion=source_synthetic.intended_concept_inclusion,
        intended_reasoning_category_targets=source_synthetic.intended_reasoning_category_targets,
        is_off_topic=source_synthetic.is_off_topic, is_contradictory=source_synthetic.is_contradictory,
        contradiction_type=source_synthetic.contradiction_type,
        diversity_seed=source_synthetic.diversity_seed, style_seed=source_synthetic.style_seed,
        rewritten_from_example_id=source_example.metadata.example_id,
        rewrite_style=style,
    )

    labels = TrainingExampleLabels(
        label_source="synthetic_ground_truth",
        dimension_labels=source_example.labels.dimension_labels,
        missing_reasoning_labels=source_example.labels.missing_reasoning_labels,
        concept_labels=_concept_labels_for_rewrite(recipe, output),
        contradiction_label=_contradiction_label_for_rewrite(recipe, output),
        overall_label=source_example.labels.overall_label,
    )

    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=f"rewrite_{_uuid.uuid4().hex[:16]}", created_at=now),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.SYNTHETIC, collection_batch_id=generation_batch_id),
        inputs=TrainingExampleInputs(
            specification=source_example.inputs.specification, question_text=source_example.inputs.question_text,
            reasoning_type=source_example.inputs.reasoning_type, answer_text=output.answer_text,
            expected_concepts=source_example.inputs.expected_concepts,
        ),
        privacy=source_example.privacy,
        synthetic=synthetic_meta,
        labels=labels,
    )
