"""
AveragedEvaluator (averaged_evaluator.py) and its tier in
deployment_evaluator._try_activate_averaged_v5. Uses stub evaluators and
temporary folders only -- never loads the real 735 MB model.
"""

import os
import tempfile
import unittest
from unittest import mock

import deployment_evaluator
import evaluator_registry
from averaged_evaluator import HEURISTIC_WEIGHT, AveragedEvaluator
from heuristic_evaluator import HeuristicEvaluator


class _Stub:
    def __init__(self, name, score=None, fail=False):
        self.name, self._score, self._fail = name, score, fail
        self.declared_dimensions, self.declared_reasoning_types = ("x",), ()

    def evaluate(self, request):
        if self._fail:
            raise RuntimeError("model broke")
        base = HeuristicEvaluator().evaluate(request)
        return base.model_copy(update={"overall_score": self._score, "model_version": (("m", self.name),),
                                       "dataset_version": "overall_v5_1088"})


def _request():
    from evaluation_request import ConversationContextSnapshot, EvaluationRequest
    from question_families import ReasoningType
    from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
    spec = QuestionSpecification(
        id="s", category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(title="Interview Coach", summary="A Flask app.", technologies=("Flask",))),
        source_type=SourceType.PROJECT, source_id="p", source_field="projects", reason="t")
    return EvaluationRequest(
        request_id="r", requested_at="2026-09-30T00:00:00+00:00", specification=spec,
        question_text="How did you store answers?", reasoning_type=ReasoningType.EXPLANATION,
        answer_text="I saved every answer in SQLite as it was submitted so a restart lost nothing.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False))


class TestBlend(unittest.TestCase):
    def test_score_is_the_weighted_blend_and_components_are_kept(self):
        heuristic = HeuristicEvaluator()
        h = heuristic.evaluate(_request()).overall_score
        ev = AveragedEvaluator(heuristic, _Stub("model", 0.2))
        result = ev.evaluate(_request())
        self.assertAlmostEqual(result.overall_score, round(HEURISTIC_WEIGHT * h + (1 - HEURISTIC_WEIGHT) * 0.2, 3), places=3)
        self.assertEqual(dict(result.raw_model_output), {"heuristic_overall": h, "model_overall": 0.2})
        self.assertTrue(result.evaluator_name.startswith("averaged-"))
        self.assertEqual(result.dataset_version, "overall_v5_1088")

    def test_model_failure_falls_back_to_the_heuristic(self):
        heuristic = HeuristicEvaluator()
        expected = heuristic.evaluate(_request()).overall_score
        self.assertEqual(AveragedEvaluator(heuristic, _Stub("model", fail=True)).evaluate(_request()).overall_score, expected)


class TestDeploymentTier(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.multiple(
            deployment_evaluator, OVERALL_V5_DIR=self.dir,
            _OVERALL_V5_WEIGHTS=os.path.join(self.dir, "best_checkpoint_weights.pt"),
            _OVERALL_V5_CHECKPOINT=os.path.join(self.dir, "best_checkpoint.json"),
            _OVERALL_V5_DECISION=os.path.join(self.dir, "final_promotion_decision.json"))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_missing_model_is_skipped_without_registering_anything(self):
        self.assertFalse(deployment_evaluator._try_activate_averaged_v5())
        self.assertEqual(evaluator_registry._registry, {})

    def test_git_lfs_pointer_is_not_mistaken_for_the_model(self):
        for name in ("best_checkpoint_weights.pt", "best_checkpoint.json", "final_promotion_decision.json"):
            with open(os.path.join(self.dir, name), "w") as f:
                f.write("version https://git-lfs.github.com/spec/v1\nsize 735421149\n")
        self.assertFalse(deployment_evaluator._try_activate_averaged_v5())

    def test_can_be_switched_off(self):
        with mock.patch.dict(os.environ, {"CAP_TRAINED_EVALUATOR": "0"}):
            self.assertFalse(deployment_evaluator._try_activate_averaged_v5())

    def test_bootstrap_falls_back_to_heuristic_when_model_absent(self):
        with mock.patch.object(deployment_evaluator, "DEPLOYED_WEIGHTS_PATH", os.path.join(self.dir, "none.pt")):
            deployment_evaluator.bootstrap_production_evaluator()
        self.assertEqual(evaluator_registry.get_active_evaluator().name, "heuristic-v1")


if __name__ == "__main__":
    unittest.main()
