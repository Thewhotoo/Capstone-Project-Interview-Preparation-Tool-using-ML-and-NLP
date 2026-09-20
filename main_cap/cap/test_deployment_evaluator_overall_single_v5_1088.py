"""
Dedicated tests for the v5_1088 deployment tier: path isolation from every
other tier, real-checkpoint loading (the actual 735MB
`deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt`
extracted from the Colab-trained `overall_single_v5_1088.zip`), the
correct architecture/version being reported, and the "heuristics never
touch overall_score" guarantee re-verified against the REAL checkpoint
(not just the tiny random encoder `test_overall_single_evaluator.py` uses).

The real-checkpoint tests are SKIPPED (not failed) if the deployment
directory/weights aren't present on this machine -- e.g. a fresh clone
before the checkpoint has been placed -- since `*.pt` is gitignored and the
weights are never committed. This mirrors how the fast, monkeypatched tests
in `test_deployment_evaluator_overall_single_v3.py` stay independent of
what is or isn't on disk, while these tests specifically exist to prove the
real artifact works.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deployment_evaluator
from evaluation_dimensions import CANONICAL_DIMENSIONS
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import DimensionScore
from model_backbone import BackboneConfig, build_tokenizer
from overall_score_model import OverallScoreModel, load_overall_checkpoint_artifact
from overall_single_evaluator import OverallSingleEvaluator
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType

_REAL_WEIGHTS_PATH = deployment_evaluator._OVERALL_SINGLE_V5_1088_WEIGHTS_PATH
_REAL_CHECKPOINT_PATH = deployment_evaluator._OVERALL_SINGLE_V5_1088_CHECKPOINT_PATH
_REAL_PROMOTION_DECISION_PATH = deployment_evaluator._OVERALL_SINGLE_V5_1088_PROMOTION_DECISION_PATH

_HAS_REAL_CHECKPOINT = os.path.exists(_REAL_WEIGHTS_PATH) and os.path.exists(_REAL_CHECKPOINT_PATH)

_EXPECTED_MODEL_VERSION = "deberta_v3_base_overall_single_v5_1088_epoch8"
_EXPECTED_DATASET_VERSION = "overall_v5_1088"


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="v5_1088_test_spec", category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(
            title="Order Management API", summary="A backend service handling the order lifecycle.",
            technologies=("FastAPI", "PostgreSQL", "Redis"),
        )),
        source_type=SourceType.PROJECT, source_id="v5_1088_test_proj", source_field="projects", reason="test",
    )


def _request(answer_text: str) -> EvaluationRequest:
    return EvaluationRequest(
        request_id="v5_1088_test_req", requested_at="2026-01-01T00:00:00+00:00",
        specification=_spec(), question_text="Why did you add a cache in front of the read-heavy endpoint?",
        reasoning_type=ReasoningType.TRADE_OFF_ANALYSIS, answer_text=answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


class TestV5_1088ArtifactPathIsolation(unittest.TestCase):
    """Static checks -- do not require the real checkpoint on disk."""

    def test_deployed_model_dir_points_at_overall_single_v5_1088(self):
        self.assertTrue(
            deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088.replace("\\", "/").endswith(
                "deployed_model_overall_single_v5_1088"
            )
        )

    def test_all_three_expected_paths_derive_from_v5_1088_dir(self):
        for p in (
            deployment_evaluator._OVERALL_SINGLE_V5_1088_WEIGHTS_PATH,
            deployment_evaluator._OVERALL_SINGLE_V5_1088_CHECKPOINT_PATH,
            deployment_evaluator._OVERALL_SINGLE_V5_1088_PROMOTION_DECISION_PATH,
        ):
            self.assertTrue(p.startswith(deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088))

    def test_isolated_from_every_other_deployment_directory(self):
        v5_dir = deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088
        for other in (
            deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3,
            deployment_evaluator.DEPLOYED_MODEL_DIR,
            deployment_evaluator.LEGACY_DEPLOYED_MODEL_DIR,
        ):
            self.assertNotEqual(v5_dir, other)

    def test_v3_directory_and_files_are_not_touched_by_this_cutover(self):
        # The old production checkpoint must remain fully present and
        # untouched -- rollback must stay possible.
        v3_dir = deployment_evaluator.DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3
        if not os.path.isdir(v3_dir):
            self.skipTest("deployed_model_overall_single_v3/ not present on this machine")
        self.assertTrue(os.path.exists(os.path.join(v3_dir, "best_checkpoint.json")))
        self.assertTrue(os.path.exists(os.path.join(v3_dir, "final_promotion_decision.json")))

    def test_bootstrap_tries_v5_1088_before_v3(self):
        import inspect
        source = inspect.getsource(deployment_evaluator.bootstrap_production_evaluator)
        v5_pos = source.find("_try_activate_overall_single_v5_1088")
        v3_pos = source.find("_try_activate_overall_single_v3")
        self.assertGreater(v5_pos, -1)
        self.assertGreater(v3_pos, -1)
        self.assertLess(v5_pos, v3_pos, "v5_1088 tier must be attempted before v3 in bootstrap order")


@unittest.skipUnless(_HAS_REAL_CHECKPOINT, "real deployed_model_overall_single_v5_1088/ checkpoint not present on this machine")
class TestV5_1088RealCheckpointLoads(unittest.TestCase):
    """Proves the ACTUAL downloaded checkpoint loads and behaves correctly
    -- not a tiny random encoder stand-in. Slower (loads the real 735MB
    deberta-v3-base weights) by design."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(_REAL_CHECKPOINT_PATH, encoding="utf-8") as f:
            cls.checkpoint_meta = json.load(f)
        cls.backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256)
        cls.tokenizer = build_tokenizer(cls.backbone_config)
        cls.model = load_overall_checkpoint_artifact(_REAL_WEIGHTS_PATH, cls.backbone_config)

    def test_checkpoint_metadata_reports_expected_model_and_dataset_version(self):
        self.assertEqual(self.checkpoint_meta["model_version"], _EXPECTED_MODEL_VERSION)
        self.assertEqual(self.checkpoint_meta["dataset_version"], _EXPECTED_DATASET_VERSION)

    def test_loaded_model_is_the_expected_architecture(self):
        self.assertIsInstance(self.model, OverallScoreModel)
        self.assertEqual(self.model.num_ordinal_classes, 5)

    def test_loaded_model_is_deberta_v3_base_sized(self):
        # deberta-v3-base has ~184M parameters; a materially different
        # count would mean the wrong backbone was loaded.
        n_params = sum(p.numel() for p in self.model.parameters())
        self.assertGreater(n_params, 170_000_000)
        self.assertLess(n_params, 200_000_000)

    def test_model_produces_an_overall_score_in_the_expected_0_to_4_range(self):
        from evaluation_request import ConversationContextSnapshot, EvaluationRequest
        from model_backbone import build_dimension_pair, grounding_to_text, tokenize_pair
        from model_heads import coral_predict
        import torch

        self.model.eval()
        with torch.no_grad():
            spec = _spec()
            context_text, answer_text = build_dimension_pair(
                "Why did you add a cache in front of the read-heavy endpoint?",
                grounding_to_text(spec.grounding), (),
                "We added Redis in front of the catalog reads because they outnumbered writes 50 to 1.",
            )
            encoding = tokenize_pair(self.tokenizer, context_text, answer_text, self.backbone_config.max_length)
            padded = self.tokenizer.pad([encoding], return_tensors="pt")
            logits = self.model(padded["input_ids"], padded["attention_mask"])
            ordinal = int(coral_predict(logits)[0].item())
        self.assertGreaterEqual(ordinal, 0)
        self.assertLessEqual(ordinal, 4)

    def test_production_evaluator_reports_the_v5_1088_model_version(self):
        checkpoint = deployment_evaluator.load_json(deployment_evaluator.Checkpoint, _REAL_CHECKPOINT_PATH)
        evaluator = OverallSingleEvaluator(checkpoint, self.model, self.tokenizer, self.backbone_config)
        self.assertIn(_EXPECTED_MODEL_VERSION, evaluator.name)
        result = evaluator.evaluate(_request("We added Redis because catalog reads outnumbered writes 50 to 1."))
        self.assertIn(_EXPECTED_MODEL_VERSION, result.evaluator_name)

    def test_four_heuristic_diagnostics_are_still_produced(self):
        checkpoint = deployment_evaluator.load_json(deployment_evaluator.Checkpoint, _REAL_CHECKPOINT_PATH)
        evaluator = OverallSingleEvaluator(checkpoint, self.model, self.tokenizer, self.backbone_config)
        result = evaluator.evaluate(_request("We added Redis because catalog reads outnumbered writes 50 to 1."))
        self.assertEqual(len(result.dimensions), 4)
        self.assertEqual({d.name for d in result.dimensions}, {d.value for d in CANONICAL_DIMENSIONS})

    def test_heuristic_diagnostics_do_not_modify_overall_score_on_the_real_checkpoint(self):
        # Same guarantee test_overall_single_evaluator.py proves against a
        # tiny random encoder -- re-proven here against the REAL v5_1088
        # weights, closing the "does this hold for the actual deployed
        # model, not just the test double" gap.
        from unittest import mock

        checkpoint = deployment_evaluator.load_json(deployment_evaluator.Checkpoint, _REAL_CHECKPOINT_PATH)
        evaluator = OverallSingleEvaluator(checkpoint, self.model, self.tokenizer, self.backbone_config)
        request = _request("We added Redis because catalog reads outnumbered writes 50 to 1.")

        baseline = evaluator.evaluate(request)

        extreme_low = tuple(
            DimensionScore(name=d.value, raw_score=0.0, weight_used=0.25, confidence=0.9,
                            confidence_source="heuristic", contributes_to_overall=False)
            for d in CANONICAL_DIMENSIONS
        )
        with mock.patch.object(evaluator.diagnostics_engine, "compute", return_value=extreme_low):
            result_low = evaluator.evaluate(request)

        extreme_high = tuple(
            DimensionScore(name=d.value, raw_score=1.0, weight_used=0.25, confidence=0.9,
                            confidence_source="heuristic", contributes_to_overall=False)
            for d in CANONICAL_DIMENSIONS
        )
        with mock.patch.object(evaluator.diagnostics_engine, "compute", return_value=extreme_high):
            result_high = evaluator.evaluate(request)

        self.assertEqual(baseline.overall_score, result_low.overall_score)
        self.assertEqual(baseline.overall_score, result_high.overall_score)
        self.assertEqual(baseline.grade, result_low.grade)
        self.assertEqual(baseline.grade, result_high.grade)


if __name__ == "__main__":
    unittest.main()
