"""
Tests for Phase 3 — the group-aware train/val/test split of the FROZEN
170-example core pool (`four_dim_experiment_split.py` / `build_four_dim_split_v1.py`).
Uses the real curated-pool artifacts (read-only) and the real tokenizer
paired with a tiny randomly-initialized backbone (approved clarification
#4) — never a full pretrained-weights download.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from build_four_dim_split_v1 import SEED, SPLIT_RATIOS
from evaluation_dimensions import CANONICAL_DIMENSIONS
from four_dim_experiment_split import CANONICAL_DIMENSION_KEYS, group_of_by_source_id, load_core_pool
from model_backbone import BackboneConfig, build_dimension_pair, build_tiny_random_encoder, build_tokenizer
from model_dataset import build_dataloaders, collate_fn
from model_heads import MultiTaskModel, compute_batch_loss
from training_experimentation import split_dataset_by_group

_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=32)

# Computed once at module scope -- these tests exercise the real 170-example
# pool, so building it (fast: pure JSON parsing + pydantic construction, no
# model/tokenizer involved) once and reusing it keeps the suite fast.
_EXAMPLES = load_core_pool()
_GROUP_OF = group_of_by_source_id(_EXAMPLES)
_EXAMPLE_IDS = tuple(e.metadata.example_id for e in _EXAMPLES)
_BY_ID = {e.metadata.example_id: e for e in _EXAMPLES}


def _split():
    return split_dataset_by_group(_EXAMPLE_IDS, _GROUP_OF, SPLIT_RATIOS, SEED)


class TestCorePoolLoading(unittest.TestCase):
    def test_loads_exactly_170_examples(self):
        self.assertEqual(len(_EXAMPLES), 170)

    def test_every_example_has_all_four_canonical_labels(self):
        for e in _EXAMPLES:
            names = {dl.name for dl in e.labels.dimension_labels}
            self.assertEqual(names, set(CANONICAL_DIMENSION_KEYS))

    def test_every_label_is_a_valid_ordinal_score(self):
        for e in _EXAMPLES:
            for dl in e.labels.dimension_labels:
                self.assertGreaterEqual(dl.score, 0.0)
                self.assertLessEqual(dl.score, 1.0)


class TestDeterministicGroupSplit(unittest.TestCase):
    def test_splitting_is_deterministic(self):
        split_a = _split()
        split_b = _split()
        self.assertEqual(split_a.train_ids, split_b.train_ids)
        self.assertEqual(split_a.val_ids, split_b.val_ids)
        self.assertEqual(split_a.test_ids, split_b.test_ids)

    def test_covers_all_170_examples_exactly_once(self):
        split = _split()
        all_ids = split.train_ids + split.val_ids + split.test_ids
        self.assertEqual(len(all_ids), 170)
        self.assertEqual(set(all_ids), set(_EXAMPLE_IDS))

    def test_approximate_split_sizes(self):
        split = _split()
        # Target ~75/12/13 (127.5/20.4/22.1); group constraints mean exact
        # ratios aren't guaranteed -- assert a generous tolerance band, not
        # an exact count, so this test documents intent without being
        # brittle to a future re-derivation of the same seed.
        self.assertTrue(115 <= len(split.train_ids) <= 140, len(split.train_ids))
        self.assertTrue(12 <= len(split.val_ids) <= 30, len(split.val_ids))
        self.assertTrue(12 <= len(split.test_ids) <= 30, len(split.test_ids))

    def test_no_group_spans_more_than_one_split(self):
        split = _split()

        def groups(ids):
            return {_BY_ID[i].inputs.specification.source_id for i in ids}

        train_groups, val_groups, test_groups = groups(split.train_ids), groups(split.val_ids), groups(split.test_ids)
        self.assertEqual(train_groups & val_groups, set())
        self.assertEqual(train_groups & test_groups, set())
        self.assertEqual(val_groups & test_groups, set())

    def test_no_cross_split_source_id_leakage(self):
        # Same guarantee as the group-isolation test above, phrased directly
        # in terms of source_id (the actual group key used), per the task's
        # explicit "zero shared source_id across splits" requirement.
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
        # None of the 170 core-pool examples are deterministic-rewrite
        # derivatives -- confirmed via the schema's own lineage field.
        for e in _EXAMPLES:
            if e.synthetic is not None:
                self.assertIsNone(e.synthetic.rewritten_from_example_id)


class TestCanonicalDataloadersOnRealSplit(unittest.TestCase):
    """dataset -> collate -> model input -> four-head output, on the REAL
    170-example split (Task 6's canonical dataloader smoke test)."""

    def test_train_val_test_loaders_all_initialize(self):
        split = _split()
        train_loader, val_loader, test_loader = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        self.assertEqual(len(train_loader.dataset), len(split.train_ids))
        self.assertEqual(len(val_loader.dataset), len(split.val_ids))
        self.assertEqual(len(test_loader.dataset), len(split.test_ids))

    def test_batches_have_exactly_four_dimension_columns_in_canonical_order(self):
        split = _split()
        _, val_loader, _ = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        batch = next(iter(val_loader))
        self.assertEqual(batch["dimension_targets"].shape[1], 4)
        self.assertEqual(batch["dimension_mask"].shape[1], 4)
        for value in batch["dimension_targets"].flatten().tolist():
            self.assertIn(value, range(5))
        # Order correctness: cross-check one example directly against
        # collate_fn's own per-example construction for the exact canonical
        # tuple order.
        example = _BY_ID[batch["example_ids"][0]]
        single = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        by_name = {dl.name: dl.score for dl in example.labels.dimension_labels}
        expected = [round(by_name[name] * 4) for name in CANONICAL_DIMENSION_KEYS]
        self.assertEqual(single["dimension_targets"][0].tolist(), expected)

    def test_contextual_input_still_question_context_expected_concepts_answer(self):
        example = _EXAMPLES[0]
        from model_backbone import grounding_to_text
        context_text, answer_text = build_dimension_pair(
            example.inputs.question_text,
            grounding_to_text(example.inputs.specification.grounding),
            example.inputs.expected_concepts,
            example.inputs.answer_text,
        )
        self.assertIn("QUESTION:", context_text)
        self.assertEqual(answer_text, example.inputs.answer_text)

    def test_four_head_model_forward_and_loss_on_real_val_batch(self):
        split = _split()
        _, val_loader, _ = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertEqual(len(model.dimension_heads.heads), 4)
        self.assertEqual(set(model.dimension_heads.heads.keys()), set(CANONICAL_DIMENSION_KEYS))

        batch = next(iter(val_loader))
        outputs = model.forward_dimensions(batch["main_input_ids"], batch["main_attention_mask"])
        self.assertEqual(set(outputs["dimension_logits"].keys()), set(CANONICAL_DIMENSION_KEYS))

        loss = compute_batch_loss(model, batch)
        self.assertTrue(torch.isfinite(loss))


if __name__ == "__main__":
    unittest.main()
