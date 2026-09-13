"""
Tests for Experiment B0 (V6 Ablation Design Review, H2: architecture) --
`model_heads.py`'s additive `DimensionPrivateProjection`/`use_private_mlp`
plumbing through `DimensionOrdinalHeads`/`MultiTaskModel`/`train_model`/
`model_checkpoint_io.load_checkpoint_artifact`, and
`run_four_dim_training.py`'s `v3_expB0` experiment wiring.

Uses a tiny randomly-initialized backbone (existing project precedent,
e.g. `test_model_heads.py`, `test_loss_weighting.py`) for every forward/
loss/round-trip check -- never a full pretrained-weights download, never
an optimizer step, never `.backward()`/`.step()` anywhere in this file
except the one dedicated "independent gradients" test, which calls
`.backward()` exactly once on a tiny random model to prove per-dimension
parameter independence (no training loop, no data loading, nothing
persisted).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from evaluation_dimensions import all_keys as canonical_dimension_keys
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer, tokenize_pair
from model_checkpoint_io import load_checkpoint_artifact, save_checkpoint_artifact
from model_heads import (
    CoralOrdinalHead,
    DimensionOrdinalHeads,
    DimensionPrivateProjection,
    MultiTaskModel,
    coral_predict,
    compute_batch_loss,
)

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()
_TOKENIZER = build_tokenizer(BackboneConfig())
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPLIT_PATH = os.path.join(_HERE, "artifacts", "four_dim_experiment_v2", "split.json")


def _batch(tokenizer, pairs: list[tuple[str, str]]):
    encodings = [tokenize_pair(tokenizer, a, b, max_length=16) for a, b in pairs]
    return tokenizer.pad(encodings, return_tensors="pt")


def _tiny_model(use_private_mlp: bool, mlp_hidden_dim: int = 8, mlp_dropout: float = 0.1) -> MultiTaskModel:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    return MultiTaskModel(
        BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS,
        use_private_mlp=use_private_mlp, mlp_hidden_dim=mlp_hidden_dim, mlp_dropout=mlp_dropout,
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. MLP output shape
# ═══════════════════════════════════════════════════════════════════════

class TestDimensionPrivateProjectionShape(unittest.TestCase):
    def test_output_shape_is_hidden_dim(self):
        proj = DimensionPrivateProjection(in_features=16, hidden_dim=8, dropout=0.1)
        pooled = torch.randn(4, 16)
        out = proj(pooled)
        self.assertEqual(out.shape, (4, 8))

    def test_default_hidden_dim_matches_b0_spec(self):
        # B0's approved design (V6 review §5): h=128.
        proj = DimensionPrivateProjection(in_features=768)
        pooled = torch.randn(2, 768)
        out = proj(pooled)
        self.assertEqual(out.shape, (2, 128))

    def test_contains_gelu_activation(self):
        # V6 review §7: GELU, matching the backbone's own internal activation.
        proj = DimensionPrivateProjection(in_features=16, hidden_dim=8)
        self.assertTrue(any(isinstance(m, torch.nn.GELU) for m in proj.net))

    def test_contains_dropout_with_configured_rate(self):
        # V6 review §8: dropout matching the encoder's own default (0.1).
        proj = DimensionPrivateProjection(in_features=16, hidden_dim=8, dropout=0.1)
        dropouts = [m for m in proj.net if isinstance(m, torch.nn.Dropout)]
        self.assertEqual(len(dropouts), 1)
        self.assertAlmostEqual(dropouts[0].p, 0.1)

    def test_single_hidden_layer_only(self):
        # V6 review §6: exactly one Linear layer inside the projection.
        proj = DimensionPrivateProjection(in_features=16, hidden_dim=8)
        linears = [m for m in proj.net if isinstance(m, torch.nn.Linear)]
        self.assertEqual(len(linears), 1)


# ═══════════════════════════════════════════════════════════════════════
# 2. CORAL head rank/shape correctness (unchanged CoralOrdinalHead, fed by
#    the MLP's output instead of the raw pooled tensor)
# ═══════════════════════════════════════════════════════════════════════

class TestCoralHeadUnchangedWithMlpInput(unittest.TestCase):
    def test_coral_head_output_shape_matches_mlp_output(self):
        proj = DimensionPrivateProjection(in_features=16, hidden_dim=8)
        head = CoralOrdinalHead(in_features=8, num_classes=5)
        pooled = torch.randn(3, 16)
        logits = head(proj(pooled))
        self.assertEqual(logits.shape, (3, 4))

    def test_biases_still_monotonically_non_increasing(self):
        # V6 review §9: CoralOrdinalHead's own monotonicity guarantee is
        # architectural and lives entirely inside CoralOrdinalHead -- must
        # be completely unaffected by what feeds it.
        head = CoralOrdinalHead(in_features=8, num_classes=5)
        x = torch.zeros(1, 8)
        logits = head(x)[0]
        diffs = logits[1:] - logits[:-1]
        self.assertTrue(torch.all(diffs <= 1e-6))

    def test_dimension_ordinal_heads_end_to_end_shape_with_private_mlp(self):
        heads = DimensionOrdinalHeads(
            in_features=16, dimension_names=CANONICAL_DIMENSION_KEYS, num_classes=5,
            use_private_mlp=True, mlp_hidden_dim=8, mlp_dropout=0.1,
        )
        pooled = torch.randn(5, 16)
        out = heads(pooled)
        self.assertEqual(set(out), set(CANONICAL_DIMENSION_KEYS))
        for name in CANONICAL_DIMENSION_KEYS:
            self.assertEqual(out[name].shape, (5, 4))
        # Confirms the CORAL heads were actually constructed at the MLP's
        # bottleneck width, not the raw 16-d input width.
        for name in CANONICAL_DIMENSION_KEYS:
            self.assertEqual(heads.heads[name].shared.in_features, 8)


# ═══════════════════════════════════════════════════════════════════════
# 3. Four dimension-specific MLPs have independent parameters/gradients
# ═══════════════════════════════════════════════════════════════════════

class TestPerDimensionMlpIndependence(unittest.TestCase):
    def test_mlp_instances_are_distinct_modules(self):
        heads = DimensionOrdinalHeads(
            in_features=16, dimension_names=CANONICAL_DIMENSION_KEYS, num_classes=5,
            use_private_mlp=True, mlp_hidden_dim=8,
        )
        projections = [heads.projections[name] for name in CANONICAL_DIMENSION_KEYS]
        for i in range(len(projections)):
            for j in range(i + 1, len(projections)):
                self.assertIsNot(projections[i], projections[j])
                # Freshly initialized independent Linear layers must not
                # happen to share identical weights.
                w_i = dict(projections[i].net.named_parameters())["0.weight"]
                w_j = dict(projections[j].net.named_parameters())["0.weight"]
                self.assertFalse(torch.equal(w_i, w_j))

    def test_gradient_on_one_dimension_does_not_touch_another_dimensions_mlp(self):
        heads = DimensionOrdinalHeads(
            in_features=16, dimension_names=CANONICAL_DIMENSION_KEYS, num_classes=5,
            use_private_mlp=True, mlp_hidden_dim=8,
        )
        pooled = torch.randn(4, 16, requires_grad=False)
        out = heads(pooled)

        tc = CANONICAL_DIMENSION_KEYS[0]
        other = CANONICAL_DIMENSION_KEYS[1]
        loss = out[tc].sum()
        loss.backward()

        tc_params = list(heads.projections[tc].parameters())
        other_params = list(heads.projections[other].parameters())
        self.assertTrue(any(p.grad is not None and torch.any(p.grad != 0) for p in tc_params))
        self.assertTrue(all(p.grad is None for p in other_params))


# ═══════════════════════════════════════════════════════════════════════
# 4. use_private_mlp=False preserves the old architecture/state behavior
# ═══════════════════════════════════════════════════════════════════════

class TestPrivateMlpDefaultIsNoOp(unittest.TestCase):
    def test_dimension_ordinal_heads_default_has_no_projections(self):
        heads = DimensionOrdinalHeads(in_features=16, dimension_names=CANONICAL_DIMENSION_KEYS, num_classes=5)
        self.assertIsNone(heads.projections)
        for name in CANONICAL_DIMENSION_KEYS:
            self.assertEqual(heads.heads[name].shared.in_features, 16)

    def test_state_dict_keys_identical_with_flag_off(self):
        # The strongest proof (V6 review §14.1): a MultiTaskModel built
        # with use_private_mlp left at its default must have EXACTLY the
        # same state_dict() key set/shapes as one built with no knowledge
        # of the new parameter at all.
        model_default = _tiny_model(use_private_mlp=False)
        model_explicit_off = MultiTaskModel(
            BackboneConfig(),
            backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        keys_default = {k: tuple(v.shape) for k, v in model_default.state_dict().items()}
        keys_explicit = {k: tuple(v.shape) for k, v in model_explicit_off.state_dict().items()}
        self.assertEqual(keys_default, keys_explicit)
        self.assertFalse(any("projections" in k for k in keys_default))

    def test_use_private_mlp_true_adds_projection_params_not_present_when_false(self):
        model_off = _tiny_model(use_private_mlp=False)
        model_on = _tiny_model(use_private_mlp=True, mlp_hidden_dim=8)
        keys_off = set(model_off.state_dict())
        keys_on = set(model_on.state_dict())
        projection_keys = {k for k in keys_on if "dimension_heads.projections" in k}
        self.assertTrue(projection_keys)
        self.assertFalse(projection_keys & keys_off)

    def test_forward_dimensions_contract_unchanged_shape(self):
        # model_evaluator.TrainedEvaluator's only dependency (V6 review
        # §15): forward_dimensions' return contract must be identical.
        model = _tiny_model(use_private_mlp=True, mlp_hidden_dim=8)
        batch = _batch(_TOKENIZER, [("question", "answer")])
        model.eval()
        with torch.no_grad():
            outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(set(outputs), {"pooled", "dimension_logits", "presence_logits", "severity_pred"})
        self.assertEqual(set(outputs["dimension_logits"]), set(CANONICAL_DIMENSION_KEYS))
        for name in CANONICAL_DIMENSION_KEYS:
            self.assertEqual(outputs["dimension_logits"][name].shape, (1, 4))


# ═══════════════════════════════════════════════════════════════════════
# 5. B0 checkpoint save/reload round-trip gives identical outputs
# ═══════════════════════════════════════════════════════════════════════

class TestB0CheckpointRoundTrip(unittest.TestCase):
    def test_save_and_reload_produces_identical_outputs(self):
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(
            BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS,
            use_private_mlp=True, mlp_hidden_dim=8, mlp_dropout=0.1,
        )
        model.eval()
        batch = _batch(_TOKENIZER, [("q1", "a1"), ("q2", "a2")])
        with torch.no_grad():
            before = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b0_weights.pt")
            save_checkpoint_artifact(model, path)
            reloaded = load_checkpoint_artifact(
                path, BackboneConfig(),
                dimension_names=CANONICAL_DIMENSION_KEYS,
                backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
                use_private_mlp=True, mlp_hidden_dim=8, mlp_dropout=0.1,
            )
        with torch.no_grad():
            after = reloaded.forward_dimensions(batch["input_ids"], batch["attention_mask"])

        for name in CANONICAL_DIMENSION_KEYS:
            self.assertTrue(torch.allclose(before["dimension_logits"][name], after["dimension_logits"][name]))

    def test_mismatched_use_private_mlp_flag_fails_loudly_on_reload(self):
        # V6 review §12.4: load_state_dict is strict by default -- loading
        # a B0 checkpoint with the flag off (or vice versa) must be a hard
        # shape-mismatch error, never silent corruption.
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(
            BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS,
            use_private_mlp=True, mlp_hidden_dim=8,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b0_weights.pt")
            save_checkpoint_artifact(model, path)
            with self.assertRaises(RuntimeError):
                load_checkpoint_artifact(
                    path, BackboneConfig(),
                    dimension_names=CANONICAL_DIMENSION_KEYS,
                    backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
                    use_private_mlp=False,  # mismatched on purpose
                )


# ═══════════════════════════════════════════════════════════════════════
# 6. Finite B0 loss on a tiny random-init model
# ═══════════════════════════════════════════════════════════════════════

class TestB0FiniteLoss(unittest.TestCase):
    def test_b0_architecture_compute_batch_loss_is_finite(self):
        # Same real, frozen 220-example V2 pool + real frozen split used by
        # A2's own finite-loss test (test_loss_weighting.py::TestA2FiniteLoss)
        # -- only the model architecture differs (private MLP, no loss
        # weighting), keeping this a genuine end-to-end production-dataflow
        # smoke test rather than a synthetic fixture.
        import json
        from four_dim_experiment_v2_split import load_v2_pool
        from model_dataset import build_dataloaders
        from training_experimentation import DatasetSplit

        with open(_SPLIT_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        split = DatasetSplit(
            train_ids=tuple(raw["train_ids"]), val_ids=tuple(raw["val_ids"]), test_ids=tuple(raw["test_ids"]),
        )
        examples = load_v2_pool()
        train_loader, _, _ = build_dataloaders(
            examples, split, _TOKENIZER, BackboneConfig(max_length=32), batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        model = _tiny_model(use_private_mlp=True, mlp_hidden_dim=8)
        model.eval()
        batch = next(iter(train_loader))
        with torch.no_grad():
            loss = compute_batch_loss(model, batch, "cpu")
        self.assertTrue(torch.isfinite(loss))


# ═══════════════════════════════════════════════════════════════════════
# 7. v3_expB0 config exists / isolation / same pool+split+seed as A0 /
#    unweighted loss / dry-run
# ═══════════════════════════════════════════════════════════════════════

class TestB0ConfigurationSelector(unittest.TestCase):
    def test_v3_expB0_registered(self):
        from run_four_dim_training import EXPERIMENTS
        self.assertIn("v3_expB0", EXPERIMENTS)

    def test_b0_uses_unweighted_loss(self):
        from run_four_dim_training import EXPERIMENTS
        b0 = EXPERIMENTS["v3_expB0"]
        self.assertEqual(b0["loss_weighting"], "none")
        self.assertEqual(b0["weighted_dimensions"], ())
        self.assertIsNone(b0["loss_weight_clip"])
        self.assertIsNone(b0["loss_weight_alpha"])

    def test_b0_architecture_flags(self):
        from run_four_dim_training import EXPERIMENTS
        b0 = EXPERIMENTS["v3_expB0"]
        self.assertTrue(b0["use_private_mlp"])
        self.assertEqual(b0["mlp_hidden_dim"], 128)
        self.assertEqual(b0["mlp_dropout"], 0.1)

    def test_b0_output_directory_distinct_from_every_other_experiment(self):
        from run_four_dim_training import EXPERIMENTS
        dirs = {
            name: os.path.normpath(EXPERIMENTS[name]["artifacts_dir"])
            for name in ("v1", "v2", "v3", "v3_expA0", "v3_expA1", "v3_expA2", "v3_expB0")
        }
        self.assertEqual(len(set(dirs.values())), len(dirs), f"artifacts_dir collision: {dirs}")

    def test_b0_same_pool_split_seed_hyperparams_as_a0(self):
        from run_four_dim_training import EXPERIMENTS
        a0, b0 = EXPERIMENTS["v3_expA0"], EXPERIMENTS["v3_expB0"]
        self.assertIs(a0["load_pool"], b0["load_pool"])
        self.assertEqual(a0["split_json_path"], b0["split_json_path"])
        self.assertEqual(a0["split_seed"], b0["split_seed"])
        self.assertEqual(a0["expected_total"], b0["expected_total"])
        self.assertEqual(a0["expected_counts"], b0["expected_counts"])
        self.assertEqual(a0["loss_weighting"], b0["loss_weighting"])
        # The ONLY difference between A0 and B0's configs is architecture:
        self.assertNotEqual(a0.get("use_private_mlp", False), b0["use_private_mlp"])

    def test_a0_a1_a2_configs_have_no_private_mlp_key_dependency(self):
        # v1/v2/v3/A0/A1/A2 never reference use_private_mlp at all --
        # train()'s `cfg.get("use_private_mlp", False)` gate is what
        # decides the architecture, and it defaults to the old behavior.
        from run_four_dim_training import EXPERIMENTS
        for name in ("v1", "v2", "v3", "v3_expA0", "v3_expA1", "v3_expA2"):
            self.assertNotIn("use_private_mlp", EXPERIMENTS[name])


class TestB0DryRun(unittest.TestCase):
    def test_dry_run_v3_expB0_shows_full_pool_and_frozen_split(self):
        import run_four_dim_training as entrypoint
        exit_code = entrypoint.dry_run("v3_expB0")
        self.assertEqual(exit_code, 0)


class TestExistingDryRunsUnaffectedByB0(unittest.TestCase):
    """Regression check: registering v3_expB0 must not perturb any other
    experiment's dry-run behavior."""

    def test_v3_expA0_a1_a2_dry_runs_still_succeed(self):
        import run_four_dim_training as entrypoint
        for name in ("v1", "v2", "v3", "v3_expA0", "v3_expA1", "v3_expA2"):
            self.assertEqual(entrypoint.dry_run(name), 0, f"dry_run({name!r}) regressed")


