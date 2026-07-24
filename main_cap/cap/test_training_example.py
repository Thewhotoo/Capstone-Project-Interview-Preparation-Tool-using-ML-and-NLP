"""Tests for training_example.py — Dataset Design RFC / Dataset Manifest RFC schema."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from evaluation_result import ConceptObservationStatus, MissingReasoningCategory
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import (
    ConceptInclusionTarget,
    ConceptLabel,
    ContradictionLabel,
    ContradictionType,
    DimensionLabel,
    MissingReasoningLabel,
    OverallLabel,
    ProvenanceSource,
    QualityTier,
    ReasoningCategoryTarget,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
    TrainingExampleSyntheticMeta,
)


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _synthetic_meta(**overrides):
    defaults = dict(
        generation_prompt_id="promptbook", prompt_version="1.0.0", generator_model="gemini-2.5-flash",
        generation_batch_id="batch_1", intended_quality_tier=QualityTier.GOOD,
        intended_concept_inclusion=(ConceptInclusionTarget(concept="caching", status=ConceptObservationStatus.DEMONSTRATED),),
        intended_reasoning_category_targets=(ReasoningCategoryTarget(category=MissingReasoningCategory.TRADEOFF, present=False),),
        diversity_seed="seed_1", style_seed="style_1",
    )
    defaults.update(overrides)
    return TrainingExampleSyntheticMeta(**defaults)


def _labels(**overrides):
    defaults = dict(
        label_source="synthetic_ground_truth",
        dimension_labels=(DimensionLabel(name="technical_accuracy", score=0.7),),
        missing_reasoning_labels=(),
        concept_labels=(ConceptLabel(concept="caching", status=ConceptObservationStatus.DEMONSTRATED, evidence="discussed TTLs"),),
        contradiction_label=ContradictionLabel(contradiction_present=False),
        overall_label=OverallLabel(score=0.7, grade="good", rationale="Solid but not exhaustive."),
    )
    defaults.update(overrides)
    return TrainingExampleLabels(**defaults)


def _example(**overrides):
    defaults = dict(
        metadata=TrainingExampleMetadata(example_id="ex_1", created_at="2026-01-01T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.SYNTHETIC, collection_batch_id="batch_1"),
        inputs=TrainingExampleInputs(
            specification=_spec(), question_text="Did Redis caching give you any trouble?",
            reasoning_type=ReasoningType.DEBUGGING, answer_text="I fixed a caching bug by adding TTLs.",
            expected_concepts=("caching",),
        ),
        privacy=TrainingExamplePrivacy(),
        synthetic=_synthetic_meta(),
        labels=_labels(),
    )
    defaults.update(overrides)
    return TrainingExample(**defaults)


class TestConstruction(unittest.TestCase):
    def test_constructs_with_all_fields(self):
        ex = _example()
        self.assertEqual(ex.provenance.source, ProvenanceSource.SYNTHETIC)

    def test_frozen(self):
        ex = _example()
        with self.assertRaises(pydantic.ValidationError):
            ex.metadata = TrainingExampleMetadata(example_id="ex_2", created_at="2026-01-01T00:00:00+00:00")

    def test_round_trip_json(self):
        ex = _example()
        restored = TrainingExample.model_validate_json(ex.model_dump_json())
        self.assertEqual(ex, restored)


class TestSyntheticPresenceMatchesSource(unittest.TestCase):
    def test_synthetic_source_requires_synthetic_meta(self):
        with self.assertRaises(pydantic.ValidationError):
            _example(synthetic=None)

    def test_real_session_source_forbids_synthetic_meta(self):
        with self.assertRaises(pydantic.ValidationError):
            _example(
                provenance=TrainingExampleProvenance(
                    source=ProvenanceSource.REAL_SESSION, collection_batch_id="b1", real_session_id="s1",
                ),
                labels=_labels(label_source="human_reviewed", labeling_guideline_version="v1"),
            )  # synthetic still set -> should fail

    def test_real_session_without_synthetic_meta_is_valid(self):
        ex = _example(
            provenance=TrainingExampleProvenance(
                source=ProvenanceSource.REAL_SESSION, collection_batch_id="b1", real_session_id="s1",
            ),
            synthetic=None,
            labels=_labels(label_source="human_reviewed", labeling_guideline_version="v1"),
        )
        self.assertIsNone(ex.synthetic)

    def test_synthetic_source_requires_synthetic_ground_truth_label(self):
        with self.assertRaises(pydantic.ValidationError):
            _example(labels=_labels(label_source="human_reviewed", labeling_guideline_version="v1"))


class TestProvenance(unittest.TestCase):
    def test_real_session_requires_session_id(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingExampleProvenance(source=ProvenanceSource.REAL_SESSION, collection_batch_id="b1")

    def test_synthetic_forbids_session_id(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingExampleProvenance(
                source=ProvenanceSource.SYNTHETIC, collection_batch_id="b1", real_session_id="s1",
            )


class TestSyntheticMeta(unittest.TestCase):
    def test_off_topic_forbids_concept_and_reasoning_targets(self):
        with self.assertRaises(pydantic.ValidationError):
            _synthetic_meta(
                intended_quality_tier=QualityTier.OFF_TOPIC, is_off_topic=True,
                intended_concept_inclusion=(ConceptInclusionTarget(concept="x", status=ConceptObservationStatus.OMITTED),),
            )

    def test_off_topic_flag_must_match_tier(self):
        with self.assertRaises(pydantic.ValidationError):
            _synthetic_meta(intended_quality_tier=QualityTier.GOOD, is_off_topic=True,
                             intended_concept_inclusion=(), intended_reasoning_category_targets=())

    def test_contradictory_requires_contradiction_type(self):
        with self.assertRaises(pydantic.ValidationError):
            _synthetic_meta(intended_quality_tier=QualityTier.CONTRADICTORY, is_contradictory=True,
                             intended_concept_inclusion=(), intended_reasoning_category_targets=())

    def test_contradictory_valid_with_type(self):
        meta = _synthetic_meta(
            intended_quality_tier=QualityTier.CONTRADICTORY, is_contradictory=True,
            contradiction_type=ContradictionType.TIMELINE,
            intended_concept_inclusion=(), intended_reasoning_category_targets=(),
        )
        self.assertEqual(meta.contradiction_type, ContradictionType.TIMELINE)

    def test_non_contradictory_forbids_contradiction_type(self):
        with self.assertRaises(pydantic.ValidationError):
            _synthetic_meta(contradiction_type=ContradictionType.FACTUAL)


class TestReasoningCategoryTarget(unittest.TestCase):
    def test_absent_target_forbids_nonzero_severity(self):
        with self.assertRaises(pydantic.ValidationError):
            ReasoningCategoryTarget(category=MissingReasoningCategory.TRADEOFF, present=False, severity=0.5)

    def test_present_target_allows_severity(self):
        target = ReasoningCategoryTarget(category=MissingReasoningCategory.TRADEOFF, present=True, severity=0.6)
        self.assertEqual(target.severity, 0.6)


class TestConceptLabel(unittest.TestCase):
    def test_omitted_forbids_evidence(self):
        with self.assertRaises(pydantic.ValidationError):
            ConceptLabel(concept="x", status=ConceptObservationStatus.OMITTED, evidence="something")

    def test_demonstrated_requires_evidence(self):
        with self.assertRaises(pydantic.ValidationError):
            ConceptLabel(concept="x", status=ConceptObservationStatus.DEMONSTRATED, evidence=None)


class TestContradictionLabel(unittest.TestCase):
    def test_present_requires_type_and_explanation(self):
        with self.assertRaises(pydantic.ValidationError):
            ContradictionLabel(contradiction_present=True)

    def test_present_valid(self):
        label = ContradictionLabel(
            contradiction_present=True, contradiction_type=ContradictionType.OWNERSHIP, explanation="Claimed sole ownership.",
        )
        self.assertTrue(label.contradiction_present)

    def test_absent_forbids_type(self):
        with self.assertRaises(pydantic.ValidationError):
            ContradictionLabel(contradiction_present=False, contradiction_type=ContradictionType.FACTUAL)


class TestTrainingExampleLabels(unittest.TestCase):
    def test_requires_at_least_one_dimension_label(self):
        with self.assertRaises(pydantic.ValidationError):
            _labels(dimension_labels=())

    def test_invalid_label_source_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _labels(label_source="made_up_source")

    def test_human_reviewed_requires_guideline_version(self):
        with self.assertRaises(pydantic.ValidationError):
            _labels(label_source="human_reviewed")

    def test_synthetic_forbids_guideline_version(self):
        with self.assertRaises(pydantic.ValidationError):
            _labels(labeling_guideline_version="v1")


class TestPrivacy(unittest.TestCase):
    def test_pii_requires_anonymized(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingExamplePrivacy(contains_pii=True, anonymized=False)

    def test_default_is_no_pii_and_anonymized(self):
        privacy = TrainingExamplePrivacy()
        self.assertFalse(privacy.contains_pii)
        self.assertTrue(privacy.anonymized)


if __name__ == "__main__":
    unittest.main()
