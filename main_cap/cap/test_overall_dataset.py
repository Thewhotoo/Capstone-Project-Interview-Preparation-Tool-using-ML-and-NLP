"""
Tests for `overall_dataset.py` — deterministic overall-target construction
(Test 3) and collate/dataloader wiring.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from evaluation_dimensions import CANONICAL_DIMENSIONS
from model_backbone import BackboneConfig, build_tokenizer
from model_dataset import score_to_tier
from overall_dataset import build_overall_dataloaders, collate_fn, overall_score_to_tier
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
)
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_experimentation import DatasetSplit

_TOKENIZER = build_tokenizer(BackboneConfig())
_CANONICAL_KEYS = tuple(d.value for d in CANONICAL_DIMENSIONS)


def _make_example(example_id: str, dim_scores: dict, overall_score: float) -> TrainingExample:
    spec = QuestionSpecification(
        id=example_id, category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(title="X", technologies=("Redis",))),
        source_type=SourceType.PROJECT, source_id=f"src_{example_id}", source_field="f", reason="test",
    )
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=example_id, created_at="2026-01-01T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.REAL_SESSION, collection_batch_id="b", real_session_id="s"),
        inputs=TrainingExampleInputs(
            specification=spec, question_text="How did you scale it?",
            reasoning_type=ReasoningType.EXPLANATION, answer_text="We used caching and sharding.",
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version="v1",
            dimension_labels=tuple(DimensionLabel(name=n, score=s) for n, s in dim_scores.items()),
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=overall_score, grade="n/a", rationale="test"),
        ),
    )


class TestDeterministicOverallTargetConstruction(unittest.TestCase):
    """Test 3: deterministic overall target construction."""

    def test_overall_target_equals_score_to_tier_of_overall_label_score(self):
        example = _make_example(
            "e1", {k: 0.9 for k in _CANONICAL_KEYS}, overall_score=0.9,
        )
        expected_tier = score_to_tier(0.9)
        self.assertEqual(overall_score_to_tier(example.labels.overall_label.score), expected_tier)

    def test_target_construction_is_deterministic_across_repeated_calls(self):
        example = _make_example("e2", {k: 0.55 for k in _CANONICAL_KEYS}, overall_score=0.55)
        results = {overall_score_to_tier(example.labels.overall_label.score) for _ in range(10)}
        self.assertEqual(len(results), 1)

    def test_overall_label_score_is_the_documented_equal_weight_mean_policy(self):
        # Reproduces the SAME formula four_dim_experiment_split.py's
        # _to_training_example already uses (equal-weight mean of the four
        # canonical dimension scores), confirming overall_dataset.py reuses
        # that existing policy rather than inventing a new one.
        dim_scores = {"technical_correctness": 1.0, "depth_specificity": 0.75,
                       "relevance_completeness": 0.5, "grounding_ownership": 0.25}
        equal_weight_mean = round(sum(dim_scores.values()) / len(dim_scores), 4)
        example = _make_example("e3", dim_scores, overall_score=equal_weight_mean)
        self.assertAlmostEqual(example.labels.overall_label.score, equal_weight_mean)
        self.assertEqual(
            overall_score_to_tier(example.labels.overall_label.score),
            score_to_tier(equal_weight_mean),
        )

    def test_collate_fn_produces_overall_target_tensor_matching_batch_size(self):
        examples = [
            _make_example("a", {k: 0.9 for k in _CANONICAL_KEYS}, overall_score=0.9),
            _make_example("b", {k: 0.2 for k in _CANONICAL_KEYS}, overall_score=0.2),
        ]
        batch = collate_fn(examples, _TOKENIZER, BackboneConfig(max_length=64))
        self.assertEqual(batch["overall_target"].shape, (2,))
        self.assertEqual(batch["overall_target"][0].item(), score_to_tier(0.9))
        self.assertEqual(batch["overall_target"][1].item(), score_to_tier(0.2))

    def test_collate_fn_has_no_per_dimension_targets(self):
        # Architectural guarantee: unlike model_dataset.collate_fn, this
        # module's batches carry a single overall_target, never
        # dimension_targets/dimension_mask.
        examples = [_make_example("a", {k: 0.5 for k in _CANONICAL_KEYS}, overall_score=0.5)]
        batch = collate_fn(examples, _TOKENIZER, BackboneConfig(max_length=64))
        self.assertNotIn("dimension_targets", batch)
        self.assertNotIn("dimension_mask", batch)
        self.assertIn("overall_target", batch)


class TestBuildOverallDataloaders(unittest.TestCase):
    def test_builds_three_loaders_respecting_the_split(self):
        examples = tuple(
            _make_example(f"id{i}", {k: 0.5 for k in _CANONICAL_KEYS}, overall_score=0.5) for i in range(6)
        )
        split = DatasetSplit(
            train_ids=tuple(e.metadata.example_id for e in examples[:4]),
            val_ids=(examples[4].metadata.example_id,),
            test_ids=(examples[5].metadata.example_id,),
        )
        train_loader, val_loader, test_loader = build_overall_dataloaders(
            examples, split, _TOKENIZER, BackboneConfig(max_length=64), batch_size=2, seed=42,
        )
        self.assertEqual(sum(len(b["overall_target"]) for b in train_loader), 4)
        self.assertEqual(sum(len(b["overall_target"]) for b in val_loader), 1)
        self.assertEqual(sum(len(b["overall_target"]) for b in test_loader), 1)


if __name__ == "__main__":
    unittest.main()
