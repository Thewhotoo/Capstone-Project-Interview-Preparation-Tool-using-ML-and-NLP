"""
Four-Dimension Dataset Generation Pipeline — Step 3 orchestration.

Ties the reused promptbook + a dimension profile + the real generation client
+ the independent rubric judge into one flow that produces training examples
whose FOUR labels come from the judge (never the generation target):

    profile + recipe
        -> assemble profiled prompt (promptbook + per-dimension guidance)
        -> client.generate            (real LLM; FakeGenerationClient NOT used here)
        -> generation_validation      (grounding fidelity, malformed, concept counts)
        -> dataset_filters.check_example  (banned phrases, hallucinated tech)
        -> judge_all_dimensions       (independent 4-dim labels)
        -> target-vs-judge agreement  (KEEP/DISCARD policy)
        -> TrainingExample            (labels from the judge)

Everything is injected (client, judge) so this module is testable with mocks
and never calls a network by itself. Nothing here trains a model or generates
a real dataset — it is the ready-to-run pipeline, exercised in tests with a
tiny mocked end-to-end run.

Reuses (never edits) the frozen generation stack: generation_recipe,
prompt_assembler, generation_client (interface), generation_validation. The
TrainingExample it builds is standard-shaped; its four DimensionLabels use the
canonical keys (evaluation_dimensions) — the schema accepts any dimension name
(DimensionLabel.name is a free string), so no schema change is needed.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from dimension_profiles import DimensionProfile, generation_guidance
from evaluation_dimensions import CANONICAL_DIMENSIONS, NUM_TIERS, EvaluationDimension
from generation_client import GenerationClient, GenerationOutput
from generation_recipe import GenerationRecipe
from generation_validation import validate_generation
from model_backbone import grounding_to_text
from prompt_assembler import (
    GENERATION_PROMPT_ID,
    PROMPT_VERSION,
    AssembledPrompt,
    assemble_prompt,
)
from rubric_judge import (
    DEFAULT_AGREEMENT_TOLERANCE,
    AgreementReport,
    JudgeVerdict,
    MismatchPolicy,
    RubricJudge,
    compute_agreement,
    judge_all_dimensions,
)
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
from evaluation_result import ConceptObservationStatus

_MAX_TIER = NUM_TIERS - 1


# ── profile <-> recipe quality tier ──────────────────────────────────────────

def profile_to_quality_tier(profile: DimensionProfile) -> QualityTier:
    """Maps a profile's average tier to a CORE quality tier, used only so the
    recipe's concept/reasoning-target sampling roughly aligns with the
    profile. The profile (not the tier) drives the actual per-dimension
    divergence via `generation_guidance`. Never returns off_topic/
    contradictory — those failure modes, when wanted, come from the profile's
    own guidance (e.g. grounding_ownership=0 = generic/contradictory)."""
    avg = sum(profile.as_tuple()) / len(CANONICAL_DIMENSIONS)
    if avg >= 3.5:
        return QualityTier.EXCELLENT
    if avg >= 2.5:
        return QualityTier.GOOD
    if avg >= 1.5:
        return QualityTier.ADEQUATE
    if avg >= 0.75:
        return QualityTier.WEAK
    return QualityTier.POOR


# ── profiled prompt (reuse promptbook + append per-dimension guidance) ────────

def assemble_profiled_prompt(
    recipe: GenerationRecipe,
    profile: DimensionProfile,
    generation_prompt_id: str = GENERATION_PROMPT_ID,
    prompt_version: str = PROMPT_VERSION,
) -> AssembledPrompt:
    """The base promptbook prompt with the per-dimension profile guidance
    appended as the final, most-specific section. Reuses the entire existing
    controller wiring; adds one deterministic block. The guidance describes
    the CONTENT to produce, never the answer's quality."""
    base = assemble_prompt(recipe, generation_prompt_id, prompt_version)
    guidance = generation_guidance(profile)
    user_text = f"{base.user_text}\n\n{guidance}" if base.user_text.strip() else guidance
    return AssembledPrompt(
        generation_prompt_id=base.generation_prompt_id,
        prompt_version=base.prompt_version,
        system_text=base.system_text,
        user_text=user_text,
    )


# ── example construction (labels from the judge) ─────────────────────────────

def _judge_dimension_labels(verdicts: dict[EvaluationDimension, JudgeVerdict]) -> tuple[DimensionLabel, ...]:
    """The four canonical DimensionLabels, scored from the JUDGE's ordinal
    tiers (0..4) mapped to the [0,1] DimensionLabel scale. This is the whole
    point of Step 3: labels come from the independent judge, not the target."""
    return tuple(
        DimensionLabel(name=dim.value, score=round(verdicts[dim].score / _MAX_TIER, 4))
        for dim in CANONICAL_DIMENSIONS
    )


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
        labels.append(MissingReasoningLabel(
            category=target.category, present=True, severity=target.severity,
            explanation=f"the answer was generated to under-develop {target.category.replace('_', ' ')}",
        ))
    return tuple(labels)


