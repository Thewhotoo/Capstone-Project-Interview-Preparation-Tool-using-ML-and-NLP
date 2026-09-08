"""
Tests for `run_four_dim_training.py`'s LOCAL-safe pieces only: environment
reporting, the hard CUDA-required gate, and config/path sanity. Never
downloads the real backbone, never trains -- that requires a GPU-backed
Colab runtime (see COLAB_RUN.md) and is explicitly out of scope for local
tests, per this phase's own constraint.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_dimensions import CANONICAL_DIMENSIONS
import run_four_dim_training as entrypoint


class TestEnvironmentReport(unittest.TestCase):
    def test_report_contains_required_fields(self):
        report = entrypoint.environment_report()
        for key in ("python_version", "torch_version", "transformers_version", "cuda_available", "gpu_name", "gpu_count"):
            self.assertIn(key, report)

    def test_gpu_name_is_none_when_cuda_unavailable(self):
        with mock.patch("torch.cuda.is_available", return_value=False):
            report = entrypoint.environment_report()
        self.assertFalse(report["cuda_available"])
        self.assertIsNone(report["gpu_name"])
        self.assertEqual(report["gpu_count"], 0)


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
        # No mocking needed here -- dry_run() must genuinely work on a
        # CPU-only machine (that's the entire point of --dry-run).
        exit_code = entrypoint.dry_run()
        self.assertEqual(exit_code, 0)

    def test_dry_run_default_is_v1(self):
        # Omitting the experiment argument must be identical to passing "v1"
        # explicitly -- the Phase 6 selector must not change existing behavior.
        self.assertEqual(entrypoint.dry_run(), entrypoint.dry_run("v1"))

    def test_dry_run_v2_loads_the_220_example_pool(self):
        exit_code = entrypoint.dry_run("v2")
        self.assertEqual(exit_code, 0)

    def test_dry_run_does_not_import_the_real_backbone_model_class(self):
        # AST-level check (same discipline as the existing
        # test_pipeline_does_not_reference_fake_generation_client-style
        # boundary tests) that dry_run's own body never references
        # anything that would trigger a real pretrained-weights download
        # (AutoModel construction lives inside CrossEncoderBackbone /
        # MultiTaskModel, neither of which dry_run touches).
        import ast
        import inspect
        source = inspect.getsource(entrypoint.dry_run)
        tree = ast.parse(source)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("MultiTaskModel", names)
        self.assertNotIn("build_tokenizer", names)


class TestConfigSanity(unittest.TestCase):
    def test_config_declares_fresh_initialization_from_the_named_base_model(self):
        self.assertEqual(entrypoint.CONFIG["base_model"], "microsoft/deberta-v3-base")
        self.assertTrue(entrypoint.CONFIG["fresh_initialization"])

    def test_config_has_no_per_experiment_keys(self):
        # dataset_split_identifier/split_seed/model_version live in
        # EXPERIMENTS now (per-experiment), not in the shared CONFIG --
        # CONFIG must be identical across v1/v2 (the experimental control).
        for key in ("dataset_split_identifier", "split_seed", "model_version"):
            self.assertNotIn(key, entrypoint.CONFIG)

    def test_canonical_dimension_keys_match_evaluation_dimensions(self):
        self.assertEqual(entrypoint.CANONICAL_DIMENSION_KEYS, tuple(d.value for d in CANONICAL_DIMENSIONS))


class TestExperimentSelector(unittest.TestCase):
    def test_v1_v2_v3_are_all_registered(self):
        self.assertEqual(set(entrypoint.EXPERIMENTS), {"v1", "v2", "v3"})

    def test_v1_config_matches_the_frozen_phase3_split(self):
        cfg = entrypoint.EXPERIMENTS["v1"]
        self.assertEqual(cfg["dataset_split_identifier"], "four_dim_experiment_v1")
        self.assertEqual(cfg["split_seed"], "four_dim_experiment_v1_41")
        self.assertEqual(cfg["expected_total"], 170)
        self.assertEqual(cfg["expected_counts"], (128, 20, 22))
        self.assertTrue(cfg["split_json_path"].replace("\\", "/").endswith(
            "artifacts/four_dim_experiment_v1/split.json"
        ))

    def test_v2_config_matches_the_approved_phase5_split(self):
        cfg = entrypoint.EXPERIMENTS["v2"]
        self.assertEqual(cfg["dataset_split_identifier"], "four_dim_experiment_v2")
        self.assertEqual(cfg["split_seed"], "four_dim_v2_split_348")
        self.assertEqual(cfg["expected_total"], 220)
        self.assertEqual(cfg["expected_counts"], (166, 27, 27))
        self.assertTrue(cfg["split_json_path"].replace("\\", "/").endswith(
            "artifacts/four_dim_experiment_v2/split.json"
        ))

    def test_v3_config_reuses_the_v2_pool_and_split_but_has_its_own_output_dir(self):
        cfg = entrypoint.EXPERIMENTS["v3"]
        # V3 is a controlled-experiment pair with v2: SAME pool loader,
        # SAME split (never regenerated) -- the only differences are the
        # output directory and model_version.
        self.assertIs(cfg["load_pool"], entrypoint.EXPERIMENTS["v2"]["load_pool"])
        self.assertEqual(cfg["split_json_path"], entrypoint.EXPERIMENTS["v2"]["split_json_path"])
        self.assertEqual(cfg["dataset_split_identifier"], "four_dim_experiment_v2")
        self.assertEqual(cfg["split_seed"], "four_dim_v2_split_348")
        self.assertEqual(cfg["expected_total"], 220)
        self.assertEqual(cfg["expected_counts"], (166, 27, 27))
        self.assertTrue(cfg["artifacts_dir"].replace("\\", "/").endswith("artifacts/four_dim_training_v3"))
        self.assertNotEqual(cfg["model_version"], entrypoint.EXPERIMENTS["v2"]["model_version"])

    def test_v1_v2_v3_output_dirs_are_all_distinct_and_never_overwrite_each_other(self):
        dirs = {name: cfg["artifacts_dir"] for name, cfg in entrypoint.EXPERIMENTS.items()}
        self.assertEqual(len(set(dirs.values())), len(dirs), f"output dirs collide: {dirs}")
        self.assertTrue(dirs["v1"].replace("\\", "/").endswith("artifacts/four_dim_training_v1"))
        self.assertTrue(dirs["v2"].replace("\\", "/").endswith("artifacts/four_dim_training_v2"))
        self.assertTrue(dirs["v3"].replace("\\", "/").endswith("artifacts/four_dim_training_v3"))

    def test_each_experiments_output_dir_is_distinct_from_its_own_split_artifact_dir(self):
        # Must never write into (and thereby risk mutating) the frozen
        # split.json / distribution_report.json directory for either experiment.
        for name, cfg in entrypoint.EXPERIMENTS.items():
            self.assertNotEqual(
                cfg["artifacts_dir"], os.path.dirname(cfg["split_json_path"]),
                f"{name}: output dir must differ from its split-artifact dir",
            )

    def test_v1_v2_v3_share_the_identical_hyperparameter_config(self):
        # The experimental control: only pool/split/output/model_version
        # may differ between v1/v2/v3 -- CONFIG itself is shared, single,
        # unparameterized by experiment.
        for key in ("learning_rate", "batch_size", "num_epochs", "max_length", "random_seed", "weight_decay"):
            self.assertIn(key, entrypoint.CONFIG)
        self.assertEqual(entrypoint.CONFIG["learning_rate"], 2e-5)
        self.assertEqual(entrypoint.CONFIG["batch_size"], 8)
        self.assertEqual(entrypoint.CONFIG["gradient_accumulation_steps"], 1)
        self.assertEqual(entrypoint.CONFIG["num_epochs"], 8)
        self.assertEqual(entrypoint.CONFIG["max_length"], 256)
        self.assertEqual(entrypoint.CONFIG["random_seed"], 42)
        self.assertEqual(entrypoint.CONFIG["weight_decay"], 0.01)
        self.assertEqual(entrypoint.CONFIG["warmup_steps"], 0)
        self.assertEqual(entrypoint.CONFIG["base_model"], "microsoft/deberta-v3-base")
        self.assertTrue(entrypoint.CONFIG["fresh_initialization"])

    def test_unknown_experiment_name_is_rejected_by_main(self):
        with mock.patch.object(sys, "argv", ["run_four_dim_training.py", "--dry-run", "v4"]):
            exit_code = entrypoint.main()
        self.assertEqual(exit_code, 2)


class TestV3DataIntegrityGate(unittest.TestCase):
    """The additional pre-training checks V3 gets on top of the generic
    pool/split/leakage checks every experiment already has."""

    def test_dry_run_v3_passes_all_integrity_checks_on_the_real_pool(self):
        # No mocking -- exercises the real 220-example pool + real artifact,
        # same discipline as the existing dry-run tests.
        self.assertEqual(entrypoint.dry_run("v3"), 0)

    def test_v3_data_integrity_confirms_exactly_42_enriched_examples(self):
        from four_dim_experiment_v2_split import load_v2_pool
        examples = load_v2_pool()
        entrypoint._assert_v3_data_integrity(examples)  # must not raise
        enriched = [e for e in examples if e.inputs.specification.grounding.project.summary]
        self.assertEqual(len(enriched), 42)

    def test_v3_data_integrity_rejects_wrong_enriched_count(self):
        from four_dim_experiment_v2_split import load_v2_pool
        examples = list(load_v2_pool())
        # Simulate grounding wiring being silently missing/broken by
        # blanking out every summary -- must be caught, not silently pass.
        broken = []
        for e in examples:
            proj = e.inputs.specification.grounding.project
            if proj.summary:
                new_proj = proj.model_copy(update={"summary": ""})
                new_grounding = e.inputs.specification.grounding.model_copy(update={"project": new_proj})
                new_spec = e.inputs.specification.model_copy(update={"grounding": new_grounding})
                new_inputs = e.inputs.model_copy(update={"specification": new_spec})
                e = e.model_copy(update={"inputs": new_inputs})
            broken.append(e)
        with self.assertRaises(SystemExit):
            entrypoint._assert_v3_data_integrity(broken)

    def test_v3_data_integrity_rejects_a_changed_cloudscaler_expected_concepts(self):
        # The CloudScaler-hold check reads the RAW on-disk pool files (the
        # actual source of truth for expected_concepts), not the in-memory
        # TrainingExample -- so simulate the failure by monkeypatching the
        # raw-record reader rather than the loaded example.
        from four_dim_experiment_v2_split import load_v2_pool
        examples = load_v2_pool()

        real_reader = entrypoint._read_raw_pool_records

        def _tampered_reader():
            records = real_reader()
            records = dict(records)
            records["seed_v1_006"] = dict(records["seed_v1_006"])
            records["seed_v1_006"]["expected_concepts"] = ["reactive metric-based autoscaling"]
            return records

        with mock.patch.object(entrypoint, "_read_raw_pool_records", _tampered_reader):
            with self.assertRaises(SystemExit):
                entrypoint._assert_v3_data_integrity(examples)


class TestPerDimensionMetrics(unittest.TestCase):
    def test_perfect_predictions_yield_qwk_one_and_zero_mae(self):
        y_true = [0, 1, 2, 3, 4, 2, 1]
        metrics = entrypoint._dimension_metrics(y_true, list(y_true))
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["within_1_accuracy"], 1.0)
        self.assertEqual(metrics["mae"], 0.0)
        self.assertEqual(metrics["qwk"], 1.0)

    def test_confusion_matrix_shape_and_totals(self):
        y_true = [0, 1, 2, 3, 4]
        y_pred = [0, 1, 1, 3, 3]
        metrics = entrypoint._dimension_metrics(y_true, y_pred)
        self.assertEqual(len(metrics["confusion_matrix"]), 5)
        self.assertEqual(len(metrics["confusion_matrix"][0]), 5)
        self.assertEqual(sum(sum(row) for row in metrics["confusion_matrix"]), 5)

    def test_mean_qwk_averages_across_all_four_dimensions(self):
        metrics_by_dim = {name: {"qwk": q} for name, q in zip(entrypoint.CANONICAL_DIMENSION_KEYS, [1.0, 0.5, 0.0, 0.5])}
        self.assertAlmostEqual(entrypoint._mean_qwk(metrics_by_dim), 0.5)


if __name__ == "__main__":
    unittest.main()
