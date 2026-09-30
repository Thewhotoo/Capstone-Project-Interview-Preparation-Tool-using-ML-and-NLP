"""
Tests for model_heads.py — CORAL ordinal regression, dimension masking,
concept-observation head, the shared missing-reasoning head, losses, and
the minimal reference trainer. Uses the real tokenizer paired with a tiny
randomly-initialized backbone (approved clarification #4).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer, tokenize_pair
from model_heads import (
    _MISSING_REASONING_CATEGORIES,
    CoralOrdinalHead,
    MultiTaskModel,
    coral_confidence,
    coral_loss,
    coral_predict,
    coral_targets,
    compute_batch_loss,
    missing_reasoning_loss,
    train_model,
)
from reasoning_dimension_relevance import ALL_DIMENSIONS

_TOKENIZER = build_tokenizer(BackboneConfig())


def _batch(tokenizer, pairs: list[tuple[str, str]]):
    encodings = [tokenize_pair(tokenizer, a, b, max_length=16) for a, b in pairs]
    return tokenizer.pad(encodings, return_tensors="pt")


class TestCoralOrdinalHead(unittest.TestCase):
    def test_output_shape_is_num_classes_minus_one(self):
        head = CoralOrdinalHead(in_features=8, num_classes=5)
        x = torch.randn(3, 8)
        logits = head(x)
        self.assertEqual(logits.shape, (3, 4))

    def test_biases_are_monotonically_non_increasing(self):
        head = CoralOrdinalHead(in_features=8, num_classes=5)
        x = torch.zeros(1, 8)  # shared(x) contributes 0 -> logits == biases
        logits = head(x)[0]
        diffs = logits[1:] - logits[:-1]
        self.assertTrue(torch.all(diffs <= 1e-6))

    def test_rejects_fewer_than_two_classes(self):
        with self.assertRaises(ValueError):
            CoralOrdinalHead(in_features=8, num_classes=1)


class TestCoralTargetsAndLoss(unittest.TestCase):
    def test_targets_encode_rank(self):
        y = torch.tensor([0, 2, 4])
        targets = coral_targets(y, num_classes=5)
        self.assertEqual(targets.tolist(), [
            [0, 0, 0, 0],
            [1, 1, 0, 0],
            [1, 1, 1, 1],
        ])

    def test_predict_recovers_perfect_targets(self):
        # Construct logits that are unambiguously correct for each true class.
        y = torch.tensor([0, 1, 2, 3, 4])
        targets = coral_targets(y, num_classes=5)
        logits = (targets * 2 - 1) * 10.0  # +-10 logits matching each target exactly
        predicted = coral_predict(logits)
        self.assertEqual(predicted.tolist(), y.tolist())

    def test_loss_is_lower_for_correct_than_incorrect_logits(self):
        y = torch.tensor([4, 4, 4])
        correct_targets = coral_targets(y, num_classes=5)
        correct_logits = (correct_targets * 2 - 1) * 10.0
        wrong_logits = -correct_logits
        self.assertLess(
            coral_loss(correct_logits, y, num_classes=5).item(),
            coral_loss(wrong_logits, y, num_classes=5).item(),
        )

    def test_confidence_is_high_for_confident_logits_low_for_uncertain(self):
        confident_logits = torch.full((1, 4), 10.0)
        uncertain_logits = torch.zeros((1, 4))
        confident = coral_confidence(confident_logits)[0].item()
        uncertain = coral_confidence(uncertain_logits)[0].item()
        self.assertGreater(confident, uncertain)
        self.assertAlmostEqual(uncertain, 0.0, places=3)


class TestMissingReasoningLoss(unittest.TestCase):
    def test_severity_loss_ignored_when_not_present(self):
        presence_logits = torch.tensor([[10.0, -10.0]])  # confidently: present, absent
        severity_pred = torch.tensor([[0.9, 0.9]])  # severity=0.9 predicted for BOTH
        presence_target = torch.tensor([[1.0, 0.0]])
        severity_target_matching = torch.tensor([[0.9, 0.0]])  # absent category's target severity is 0
        loss_matching = missing_reasoning_loss(presence_logits, severity_pred, presence_target, severity_target_matching)

        severity_target_mismatched_on_absent = torch.tensor([[0.9, 0.5]])  # differs only on the absent slot
        loss_mismatched = missing_reasoning_loss(
            presence_logits, severity_pred, presence_target, severity_target_mismatched_on_absent,
        )
        # Severity target on an absent category must not affect the loss at all.
        self.assertAlmostEqual(loss_matching.item(), loss_mismatched.item(), places=5)


class TestMultiTaskModel(unittest.TestCase):
    def _model(self) -> MultiTaskModel:
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        return MultiTaskModel(BackboneConfig(), backbone=backbone)

    def test_forward_dimensions_produces_all_declared_dimensions(self):
        model = self._model()
        batch = _batch(_TOKENIZER, [("question", "answer")])
        outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(set(outputs["dimension_logits"].keys()), set(ALL_DIMENSIONS))
        self.assertEqual(outputs["presence_logits"].shape, (1, len(_MISSING_REASONING_CATEGORIES)))
        self.assertEqual(outputs["severity_pred"].shape, (1, len(_MISSING_REASONING_CATEGORIES)))

    def test_forward_concept_produces_three_class_logits(self):
        model = self._model()
        batch = _batch(_TOKENIZER, [("answer", "caching")])
        logits = model.forward_concept(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(logits.shape, (1, 3))


class TestComputeBatchLossAndTrainModel(unittest.TestCase):
    def _fake_batch(self, n: int = 2, with_concepts: bool = True) -> dict:
        pairs = [("question", "answer") for _ in range(n)]
        main = _batch(_TOKENIZER, pairs)
        dimension_targets = torch.randint(0, 5, (n, len(ALL_DIMENSIONS)))
        dimension_mask = torch.ones((n, len(ALL_DIMENSIONS)))
        presence_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        presence_target[:, 0] = 1.0
        severity_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        severity_target[:, 0] = 0.5

        if with_concepts:
            concept_batch = _batch(_TOKENIZER, [("answer", "caching")] * n)
            concept_input_ids = concept_batch["input_ids"]
            concept_attention_mask = concept_batch["attention_mask"]
            concept_targets = torch.zeros(n, dtype=torch.long)
        else:
            concept_input_ids = None
            concept_attention_mask = None
            concept_targets = torch.empty(0, dtype=torch.long)

        return {
            "main_input_ids": main["input_ids"], "main_attention_mask": main["attention_mask"],
            "dimension_targets": dimension_targets, "dimension_mask": dimension_mask,
            "presence_target": presence_target, "severity_target": severity_target,
            "concept_input_ids": concept_input_ids, "concept_attention_mask": concept_attention_mask,
            "concept_targets": concept_targets,
        }

    def test_compute_batch_loss_is_a_scalar_requiring_grad(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)
        loss = compute_batch_loss(model, self._fake_batch())
        self.assertEqual(loss.dim(), 0)
        self.assertTrue(loss.requires_grad)

    def test_compute_batch_loss_handles_no_concepts(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)
        loss = compute_batch_loss(model, self._fake_batch(with_concepts=False))
        self.assertEqual(loss.dim(), 0)

    def test_train_model_produces_a_model_with_updated_weights(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        before = {name: p.clone() for name, p in MultiTaskModel(BackboneConfig(), backbone=backbone).named_parameters()}

        backbone_for_training = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        train_loader = [self._fake_batch(), self._fake_batch()]
        trained = train_model(train_loader, None, BackboneConfig(), num_epochs=1, backbone=backbone_for_training)

        self.assertIsInstance(trained, MultiTaskModel)
        self.assertFalse(trained.training)  # left in eval() mode


class TestTrainModelReproducibility(unittest.TestCase):
    """Experiment 0 (research-validity milestone): with an explicit
    `random_seed`, repeated `train_model` calls must produce bit-identical
    trained weights given identical inputs; different seeds must produce
    different weights (proving the seed has a real effect, not a no-op)."""

    def _fake_batch(self, n: int = 2) -> dict:
        pairs = [("question", "answer") for _ in range(n)]
        main = _batch(_TOKENIZER, pairs)
        dimension_targets = torch.randint(0, 5, (n, len(ALL_DIMENSIONS)))
        dimension_mask = torch.ones((n, len(ALL_DIMENSIONS)))
        presence_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        presence_target[:, 0] = 1.0
        severity_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        severity_target[:, 0] = 0.5
        concept_batch = _batch(_TOKENIZER, [("answer", "caching")] * n)
        return {
            "main_input_ids": main["input_ids"], "main_attention_mask": main["attention_mask"],
            "dimension_targets": dimension_targets, "dimension_mask": dimension_mask,
            "presence_target": presence_target, "severity_target": severity_target,
            "concept_input_ids": concept_batch["input_ids"], "concept_attention_mask": concept_batch["attention_mask"],
            "concept_targets": torch.zeros(n, dtype=torch.long),
        }

    def _identically_seeded_backbones(self, seed: int):
        """Two SEPARATE tiny backbone instances with bit-identical initial
        weights -- each construction is preceded by the same manual_seed
        call, so both consume the RNG identically."""
        torch.manual_seed(seed)
        backbone_a = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        torch.manual_seed(seed)
        backbone_b = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        return backbone_a, backbone_b

    def _state_dicts_equal(self, model_a: MultiTaskModel, model_b: MultiTaskModel) -> bool:
        state_a, state_b = model_a.state_dict(), model_b.state_dict()
        if set(state_a.keys()) != set(state_b.keys()):
            return False
        return all(torch.equal(state_a[k], state_b[k]) for k in state_a)

    def test_identically_seeded_backbones_start_with_equal_weights(self):
        backbone_a, backbone_b = self._identically_seeded_backbones(seed=123)
        self.assertTrue(torch.equal(
            dict(backbone_a.named_parameters())["encoder.embeddings.word_embeddings.weight"],
            dict(backbone_b.named_parameters())["encoder.embeddings.word_embeddings.weight"],
        ))

    def test_same_seed_produces_bit_identical_trained_weights(self):
        backbone_a, backbone_b = self._identically_seeded_backbones(seed=42)
        train_loader = [self._fake_batch(), self._fake_batch()]

        trained_a = train_model(
            list(train_loader), None, BackboneConfig(), num_epochs=1, backbone=backbone_a, random_seed=7,
        )
        trained_b = train_model(
            list(train_loader), None, BackboneConfig(), num_epochs=1, backbone=backbone_b, random_seed=7,
        )
        self.assertTrue(self._state_dicts_equal(trained_a, trained_b))

    def test_different_seed_produces_different_trained_weights(self):
        backbone_a, backbone_b = self._identically_seeded_backbones(seed=42)
        train_loader = [self._fake_batch(), self._fake_batch()]

        trained_a = train_model(
            list(train_loader), None, BackboneConfig(), num_epochs=1, backbone=backbone_a, random_seed=1,
        )
        trained_b = train_model(
            list(train_loader), None, BackboneConfig(), num_epochs=1, backbone=backbone_b, random_seed=2,
        )
        self.assertFalse(self._state_dicts_equal(trained_a, trained_b))

    def test_no_seed_still_trains_without_error(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        train_loader = [self._fake_batch()]
        trained = train_model(train_loader, None, BackboneConfig(), num_epochs=1, backbone=backbone)
        self.assertIsInstance(trained, MultiTaskModel)


class TestTrainModelEpochCheckpointing(unittest.TestCase):
    """Experiment 1 (session 10): on_epoch_end lets a caller capture the
    model's state at every point along an epoch curve from ONE training
    run, instead of restarting from scratch per epoch count."""

    def _fake_batch(self, n: int = 2) -> dict:
        pairs = [("question", "answer") for _ in range(n)]
        main = _batch(_TOKENIZER, pairs)
        dimension_targets = torch.randint(0, 5, (n, len(ALL_DIMENSIONS)))
        dimension_mask = torch.ones((n, len(ALL_DIMENSIONS)))
        presence_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        presence_target[:, 0] = 1.0
        severity_target = torch.zeros((n, len(_MISSING_REASONING_CATEGORIES)))
        severity_target[:, 0] = 0.5
        concept_batch = _batch(_TOKENIZER, [("answer", "caching")] * n)
        return {
            "main_input_ids": main["input_ids"], "main_attention_mask": main["attention_mask"],
            "dimension_targets": dimension_targets, "dimension_mask": dimension_mask,
            "presence_target": presence_target, "severity_target": severity_target,
            "concept_input_ids": concept_batch["input_ids"], "concept_attention_mask": concept_batch["attention_mask"],
            "concept_targets": torch.zeros(n, dtype=torch.long),
        }

    def test_callback_fires_once_before_training_and_once_per_epoch(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        train_loader = [self._fake_batch(), self._fake_batch()]
        val_loader = [self._fake_batch()]
        calls = []

        def on_epoch_end(epoch_index, model, train_loss, val_loss):
            calls.append((epoch_index, isinstance(model, MultiTaskModel), train_loss, val_loss))

        train_model(
            train_loader, val_loader, BackboneConfig(), num_epochs=3, backbone=backbone,
            on_epoch_end=on_epoch_end,
        )

        self.assertEqual([c[0] for c in calls], [0, 1, 2, 3])
        self.assertTrue(all(c[1] for c in calls))
        # Epoch 0 (untrained) has no loss yet; epochs 1-3 have both train and val loss.
        self.assertEqual(calls[0][2], None)
        self.assertEqual(calls[0][3], None)
        for epoch_index, _, train_loss, val_loss in calls[1:]:
            self.assertIsInstance(train_loss, float)
            self.assertIsInstance(val_loss, float)

    def test_callback_receives_none_val_loss_without_a_val_loader(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        train_loader = [self._fake_batch()]
        calls = []

        train_model(
            train_loader, None, BackboneConfig(), num_epochs=1, backbone=backbone,
            on_epoch_end=lambda i, m, tl, vl: calls.append((i, tl, vl)),
        )
        self.assertEqual(calls[-1][2], None)

    def test_no_callback_preserves_prior_behavior(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        train_loader = [self._fake_batch()]
        trained = train_model(train_loader, None, BackboneConfig(), num_epochs=1, backbone=backbone)
        self.assertIsInstance(trained, MultiTaskModel)


if __name__ == "__main__":
    unittest.main()
