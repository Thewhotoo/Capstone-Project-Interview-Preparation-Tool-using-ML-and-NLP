"""
Tests for the V3 single-overall-score production cutover:
`deployment_evaluator.py`'s three-tier fallback chain (V3 single-overall ->
A2 -> bare HeuristicEvaluator), `deployed_model_overall_single_v3/` wiring,
and `activate_a2_rollback()`'s standalone rollback path.

Never touches the actual `deployed_model_overall_single_v3/`/
`deployed_model_a2/`/`deployed_model/` directories on disk -- paths are
monkeypatched to temp directories throughout, mirroring
`test_deployment_evaluator_a2.py`'s own `_PatchedA2DeploymentPaths`.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deployment_evaluator
import evaluator_registry
from experiment_dataset_io import save_json
from heuristic_evaluator import HeuristicEvaluator
from hybrid_evaluator import HybridEvaluator
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from overall_score_model import OverallScoreModel, save_overall_checkpoint_artifact
from overall_single_evaluator import OverallSingleEvaluator
from training_experimentation import ExperimentConfig, PromotionDecision, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


def _tiny_overall_model() -> OverallScoreModel:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    return OverallScoreModel(BackboneConfig(), backbone=backbone)


def _write_overall_single_fixture_deployment(deploy_dir: str, approved: bool = True) -> None:
    os.makedirs(deploy_dir, exist_ok=True)
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=42, dataset_version="four_dim_experiment_v2")
    checkpoint = assemble_checkpoint(
        model_version="deberta_v3_base_overall_single_v3_epoch6",
        experiment_config=config, artifact_uri="unused",
    )
    save_json(checkpoint, os.path.join(deploy_dir, "best_checkpoint.json"))
    decision = PromotionDecision(
        approved=approved, rationale="test fixture", checkpoint_model_version=checkpoint.model_version,
        benchmark_id="test_bench",
    )
    save_json(decision, os.path.join(deploy_dir, "final_promotion_decision.json"))
    save_overall_checkpoint_artifact(_tiny_overall_model(), os.path.join(deploy_dir, "best_checkpoint_weights.pt"))


def _write_a2_fixture_deployment(deploy_dir: str, approved: bool = True) -> None:
    from model_backbone import build_tiny_random_encoder as _bte
    from model_checkpoint_io import save_checkpoint_artifact
    from model_heads import MultiTaskModel
    from evaluation_dimensions import all_keys as canonical_dimension_keys

    os.makedirs(deploy_dir, exist_ok=True)
    backbone = _bte(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=canonical_dimension_keys())
    save_checkpoint_artifact(model, os.path.join(deploy_dir, "best_checkpoint_weights.pt"))

    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=42, dataset_version="four_dim_experiment_v2")
    checkpoint = assemble_checkpoint(
        model_version="deberta_v3_base_four_dim_training_v3_expA2_epoch7",
        experiment_config=config, artifact_uri="unused",
    )
    save_json(checkpoint, os.path.join(deploy_dir, "best_checkpoint.json"))
    decision = PromotionDecision(
        approved=approved, rationale="test fixture", checkpoint_model_version=checkpoint.model_version,
        benchmark_id="test_bench",
    )
    save_json(decision, os.path.join(deploy_dir, "final_promotion_decision.json"))


def _tiny_canonical_a2_loader(path, backbone_config, **kwargs):
    from model_heads import MultiTaskModel
    from evaluation_dimensions import all_keys as canonical_dimension_keys
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    return MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=canonical_dimension_keys())


def _tiny_overall_loader(path, backbone_config, **kwargs):
    return _tiny_overall_model()


class _PatchedDeploymentPaths:
    """Patches BOTH tier-1 (overall_single_v3) and tier-2 (A2) module
    globals at once, plus their loader functions -- so a test can control
    which tier's directory has real fixture files and which is empty
    (simulating that tier's failure) independently."""

    def __init__(self, overall_single_dir: str, a2_dir: str):
        self.overall_single_dir = overall_single_dir
        self.a2_dir = a2_dir
        self._originals = {}

    def __enter__(self):
        self._originals = {
            "DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3": deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3,
            "_OVERALL_SINGLE_V3_WEIGHTS_PATH": deployment_evaluator._OVERALL_SINGLE_V3_WEIGHTS_PATH,
            "_OVERALL_SINGLE_V3_CHECKPOINT_PATH": deployment_evaluator._OVERALL_SINGLE_V3_CHECKPOINT_PATH,
            "_OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH": deployment_evaluator._OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH,
            "load_overall_checkpoint_artifact": deployment_evaluator.load_overall_checkpoint_artifact,
            "DEPLOYED_MODEL_DIR": deployment_evaluator.DEPLOYED_MODEL_DIR,
            "DEPLOYED_WEIGHTS_PATH": deployment_evaluator.DEPLOYED_WEIGHTS_PATH,
            "DEPLOYED_CHECKPOINT_PATH": deployment_evaluator.DEPLOYED_CHECKPOINT_PATH,
            "DEPLOYED_PROMOTION_DECISION_PATH": deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH,
            "load_checkpoint_artifact": deployment_evaluator.load_checkpoint_artifact,
        }
        deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3 = self.overall_single_dir
        deployment_evaluator._OVERALL_SINGLE_V3_WEIGHTS_PATH = os.path.join(self.overall_single_dir, "best_checkpoint_weights.pt")
        deployment_evaluator._OVERALL_SINGLE_V3_CHECKPOINT_PATH = os.path.join(self.overall_single_dir, "best_checkpoint.json")
        deployment_evaluator._OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH = os.path.join(self.overall_single_dir, "final_promotion_decision.json")
        deployment_evaluator.load_overall_checkpoint_artifact = _tiny_overall_loader

        deployment_evaluator.DEPLOYED_MODEL_DIR = self.a2_dir
        deployment_evaluator.DEPLOYED_WEIGHTS_PATH = os.path.join(self.a2_dir, "best_checkpoint_weights.pt")
        deployment_evaluator.DEPLOYED_CHECKPOINT_PATH = os.path.join(self.a2_dir, "best_checkpoint.json")
        deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(self.a2_dir, "final_promotion_decision.json")
        deployment_evaluator.load_checkpoint_artifact = _tiny_canonical_a2_loader
        return self

    def __exit__(self, *exc_info):
        for name, value in self._originals.items():
            setattr(deployment_evaluator, name, value)


class _RegistryReset(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None


class TestOverallSingleV3ArtifactPaths(unittest.TestCase):
    def test_deployed_model_dir_points_at_overall_single_v3(self):
        self.assertTrue(
            deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3.replace("\\", "/").endswith(
                "deployed_model_overall_single_v3"
            )
        )

    def test_all_three_expected_paths_derive_from_overall_single_v3_dir(self):
        for p in (
            deployment_evaluator._OVERALL_SINGLE_V3_WEIGHTS_PATH,
            deployment_evaluator._OVERALL_SINGLE_V3_CHECKPOINT_PATH,
            deployment_evaluator._OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH,
        ):
            self.assertTrue(p.startswith(deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3))

    def test_isolated_from_a2_and_legacy_directories(self):
        self.assertNotEqual(
            deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, deployment_evaluator.DEPLOYED_MODEL_DIR,
        )
        self.assertNotEqual(
            deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR,
        )


class TestThreeTierFallbackChain(_RegistryReset):
    def test_tier1_succeeds_overall_single_evaluator_becomes_active(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            _write_overall_single_fixture_deployment(overall_dir)
            _write_a2_fixture_deployment(a2_dir)  # present but must NOT be used
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, OverallSingleEvaluator)
            self.assertNotIsInstance(active, HybridEvaluator)

    def test_tier1_missing_falls_back_to_tier2_a2(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            # overall_dir left EMPTY -- tier 1 must fail.
            _write_a2_fixture_deployment(a2_dir)
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HybridEvaluator)

    def test_tier1_and_tier2_both_missing_falls_back_to_heuristic(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            # Both left EMPTY -- both tiers must fail.
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HeuristicEvaluator)

    def test_tier1_unapproved_promotion_falls_back_to_tier2(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            _write_overall_single_fixture_deployment(overall_dir, approved=False)
            _write_a2_fixture_deployment(a2_dir)
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HybridEvaluator)

    def test_overall_single_evaluator_registered_under_its_own_declared_name(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            _write_overall_single_fixture_deployment(overall_dir)
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertTrue(active.name.startswith("overall-single-"))
            self.assertEqual(evaluator_registry.get_evaluator(active.name), active)


class TestA2RollbackExplicitPath(_RegistryReset):
    def test_activate_a2_rollback_skips_tier1_even_when_it_would_succeed(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            _write_overall_single_fixture_deployment(overall_dir)  # tier 1 WOULD succeed
            _write_a2_fixture_deployment(a2_dir)
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.activate_a2_rollback()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HybridEvaluator)
            self.assertNotIsInstance(active, OverallSingleEvaluator)

    def test_activate_a2_rollback_falls_back_to_heuristic_if_a2_unavailable(self):
        with tempfile.TemporaryDirectory() as overall_dir, tempfile.TemporaryDirectory() as a2_dir:
            # a2_dir left empty -- rollback tier itself unavailable.
            with _PatchedDeploymentPaths(overall_dir, a2_dir):
                deployment_evaluator.activate_a2_rollback()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HeuristicEvaluator)


class TestNoInventedDimensionMapping(unittest.TestCase):
    def test_deployment_evaluator_module_has_no_new_dimension_mapping_code(self):
        import inspect
        source = inspect.getsource(deployment_evaluator)
        self.assertNotIn("LEGACY_DIMENSION_MAP", source)


if __name__ == "__main__":
    unittest.main()
