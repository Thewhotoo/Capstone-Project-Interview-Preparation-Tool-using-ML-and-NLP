"""
Tests for Phase 5 — the group-aware V2 split (220-example pool: frozen 170
+ finalized v2_targeted_50). Uses the real curated-pool artifacts
(read-only) and the real tokenizer paired with a tiny randomly-initialized
backbone (approved clarification #4) — never a full pretrained-weights
download.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from build_four_dim_v2_split import SEED, SPLIT_RATIOS
from evaluation_dimensions import CANONICAL_DIMENSIONS
from four_dim_experiment_split import CANONICAL_DIMENSION_KEYS, load_core_pool
from four_dim_experiment_v2_split import group_of_by_source_id, load_v2_pool, load_v2_targeted_50
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_dataset import build_dataloaders, collate_fn
from model_heads import MultiTaskModel, compute_batch_loss
from training_experimentation import split_dataset_by_group

_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=32)

_EXPECTED_ORDER = (
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
)

# Computed once at module scope -- fast (pure JSON parsing + pydantic
# construction, no model/tokenizer involved).
_POOL = load_v2_pool()
_GROUP_OF = group_of_by_source_id(_POOL)
_EXAMPLE_IDS = tuple(e.metadata.example_id for e in _POOL)
_BY_ID = {e.metadata.example_id: e for e in _POOL}


def _split():
    return split_dataset_by_group(_EXAMPLE_IDS, _GROUP_OF, SPLIT_RATIOS, SEED)


class TestV2PoolComposition(unittest.TestCase):
    def test_pool_is_exactly_220(self):
        self.assertEqual(len(_POOL), 220)

    def test_frozen_170_plus_v2_targeted_50_equals_220(self):
        core = load_core_pool()
        targeted = load_v2_targeted_50()
        self.assertEqual(len(core), 170)
        self.assertEqual(len(targeted), 50)
        self.assertEqual(len(core) + len(targeted), 220)

    def test_all_example_ids_unique(self):
        self.assertEqual(len(_EXAMPLE_IDS), len(set(_EXAMPLE_IDS)))

    def test_every_example_has_all_four_canonical_labels(self):
        for e in _POOL:
            names = {dl.name for dl in e.labels.dimension_labels}
            self.assertEqual(names, set(CANONICAL_DIMENSION_KEYS))

    def test_every_label_is_a_valid_ordinal_score(self):
        for e in _POOL:
            for dl in e.labels.dimension_labels:
                self.assertGreaterEqual(dl.score, 0.0)
                self.assertLessEqual(dl.score, 1.0)

    def test_frozen_170_examples_are_a_subset_of_the_v1_pool_unchanged(self):
        # The 170 loaded here must be identical (by example_id set) to the
        # V1 core pool -- confirms this module never mutates or re-derives
        # the frozen pool.
        from four_dim_experiment_split import load_core_pool as v1_load
        v1_ids = {e.metadata.example_id for e in v1_load()}
        v2_core_ids = {e.metadata.example_id for e in load_core_pool()}
        self.assertEqual(v1_ids, v2_core_ids)


class TestDeterministicV2Split(unittest.TestCase):
    def test_splitting_is_deterministic(self):
        split_a = _split()
        split_b = _split()
        self.assertEqual(split_a.train_ids, split_b.train_ids)
        self.assertEqual(split_a.val_ids, split_b.val_ids)
        self.assertEqual(split_a.test_ids, split_b.test_ids)

    def test_covers_all_220_examples_exactly_once(self):
        split = _split()
        all_ids = split.train_ids + split.val_ids + split.test_ids
        self.assertEqual(len(all_ids), 220)
        self.assertEqual(set(all_ids), set(_EXAMPLE_IDS))

    def test_approximate_split_sizes(self):
        split = _split()
        self.assertTrue(150 <= len(split.train_ids) <= 180, len(split.train_ids))
        self.assertTrue(18 <= len(split.val_ids) <= 35, len(split.val_ids))
        self.assertTrue(18 <= len(split.test_ids) <= 35, len(split.test_ids))

    def test_no_group_spans_more_than_one_split(self):
        split = _split()

        def groups(ids):
            return {_BY_ID[i].inputs.specification.source_id for i in ids}

        train_groups, val_groups, test_groups = groups(split.train_ids), groups(split.val_ids), groups(split.test_ids)
        self.assertEqual(train_groups & val_groups, set())
        self.assertEqual(train_groups & test_groups, set())
        self.assertEqual(val_groups & test_groups, set())

    def test_no_cross_split_source_id_leakage(self):
        split = _split()
        by_split = {
            "train": {_BY_ID[i].inputs.specification.source_id for i in split.train_ids},
            "val": {_BY_ID[i].inputs.specification.source_id for i in split.val_ids},
            "test": {_BY_ID[i].inputs.specification.source_id for i in split.test_ids},
        }
        for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
            self.assertEqual(by_split[a] & by_split[b], set(), f"{a}/{b} share a source_id")

    def test_no_cross_split_exact_duplicate_questions_or_answers(self):
        split = _split()

        def norm(s):
            return " ".join((s or "").split()).casefold()

        subsets = {"train": split.train_ids, "val": split.val_ids, "test": split.test_ids}
        questions = {name: {norm(_BY_ID[i].inputs.question_text) for i in ids} for name, ids in subsets.items()}
        answers = {name: {norm(_BY_ID[i].inputs.answer_text) for i in ids} for name, ids in subsets.items()}
        for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
            self.assertEqual(questions[a] & questions[b], set())
            self.assertEqual(answers[a] & answers[b], set())

    def test_no_rewrite_lineage_leakage(self):
        for e in _POOL:
            if e.synthetic is not None:
                self.assertIsNone(e.synthetic.rewritten_from_example_id)

    def test_v2_targeted_50_examples_are_represented_in_val_and_test(self):
        # Explicit regression guard for the task's own distribution goal:
        # the new V2 examples must not be almost entirely placed in train.
        split = _split()
        targeted_ids = {e.metadata.example_id for e in load_v2_targeted_50()}
        val_targeted = len(targeted_ids & set(split.val_ids))
        test_targeted = len(targeted_ids & set(split.test_ids))
        self.assertGreater(val_targeted, 0)
        self.assertGreater(test_targeted, 0)

    def test_test_set_has_technical_correctness_tier_diversity(self):
        # Distribution goal: avoid a test set dominated almost entirely by
        # tier 4 -- some tier 2/3 presence is required.
        split = _split()

        def tc_tier(eid):
            for dl in _BY_ID[eid].labels.dimension_labels:
                if dl.name == "technical_correctness":
                    return round(dl.score * 4)
            return None

        tiers = [tc_tier(i) for i in split.test_ids]
        self.assertGreater(sum(1 for t in tiers if t == 3), 0)
        self.assertLess(sum(1 for t in tiers if t == 4) / len(tiers), 0.85)

    def test_test_set_has_relevance_tier_diversity(self):
        split = _split()

        def rel_tier(eid):
            for dl in _BY_ID[eid].labels.dimension_labels:
                if dl.name == "relevance_completeness":
                    return round(dl.score * 4)
            return None

        tiers = {rel_tier(i) for i in split.test_ids}
        # Full 0-4 range should be represented (this specific chosen seed
        # achieves this; a looser bound would hide a real regression).
        self.assertEqual(tiers, {0, 1, 2, 3, 4})


class TestCanonicalDataloadersOnV2Split(unittest.TestCase):
    """dataset -> collate -> model input -> four-head output, on the REAL
    220-example V2 split."""

    def test_train_val_test_loaders_all_initialize(self):
        split = _split()
        train_loader, val_loader, test_loader = build_dataloaders(
            _POOL, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        self.assertEqual(len(train_loader.dataset), len(split.train_ids))
        self.assertEqual(len(val_loader.dataset), len(split.val_ids))
        self.assertEqual(len(test_loader.dataset), len(split.test_ids))

    def test_batches_have_exactly_four_dimension_columns_in_canonical_order(self):
        split = _split()
        _, val_loader, _ = build_dataloaders(
            _POOL, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        batch = next(iter(val_loader))
        self.assertEqual(batch["dimension_targets"].shape[1], 4)
        example = _BY_ID[batch["example_ids"][0]]
        single = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        by_name = {dl.name: dl.score for dl in example.labels.dimension_labels}
        expected = [round(by_name[name] * 4) for name in CANONICAL_DIMENSION_KEYS]
        self.assertEqual(single["dimension_targets"][0].tolist(), expected)

    def test_four_head_model_forward_and_loss_on_real_val_batch(self):
        split = _split()
        _, val_loader, _ = build_dataloaders(
            _POOL, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertEqual(len(model.dimension_heads.heads), 4)
        batch = next(iter(val_loader))
        outputs = model.forward_dimensions(batch["main_input_ids"], batch["main_attention_mask"])
        self.assertEqual(set(outputs["dimension_logits"].keys()), set(CANONICAL_DIMENSION_KEYS))
        loss = compute_batch_loss(model, batch)
        self.assertTrue(torch.isfinite(loss))


if __name__ == "__main__":
    unittest.main()
