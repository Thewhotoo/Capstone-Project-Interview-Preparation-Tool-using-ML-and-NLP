"""
Tests for the A2 production-deployment cutover: `deployment_evaluator.py`'s
`deployed_model_a2/` wiring (canonical four-dimension `dimension_names`,
`max_length=256`, `use_private_mlp=False`), the checkpoint-architecture
safety guarantee (loads correctly as canonical, fails loudly as legacy),
and `HybridEvaluator`'s already-existing, verified-here, pass-through
behavior for a canonical (A2-shaped) `TrainedEvaluator` (no legacy-name
mapping invented, no legacy score ever overwrites an A2 score).

Uses a tiny random backbone (existing project precedent, e.g.
`test_model_evaluator.py`, `test_deployment_evaluator.py`) -- never a full
pretrained-weights download, never any real training, and never touches
the actual `deployed_model_a2/`/`deployed_model/` directories on disk
(paths are monkeypatched to a temp directory throughout, mirroring
`test_deployment_evaluator.py`'s own `_PatchedDeploymentPaths`).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

import deployment_evaluator
import evaluator_registry
from evaluation_dimensions import all_keys as canonical_dimension_keys
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from experiment_dataset_io import save_json
from heuristic_evaluator import HeuristicEvaluator
from hybrid_evaluator import HybridEvaluator
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact, save_checkpoint_artifact
from model_evaluator import TrainedEvaluator
from model_heads import MultiTaskModel, coral_predict
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from reasoning_dimension_relevance import ALL_DIMENSIONS
from training_experimentation import ExperimentConfig, PromotionDecision, assemble_checkpoint

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()
_TOKENIZER = build_tokenizer(BackboneConfig())


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _request(request_id: str = "r1") -> EvaluationRequest:
    return EvaluationRequest(
        request_id=request_id, requested_at="2026-07-24T00:00:00+00:00",
        specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING,
        answer_text="I worked through a cache invalidation bug using Redis carefully.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=("caching",),
    )


def _tiny_canonical_model(use_private_mlp: bool = False) -> MultiTaskModel:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    return MultiTaskModel(
        BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS,
        use_private_mlp=use_private_mlp, mlp_hidden_dim=8, mlp_dropout=0.1,
    )


def _canonical_trained_evaluator() -> TrainedEvaluator:
    model = _tiny_canonical_model()
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=42, dataset_version="four_dim_experiment_v2")
    checkpoint = assemble_checkpoint(
        model_version="deberta_v3_base_four_dim_training_v3_expA2_epoch7",
        experiment_config=config, artifact_uri="in-memory-test-artifact",
    )
    return TrainedEvaluator(checkpoint, model, _TOKENIZER, BackboneConfig(max_length=32))


# ═══════════════════════════════════════════════════════════════════════
# 1. A2 deployment artifact discovery
# ═══════════════════════════════════════════════════════════════════════

class TestA2DeploymentArtifactDiscovery(unittest.TestCase):
    def test_deployed_model_dir_points_at_deployed_model_a2(self):
        self.assertTrue(deployment_evaluator.DEPLOYED_MODEL_DIR.endswith("deployed_model_a2"))

    def test_all_three_expected_paths_derive_from_deployed_model_a2(self):
        for p in (
            deployment_evaluator.DEPLOYED_WEIGHTS_PATH,
            deployment_evaluator.DEPLOYED_CHECKPOINT_PATH,
            deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH,
        ):
            self.assertTrue(p.startswith(deployment_evaluator.DEPLOYED_MODEL_DIR))
        self.assertTrue(deployment_evaluator.DEPLOYED_WEIGHTS_PATH.endswith("best_checkpoint_weights.pt"))
        self.assertTrue(deployment_evaluator.DEPLOYED_CHECKPOINT_PATH.endswith("best_checkpoint.json"))
        self.assertTrue(deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH.endswith("final_promotion_decision.json"))

    def test_legacy_deployed_model_dir_is_documented_and_distinct(self):
        self.assertTrue(deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR.endswith(os.sep + "deployed_model"))
        self.assertNotEqual(deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR, deployment_evaluator.DEPLOYED_MODEL_DIR)

    def test_legacy_deployment_files_are_untouched_on_disk(self):
        # This is a SAFE, ISOLATED migration -- the legacy deployment must
        # still physically exist, byte-identical, for rollback.
        legacy_dir = deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR
        for fname in ("best_checkpoint_weights.pt", "best_checkpoint.json", "final_promotion_decision.json"):
            self.assertTrue(os.path.exists(os.path.join(legacy_dir, fname)), f"legacy file missing: {fname}")

    def test_deployed_model_a2_directory_exists_with_promotion_decision(self):
        a2_dir = deployment_evaluator.DEPLOYED_MODEL_DIR
        self.assertTrue(os.path.isdir(a2_dir))
        self.assertTrue(os.path.exists(os.path.join(a2_dir, "final_promotion_decision.json")))

    def test_promotion_decision_is_valid_and_approved(self):
        from experiment_dataset_io import load_json
        decision = load_json(PromotionDecision, deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH)
        self.assertTrue(decision.approved)
        self.assertIn("epoch7", decision.checkpoint_model_version)
        self.assertIn("expA2", decision.checkpoint_model_version)


# ═══════════════════════════════════════════════════════════════════════
# 2/3. Canonical load succeeds; legacy-architecture load fails loudly
# ═══════════════════════════════════════════════════════════════════════

class TestA2CheckpointArchitectureSafety(unittest.TestCase):
    def test_a2_shaped_checkpoint_loads_with_canonical_dimension_names(self):
        model = _tiny_canonical_model()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "weights.pt")
            save_checkpoint_artifact(model, path)
            reloaded = load_checkpoint_artifact(
                path, BackboneConfig(),
                dimension_names=CANONICAL_DIMENSION_KEYS,
                backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
                use_private_mlp=False, mlp_hidden_dim=128, mlp_dropout=0.1,
            )
        self.assertEqual(tuple(reloaded.dimension_names), CANONICAL_DIMENSION_KEYS)
        self.assertEqual(set(reloaded.dimension_names), {
            "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
        })

    def test_a2_shaped_checkpoint_fails_loudly_as_legacy_12_dimension_architecture(self):
        model = _tiny_canonical_model()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "weights.pt")
            save_checkpoint_artifact(model, path)
            with self.assertRaises(RuntimeError):
                load_checkpoint_artifact(
                    path, BackboneConfig(),
                    dimension_names=ALL_DIMENSIONS,  # WRONG -- legacy 12-dim scheme
                    backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
                )

    def test_a2_shaped_checkpoint_fails_loudly_with_default_dimension_names(self):
        # The exact bug this cutover fixed in the OLD deployment_evaluator.py
        # code: calling load_checkpoint_artifact WITHOUT dimension_names=
        # CANONICAL_DIMENSION_KEYS silently defaults to ALL_DIMENSIONS
        # (legacy). Must fail loudly, not silently misconstruct.
        model = _tiny_canonical_model()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "weights.pt")
            save_checkpoint_artifact(model, path)
            with self.assertRaises(RuntimeError):
                load_checkpoint_artifact(
                    path, BackboneConfig(),
                    backbone=build_tiny_random_encoder(_TOKENIZER, hidden_size=16),
                )  # dimension_names omitted entirely


# ═══════════════════════════════════════════════════════════════════════
# 4. max_length=256
# ═══════════════════════════════════════════════════════════════════════

class TestA2MaxLength(unittest.TestCase):
    def test_deployed_max_length_is_256(self):
        self.assertEqual(deployment_evaluator._DEPLOYED_MAX_LENGTH, 256)

    def test_deployed_use_private_mlp_is_false(self):
        # A2 does NOT use B0's private-MLP architecture.
        self.assertFalse(deployment_evaluator._DEPLOYED_USE_PRIVATE_MLP)


# ═══════════════════════════════════════════════════════════════════════
# 5. Active evaluator is the intended A2 evaluator (bootstrap end-to-end)
# ═══════════════════════════════════════════════════════════════════════

def _write_a2_fixture_deployment(deploy_dir: str, approved: bool = True) -> None:
    os.makedirs(deploy_dir, exist_ok=True)
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
    open(os.path.join(deploy_dir, "best_checkpoint_weights.pt"), "wb").close()


def _tiny_canonical_loader(path, backbone_config, **kwargs):
    return _tiny_canonical_model(use_private_mlp=kwargs.get("use_private_mlp", False))


class _PatchedA2DeploymentPaths:
    """Also forces TIER 1 (V3 single-overall-score) to fail by pointing
    `deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3` at an empty
    sibling directory -- this suite specifically exercises the A2 tier in
    isolation, and post V3-cutover the real `deployed_model_overall_single_v3/`
    on disk contains a real, loadable checkpoint that would otherwise win
    tier 1 every time (see test_deployment_evaluator_overall_single_v3.py
    for the dedicated three-tier fallback-chain coverage)."""

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
            "DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3": deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3,
            "_OVERALL_SINGLE_V3_WEIGHTS_PATH": deployment_evaluator._OVERALL_SINGLE_V3_WEIGHTS_PATH,
            "_OVERALL_SINGLE_V3_CHECKPOINT_PATH": deployment_evaluator._OVERALL_SINGLE_V3_CHECKPOINT_PATH,
            "_OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH": deployment_evaluator._OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH,
        }
        deployment_evaluator.DEPLOYED_MODEL_DIR = self.deploy_dir
        deployment_evaluator.DEPLOYED_WEIGHTS_PATH = os.path.join(self.deploy_dir, "best_checkpoint_weights.pt")
        deployment_evaluator.DEPLOYED_CHECKPOINT_PATH = os.path.join(self.deploy_dir, "best_checkpoint.json")
        deployment_evaluator.DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(self.deploy_dir, "final_promotion_decision.json")
        deployment_evaluator.load_checkpoint_artifact = _tiny_canonical_loader

        empty_tier1_dir = os.path.join(self.deploy_dir, "_empty_tier1_for_isolation")
        os.makedirs(empty_tier1_dir, exist_ok=True)
        deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3 = empty_tier1_dir
        deployment_evaluator._OVERALL_SINGLE_V3_WEIGHTS_PATH = os.path.join(empty_tier1_dir, "best_checkpoint_weights.pt")
        deployment_evaluator._OVERALL_SINGLE_V3_CHECKPOINT_PATH = os.path.join(empty_tier1_dir, "best_checkpoint.json")
        deployment_evaluator._OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH = os.path.join(empty_tier1_dir, "final_promotion_decision.json")
        return self

    def __exit__(self, *exc_info):
        for name, value in self._originals.items():
            setattr(deployment_evaluator, name, value)


class TestA2BootstrapEndToEnd(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None

    def test_a2_hybrid_evaluator_becomes_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_a2_fixture_deployment(tmpdir)
            with _PatchedA2DeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            active = evaluator_registry.get_active_evaluator()
            self.assertIsInstance(active, HybridEvaluator)
            self.assertEqual(active.declared_dimensions, HeuristicEvaluator().declared_dimensions)  # unchanged contract

    def test_a2_trained_evaluator_registered_with_canonical_declared_dimensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_a2_fixture_deployment(tmpdir)
            with _PatchedA2DeploymentPaths(tmpdir):
                deployment_evaluator.bootstrap_production_evaluator()

            trained_name = next(n for n in evaluator_registry.registered_evaluator_names() if n.startswith("trained-"))
            trained = evaluator_registry.get_evaluator(trained_name)
            self.assertEqual(set(trained.declared_dimensions), set(CANONICAL_DIMENSION_KEYS))


# ═══════════════════════════════════════════════════════════════════════
# 6/7. Four canonical dimensions returned; scores are integers in [0,4]
# ═══════════════════════════════════════════════════════════════════════

class TestA2EvaluationOutputShape(unittest.TestCase):
    def test_evaluate_returns_exactly_the_four_canonical_dimensions(self):
        evaluator = _canonical_trained_evaluator()
        result = evaluator.evaluate(_request())
        self.assertEqual({d.name for d in result.dimensions}, set(CANONICAL_DIMENSION_KEYS))
        self.assertEqual(len(result.dimensions), 4)

    def test_canonical_dimensions_apply_regardless_of_reasoning_type(self):
        # Per model_evaluator.py: the four canonical dimensions apply to
        # EVERY question intent by construction -- no legacy relevance/
        # exclusion table entry exists for these names.
        evaluator = _canonical_trained_evaluator()
        for rt in (ReasoningType.DEBUGGING, ReasoningType.TRADE_OFF_ANALYSIS, ReasoningType.DESIGN):
            request = EvaluationRequest(
                request_id=f"r_{rt.value}", requested_at="2026-07-24T00:00:00+00:00",
                specification=_spec(), question_text="Q", reasoning_type=rt,
                answer_text="An answer about Redis caching.",
                conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
                expected_concepts=(),
            )
            result = evaluator.evaluate(request)
            self.assertEqual({d.name for d in result.dimensions}, set(CANONICAL_DIMENSION_KEYS))

    def test_underlying_ordinal_predictions_are_integers_in_0_to_4(self):
        # The API's DimensionScore.raw_score is intentionally a 0..1 FLOAT
        # (ordinal / (num_classes-1)) for direct percentage rendering -- the
        # underlying CORAL ordinal tier itself (what coral_predict produces
        # before that normalization) is what must be an integer in [0,4],
        # the "ordinal 0-4" scale evaluation_dimensions.py specifies.
        model = _tiny_canonical_model()
        model.eval()
        from model_backbone import build_dimension_pair, tokenize_pair
        text_a, text_b = build_dimension_pair("A question", "", (), "An answer.")
        encoding = tokenize_pair(_TOKENIZER, text_a, text_b, 32)
        batch = _TOKENIZER.pad([encoding], return_tensors="pt")
        with torch.no_grad():
            outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])
        for name in CANONICAL_DIMENSION_KEYS:
            ordinal = int(coral_predict(outputs["dimension_logits"][name])[0].item())
            self.assertIsInstance(ordinal, int)
            self.assertGreaterEqual(ordinal, 0)
            self.assertLessEqual(ordinal, 4)

    def test_raw_score_is_a_valid_fraction_of_the_5_tier_ordinal_scale(self):
        evaluator = _canonical_trained_evaluator()
        result = evaluator.evaluate(_request())
        valid_fractions = {round(i / 4, 3) for i in range(5)}  # 0, 0.25, 0.5, 0.75, 1.0
        for d in result.dimensions:
            self.assertIn(round(d.raw_score, 3), valid_fractions)


# ═══════════════════════════════════════════════════════════════════════
# 8. No legacy dimension names accidentally required for A2 evaluation
# ═══════════════════════════════════════════════════════════════════════

class TestA2NeverRequiresLegacyDimensionNames(unittest.TestCase):
    def test_canonical_evaluator_never_references_legacy_dimension_names(self):
        evaluator = _canonical_trained_evaluator()
        result = evaluator.evaluate(_request())
        legacy_names = set(ALL_DIMENSIONS)
        produced_names = {d.name for d in result.dimensions}
        self.assertFalse(produced_names & legacy_names, "A2 evaluation unexpectedly produced a legacy dimension name")

    def test_hybrid_evaluator_a2_scores_pass_through_unmodified(self):
        # HYBRID EVALUATOR DECISION (this cutover): hybrid_evaluator.py is
        # UNCHANGED. Because A2's canonical dimension names never match any
        # HeuristicEvaluator legacy name, every dimension takes the
        # pre-existing "no overlapping dimensions to compare" branch --
        # verified here directly against the real, unmodified
        # HybridEvaluator: A2's dimensions/overall_score/grade must be
        # byte-for-byte what the bare TrainedEvaluator itself produced.
        trained = _canonical_trained_evaluator()
        hybrid = HybridEvaluator(HeuristicEvaluator(), trained)
        request = _request()

        trained_result = trained.evaluate(request)
        hybrid_result = hybrid.evaluate(request)

        trained_by_name = {d.name: d.raw_score for d in trained_result.dimensions}
        hybrid_by_name = {d.name: d.raw_score for d in hybrid_result.dimensions}
        self.assertEqual(trained_by_name, hybrid_by_name, "HybridEvaluator altered an A2 score -- must never happen")
        self.assertEqual(hybrid_result.overall_score, trained_result.overall_score)
        self.assertEqual(hybrid_result.grade, trained_result.grade)

    def test_hybrid_evaluator_confidence_degrades_honestly_not_fabricated(self):
        trained = _canonical_trained_evaluator()
        hybrid = HybridEvaluator(HeuristicEvaluator(), trained)
        result = hybrid.evaluate(_request())
        self.assertIn("no heuristic dimensions were available for comparison", result.confidence_rationale)
        self.assertEqual(result.confidence, trained.evaluate(_request()).confidence)

    def test_no_legacy_heuristic_score_ever_overwrites_an_a2_score(self):
        # Direct, adversarial check: even when the heuristic's OWN score
        # for whatever it calls a dimension is very low (which would, for
        # an overlapping legacy dimension, risk triggering the Dimension
        # Plausibility Guardrail), an A2 dimension must be completely
        # unaffected, since h_dim is always None for every A2 dimension
        # name -- the guardrail's own `if h_dim is not None and ...` guard
        # structurally cannot fire.
        trained = _canonical_trained_evaluator()
        hybrid = HybridEvaluator(HeuristicEvaluator(), trained)
        request = EvaluationRequest(
            request_id="adversarial", requested_at="2026-07-24T00:00:00+00:00",
            specification=_spec(), question_text="Q", reasoning_type=ReasoningType.DEBUGGING,
            answer_text="lol idk whatever gibberish blah",  # heuristic will score this very low
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=(),
        )
        trained_result = trained.evaluate(request)
        hybrid_result = hybrid.evaluate(request)
        trained_by_name = {d.name: d.raw_score for d in trained_result.dimensions}
        hybrid_by_name = {d.name: d.raw_score for d in hybrid_result.dimensions}
        self.assertEqual(trained_by_name, hybrid_by_name)


if __name__ == "__main__":
    unittest.main()
