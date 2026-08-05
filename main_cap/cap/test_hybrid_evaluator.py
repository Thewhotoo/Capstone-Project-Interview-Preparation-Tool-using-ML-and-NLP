"""Tests for hybrid_evaluator.py — HybridEvaluator round 2: per-dimension
agreement-banded blending (HIGH/MEDIUM/LOW), overall_score recomputed from
the final blended dimensions, confidence combining agreement + trained
model confidence, feedback text still entirely heuristic-sourced."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import ConfidenceSource, EvaluationResult
from evaluator import Evaluator, check_conformance
from heuristic_evaluator import HeuristicEvaluator
from hybrid_evaluator import (
    _agreement_band, _blend_dimension, _compute_confidence, _recompute_overall, HybridEvaluator,
)
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_evaluator import TrainedEvaluator
from model_heads import MultiTaskModel
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_experimentation import ExperimentConfig, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _request(request_id: str = "r1", answer: str = "I fixed a caching bug by adding TTLs to Redis.") -> EvaluationRequest:
    return EvaluationRequest(
        request_id=request_id, requested_at="2026-07-24T00:00:00+00:00",
        specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING, answer_text=answer,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=(),
    )


def _checkpoint():
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="v1")
    return assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="in-memory-test-artifact")


def _real_trained_evaluator() -> TrainedEvaluator:
    """Real TrainedEvaluator over a tiny random (untrained) backbone -- same
    fixture pattern test_model_evaluator.py uses. Proves the real wiring
    works end-to-end; its predictions aren't meaningful, so band/blend
    behavior is tested against fully-controlled stubs instead."""
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone)
    return TrainedEvaluator(_checkpoint(), model, _TOKENIZER, BackboneConfig(max_length=32))


class _StubEvaluatorWrapper:
    """Wraps a result-transforming function as an Evaluator-conformant
    stand-in for TrainedEvaluator, so per-dimension scores can be
    engineered exactly (a real, even tiny-random, TrainedEvaluator's
    output can't be forced to a specific value on demand)."""

    name = "stub-trained"
    version = "0.0.0"
    declared_dimensions = HeuristicEvaluator.declared_dimensions
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def __init__(self, transform):
        self._transform = transform

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        heuristic = HeuristicEvaluator()
        base = heuristic.evaluate(request)
        return self._transform(base, request).model_copy(update={
            "evaluator_name": "stub-trained", "evaluator_version": "0.0.0",
            "confidence_source": "model_derived",
        })


def _with_dimension_overrides(overrides: dict, confidence: float = 0.8):
    """Builds a transform producing a trained-like result where specific
    dimensions are overridden to exact raw_score values (engineering a
    specific per-dimension agreement level); every other dimension is
    copied from the heuristic result unchanged (agreement == 1.0, HIGH
    band, for dimensions not under test)."""

    def _transform(heuristic_result, request):
        new_dims = tuple(
            d.model_copy(update={"raw_score": overrides[d.name]}) if d.name in overrides else d
            for d in heuristic_result.dimensions
        )
        return heuristic_result.model_copy(update={"dimensions": new_dims, "confidence": confidence})

    return _transform


def _hybrid_with_stub(transform, tmp_log_path=os.devnull, confidence=0.8):
    heuristic = HeuristicEvaluator()
    return HybridEvaluator(heuristic, _StubEvaluatorWrapper(transform), diagnostics_log_path=tmp_log_path)


class _RaisingTrainedEvaluator:
    name = "raising-trained"
    version = "0.0.0"
    declared_dimensions = HeuristicEvaluator.declared_dimensions
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        raise RuntimeError("simulated trained-model failure")


# ─── Unit tests for the pure helper functions ───────────────────────────

class TestAgreementBandClassification(unittest.TestCase):
    def test_high_agreement_band(self):
        self.assertEqual(_agreement_band(0.95), "high")
        self.assertEqual(_agreement_band(0.85), "high")

    def test_medium_agreement_band(self):
        self.assertEqual(_agreement_band(0.70), "medium")
        self.assertEqual(_agreement_band(0.60), "medium")

    def test_low_agreement_band(self):
        self.assertEqual(_agreement_band(0.59), "low")
        self.assertEqual(_agreement_band(0.0), "low")


class TestBlendDimension(unittest.TestCase):
    def _dim(self, name="technical_accuracy", raw_score=0.8):
        from evaluation_result import DimensionScore
        return DimensionScore(
            name=name, raw_score=raw_score, weight_used=0.2, confidence=0.7,
            confidence_source="heuristic", contributes_to_overall=True,
        )

    def test_no_trained_dimension_falls_back_to_heuristic_unchanged(self):
        h = self._dim(raw_score=0.6)
        final, band, agreement = _blend_dimension(h, None)
        self.assertEqual(final.raw_score, 0.6)
        self.assertIsNone(band)
        self.assertIsNone(agreement)

    def test_high_agreement_blends_biased_toward_trained_not_pure_trained(self):
        h = self._dim(raw_score=0.60)
        t = self._dim(raw_score=0.62)  # agreement = 0.98 -> high
        final, band, agreement = _blend_dimension(h, t)
        self.assertEqual(band, "high")
        # 0.80*0.62 + 0.20*0.60 = 0.616 -- biased toward trained, not equal to either pure value
        self.assertAlmostEqual(final.raw_score, 0.616, places=3)
        self.assertNotEqual(final.raw_score, t.raw_score)
        self.assertNotEqual(final.raw_score, h.raw_score)

    def test_medium_agreement_blends_evenly(self):
        h = self._dim(raw_score=0.60)
        t = self._dim(raw_score=0.85)  # diff=0.25, agreement=0.75 -> medium
        final, band, agreement = _blend_dimension(h, t)
        self.assertEqual(band, "medium")
        self.assertAlmostEqual(final.raw_score, 0.725, places=3)  # even split

    def test_low_agreement_heuristic_fully_authoritative(self):
        h = self._dim(raw_score=0.60)
        t = self._dim(raw_score=0.05)  # diff=0.55, agreement=0.45 -> low
        final, band, agreement = _blend_dimension(h, t)
        self.assertEqual(band, "low")
        self.assertEqual(final.raw_score, h.raw_score)

    def test_never_simply_picks_the_higher_score(self):
        """Explicit requirement 5: the policy must not just choose
        whichever score is higher. At medium agreement, a LOWER trained
        score still pulls the blend down from heuristic, not toward
        whichever is higher."""
        h = self._dim(raw_score=0.80)
        t = self._dim(raw_score=0.55)  # diff=0.25 -> medium; trained is LOWER
        final, band, agreement = _blend_dimension(h, t)
        self.assertEqual(band, "medium")
        self.assertLess(final.raw_score, h.raw_score)  # pulled down, not kept at the higher heuristic value
        self.assertGreater(final.raw_score, t.raw_score)  # genuinely blended, not just copied from trained either

    def test_final_dimension_confidence_source_reflects_band_when_blended(self):
        h = self._dim(raw_score=0.60)
        t = self._dim(raw_score=0.62)
        final, band, _ = _blend_dimension(h, t)
        self.assertIn(band, final.confidence_source)

    def test_final_dimension_confidence_source_stays_heuristic_when_low_agreement(self):
        h = self._dim(raw_score=0.60)
        t = self._dim(raw_score=0.05)
        final, band, _ = _blend_dimension(h, t)
        self.assertEqual(final.confidence_source, "heuristic")


class TestRecomputeOverall(unittest.TestCase):
    def _dim(self, name, raw_score, weight, contributes=True):
        from evaluation_result import DimensionScore
        return DimensionScore(
            name=name, raw_score=raw_score, weight_used=weight, confidence=0.7,
            confidence_source="heuristic", contributes_to_overall=contributes,
        )

    def test_weighted_average_of_final_scores(self):
        dims = (self._dim("a", 0.8, 0.6), self._dim("b", 0.4, 0.4))
        # (0.8*0.6 + 0.4*0.4) / (0.6+0.4) = (0.48+0.16)/1.0 = 0.64
        self.assertAlmostEqual(_recompute_overall(dims), 0.64, places=3)

    def test_non_contributing_dimensions_excluded(self):
        dims = (self._dim("a", 1.0, 0.5), self._dim("authenticity", 0.0, 0.5, contributes=False))
        self.assertAlmostEqual(_recompute_overall(dims), 1.0, places=3)

    def test_empty_or_all_non_contributing_returns_zero(self):
        dims = (self._dim("authenticity", 0.9, 0.5, contributes=False),)
        self.assertEqual(_recompute_overall(dims), 0.0)


class TestComputeConfidence(unittest.TestCase):
    """Part 2: confidence combines agreement (dominant) + genuine model
    confidence (secondary), per the requested worked examples."""

    def test_high_agreement_high_model_confidence_is_highest(self):
        conf, mult, tier = _compute_confidence(0.8, "high", 0.95)
        self.assertEqual(tier, "very high")
        self.assertGreater(mult, 0.95)

    def test_high_agreement_low_model_confidence_still_high_but_less(self):
        high_high_conf, high_high_mult, _ = _compute_confidence(0.8, "high", 0.95)
        high_low_conf, high_low_mult, tier = _compute_confidence(0.8, "high", 0.10)
        self.assertLess(high_low_mult, high_high_mult)
        self.assertIn(tier, ("high", "very high"))

    def test_low_agreement_low_model_confidence_is_lowest(self):
        conf, mult, tier = _compute_confidence(0.8, "low", 0.10)
        self.assertEqual(tier, "low")

    def test_low_agreement_high_model_confidence_still_capped_by_band(self):
        """A confident-but-disagreeing model should not produce full
        confidence -- agreement is the dominant signal."""
        low_agreement_high_model, mult, tier = _compute_confidence(0.8, "low", 0.95)
        high_agreement_low_model, mult2, _ = _compute_confidence(0.8, "high", 0.10)
        self.assertLess(low_agreement_high_model, high_agreement_low_model)

    def test_confidence_never_exceeds_original_heuristic_confidence(self):
        for band in ("high", "medium", "low"):
            for model_conf in (0.0, 0.5, 1.0):
                conf, _, _ = _compute_confidence(0.8, band, model_conf)
                self.assertLessEqual(conf, 0.8 + 1e-9)

    def test_monotonic_in_model_confidence_within_a_fixed_band(self):
        low_model, _, _ = _compute_confidence(0.8, "medium", 0.0)
        high_model, _, _ = _compute_confidence(0.8, "medium", 1.0)
        self.assertLess(low_model, high_model)


# ─── Integration tests on HybridEvaluator.evaluate() ────────────────────

class TestConformsToInterface(unittest.TestCase):
    def test_is_an_evaluator(self):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        self.assertIsInstance(evaluator, Evaluator)

    def test_passes_conformance_check(self):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        check_conformance(evaluator, _request())  # must not raise

    def test_requires_network_is_false(self):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        self.assertFalse(evaluator.requires_network)


class TestBothEvaluatorsRun(unittest.TestCase):
    def test_trained_evaluator_is_actually_invoked(self):
        calls = []

        class _CountingTrained:
            name, version = "counting-trained", "0.0.0"
            declared_dimensions = HeuristicEvaluator.declared_dimensions
            declared_reasoning_types = tuple(ReasoningType)
            requires_network = False

            def evaluate(self, request):
                calls.append(request.request_id)
                return HeuristicEvaluator().evaluate(request).model_copy(update={
                    "evaluator_name": "counting-trained", "evaluator_version": "0.0.0",
                })

        evaluator = HybridEvaluator(HeuristicEvaluator(), _CountingTrained(), diagnostics_log_path=os.devnull)
        evaluator.evaluate(_request(request_id="r42"))
        self.assertEqual(calls, ["r42"])


class TestOverallScoreRecomputedFromBlendedDimensions(unittest.TestCase):
    def test_overall_score_reflects_blended_dimensions_not_pure_heuristic(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        # Push every dimension down hard but keep it within HIGH agreement
        # (small diff) so blending actually applies to all of them.
        overrides = {d.name: max(0.0, d.raw_score - 0.05) for d in heuristic_result.dimensions}
        hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides))
        result = hybrid.evaluate(req)
        self.assertNotEqual(result.overall_score, heuristic_result.overall_score)

    def test_grade_recomputed_consistently_with_new_overall_score(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        overrides = {d.name: 0.98 for d in heuristic_result.dimensions}
        hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides))
        result = hybrid.evaluate(req)
        self.assertEqual(result.grade, HeuristicEvaluator._grade(result.overall_score))


