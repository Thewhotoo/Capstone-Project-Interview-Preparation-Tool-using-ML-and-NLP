"""Tests for deployment_evaluator.py's bootstrap wiring -- specifically
that a successfully-loaded, promotion-approved trained checkpoint results
in a HybridEvaluator (not a bare TrainedEvaluator) becoming the active
production evaluator, per the Hybrid Evaluator design.

Uses a tiny random backbone and a temp directory standing in for
deployed_model/ (monkeypatched module-level paths) -- never touches the
real, large local checkpoint on this machine, and works identically on a
fresh machine with no checkpoint at all."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deployment_evaluator
import evaluator_registry
from experiment_dataset_io import save_json
from hybrid_evaluator import HybridEvaluator
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_heads import MultiTaskModel
from training_experimentation import ExperimentConfig, PromotionDecision, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


def _write_fixture_deployment(deploy_dir: str, approved: bool) -> None:
    """Writes checkpoint/promotion-decision JSON only -- deliberately no
    real weights file. bootstrap_production_evaluator's own
    load_checkpoint_artifact call is monkeypatched (see
    _PatchedDeploymentPaths) to return a tiny random model instead of
    actually loading the real deberta-v3-base architecture these tests
    don't need and shouldn't pay the cost of downloading/loading."""
    os.makedirs(deploy_dir, exist_ok=True)
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="v1")
    checkpoint = assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="unused")
    save_json(checkpoint, os.path.join(deploy_dir, "best_checkpoint.json"))

    decision = PromotionDecision(
        approved=approved, rationale="test fixture",
        checkpoint_model_version="m1", benchmark_id="bench_1",
    )
    save_json(decision, os.path.join(deploy_dir, "final_promotion_decision.json"))

    # Placeholder so a missing-file check (if any) doesn't short-circuit
    # before the monkeypatched loader is reached.
    open(os.path.join(deploy_dir, "best_checkpoint_weights.pt"), "wb").close()


def _tiny_model_loader(path, backbone_config):
    """Stand-in for model_checkpoint_io.load_checkpoint_artifact -- same
    signature, ignores both arguments, returns a fresh tiny-random
    MultiTaskModel so the bootstrap control-flow under test never touches
    the real pretrained deberta-v3-base backbone."""
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    return MultiTaskModel(BackboneConfig(), backbone=backbone)


class _PatchedDeploymentPaths:
    """Context manager: monkeypatches deployment_evaluator's module-level
    path constants to point at a fixture directory, restoring the real
    ones afterward -- never mutates the actual deployed_model/ paths."""

    def __init__(self, deploy_dir):
        self.deploy_dir = deploy_dir
        self._originals = {}

    def __enter__(self):
        self._originals = {
            "DEPLOYED_MODEL_DIR": deployment_evaluator.DEPLOYED_MODEL_DIR,
            "DEPLOYED_WEIGHTS_PATH": deployment_evaluator.DEPLOYED_WEIGHTS_PATH,
            "DEPLOYED_CHECKPOINT_PATH": deployment_evaluator.DEPLOYED_CHECKPOINT_PATH,
            "DEPLOYED_PROMOTION_DECISION_PATH": deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH,
            "load_checkpoint_artifact": deployment_evaluator.load_checkpoint_artifact,
        }
        deployment_evaluator.DEPLOYED_MODEL_DIR = self.deploy_dir
        deployment_evaluator.DEPLOYED_WEIGHTS_PATH = os.path.join(self.deploy_dir, "best_checkpoint_weights.pt")
        deployment_evaluator.DEPLOYED_CHECKPOINT_PATH = os.path.join(self.deploy_dir, "best_checkpoint.json")
        deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(self.deploy_dir, "final_promotion_decision.json")
        deployment_evaluator.load_checkpoint_artifact = _tiny_model_loader
        return self

    def __exit__(self, *exc_info):
        for name, value in self._originals.items():
            setattr(deployment_evaluator, name, value)


class TestBootstrapWithApprovedCheckpoint(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None

    def test_hybrid_evaluator_becomes_active_not_bare_trained_evaluator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_fixture_deployment(tmpdir, approved=True)
            with _PatchedDeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HybridEvaluator)
            self.assertEqual(evaluator_registry.active_evaluator_name(), "hybrid-v1")

    def test_trained_evaluator_still_registered_but_not_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_fixture_deployment(tmpdir, approved=True)
            with _PatchedDeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            registered_names = evaluator_registry.registered_evaluator_names()
            self.assertIn("hybrid-v1", registered_names)
            self.assertTrue(any(n.startswith("trained-") for n in registered_names))
            self.assertNotEqual(evaluator_registry.active_evaluator_name(), next(
                n for n in registered_names if n.startswith("trained-")
            ))


class TestBootstrapFallback(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None

    def test_falls_back_to_bare_heuristic_when_checkpoint_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Deliberately empty directory -- no checkpoint files at all,
            # simulating a fresh clone (the documented, expected real-world
            # default state per the earlier architecture investigation).
            with _PatchedDeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            self.assertEqual(evaluator_registry.active_evaluator_name(), "heuristic-v1")

    def test_falls_back_to_bare_heuristic_when_promotion_not_approved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_fixture_deployment(tmpdir, approved=False)
            with _PatchedDeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            self.assertEqual(evaluator_registry.active_evaluator_name(), "heuristic-v1")


if __name__ == "__main__":
    unittest.main()
