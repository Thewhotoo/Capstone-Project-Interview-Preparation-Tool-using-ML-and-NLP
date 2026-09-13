"""
Tests for Experiment A (V5 Ablation Design Review, H1: loss/calibration) --
`loss_weighting.py`'s train-only pos_weight computation, `model_heads.py`'s
additive `pos_weight`/`dimension_pos_weights` plumbing, and
`run_four_dim_training.py`'s A0/A1 experiment wiring.

Uses the real frozen 220-example V2/V3 pool (read-only) + the real frozen
`four_dim_experiment_v2/split.json` for the train-only-isolation checks, and
a tiny randomly-initialized backbone (existing project precedent, e.g.
`test_four_dim_experiment_split.py`) for the forward/loss checks -- never a
full pretrained-weights download, never an optimizer step, never
`.backward()`/`.step()` anywhere in this file (loss VALUES are computed and
compared, but nothing is ever trained).
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from evaluation_dimensions import all_keys as canonical_dimension_keys
from four_dim_experiment_v2_split import load_v2_pool
from loss_weighting import (
    A1_ALPHA,
    A2_ALPHA,
    DEFAULT_CLIP,
    DEFAULT_WEIGHTED_DIMENSIONS,
    compute_dimension_pos_weights,
    pos_weight_from_tier_counts,
    tier_counts_from_examples,
)
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_dataset import build_dataloaders
from model_heads import CoralOrdinalHead, MultiTaskModel, coral_loss, coral_predict, coral_targets, compute_batch_loss
from training_experimentation import DatasetSplit

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPLIT_PATH = os.path.join(_HERE, "artifacts", "four_dim_experiment_v2", "split.json")

_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=32)
_EXAMPLES = load_v2_pool()  # real, frozen, read-only 220-example pool


def _real_split() -> DatasetSplit:
    with open(_SPLIT_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return DatasetSplit(train_ids=tuple(d["train_ids"]), val_ids=tuple(d["val_ids"]), test_ids=tuple(d["test_ids"]))


def _fake_example(example_id: str, dims: dict) -> SimpleNamespace:
    """Minimal duck-typed stand-in for `TrainingExample`, matching exactly
    the attributes `loss_weighting.tier_counts_from_examples` reads
    (`.labels.dimension_labels[i].name/.score`)."""
    labels = [SimpleNamespace(name=name, score=score) for name, score in dims.items()]
    return SimpleNamespace(
        metadata=SimpleNamespace(example_id=example_id),
        labels=SimpleNamespace(dimension_labels=labels),
    )


class TestPosWeightFormula(unittest.TestCase):
    """Pure-function tests of the weighting formula itself (Requirement 3:
    weighted loss produces finite values; formula correctness)."""

    def test_balanced_tier_distribution_matches_hand_computed_thresholds(self):
        # tier 0..4 evenly represented (10 each). NOTE: a uniform TIER
        # distribution does NOT mean a uniform THRESHOLD distribution --
        # CORAL's own binary decomposition means threshold k's positive
        # class is "tier > k", so even with balanced tiers, low thresholds
        # (k=0) are positive-heavy (4/5 tiers exceed 0) and high thresholds
        # (k=3) are positive-light (only 1/5 tiers exceed 3). This test
        # asserts the formula matches that expected, hand-computed shape --
        # not an arbitrary "near 1.0" expectation.
        counts = {0: 10, 1: 10, 2: 10, 3: 10, 4: 10}
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.01, 100.0))
        # k=0: pos=40 neg=10 -> 10/40=0.25 | k=1: pos=30 neg=20 -> 20/30=0.667
        # k=2: pos=20 neg=30 -> 30/20=1.5  | k=3: pos=10 neg=40 -> 40/10=4.0
        expected = [10 / 40, 20 / 30, 30 / 20, 40 / 10]
        for w, e in zip(weights, expected):
            self.assertAlmostEqual(w, e, places=4)

    def test_skewed_high_counts_downweight_positive_threshold(self):
        # Overwhelmingly tier-4 (like real technical_correctness): at low
        # thresholds (k=0,1,2) positives (tier>k) vastly outnumber
        # negatives -> pos_weight should be pulled toward the floor (<1).
        counts = {0: 1, 1: 1, 2: 2, 3: 6, 4: 90}
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=DEFAULT_CLIP)
        self.assertLess(weights[0], 1.0)  # threshold k=0: positives dominate
        self.assertLess(weights[1], 1.0)

    def test_weights_are_clipped_to_bounds(self):
        counts = {4: 1000}  # every example at the top tier -> maximally skewed
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.34, 3.0))
        for w in weights:
            self.assertGreaterEqual(w, 0.34)
            self.assertLessEqual(w, 3.0)

    def test_no_positives_at_threshold_uses_clip_max(self):
        counts = {0: 50}  # nobody exceeds any threshold -> positives=0 everywhere
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.34, 3.0))
        for w in weights:
            self.assertEqual(w, 3.0)

    def test_no_negatives_at_threshold_uses_clip_min(self):
        counts = {4: 50}  # everybody exceeds threshold 0,1,2 -> negatives=0 there
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.34, 3.0))
        self.assertEqual(weights[0], 0.34)

    def test_returns_exactly_num_classes_minus_one_weights(self):
        weights = pos_weight_from_tier_counts({0: 1, 4: 1}, num_classes=5)
        self.assertEqual(len(weights), 4)


class TestTrainOnlyIsolation(unittest.TestCase):
    """Requirement: weights must be derived ONLY from training labels --
    never validation/test/V4 labels."""

    def test_weights_computed_from_passed_examples_only(self):
        # Two disjoint synthetic "pools" with OPPOSITE tier skew. If the
        # weighting function ever reached outside what's explicitly passed
        # in, mixing them in would change a call that only passed pool A.
        pool_a_low = [_fake_example(f"a{i}", {"technical_correctness": 0.1}) for i in range(20)]
        pool_b_high = [_fake_example(f"b{i}", {"technical_correctness": 0.95}) for i in range(20)]

        weights_a_only = compute_dimension_pos_weights(
            pool_a_low, CANONICAL_DIMENSION_KEYS, weighted_dimensions=("technical_correctness",),
        )
        weights_a_only_again = compute_dimension_pos_weights(
            pool_a_low, CANONICAL_DIMENSION_KEYS, weighted_dimensions=("technical_correctness",),
        )
        # Same input -> same output (deterministic, no hidden state).
        self.assertEqual(weights_a_only, weights_a_only_again)

        weights_combined = compute_dimension_pos_weights(
            pool_a_low + pool_b_high, CANONICAL_DIMENSION_KEYS, weighted_dimensions=("technical_correctness",),
        )
        # Combined pool MUST differ from pool_a-only -- proves the function
        # only ever reflects exactly what was passed in, nothing cached or
        # reached-for externally (e.g. no accidental global pool import).
        self.assertNotEqual(weights_a_only["technical_correctness"], weights_combined["technical_correctness"])

    def test_run_four_dim_training_filters_to_train_ids_only(self):
        # Exercises the EXACT filtering expression used in
        # run_four_dim_training.train() (copied here, not imported, since
        # that line lives inside a CUDA-gated function we must not call --
        # this test proves the filter LOGIC in isolation).
        split = _real_split()
        train_only_examples = [e for e in _EXAMPLES if e.metadata.example_id in set(split.train_ids)]
        resulting_ids = {e.metadata.example_id for e in train_only_examples}
        self.assertEqual(resulting_ids, set(split.train_ids))
        self.assertEqual(resulting_ids & set(split.val_ids), set())
        self.assertEqual(resulting_ids & set(split.test_ids), set())

    def test_loss_weighting_module_never_imports_a_split_or_pool_loader(self):
        # Static guard: loss_weighting.py must have no way to reach
        # val/test/V4 data on its own -- it must only ever see what a
        # caller explicitly passes in. Checks actual `import`/`from` lines
        # only (not prose in comments/docstrings, which legitimately
        # discuss the isolation contract by name).
        import ast
        import loss_weighting
        source_path = loss_weighting.__file__
        with open(source_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=source_path)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_names.add(node.module or "")
                imported_names.update(alias.name for alias in node.names)
        forbidden = ("load_v2_pool", "load_core_pool", "v4_diagnostic", "four_dim_experiment", "training_experimentation")
        for name in forbidden:
            self.assertNotIn(name, imported_names, f"loss_weighting.py must not import {name!r} (imports: {sorted(imported_names)})")

    def test_real_train_split_weights_differ_from_val_or_test_split_weights(self):
        # Real-data sanity: computing weights from train_ids vs val_ids
        # (both real subsets of the same frozen pool) is not guaranteed to
        # differ by any particular amount, but the FUNCTION must at least
        # be sensitive to which ids were passed -- confirms no silent
        # full-pool fallback is happening.
        split = _real_split()
        by_id = {e.metadata.example_id: e for e in _EXAMPLES}
        train_examples = [by_id[i] for i in split.train_ids]
        val_examples = [by_id[i] for i in split.val_ids]
        train_counts = tier_counts_from_examples(train_examples, "technical_correctness")
        val_counts = tier_counts_from_examples(val_examples, "technical_correctness")
        # The two id sets are disjoint by construction (DatasetSplit), so
        # unless by wild coincidence the histograms are pixel-identical,
        # this proves train/val are genuinely different inputs being read.
        self.assertNotEqual(sorted(train_counts.items()), sorted(val_counts.items()))


class TestDimensionMapping(unittest.TestCase):
    def test_all_four_canonical_dimensions_present_in_output(self):
        weights = compute_dimension_pos_weights([], CANONICAL_DIMENSION_KEYS)
        self.assertEqual(set(weights.keys()), set(CANONICAL_DIMENSION_KEYS))

    def test_default_weighted_dimensions_are_tc_and_relevance_only(self):
        self.assertEqual(set(DEFAULT_WEIGHTED_DIMENSIONS), {"technical_correctness", "relevance_completeness"})

    def test_unweighted_dimensions_map_to_none(self):
        examples = [_fake_example("x", {
            "technical_correctness": 0.9, "depth_specificity": 0.9,
            "relevance_completeness": 0.9, "grounding_ownership": 0.9,
        })]
        weights = compute_dimension_pos_weights(examples, CANONICAL_DIMENSION_KEYS)
        self.assertIsNone(weights["depth_specificity"])
        self.assertIsNone(weights["grounding_ownership"])
        self.assertIsNotNone(weights["technical_correctness"])
        self.assertIsNotNone(weights["relevance_completeness"])

    def test_weighted_dimensions_configurable(self):
        examples = [_fake_example("x", {"grounding_ownership": 0.9})]
        weights = compute_dimension_pos_weights(
            examples, CANONICAL_DIMENSION_KEYS, weighted_dimensions=("grounding_ownership",),
        )
        self.assertIsNotNone(weights["grounding_ownership"])
        self.assertIsNone(weights["technical_correctness"])


class TestCoralStructureUnchanged(unittest.TestCase):
    """Requirement: CORAL ordinal structure (targets/decoding/monotonicity)
    must be completely unaffected by loss weighting."""

    def test_coral_targets_unchanged(self):
        y = torch.tensor([0, 2, 4])
        targets = coral_targets(y, num_classes=5)
        expected = torch.tensor([
            [0., 0., 0., 0.],
            [1., 1., 0., 0.],
            [1., 1., 1., 1.],
        ])
        self.assertTrue(torch.equal(targets, expected))

    def test_coral_predict_unaffected_by_loss_weighting(self):
        # pos_weight only participates in the LOSS, never in decoding --
        # coral_predict takes only logits, same signature, same behavior.
        logits = torch.tensor([[2.0, 1.0, -1.0, -2.0]])
        pred = coral_predict(logits)
        self.assertEqual(pred.item(), 2)  # two thresholds exceeded (P>0.5)

    def test_coral_head_monotonicity_unaffected(self):
        head = CoralOrdinalHead(in_features=8, num_classes=5)
        x = torch.randn(3, 8)
        out = head(x)
        # biases must still be non-increasing across thresholds (rank
        # consistency), independent of anything loss-related.
        biases = out[0] - (head.shared(x)[0].item())
        for i in range(len(biases) - 1):
            self.assertGreaterEqual(biases[i].item(), biases[i + 1].item() - 1e-6)

    def test_coral_loss_pos_weight_none_is_default(self):
        import inspect
        sig = inspect.signature(coral_loss)
        self.assertIn("pos_weight", sig.parameters)
        self.assertIsNone(sig.parameters["pos_weight"].default)


class TestUnweightedBehaviorUnchanged(unittest.TestCase):
    """Requirement 1: default/unweighted behavior remains byte-identical."""

    def test_coral_loss_with_and_without_explicit_none_are_identical(self):
        torch.manual_seed(0)
        logits = torch.randn(5, 4)
        y = torch.randint(0, 5, (5,))
        loss_default = coral_loss(logits, y, num_classes=5)
        loss_explicit_none = coral_loss(logits, y, num_classes=5, pos_weight=None)
        self.assertEqual(loss_default.item(), loss_explicit_none.item())

    def test_compute_batch_loss_default_matches_explicit_none_dict(self):
        split = _real_split()
        # Build a DatasetSplit-shaped object matching build_dataloaders' expectations.
        train_loader, _, _ = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        model.eval()
        batch = next(iter(train_loader))
        with torch.no_grad():
            loss_no_arg = compute_batch_loss(model, batch)
            loss_explicit_none = compute_batch_loss(model, batch, "cpu", None)
            loss_all_none_dict = compute_batch_loss(
                model, batch, "cpu", {name: None for name in CANONICAL_DIMENSION_KEYS},
            )
        self.assertEqual(loss_no_arg.item(), loss_explicit_none.item())
        self.assertEqual(loss_no_arg.item(), loss_all_none_dict.item())


class TestWeightedLossFinite(unittest.TestCase):
    """Requirement 2: weighted loss produces finite values, and differs
    from the unweighted loss when weights are non-trivial."""

    def test_weighted_coral_loss_is_finite_and_differs(self):
        torch.manual_seed(1)
        logits = torch.randn(6, 4)
        y = torch.randint(0, 5, (6,))
        unweighted = coral_loss(logits, y, num_classes=5)
        weighted = coral_loss(logits, y, num_classes=5, pos_weight=torch.tensor([3.0, 3.0, 3.0, 3.0]))
        self.assertTrue(torch.isfinite(unweighted))
        self.assertTrue(torch.isfinite(weighted))
        self.assertNotAlmostEqual(unweighted.item(), weighted.item(), places=4)

    def test_compute_batch_loss_with_real_train_derived_weights_is_finite(self):
        split = _real_split()
        train_loader, _, _ = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        by_id = {e.metadata.example_id: e for e in _EXAMPLES}
        train_only_examples = [by_id[i] for i in split.train_ids]
        dimension_pos_weights = compute_dimension_pos_weights(train_only_examples, CANONICAL_DIMENSION_KEYS)

        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        model.eval()
        batch = next(iter(train_loader))
        with torch.no_grad():
            loss_unweighted = compute_batch_loss(model, batch)
            loss_weighted = compute_batch_loss(model, batch, "cpu", dimension_pos_weights)
        self.assertTrue(torch.isfinite(loss_unweighted))
        self.assertTrue(torch.isfinite(loss_weighted))


class TestA0A1ConfigurationsDistinguishable(unittest.TestCase):
    """Requirement 4: A0 and A1 must be distinguishable, runnable
    configurations, and neither may write to artifacts/four_dim_training_v3/."""

    def test_a0_and_a1_exist_and_differ(self):
        from run_four_dim_training import EXPERIMENTS
        self.assertIn("v3_expA0", EXPERIMENTS)
        self.assertIn("v3_expA1", EXPERIMENTS)
        a0, a1 = EXPERIMENTS["v3_expA0"], EXPERIMENTS["v3_expA1"]
        self.assertEqual(a0.get("loss_weighting"), "none")
        self.assertEqual(a1.get("loss_weighting"), "train_derived_pos_weight")
        self.assertEqual(a1.get("weighted_dimensions"), ("technical_correctness", "relevance_completeness"))
        self.assertNotEqual(a0["artifacts_dir"], a1["artifacts_dir"])

    def test_neither_a0_nor_a1_writes_to_v3_artifacts_dir(self):
        import os
        from run_four_dim_training import EXPERIMENTS
        v3_dir = os.path.normpath(EXPERIMENTS["v3"]["artifacts_dir"])
        for name in ("v3_expA0", "v3_expA1"):
            other_dir = os.path.normpath(EXPERIMENTS[name]["artifacts_dir"])
            self.assertNotEqual(other_dir, v3_dir)
            # Genuine nesting check (not a naive substring match, which
            # would false-positive on "four_dim_training_v3_expA0" simply
            # starting with the same characters as "four_dim_training_v3").
            self.assertFalse(
                os.path.commonpath([other_dir, v3_dir]) == v3_dir and other_dir != v3_dir
                and other_dir.startswith(v3_dir + os.sep),
                f"{other_dir} must not be nested inside {v3_dir}",
            )

    def test_v1_v2_v3_have_no_loss_weighting_key_set(self):
        # v1/v2/v3 must stay exactly as before -- no loss_weighting key at
        # all, so `cfg.get("loss_weighting")` defaults to None/"none" and
        # `dimension_pos_weights` stays None for those three experiments.
        from run_four_dim_training import EXPERIMENTS
        for name in ("v1", "v2", "v3"):
            self.assertNotIn("loss_weighting", EXPERIMENTS[name])

    def test_same_pool_and_split_as_v3(self):
        # A0/A1 must use the EXACT SAME frozen pool/split as v3 -- only
        # loss weighting differs.
        from run_four_dim_training import EXPERIMENTS
        v3 = EXPERIMENTS["v3"]
        for name in ("v3_expA0", "v3_expA1"):
            cfg = EXPERIMENTS[name]
            self.assertEqual(cfg["split_json_path"], v3["split_json_path"])
            self.assertEqual(cfg["dataset_split_identifier"], v3["dataset_split_identifier"])
            self.assertEqual(cfg["split_seed"], v3["split_seed"])
            self.assertEqual(cfg["expected_total"], v3["expected_total"])
            self.assertEqual(cfg["expected_counts"], v3["expected_counts"])
            self.assertIs(cfg["load_pool"], v3["load_pool"])


class TestNoV4Reference(unittest.TestCase):
    def test_run_four_dim_training_still_does_not_reference_v4(self):
        import run_four_dim_training
        with open(run_four_dim_training.__file__, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("v4_diagnostic", content)
        self.assertNotIn("v4h_", content)


# ═══════════════════════════════════════════════════════════════════════
# Experiment A2 (power-law-dampened pos_weight, alpha=0.4) -- follow-up
# read-only design review, approved. Same formula/module/entrypoint
# pattern as A0/A1; the ONLY new variable is `alpha`.
# ═══════════════════════════════════════════════════════════════════════

class TestAlphaExactFormula(unittest.TestCase):
    """Requirement 6: the transform must be exactly
    `clip((neg_k/pos_k) ** alpha, clip_min, clip_max)`."""

    def test_alpha_default_is_a1_identity(self):
        self.assertEqual(A1_ALPHA, 1.0)

    def test_a2_alpha_is_exactly_0_4(self):
        # Guards against silent drift -- A2's alpha must remain the fixed
        # design value from the approved design review, never tuned.
        self.assertEqual(A2_ALPHA, 0.4)

    def test_alpha_1_reproduces_raw_ratio_exactly(self):
        counts = {0: 11, 1: 3, 2: 3, 3: 54, 4: 95}
        w_default = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.0, 100.0))
        w_explicit_alpha1 = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.0, 100.0), alpha=1.0)
        # Hand-computed raw ratios (unclipped, so the transform is visible).
        expected_raw = [11 / 155, 14 / 152, 17 / 149, 71 / 95]
        for w, e in zip(w_default, expected_raw):
            self.assertAlmostEqual(w, e, places=9)
        self.assertEqual(w_default, w_explicit_alpha1)

    def test_alpha_0_4_matches_hand_computed_power_law(self):
        counts = {0: 11, 1: 3, 2: 3, 3: 54, 4: 95}
        weights = pos_weight_from_tier_counts(counts, num_classes=5, clip=(0.0, 100.0), alpha=0.4)
        expected = [(11 / 155) ** 0.4, (14 / 152) ** 0.4, (17 / 149) ** 0.4, (71 / 95) ** 0.4]
        for w, e in zip(weights, expected):
            self.assertAlmostEqual(w, e, places=9)

    def test_edge_cases_unaffected_by_alpha(self):
        # positives_k == 0 -> clip_max regardless of alpha; negatives_k == 0
        # -> clip_min regardless of alpha (the alpha transform only applies
        # to the ordinary ratio case, per the formula's own contract).
        no_positives = {0: 10}
        no_negatives = {4: 10}
        for alpha in (1.0, 0.4, 0.1):
            w = pos_weight_from_tier_counts(no_positives, num_classes=5, clip=(0.34, 3.0), alpha=alpha)
            self.assertTrue(all(x == 3.0 for x in w))
            w = pos_weight_from_tier_counts(no_negatives, num_classes=5, clip=(0.34, 3.0), alpha=alpha)
            self.assertTrue(all(x == 0.34 for x in w))


class TestA2ExpectedWeightsOnRealTrainSplit(unittest.TestCase):
    """Requirement: verify the actual A2 weights independently from the
    real 166-example train split (not hardcoded design-review estimates)."""

    @classmethod
    def setUpClass(cls):
        split = _real_split()
        by_id = {e.metadata.example_id: e for e in _EXAMPLES}
        cls.train_only_examples = [by_id[i] for i in split.train_ids]
        cls.a1_weights = compute_dimension_pos_weights(
            cls.train_only_examples, CANONICAL_DIMENSION_KEYS, alpha=A1_ALPHA,
        )
        cls.a2_weights = compute_dimension_pos_weights(
            cls.train_only_examples, CANONICAL_DIMENSION_KEYS, alpha=A2_ALPHA,
        )

    def test_train_split_size_is_166(self):
        self.assertEqual(len(self.train_only_examples), 166)

    def test_a1_weights_unchanged_from_before_a2_existed(self):
        # Exact values recorded in the real A1 checkpoint's
        # `dimension_pos_weights` metadata (verified against
        # best_checkpoint.json in an earlier session) -- A2's addition must
        # not perturb these at all.
        expected_tc = [1 / 3, 1 / 3, 1 / 3, 0.7473684210526316]
        expected_rel = [1 / 3, 1 / 3, 0.34959349593495936, 0.711340206185567]
        for w, e in zip(self.a1_weights["technical_correctness"], expected_tc):
            self.assertAlmostEqual(w, e, places=9)
        for w, e in zip(self.a1_weights["relevance_completeness"], expected_rel):
            self.assertAlmostEqual(w, e, places=9)
        self.assertIsNone(self.a1_weights["depth_specificity"])
        self.assertIsNone(self.a1_weights["grounding_ownership"])

    def test_a2_technical_correctness_weights(self):
        # Independently verified against the real train split this session:
        # [0.3471, 0.3852, 0.4197, 0.8900]. (Not 0.829 at k=3 -- that value
        # belongs to a different, non-selected design-review candidate;
        # 0.890 is the actual A2/alpha=0.4 result, confirmed by direct
        # computation from the real 166-example train split.)
        expected = [0.347075849089803, 0.38522439262462416, 0.41966723273451667, 0.890048960631373]
        for w, e in zip(self.a2_weights["technical_correctness"], expected):
            self.assertAlmostEqual(w, e, places=6)

    def test_a2_relevance_completeness_weights(self):
        expected = [1 / 3, 0.5005971334627136, 0.6567881941079629, 0.8726316137626134]
        for w, e in zip(self.a2_weights["relevance_completeness"], expected):
            self.assertAlmostEqual(w, e, places=6)

    def test_a2_depth_and_grounding_remain_unweighted(self):
        self.assertIsNone(self.a2_weights["depth_specificity"])
        self.assertIsNone(self.a2_weights["grounding_ownership"])

    def test_a2_differs_from_a1_on_weighted_dimensions(self):
        self.assertNotEqual(self.a1_weights["technical_correctness"], self.a2_weights["technical_correctness"])
        self.assertNotEqual(self.a1_weights["relevance_completeness"], self.a2_weights["relevance_completeness"])

    def test_a2_weights_have_no_duplicate_saturated_floor_values_for_tc(self):
        # The specific defect A2 was designed to fix: A1's TC weights had
        # k=0,1,2 all identically pinned to the clip floor. A2 must not.
        tc = self.a2_weights["technical_correctness"]
        self.assertEqual(len(set(round(w, 6) for w in tc)), 4, f"expected 4 distinct values, got {tc}")

    def test_a2_weights_are_deterministic(self):
        again = compute_dimension_pos_weights(self.train_only_examples, CANONICAL_DIMENSION_KEYS, alpha=A2_ALPHA)
        self.assertEqual(again, self.a2_weights)

    def test_a2_weights_within_clip_bounds(self):
        for dim in ("technical_correctness", "relevance_completeness"):
            for w in self.a2_weights[dim]:
                self.assertGreaterEqual(w, 1 / 3 - 1e-9)
                self.assertLessEqual(w, 3.0)


class TestA2FiniteLoss(unittest.TestCase):
    def test_a2_weighted_compute_batch_loss_is_finite(self):
        split = _real_split()
        train_loader, _, _ = build_dataloaders(
            _EXAMPLES, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=8,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        by_id = {e.metadata.example_id: e for e in _EXAMPLES}
        train_only_examples = [by_id[i] for i in split.train_ids]
        dimension_pos_weights = compute_dimension_pos_weights(
            train_only_examples, CANONICAL_DIMENSION_KEYS, alpha=A2_ALPHA,
        )
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        model.eval()
        batch = next(iter(train_loader))
        with torch.no_grad():
            loss = compute_batch_loss(model, batch, "cpu", dimension_pos_weights)
        self.assertTrue(torch.isfinite(loss))


class TestA2ConfigurationSelector(unittest.TestCase):
    def test_a2_registered_and_isolated(self):
        from run_four_dim_training import EXPERIMENTS
        self.assertIn("v3_expA2", EXPERIMENTS)
        a2 = EXPERIMENTS["v3_expA2"]
        self.assertEqual(a2["loss_weighting"], "train_derived_pos_weight")
        self.assertEqual(a2["weighted_dimensions"], ("technical_correctness", "relevance_completeness"))
        self.assertEqual(a2["loss_weight_alpha"], A2_ALPHA)
        self.assertEqual(a2["loss_weight_clip"], (1.0 / 3.0, 3.0))

    def test_a2_does_not_overwrite_v3_a0_or_a1_artifacts_dirs(self):
        import os
        from run_four_dim_training import EXPERIMENTS
        dirs = {name: os.path.normpath(EXPERIMENTS[name]["artifacts_dir"]) for name in ("v3", "v3_expA0", "v3_expA1", "v3_expA2")}
        self.assertEqual(len(set(dirs.values())), 4, f"artifacts_dir collision: {dirs}")

    def test_a1_config_explicitly_records_alpha_1(self):
        from run_four_dim_training import EXPERIMENTS
        self.assertEqual(EXPERIMENTS["v3_expA1"]["loss_weight_alpha"], A1_ALPHA)

    def test_a2_same_pool_split_hyperparams_as_a1(self):
        from run_four_dim_training import EXPERIMENTS
        a1, a2 = EXPERIMENTS["v3_expA1"], EXPERIMENTS["v3_expA2"]
        self.assertIs(a1["load_pool"], a2["load_pool"])
        self.assertEqual(a1["split_json_path"], a2["split_json_path"])
        self.assertEqual(a1["split_seed"], a2["split_seed"])
        self.assertEqual(a1["expected_total"], a2["expected_total"])
        self.assertEqual(a1["expected_counts"], a2["expected_counts"])
        self.assertEqual(a1["weighted_dimensions"], a2["weighted_dimensions"])
        self.assertEqual(a1["loss_weight_clip"], a2["loss_weight_clip"])
        # The ONLY difference between A1 and A2's configs:
        self.assertNotEqual(a1["loss_weight_alpha"], a2["loss_weight_alpha"])

    def test_v1_v2_v3_still_have_no_loss_weight_alpha_key_dependency(self):
        # v1/v2/v3 never reference loss_weighting at all -- unaffected by
        # A2's addition (train()'s `cfg.get("loss_weighting")` gate is
        # still what decides whether alpha is ever read).
        from run_four_dim_training import EXPERIMENTS
        for name in ("v1", "v2", "v3"):
            self.assertNotIn("loss_weighting", EXPERIMENTS[name])


if __name__ == "__main__":
    unittest.main()