class TestFeedbackStaysHeuristicSourced(unittest.TestCase):
    """Requirement 8: strengths, weaknesses, missing_reasoning, suggested
    improvements, recommended topics, and concept coverage must remain
    entirely heuristic-sourced, regardless of how much the dimension
    scores themselves were blended."""

    def test_strengths_weaknesses_and_recommendations_equal_heuristic_exactly(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        overrides = {d.name: 0.02 for d in heuristic_result.dimensions}  # force LOW agreement everywhere
        hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides))
        result = hybrid.evaluate(req)

        self.assertEqual(result.strengths, heuristic_result.strengths)
        self.assertEqual(result.weaknesses, heuristic_result.weaknesses)
        self.assertEqual(result.missing_reasoning, heuristic_result.missing_reasoning)
        self.assertEqual(result.suggested_improvements, heuristic_result.suggested_improvements)
        self.assertEqual(result.recommended_topics, heuristic_result.recommended_topics)
        self.assertEqual(result.concept_coverage, heuristic_result.concept_coverage)
        self.assertEqual(result.contradiction_detected, heuristic_result.contradiction_detected)

    def test_low_agreement_everywhere_leaves_dimensions_and_overall_equal_to_heuristic(self):
        """Sanity check: LOW band's trained_weight is 0.0, so if every
        dimension lands in LOW band, the final scores collapse back to
        exactly the heuristic's own -- the degenerate case that proves
        'heuristic becomes authoritative' really means authoritative."""
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        overrides = {d.name: 0.02 for d in heuristic_result.dimensions}
        hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides))
        result = hybrid.evaluate(req)
        self.assertEqual(result.overall_score, heuristic_result.overall_score)
        self.assertEqual(
            [(d.name, d.raw_score) for d in result.dimensions],
            [(d.name, d.raw_score) for d in heuristic_result.dimensions],
        )


