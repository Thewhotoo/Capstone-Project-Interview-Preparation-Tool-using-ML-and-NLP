"""
Tests for `run_overall_single_training.py`'s LOCAL-safe pieces: environment
reporting, the hard CUDA-required gate, config sanity, and isolation from
every existing artifact directory. Never downloads the real backbone,
never trains -- mirrors `test_four_dim_training_entrypoint.py`'s own
discipline for `run_four_dim_training.py`.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_four_dim_training
import run_overall_single_training as entrypoint


class TestEnvironmentReport(unittest.TestCase):
    def test_report_contains_required_fields(self):
        report = entrypoint.environment_report()
        for key in ("python_version", "torch_version", "transformers_version", "cuda_available", "gpu_name", "gpu_count"):
            self.assertIn(key, report)


class TestRequireCudaOrExit(unittest.TestCase):
    def test_exits_when_cuda_unavailable(self):
        with self.assertRaises(SystemExit) as ctx:
            entrypoint.require_cuda_or_exit({"cuda_available": False})
        self.assertEqual(ctx.exception.code, 1)

    def test_does_not_exit_when_cuda_available(self):
        try:
            entrypoint.require_cuda_or_exit({"cuda_available": True})
        except SystemExit:
            self.fail("require_cuda_or_exit must not exit when cuda_available is True")


class TestDryRunIsSafe(unittest.TestCase):
    def test_dry_run_never_requires_cuda_and_loads_the_frozen_pool(self):
        exit_code = entrypoint.dry_run()
        self.assertEqual(exit_code, 0)

    def test_dry_run_does_not_import_the_real_backbone_model_class(self):
        import ast
        import inspect
        source = inspect.getsource(entrypoint.dry_run)
        tree = ast.parse(source)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("OverallScoreModel", names)
        self.assertNotIn("build_tokenizer", names)


class TestConfigSanity(unittest.TestCase):
    def test_config_matches_the_specified_hyperparameters(self):
        self.assertEqual(entrypoint.CONFIG["base_model"], "microsoft/deberta-v3-base")
        self.assertTrue(entrypoint.CONFIG["fresh_initialization"])
        self.assertEqual(entrypoint.CONFIG["random_seed"], 42)
        self.assertEqual(entrypoint.CONFIG["learning_rate"], 2e-5)
        self.assertEqual(entrypoint.CONFIG["batch_size"], 8)
        self.assertEqual(entrypoint.CONFIG["num_epochs"], 8)
        self.assertEqual(entrypoint.CONFIG["max_length"], 256)
        self.assertEqual(entrypoint.CONFIG["weight_decay"], 0.01)
        self.assertIn("AdamW", entrypoint.CONFIG["optimizer"])
        self.assertIn("none", entrypoint.CONFIG["scheduler"])
        self.assertIn("unweighted", entrypoint.CONFIG["loss"])

    def test_experiment_registered_and_reuses_the_frozen_v2_pool_and_split(self):
        cfg = entrypoint.EXPERIMENTS["v3_overall_single"]
        self.assertEqual(cfg["dataset_split_identifier"], "four_dim_experiment_v2")
        self.assertEqual(cfg["split_seed"], "four_dim_v2_split_348")
        self.assertEqual(cfg["expected_total"], 220)
        self.assertEqual(cfg["expected_counts"], (166, 27, 27))
        self.assertTrue(cfg["split_json_path"].replace("\\", "/").endswith(
            "artifacts/four_dim_experiment_v2/split.json"
        ))


class TestIsolationFromExistingArtifacts(unittest.TestCase):
    """This training script must never be able to overwrite any prior
    experiment's checkpoint or the currently-deployed A2 artifacts."""

    def test_artifacts_dir_is_new_and_distinct_from_every_existing_experiment_dir(self):
        this_dir = entrypoint.EXPERIMENTS["v3_overall_single"]["artifacts_dir"]
        self.assertTrue(this_dir.replace("\\", "/").endswith("artifacts/overall_single_v3"))
        existing_dirs = {cfg["artifacts_dir"] for cfg in run_four_dim_training.EXPERIMENTS.values()}
        self.assertNotIn(this_dir, existing_dirs)

    def test_artifacts_dir_is_distinct_from_deployed_model_directories(self):
        import deployment_evaluator
        this_dir = entrypoint.EXPERIMENTS["v3_overall_single"]["artifacts_dir"]
        self.assertNotEqual(this_dir, deployment_evaluator.DEPLOYED_MODEL_DIR)
        self.assertNotEqual(this_dir, deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR)

    def test_never_imports_or_touches_registration_machinery(self):
        # This script only produces a checkpoint on disk -- it must never
        # import the registry (would imply it could go live on its own).
        import ast
        import inspect
        source = inspect.getsource(entrypoint)
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
        self.assertNotIn("evaluator_registry", imported_modules)
        self.assertNotIn("deployment_evaluator", imported_modules)


class TestUnknownExperimentRejected(unittest.TestCase):
    def test_unknown_experiment_name_is_rejected_by_main(self):
        with mock.patch.object(sys, "argv", ["run_overall_single_training.py", "--dry-run", "nope"]):
            exit_code = entrypoint.main()
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
