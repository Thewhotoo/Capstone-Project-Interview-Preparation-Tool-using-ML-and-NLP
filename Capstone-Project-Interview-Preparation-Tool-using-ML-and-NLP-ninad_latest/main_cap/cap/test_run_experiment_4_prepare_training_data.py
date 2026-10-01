"""
Tests for run_experiment_4_prepare_training_data.py — the source+augmented
dataset combine/export script. Runs the REAL script against the REAL
already-generated artifacts on disk (no mocking of the combine logic
itself — this is exactly what the Colab-prep step actually does), then
verifies every requirement the DeBERTa integration milestone asked for:
no leakage, label-mapping consistency with the actual training-code
constants, and that the combined dataset round-trips through the
already-existing, already-tested `model_dataset.build_dataloaders`
end-to-end (the real proof it's genuinely Colab/HF-ready, not just
schema-valid JSON).

Skips (rather than fails) if the prerequisite artifacts aren't present on
this machine — this script only ever runs after
`run_experiment_4_deterministic.py generate_full` has produced its output
locally; a fresh clone/CI environment without those large, gitignored
artifacts should not see this as a failure.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from experiment_dataset_io import load_examples_jsonl, load_json
from run_experiment_4_pilot import SOURCE_DATASET_PATH, SOURCE_SPLIT_PATH
import run_experiment_4_prepare_training_data as prepare_module
from training_example import TrainingExample
from training_experimentation import DatasetSplit

_PREREQS_PRESENT = all(os.path.exists(p) for p in (
    SOURCE_DATASET_PATH, SOURCE_SPLIT_PATH,
    prepare_module.AUGMENTED_DATASET_PATH, prepare_module.AUGMENTED_SPLIT_PATH,
))


@unittest.skipUnless(_PREREQS_PRESENT, "source/augmented dataset artifacts not present on this machine")
class TestPrepareTrainingDataScript(unittest.TestCase):
    """Runs the real script once for the whole class (I/O + manifest
    assembly over ~5,600 examples takes a few seconds; no need to repeat
    it per test method)."""

    @classmethod
    def setUpClass(cls):
        exit_code = prepare_module.main()
        assert exit_code == 0, f"prepare script exited {exit_code}"
        cls.combined_examples = load_examples_jsonl(prepare_module.DATASET_PATH)
        cls.combined_split = load_json(DatasetSplit, prepare_module.SPLIT_PATH)
        with open(prepare_module.LABEL_MAPPINGS_PATH, encoding="utf-8") as f:
            cls.label_mappings = json.load(f)
        with open(prepare_module.PREPARE_SUMMARY_PATH, encoding="utf-8") as f:
            cls.summary = json.load(f)

    # ── Round-trip / schema ──────────────────────────────────────────────

    def test_combined_dataset_round_trips_as_training_examples(self):
        self.assertTrue(self.combined_examples)
        self.assertTrue(all(isinstance(e, TrainingExample) for e in self.combined_examples))

    def test_combined_count_equals_source_plus_augmented(self):
        source_count = len(load_examples_jsonl(SOURCE_DATASET_PATH))
        augmented_count = len(load_examples_jsonl(prepare_module.AUGMENTED_DATASET_PATH))
        self.assertEqual(len(self.combined_examples), source_count + augmented_count)

    def test_every_example_stamped_with_combined_dataset_version(self):
        self.assertTrue(all(
            e.metadata.dataset_version == prepare_module.COMBINED_DATASET_VERSION for e in self.combined_examples
        ))

    # ── No leakage ───────────────────────────────────────────────────────

    def test_val_and_test_ids_are_unchanged_from_source(self):
        source_split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
        self.assertEqual(set(self.combined_split.val_ids), set(source_split.val_ids))
        self.assertEqual(set(self.combined_split.test_ids), set(source_split.test_ids))

    def test_no_duplicate_ids_anywhere_in_the_combined_split(self):
        all_ids = self.combined_split.train_ids + self.combined_split.val_ids + self.combined_split.test_ids
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_augmented_examples_are_all_and_only_in_train(self):
        augmented_split = load_json(DatasetSplit, prepare_module.AUGMENTED_SPLIT_PATH)
        augmented_ids = set(augmented_split.train_ids)
        self.assertTrue(augmented_ids.issubset(set(self.combined_split.train_ids)))
        self.assertTrue(augmented_ids.isdisjoint(set(self.combined_split.val_ids)))
        self.assertTrue(augmented_ids.isdisjoint(set(self.combined_split.test_ids)))

    def test_every_combined_example_id_is_in_the_split(self):
        split_ids = set(self.combined_split.train_ids) | set(self.combined_split.val_ids) | set(self.combined_split.test_ids)
        example_ids = {e.metadata.example_id for e in self.combined_examples}
        self.assertEqual(example_ids, split_ids)

    # ── Label-mapping consistency (no drift between the exported JSON and
    #    the actual training-code constants) ──────────────────────────────

    def test_label_mappings_dimension_names_match_reasoning_dimension_relevance(self):
        from reasoning_dimension_relevance import ALL_DIMENSIONS
        self.assertEqual(self.label_mappings["dimension_names"], list(ALL_DIMENSIONS))

    def test_label_mappings_missing_reasoning_categories_match_model_heads(self):
        from model_heads import _MISSING_REASONING_CATEGORIES
        self.assertEqual(self.label_mappings["missing_reasoning_categories"], list(_MISSING_REASONING_CATEGORIES))

    def test_label_mappings_concept_status_order_matches_model_evaluator(self):
        from model_evaluator import _CONCEPT_STATUS_ORDER
        self.assertEqual(
            self.label_mappings["concept_status_order"], [s.value for s in _CONCEPT_STATUS_ORDER],
        )

    def test_label_mappings_ordinal_grades_match_model_evaluator(self):
        from model_evaluator import _ORDINAL_GRADES
        self.assertEqual(self.label_mappings["ordinal_class_index_to_grade"], list(_ORDINAL_GRADES))

    def test_label_mappings_num_ordinal_classes_matches_model_heads_default(self):
        from model_heads import _NUM_ORDINAL_CLASSES_DEFAULT
        self.assertEqual(self.label_mappings["num_ordinal_classes"], _NUM_ORDINAL_CLASSES_DEFAULT)

    def test_label_mappings_score_to_tier_cutpoints_match_model_dataset(self):
        from model_dataset import score_to_tier
        cutpoints = self.label_mappings["dimension_score_to_tier_cutpoints"]
        for grade, info in cutpoints.items():
            self.assertEqual(score_to_tier(info["min_score"]), info["tier_index"])
            # just below the cutpoint must fall into a strictly lower tier
            if info["min_score"] > 0.0:
                self.assertLess(score_to_tier(info["min_score"] - 0.001), info["tier_index"])

    # ── Summary sanity ───────────────────────────────────────────────────

    def test_summary_counts_match_actual_artifacts(self):
        self.assertEqual(self.summary["combined_example_count"], len(self.combined_examples))
        self.assertEqual(self.summary["combined_split_counts"]["train"], len(self.combined_split.train_ids))
        self.assertEqual(self.summary["combined_split_counts"]["val"], len(self.combined_split.val_ids))
        self.assertEqual(self.summary["combined_split_counts"]["test"], len(self.combined_split.test_ids))

    # ── Genuine end-to-end proof: the combined dataset is real HF/
    #    Transformers-ready training data, not just schema-valid JSON ─────

    def test_combined_dataset_builds_real_dataloaders_and_tokenizes(self):
        from model_backbone import BackboneConfig, build_tokenizer
        from model_dataset import build_dataloaders

        backbone_config = BackboneConfig(max_length=32)
        tokenizer = build_tokenizer(backbone_config)
        # A small slice is enough to prove tokenization/collation works
        # end-to-end -- building dataloaders over all 5,664 examples isn't
        # necessary to prove this and would just slow the test down.
        small_split = DatasetSplit(
            train_ids=self.combined_split.train_ids[:6],
            val_ids=self.combined_split.val_ids[:2],
            test_ids=self.combined_split.test_ids[:2],
        )
        train_loader, val_loader, test_loader = build_dataloaders(
            self.combined_examples, small_split, tokenizer, backbone_config, batch_size=2,
        )
        batch = next(iter(train_loader))
        self.assertIn("main_input_ids", batch)
        self.assertEqual(batch["main_input_ids"].shape[0], 2)
        self.assertTrue(len(val_loader) >= 1)
        self.assertTrue(len(test_loader) >= 1)


if __name__ == "__main__":
    unittest.main()