class TestGracefulDegradationOnTrainedFailure(unittest.TestCase):
    def test_trained_evaluator_exception_does_not_crash_evaluate(self):
        hybrid = HybridEvaluator(HeuristicEvaluator(), _RaisingTrainedEvaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())  # must not raise
        self.assertIsInstance(result, EvaluationResult)

    def test_falls_back_to_pure_heuristic_scoring_and_confidence_when_trained_fails(self):
        heuristic = HeuristicEvaluator()
        req = _request()
        heuristic_result = heuristic.evaluate(req)
        hybrid = HybridEvaluator(heuristic, _RaisingTrainedEvaluator(), diagnostics_log_path=os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(hybrid_result.confidence, heuristic_result.confidence)
        self.assertEqual(hybrid_result.overall_score, heuristic_result.overall_score)
        self.assertEqual(
            [(d.name, d.raw_score) for d in hybrid_result.dimensions],
            [(d.name, d.raw_score) for d in heuristic_result.dimensions],
        )

    def test_diagnostics_logging_failure_does_not_crash_evaluate(self):
        bogus_path = os.path.join("Z:", "does", "not", "exist", "diagnostics.jsonl")
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=bogus_path)
        result = hybrid.evaluate(_request())  # must not raise
        self.assertIsInstance(result, EvaluationResult)


