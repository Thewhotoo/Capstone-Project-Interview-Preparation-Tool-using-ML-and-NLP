"""
Tests for model_backbone.py — BackboneConfig, tokenizer pipeline, and the
CrossEncoderBackbone wrapper. Uses the real tokenizer paired with a tiny,
randomly-initialized DeBERTa-v2 body (approved clarification #4) — never a
full pretrained-weight download in unit tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer, tokenize_pair

_TOKENIZER = build_tokenizer(BackboneConfig())


class TestBackboneConfig(unittest.TestCase):
    def test_defaults(self):
        config = BackboneConfig()
        self.assertEqual(config.hf_model_id, "microsoft/deberta-v3-base")
        self.assertEqual(config.pooling, "cls")
        self.assertEqual(config.max_length, 256)

    def test_rejects_empty_model_id(self):
        with self.assertRaises(ValueError):
            BackboneConfig(hf_model_id="  ")

    def test_rejects_non_positive_max_length(self):
        with self.assertRaises(ValueError):
            BackboneConfig(max_length=0)

    def test_rejects_invalid_pooling(self):
        with self.assertRaises(ValueError):
            BackboneConfig(pooling="max")


class TestTokenizePair(unittest.TestCase):
    def test_produces_input_ids_and_attention_mask(self):
        encoding = tokenize_pair(_TOKENIZER, "question text", "answer text", max_length=32)
        self.assertIn("input_ids", encoding)
        self.assertIn("attention_mask", encoding)

    def test_truncates_to_max_length(self):
        long_text = " ".join(["word"] * 500)
        encoding = tokenize_pair(_TOKENIZER, long_text, long_text, max_length=16)
        self.assertLessEqual(len(encoding["input_ids"]), 16)


class TestCrossEncoderBackbone(unittest.TestCase):
    def test_cls_pooling_produces_expected_shape(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        encoding = tokenize_pair(_TOKENIZER, "question", "answer", max_length=16)
        batch = _TOKENIZER.pad([encoding], return_tensors="pt")
        pooled = backbone(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(pooled.shape, (1, 16))

    def test_mean_pooling_produces_expected_shape(self):
        from model_backbone import CrossEncoderBackbone
        from transformers import AutoModel, DebertaV2Config

        tiny_config = DebertaV2Config(
            vocab_size=_TOKENIZER.vocab_size, hidden_size=16, num_hidden_layers=1,
            num_attention_heads=2, intermediate_size=32, pad_token_id=_TOKENIZER.pad_token_id or 0,
        )
        encoder = AutoModel.from_config(tiny_config)
        backbone = CrossEncoderBackbone(BackboneConfig(pooling="mean"), encoder=encoder)
        encoding = tokenize_pair(_TOKENIZER, "question", "answer", max_length=16)
        batch = _TOKENIZER.pad([encoding], return_tensors="pt")
        pooled = backbone(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(pooled.shape, (1, 16))

    def test_batch_of_pairs_produces_one_embedding_per_pair(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        encodings = [
            tokenize_pair(_TOKENIZER, "q1", "a1", max_length=16),
            tokenize_pair(_TOKENIZER, "q2", "a2 longer text here", max_length=16),
        ]
        batch = _TOKENIZER.pad(encodings, return_tensors="pt")
        pooled = backbone(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(pooled.shape, (2, 16))


if __name__ == "__main__":
    unittest.main()