def build_four_dim_example(
    recipe: GenerationRecipe,
    output: GenerationOutput,
    verdicts: dict[EvaluationDimension, JudgeVerdict],
    *,
    profile: DimensionProfile,
    judge_version: str,
    generator_model: str,
    generation_batch_id: str,
    generation_prompt_id: str = GENERATION_PROMPT_ID,
    prompt_version: str = PROMPT_VERSION,
) -> TrainingExample:
    """Build a standard `TrainingExample` whose four dimension labels come
    from the independent judge. `label_source` stays `synthetic_ground_truth`
    (the answer is LLM-generated), which the schema requires for synthetic
    provenance; the judge is the labeling mechanism within that source."""
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

    contradiction_label = (
        ContradictionLabel(
            contradiction_present=True, contradiction_type=recipe.contradiction_type,
            explanation=output.contradiction_note.strip() or "a deliberate contradiction was introduced",
        )
        if recipe.is_contradictory else ContradictionLabel(contradiction_present=False)
    )

    # Overall grade derived from the judged dimension scores' average tier —
    # NOT a "generated to target" rationale (that phrase is banned and would
    # be a leak if it ever reached an answer; here we keep the label honest).
    avg_tier = sum(v.score for v in verdicts.values()) / len(verdicts)
    overall_score = round(avg_tier / _MAX_TIER, 4)
    labels = TrainingExampleLabels(
        label_source="synthetic_ground_truth",
        dimension_labels=_judge_dimension_labels(verdicts),
        missing_reasoning_labels=_missing_reasoning_labels(recipe),
        concept_labels=_concept_labels(recipe, output),
        contradiction_label=contradiction_label,
        overall_label=OverallLabel(
            score=overall_score,
            grade=_grade_from_score(overall_score),
            rationale="Labeled independently by the four-dimension rubric judge.",
        ),
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


def _grade_from_score(score: float) -> str:
    if score >= 0.90:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


# ── the generate -> judge -> validate -> accept/reject result ────────────────

@dataclass(frozen=True)
class LabeledExample:
    """The pipeline's per-attempt output. `example` is None when the attempt
    was rejected (generation invalid, filter tripped, or judge/target
    mismatch under DISCARD). `group_key` (grounding source) drives leak-free
    splitting; `profile_id` records which hard-case/coherent cell this was."""

    accepted: bool
    profile_id: str
    group_key: str
    profile: DimensionProfile
    reject_reasons: tuple[str, ...] = ()
    example: Optional[TrainingExample] = None
    verdicts: dict = field(default_factory=dict)
    agreement: Optional[AgreementReport] = None


def generate_and_label(
    recipe: GenerationRecipe,
    profile: DimensionProfile,
    client: GenerationClient,
    judge: RubricJudge,
    *,
    profile_id: str,
    generation_batch_id: str,
    policy: MismatchPolicy = MismatchPolicy.DISCARD,
    tolerance: int = DEFAULT_AGREEMENT_TOLERANCE,
    group_key: Optional[str] = None,
) -> LabeledExample:
    """One full attempt. Deterministic given deterministic client+judge.
    NEVER uses FakeGenerationClient — the caller injects the real client (or a
    test mock). The default `policy` is conservative (DISCARD on mismatch);
    labels always come from the judge regardless of policy."""
    from dataset_filters import check_example

    group = group_key or recipe.specification.source_id
    grounding_text = grounding_to_text(recipe.specification.grounding)

    def _reject(*reasons: str) -> LabeledExample:
        return LabeledExample(
            accepted=False, profile_id=profile_id, group_key=group, profile=profile,
            reject_reasons=tuple(reasons),
        )

    # 1. generate
    prompt = assemble_profiled_prompt(recipe, profile)
    output = client.generate(prompt)

    # 2. frozen generation validation (grounding fidelity, malformed, concepts)
    verdict = validate_generation(output, recipe)
    if not verdict.accepted:
        return _reject(*(f"generation_validation:{r}" for r in verdict.rejection_reasons))

    # 3. leakage/quality filters (banned phrases, malformed, hallucinated tech)
    allowed_tech = (
        recipe.specification.grounding.project.technologies
        if recipe.specification.grounding.project is not None else ()
    )
    filt = check_example(output.answer_text, allowed_technologies=allowed_tech)
    if not filt.accepted:
        return _reject(*(f"filter:{r}" for r in filt.reasons))

    # 4. independent four-dimension judging (labels)
    verdicts = judge_all_dimensions(
        judge, recipe.question_text, output.answer_text, grounding_text, recipe.expected_concepts,
    )

    # 5. target-vs-judge agreement -> keep/discard
    agreement = compute_agreement(profile, verdicts, tolerance=tolerance)
    if not agreement.all_acceptable and policy is MismatchPolicy.DISCARD:
        deltas = ", ".join(f"{d.dimension}:{d.delta}" for d in agreement.per_dimension if not d.acceptable)
        return LabeledExample(
            accepted=False, profile_id=profile_id, group_key=group, profile=profile,
            reject_reasons=(f"target_judge_mismatch:{deltas}",),
            verdicts={d.value: v for d, v in verdicts.items()}, agreement=agreement,
        )

    # 6. build the example (labels from the judge)
    example = build_four_dim_example(
        recipe, output, verdicts, profile=profile, judge_version=judge.judge_version,
        generator_model=getattr(client, "model_name", "unknown"),
        generation_batch_id=generation_batch_id,
    )
    return LabeledExample(
        accepted=True, profile_id=profile_id, group_key=group, profile=profile,
        example=example, verdicts={d.value: v for d, v in verdicts.items()}, agreement=agreement,
    )


# ── leak-free grouped splitting ──────────────────────────────────────────────

def group_of_from_labeled(labeled: list[LabeledExample]) -> dict[str, str]:
    """example_id -> group_key, for the accepted examples only — the input to
    `training_experimentation.split_dataset_by_group`."""
    return {le.example.metadata.example_id: le.group_key for le in labeled if le.accepted and le.example}


def split_labeled(labeled: list[LabeledExample], split_ratios=(0.7, 0.15, 0.15), seed: str = "four_dim_v1"):
    """Group-aware split over accepted examples (never the row-level
    `split_dataset`), so all examples sharing a grounding source stay in one
    split. Returns a `DatasetSplit`."""
    from training_experimentation import split_dataset_by_group

    group_of = group_of_from_labeled(labeled)
    example_ids = tuple(group_of.keys())
    return split_dataset_by_group(example_ids, group_of, split_ratios, seed)