class TestDiagnosticsRecording(unittest.TestCase):
    def test_writes_one_jsonl_line_per_call_with_required_fields(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "diagnostics.jsonl")
            heuristic_result_dims = HeuristicEvaluator().evaluate(_request()).dimensions
            overrides = {d.name: max(0.0, d.raw_score - 0.1) for d in heuristic_result_dims}
            hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides), tmp_log_path=log_path)
            hybrid.evaluate(_request(request_id="r1"))
            hybrid.evaluate(_request(request_id="r2"))

            with open(log_path, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 2)
            record = lines[0]
            self.assertEqual(record["request_id"], "r1")
            # Requirement 9: heuristic score, DeBERTa score, final hybrid
            # score, agreement band, evaluator confidence.
            for key in (
                "heuristic_overall_score", "trained_overall_score", "final_hybrid_overall_score",
                "overall_agreement_band", "final_confidence", "per_dimension",
            ):
                self.assertIn(key, record)
            self.assertTrue(record["trained_available"])

    def test_diagnostics_record_trained_unavailable_when_it_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "diagnostics.jsonl")
            hybrid = HybridEvaluator(HeuristicEvaluator(), _RaisingTrainedEvaluator(), diagnostics_log_path=log_path)
            hybrid.evaluate(_request())
            with open(log_path, encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertFalse(record["trained_available"])
            self.assertIsNotNone(record["trained_error"])
            self.assertIsNone(record["overall_agreement"])

    def test_raw_model_output_populated_with_the_real_trained_evaluator(self):
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())
        keys = {name for name, _ in result.raw_model_output}
        self.assertTrue(any(k.startswith("trained_") for k in keys), f"got keys: {keys}")
        self.assertTrue(any(k.startswith("final_") for k in keys), f"got keys: {keys}")
        self.assertIn("agreement_score", keys)


class TestEvaluatorIdentity(unittest.TestCase):
    def test_result_carries_hybrid_identity_not_the_sub_evaluators(self):
        req = _request()
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(req)
        self.assertEqual(result.evaluator_name, "hybrid-v1")
        self.assertEqual(result.evaluator_version, "1.0.0")

    def test_confidence_source_is_hybrid_when_trained_available(self):
        req = _request()
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(req)
        self.assertEqual(result.confidence_source, ConfidenceSource.HYBRID)


class TestDeterminism(unittest.TestCase):
    def test_same_request_produces_same_result(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        overrides = {d.name: 0.5 for d in heuristic_result.dimensions}
        hybrid = _hybrid_with_stub(_with_dimension_overrides(overrides))
        r1 = hybrid.evaluate(req)
        r2 = hybrid.evaluate(req)
        self.assertEqual(r1.overall_score, r2.overall_score)
        self.assertEqual(r1.confidence, r2.confidence)
        self.assertEqual([d.raw_score for d in r1.dimensions], [d.raw_score for d in r2.dimensions])


class TestRealEndToEndWiring(unittest.TestCase):
    """One integration-style test with the REAL TrainedEvaluator (tiny
    random backbone) to prove the actual wiring works end-to-end without
    mocking anything."""

    def test_evaluate_with_real_trained_evaluator_does_not_raise(self):
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.evaluator_name, "hybrid-v1")
        self.assertTrue(result.dimensions)


if __name__ == "__main__":
    unittest.main()
