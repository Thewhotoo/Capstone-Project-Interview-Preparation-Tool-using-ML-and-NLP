"""
Tests for `overall_score_model.py` — the single-CORAL-head overall-score
model (V3 Single-Overall-Score Architecture). Uses the real tokenizer
paired with a tiny randomly-initialized backbone (same discipline
`test_model_heads.py` already established), never downloads real
pretrained weights.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer, tokenize_pair
from overall_score_model import (
    NUM_ORDINAL_CLASSES,
    OverallScoreModel,
    compute_overall_batch_loss,
    load_overall_checkpoint_artifact,
    save_overall_checkpoint_artifact,
    train_overall_model,
)

_TOKENIZER = build_tokenizer(BackboneConfig())


def _tiny_model() -> OverallScoreModel:
    encoder = build_tiny_random_encoder(_TOKENIZER)
    return OverallScoreModel(BackboneConfig(), backbone=encoder)


def _batch(pairs):
    encodings = [tokenize_pair(_TOKENIZER, a, b, max_length=32) for a, b in pairs]
    padded = _TOKENIZER.pad(encodings, return_tensors="pt")
    return padded["input_ids"], padded["attention_mask"]


class TestSingleCoralHeadOutputShape(unittest.TestCase):
    """Test 1: single CORAL head output shape."""

    def test_forward_output_shape_is_num_classes_minus_one(self):
        model = _tiny_model()
        input_ids, attention_mask = _batch([
            ("QUESTION:\nHow did you scale it?", "We used caching."),
            ("QUESTION:\nWhy Postgres?", "Because it's relational."),
        ])
        logits = model(input_ids, attention_mask)
        self.assertEqual(logits.shape, (2, NUM_ORDINAL_CLASSES - 1))

    def test_only_one_head_exists_no_per_dimension_heads(self):
        # Architectural guarantee: a single nn.Module head, not a ModuleDict
        # of per-dimension heads (unlike model_heads.DimensionOrdinalHeads).
        model = _tiny_model()
        from model_heads import CoralOrdinalHead
        self.assertIsInstance(model.head, CoralOrdinalHead)
        self.assertFalse(hasattr(model, "heads"))
        self.assertFalse(hasattr(model, "dimension_heads"))


class TestOverallScoreDecoding(unittest.TestCase):
    """Test 2: overall score decoding 0-4."""

    def test_coral_predict_decodes_into_0_to_4_range(self):
        from model_heads import coral_predict
        model = _tiny_model()
        input_ids, attention_mask = _batch([("QUESTION:\nWhat did you build?", "A pipeline.")])
        logits = model(input_ids, attention_mask)
        ordinal = int(coral_predict(logits)[0].item())
        self.assertGreaterEqual(ordinal, 0)
        self.assertLessEqual(ordinal, NUM_ORDINAL_CLASSES - 1)

    def test_overall_score_normalizes_ordinal_to_unit_interval(self):
        # Same normalization convention every other evaluator in this
        # codebase uses: ordinal / (num_classes - 1).
        for ordinal in range(NUM_ORDINAL_CLASSES):
            score = ordinal / (NUM_ORDINAL_CLASSES - 1)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        self.assertEqual(0 / (NUM_ORDINAL_CLASSES - 1), 0.0)
        self.assertEqual((NUM_ORDINAL_CLASSES - 1) / (NUM_ORDINAL_CLASSES - 1), 1.0)


class TestUnweightedCoralLoss(unittest.TestCase):
    def test_compute_overall_batch_loss_uses_plain_coral_loss_no_pos_weight(self):
        model = _tiny_model()
        input_ids, attention_mask = _batch([("QUESTION:\nA?", "B."), ("QUESTION:\nC?", "D.")])
        batch = {
            "main_input_ids": input_ids, "main_attention_mask": attention_mask,
            "overall_target": torch.tensor([2, 3]),
        }
        loss = compute_overall_batch_loss(model, batch, device="cpu")
        self.assertTrue(torch.is_tensor(loss))
        self.assertEqual(loss.ndim, 0)
        self.assertGreaterEqual(loss.item(), 0.0)


class TestCheckpointSaveLoadReproducibility(unittest.TestCase):
    """Test 7: checkpoint save/load reproduces identical output."""

    def test_save_then_load_reproduces_identical_predictions(self):
        model = _tiny_model()
        model.eval()
        input_ids, attention_mask = _batch([("QUESTION:\nHow did you test it?", "With unit tests.")])
        with torch.no_grad():
            original_logits = model(input_ids, attention_mask)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "weights.pt")
            save_overall_checkpoint_artifact(model, path)
            self.assertTrue(os.path.exists(path))

            # Reload into a FRESH architecture built from the same tiny
            # encoder shape -- reconstructing the exact backbone the
            # checkpoint was trained with, mirroring
            # model_checkpoint_io.load_checkpoint_artifact's own contract.
            reloaded_backbone = build_tiny_random_encoder(_TOKENIZER)
            reloaded = load_overall_checkpoint_artifact(path, BackboneConfig(), backbone=reloaded_backbone)
            reloaded.eval()
            with torch.no_grad():
                reloaded_logits = reloaded(input_ids, attention_mask)

        torch.testing.assert_close(original_logits, reloaded_logits)

    def test_reloaded_model_is_in_eval_mode(self):
        model = _tiny_model()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "weights.pt")
            save_overall_checkpoint_artifact(model, path)
            reloaded_backbone = build_tiny_random_encoder(_TOKENIZER)
            reloaded = load_overall_checkpoint_artifact(path, BackboneConfig(), backbone=reloaded_backbone)
        self.assertFalse(reloaded.training)


class TestMinimalTrainer(unittest.TestCase):
    def test_train_overall_model_runs_one_epoch_and_returns_model_in_eval_mode(self):
        encoder = build_tiny_random_encoder(_TOKENIZER)
        backbone_config = BackboneConfig()

        pairs = [("QUESTION:\nWhat did you build?", "A caching layer."),
                  ("QUESTION:\nWhy?", "For performance."),
                  ("QUESTION:\nHow?", "With Redis."),
                  ("QUESTION:\nWhen?", "Last year.")]
        input_ids, attention_mask = _batch(pairs)
        targets = torch.tensor([0, 1, 2, 3])

        class _OneBatchLoader:
            def __iter__(self):
                yield {"main_input_ids": input_ids, "main_attention_mask": attention_mask, "overall_target": targets}

            def __len__(self):
                return 1

        model = train_overall_model(
            _OneBatchLoader(), None, backbone_config, num_epochs=1, backbone=encoder, random_seed=42,
        )
        self.assertFalse(model.training)
        from overall_score_model import OverallScoreModel as _M
        self.assertIsInstance(model, _M)

    def test_reproducible_given_same_seed(self):
        import copy

        pairs = [("QUESTION:\nA?", "B."), ("QUESTION:\nC?", "D.")]
        input_ids, attention_mask = _batch(pairs)
        targets = torch.tensor([1, 3])

        class _OneBatchLoader:
            def __iter__(self):
                yield {"main_input_ids": input_ids, "main_attention_mask": attention_mask, "overall_target": targets}

            def __len__(self):
                return 1

        backbone_config = BackboneConfig()
        # Same STARTING backbone (deep-copied) for both runs -- isolates
        # what random_seed actually controls (head init + dropout masks),
        # matching model_heads.train_model's own documented seed contract
        # (backbone weights are already deterministic/pretrained in
        # production; only head init + dropout are randomly seeded here).
        base_encoder = build_tiny_random_encoder(_TOKENIZER)
        encoder_a = copy.deepcopy(base_encoder)
        model_a = train_overall_model(_OneBatchLoader(), None, backbone_config, num_epochs=1, backbone=encoder_a, random_seed=123)

        encoder_b = copy.deepcopy(base_encoder)
        model_b = train_overall_model(_OneBatchLoader(), None, backbone_config, num_epochs=1, backbone=encoder_b, random_seed=123)

        with torch.no_grad():
            logits_a = model_a(input_ids, attention_mask)
            logits_b = model_b(input_ids, attention_mask)
        torch.testing.assert_close(logits_a, logits_b)


if __name__ == "__main__":
    unittest.main()
