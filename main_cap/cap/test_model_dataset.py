"""
Tests for model_dataset.py — TrainingExample -> tensor adapter, collate_fn,
and build_dataloaders. Uses the real tokenizer paired with a tiny
randomly-initialized backbone config (approved clarification #4) — the
tokenizer is what's actually exercised here, no model forward pass needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from model_backbone import BackboneConfig, build_tokenizer
from model_dataset import TrainingExampleDataset, build_dataloaders, collate_fn, score_to_tier
from model_heads import _MISSING_REASONING_CATEGORIES
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from reasoning_dimension_relevance import ALL_DIMENSIONS
from training_example import (
    ConceptLabel,
    ContradictionLabel,
    DimensionLabel,
    MissingReasoningLabel,
    OverallLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
)
from training_experimentation import DatasetSplit

_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=32)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _example(example_id: str, dimension_score: float = 0.7, with_concept: bool = True,
             with_missing_reasoning: bool = True) -> TrainingExample:
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=example_id, created_at="2026-07-24T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION, collection_batch_id="b1", real_session_id="s1",
        ),
        inputs=TrainingExampleInputs(
            specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, answer_text="I worked through a cache invalidation bug.",
            expected_concepts=("caching",),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version="g1",
            dimension_labels=(DimensionLabel(name="debugging", score=dimension_score),),
            concept_labels=(
                (ConceptLabel(concept="caching", status=ConceptObservationStatus.DEMONSTRATED, evidence="discussed it"),)
                if with_concept else ()
            ),
            missing_reasoning_labels=(
                (MissingReasoningLabel(category="testing", present=True, severity=0.4, explanation="no tests mentioned"),)
                if with_missing_reasoning else ()
            ),
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=dimension_score, grade="good", rationale="test"),
        ),
    )


class TestScoreToTier(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(score_to_tier(0.95), 4)
        self.assertEqual(score_to_tier(0.80), 4)
        self.assertEqual(score_to_tier(0.65), 3)
        self.assertEqual(score_to_tier(0.45), 2)
        self.assertEqual(score_to_tier(0.30), 1)
        self.assertEqual(score_to_tier(0.10), 0)


class TestTrainingExampleDataset(unittest.TestCase):
    def test_selects_examples_by_split_subset(self):
        examples = (_example("a"), _example("b"), _example("c"))
        split = DatasetSplit(train_ids=("a", "b"), val_ids=("c",), test_ids=())
        train_ds = TrainingExampleDataset(examples, split, "train")
        val_ds = TrainingExampleDataset(examples, split, "val")
        self.assertEqual(len(train_ds), 2)
        self.assertEqual(len(val_ds), 1)
        self.assertEqual(val_ds[0].metadata.example_id, "c")

    def test_rejects_unknown_subset(self):
        examples = (_example("a"),)
        split = DatasetSplit(train_ids=("a",))
        with self.assertRaises(ValueError):
            TrainingExampleDataset(examples, split, "bogus")

    def test_rejects_missing_example_id(self):
        examples = (_example("a"),)
        split = DatasetSplit(train_ids=("a", "missing"))
        with self.assertRaises(ValueError):
            TrainingExampleDataset(examples, split, "train")


class TestCollateFn(unittest.TestCase):
    def test_produces_expected_tensor_shapes(self):
        batch = [_example("a", with_concept=True), _example("b", with_concept=False)]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG)
        self.assertEqual(collated["main_input_ids"].shape[0], 2)
        self.assertEqual(collated["dimension_targets"].shape, (2, len(ALL_DIMENSIONS)))
        self.assertEqual(collated["dimension_mask"].shape, (2, len(ALL_DIMENSIONS)))
        self.assertEqual(collated["presence_target"].shape, (2, len(_MISSING_REASONING_CATEGORIES)))
        self.assertEqual(collated["severity_target"].shape, (2, len(_MISSING_REASONING_CATEGORIES)))
        # Only "a" has a concept label -> exactly one flattened concept pair.
        self.assertEqual(collated["concept_targets"].shape, (1,))
        self.assertEqual(collated["concept_example_index"].tolist(), [0])

    def test_no_concepts_in_batch_yields_none_concept_tensors(self):
        batch = [_example("a", with_concept=False), _example("b", with_concept=False)]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG)
        self.assertIsNone(collated["concept_input_ids"])
        self.assertIsNone(collated["concept_attention_mask"])
        self.assertEqual(collated["concept_targets"].shape, (0,))

    def test_dimension_mask_reflects_relevance_for_reasoning_type(self):
        batch = [_example("a")]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG)
        debugging_index = ALL_DIMENSIONS.index("debugging")
        # DEBUGGING reasoning_type includes the "debugging" dimension as relevant.
        self.assertEqual(collated["dimension_mask"][0, debugging_index].item(), 1.0)

    def test_missing_reasoning_targets_reflect_labels(self):
        batch = [_example("a", with_missing_reasoning=True), _example("b", with_missing_reasoning=False)]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG)
        testing_index = _MISSING_REASONING_CATEGORIES.index("testing")
        self.assertEqual(collated["presence_target"][0, testing_index].item(), 1.0)
        self.assertAlmostEqual(collated["severity_target"][0, testing_index].item(), 0.4, places=5)
        self.assertEqual(collated["presence_target"][1, testing_index].item(), 0.0)
        self.assertEqual(collated["severity_target"][1, testing_index].item(), 0.0)


class TestBuildDataloaders(unittest.TestCase):
    def test_produces_three_loaders_with_expected_sizes(self):
        examples = tuple(_example(f"ex_{i}") for i in range(6))
        split = DatasetSplit(
            train_ids=tuple(f"ex_{i}" for i in range(4)),
            val_ids=("ex_4",), test_ids=("ex_5",),
        )
        train_loader, val_loader, test_loader = build_dataloaders(
            examples, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=2,
        )
        self.assertEqual(len(train_loader.dataset), 4)
        self.assertEqual(len(val_loader.dataset), 1)
        self.assertEqual(len(test_loader.dataset), 1)
        batches = list(train_loader)
        self.assertEqual(sum(b["main_input_ids"].shape[0] for b in batches), 4)

    def _shuffle_order(self, seed) -> list:
        examples = tuple(_example(f"ex_{i}") for i in range(10))
        split = DatasetSplit(train_ids=tuple(f"ex_{i}" for i in range(10)), val_ids=(), test_ids=())
        train_loader, _, _ = build_dataloaders(
            examples, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=1, seed=seed,
        )
        return [b["example_ids"][0] for b in train_loader]

    def test_seeded_shuffle_is_reproducible(self):
        order_a = self._shuffle_order(seed=42)
        order_b = self._shuffle_order(seed=42)
        self.assertEqual(order_a, order_b)

    def test_different_seed_can_change_shuffle_order(self):
        order_a = self._shuffle_order(seed=42)
        order_b = self._shuffle_order(seed=99)
        self.assertNotEqual(order_a, order_b)

    def test_unseeded_train_loader_still_works(self):
        examples = tuple(_example(f"ex_{i}") for i in range(4))
        split = DatasetSplit(train_ids=tuple(f"ex_{i}" for i in range(4)), val_ids=(), test_ids=())
        train_loader, _, _ = build_dataloaders(examples, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=2)
        batches = list(train_loader)
        self.assertEqual(sum(b["main_input_ids"].shape[0] for b in batches), 4)


if __name__ == "__main__":
    unittest.main()
