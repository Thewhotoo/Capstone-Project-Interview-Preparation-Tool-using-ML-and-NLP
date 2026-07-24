"""
Tests for model_checkpoint_io.py — torch state-dict <-> Checkpoint.artifact_uri
glue. Uses the tiny random backbone (approved clarification #4).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact, save_checkpoint_artifact
from model_heads import MultiTaskModel

_TOKENIZER = build_tokenizer(BackboneConfig())


class TestSaveAndLoadCheckpointArtifact(unittest.TestCase):
    def test_round_trips_weights(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.pt")
            returned_path = save_checkpoint_artifact(model, path)
            self.assertEqual(returned_path, path)
            self.assertTrue(os.path.exists(path))

            reload_backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
            loaded = load_checkpoint_artifact(path, BackboneConfig(), backbone=reload_backbone)

            original_state = model.state_dict()
            loaded_state = loaded.state_dict()
            self.assertEqual(set(original_state.keys()), set(loaded_state.keys()))
            for key in original_state:
                self.assertTrue(torch.equal(original_state[key], loaded_state[key]), f"mismatch at {key!r}")

    def test_loaded_model_is_in_eval_mode(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.pt")
            save_checkpoint_artifact(model, path)
            reload_backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
            loaded = load_checkpoint_artifact(path, BackboneConfig(), backbone=reload_backbone)
            self.assertFalse(loaded.training)

    def test_mismatched_architecture_raises(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.pt")
            save_checkpoint_artifact(model, path)
            mismatched_backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=8)  # different hidden size
            with self.assertRaises(RuntimeError):
                load_checkpoint_artifact(path, BackboneConfig(), backbone=mismatched_backbone)


if __name__ == "__main__":
    unittest.main()