# ═══════════════════════════════════════════════════════════════════════
# 8. V4 isolation -- B0's training entrypoint has no path to V4 at all
#    (the actual b0_inference/ workflow, mirroring a1_inference/ and
#    a2_inference/, is a separate, later step per the V6 review's own
#    scoping -- this test only guards that B0's architecture/training code
#    added in this change introduces no such path).
# ═══════════════════════════════════════════════════════════════════════

class TestB0HasNoV4TrainingPath(unittest.TestCase):
    def test_run_four_dim_training_source_never_references_v4(self):
        import run_four_dim_training as entrypoint
        source = open(entrypoint.__file__, encoding="utf-8").read()
        self.assertNotIn("v4_diagnostic", source)
        self.assertNotIn("v4h_", source)

    def test_model_heads_source_never_references_v4(self):
        import model_heads
        source = open(model_heads.__file__, encoding="utf-8").read()
        self.assertNotIn("v4_diagnostic", source)
        self.assertNotIn("v4h_", source)

    def test_v4_diagnostic_dataset_file_unchanged(self):
        # Byte-count/shape sanity only (this test file makes no claim to be
        # the authoritative V4 validator -- that is
        # artifacts/v4_diagnostic/validate_v4_diagnostic.py /
        # test_v4_diagnostic.py); confirms B0's implementation did not
        # touch the frozen 58-example file.
        import json
        v4_path = os.path.join(_HERE, "artifacts", "v4_diagnostic", "v4_diagnostic_58.jsonl")
        if not os.path.exists(v4_path):
            self.skipTest("V4 diagnostic artifact not present in this environment")
        with open(v4_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(rows), 58)


if __name__ == "__main__":
    unittest.main()
