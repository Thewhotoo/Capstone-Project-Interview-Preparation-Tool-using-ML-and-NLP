"""Tests for hybrid_evaluator.py — HybridEvaluator (runs both evaluators,
never blends scores, adjusts only reported confidence based on agreement)."""

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
from hybrid_evaluator import HybridEvaluator
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


def _checkpoint() -> "assemble_checkpoint":
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="v1")
    return assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="in-memory-test-artifact")


def _real_trained_evaluator() -> TrainedEvaluator:
    """A real TrainedEvaluator over a tiny random (untrained) backbone --
    same fixture pattern test_model_evaluator.py already uses. Its
    predictions are not meaningful, but this proves the real wiring
    (tokenization, forward pass, EvaluationResult construction) works
    end-to-end without mocking anything."""
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone)
    return TrainedEvaluator(_checkpoint(), model, _TOKENIZER, BackboneConfig(max_length=32))


class _StubTrainedEvaluator:
    """Deterministic stand-in for TrainedEvaluator, conforming to the same
    Evaluator Protocol, used to test HybridEvaluator's agreement/confidence
    logic under FULLY CONTROLLED conditions -- a real (even tiny-random)
    TrainedEvaluator's output can't be forced to a specific agreement level
    on demand."""

    name = "stub-trained"
    version = "0.0.0"
    declared_dimensions = HeuristicEvaluator.declared_dimensions
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def __init__(self, result_factory):
        self._result_factory = result_factory

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        return self._result_factory(request)


def _stub_result_matching(heuristic_result: EvaluationResult, request: EvaluationRequest) -> EvaluationResult:
    """Builds a stub 'trained' result with IDENTICAL per-dimension scores
    to the given heuristic result -- perfect agreement, agreement_score == 1.0."""
    return heuristic_result.model_copy(update={
        "evaluator_name": "stub-trained", "evaluator_version": "0.0.0",
        "confidence_source": "model_derived",
    })


def _stub_result_disagreeing(heuristic_result: EvaluationResult, request: EvaluationRequest) -> EvaluationResult:
    """Builds a stub 'trained' result with every dimension's raw_score
    flipped to the opposite end of [0, 1] -- maximal disagreement."""
    flipped = tuple(d.model_copy(update={"raw_score": round(1.0 - d.raw_score, 3)}) for d in heuristic_result.dimensions)
    return heuristic_result.model_copy(update={
        "evaluator_name": "stub-trained", "evaluator_version": "0.0.0",
        "confidence_source": "model_derived", "dimensions": flipped,
    })


class _RaisingTrainedEvaluator:
    name = "raising-trained"
    version = "0.0.0"
    declared_dimensions = HeuristicEvaluator.declared_dimensions
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        raise RuntimeError("simulated trained-model failure")


def _hybrid_with_stub(stub_factory, tmp_log_path):
    heuristic = HeuristicEvaluator()

    class _Wrapper:
        name = "stub-trained"
        version = "0.0.0"
        declared_dimensions = HeuristicEvaluator.declared_dimensions
        declared_reasoning_types = tuple(ReasoningType)
        requires_network = False

        def evaluate(self, request):
            base = heuristic.evaluate(request)
            return stub_factory(base, request)

    return HybridEvaluator(heuristic, _Wrapper(), diagnostics_log_path=tmp_log_path)


class TestConformsToInterface(unittest.TestCase):
    def test_is_an_evaluator(self):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        self.assertIsInstance(evaluator, Evaluator)

    def test_passes_conformance_check(self, tmp_path=None):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        check_conformance(evaluator, _request())  # must not raise

    def test_requires_network_is_false(self):
        evaluator = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator())
        self.assertFalse(evaluator.requires_network)


class TestBothEvaluatorsRun(unittest.TestCase):
    def test_trained_evaluator_is_actually_invoked(self):
        calls = []
        heuristic = HeuristicEvaluator()

        class _CountingTrained:
            name, version = "counting-trained", "0.0.0"
            declared_dimensions = HeuristicEvaluator.declared_dimensions
            declared_reasoning_types = tuple(ReasoningType)
            requires_network = False

            def evaluate(self, request):
                calls.append(request.request_id)
                return heuristic.evaluate(request).model_copy(update={
                    "evaluator_name": "counting-trained", "evaluator_version": "0.0.0",
                })

        evaluator = HybridEvaluator(heuristic, _CountingTrained(), diagnostics_log_path=os.devnull)
        evaluator.evaluate(_request(request_id="r42"))
        self.assertEqual(calls, ["r42"])


class TestHeuristicIsAuthoritative(unittest.TestCase):
    """Requirement 6: strengths, weaknesses, recommendations, explanations
    (and every other candidate-facing scoring field) must be sourced
    entirely from the heuristic evaluator, unchanged."""

    def test_overall_score_and_grade_equal_heuristic_exactly(self):
        heuristic = HeuristicEvaluator()
        req = _request()
        heuristic_result = heuristic.evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(hybrid_result.overall_score, heuristic_result.overall_score)
        self.assertEqual(hybrid_result.grade, heuristic_result.grade)

    def test_dimension_raw_scores_equal_heuristic_exactly(self):
        heuristic = HeuristicEvaluator()
        req = _request()
        heuristic_result = heuristic.evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(
            [(d.name, d.raw_score) for d in hybrid_result.dimensions],
            [(d.name, d.raw_score) for d in heuristic_result.dimensions],
        )

    def test_strengths_weaknesses_missing_reasoning_equal_heuristic_exactly(self):
        heuristic = HeuristicEvaluator()
        req = _request()
        heuristic_result = heuristic.evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(hybrid_result.strengths, heuristic_result.strengths)
        self.assertEqual(hybrid_result.weaknesses, heuristic_result.weaknesses)
        self.assertEqual(hybrid_result.missing_reasoning, heuristic_result.missing_reasoning)
        self.assertEqual(hybrid_result.suggested_improvements, heuristic_result.suggested_improvements)
        self.assertEqual(hybrid_result.recommended_topics, heuristic_result.recommended_topics)
        self.assertEqual(hybrid_result.concept_coverage, heuristic_result.concept_coverage)
        self.assertEqual(hybrid_result.contradiction_detected, heuristic_result.contradiction_detected)


class TestAgreementAdjustsOnlyConfidence(unittest.TestCase):
    def test_perfect_agreement_leaves_confidence_unchanged(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_matching, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(hybrid_result.confidence, heuristic_result.confidence)
        self.assertEqual(hybrid_result.confidence_source, heuristic_result.confidence_source)

    def test_disagreement_lowers_confidence_and_never_raises_it(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertLessEqual(hybrid_result.confidence, heuristic_result.confidence)
        self.assertEqual(hybrid_result.confidence_source, ConfidenceSource.HYBRID)

    def test_disagreement_confidence_never_drops_below_the_dampened_floor(self):
        req = _request()
        heuristic_result = HeuristicEvaluator().evaluate(req)
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)

        # Even at maximal disagreement, confidence must not collapse to 0 --
        # the dampening floor (_MIN_CONFIDENCE_MULTIPLIER) guarantees at
        # least half of the heuristic's own confidence survives.
        self.assertGreaterEqual(hybrid_result.confidence, heuristic_result.confidence * 0.5 - 1e-6)

    def test_confidence_rationale_mentions_agreement(self):
        req = _request()
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        hybrid_result = hybrid.evaluate(req)
        self.assertIn("agreement", hybrid_result.confidence_rationale.lower())


class TestGracefulDegradationOnTrainedFailure(unittest.TestCase):
    def test_trained_evaluator_exception_does_not_crash_evaluate(self):
        heuristic = HeuristicEvaluator()
        hybrid = HybridEvaluator(heuristic, _RaisingTrainedEvaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())  # must not raise
        self.assertIsInstance(result, EvaluationResult)

    def test_falls_back_to_heuristic_confidence_when_trained_fails(self):
        heuristic = HeuristicEvaluator()
        req = _request()
        heuristic_result = heuristic.evaluate(req)
        hybrid = HybridEvaluator(heuristic, _RaisingTrainedEvaluator(), diagnostics_log_path=os.devnull)
        hybrid_result = hybrid.evaluate(req)

        self.assertEqual(hybrid_result.confidence, heuristic_result.confidence)

    def test_diagnostics_logging_failure_does_not_crash_evaluate(self):
        heuristic = HeuristicEvaluator()
        # An unwritable directory path as the log target.
        bogus_path = os.path.join("Z:", "does", "not", "exist", "diagnostics.jsonl")
        hybrid = HybridEvaluator(heuristic, _real_trained_evaluator(), diagnostics_log_path=bogus_path)
        result = hybrid.evaluate(_request())  # must not raise
        self.assertIsInstance(result, EvaluationResult)


class TestDiagnosticsRecording(unittest.TestCase):
    def test_writes_one_jsonl_line_per_call(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "diagnostics.jsonl")
            hybrid = _hybrid_with_stub(_stub_result_matching, log_path)
            hybrid.evaluate(_request(request_id="r1"))
            hybrid.evaluate(_request(request_id="r2"))

            with open(log_path, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["request_id"], "r1")
            self.assertEqual(lines[1]["request_id"], "r2")
            self.assertIn("agreement_score", lines[0])
            self.assertTrue(lines[0]["trained_available"])

    def test_raw_model_output_includes_trained_and_agreement_entries(self):
        req = _request()
        hybrid = _hybrid_with_stub(_stub_result_matching, os.devnull)
        result = hybrid.evaluate(req)
        keys = {name for name, _ in result.raw_model_output}
        self.assertTrue(any(k.startswith("trained_") for k in keys))
        self.assertIn("agreement_score", keys)

    def test_raw_model_output_populated_with_the_real_trained_evaluator(self):
        """Regression test: TrainedEvaluator itself leaves
        EvaluationResult.raw_model_output at its default empty tuple (it
        never sets that field) -- trained_* entries here must be built
        from trained_result.dimensions, not trained_result.raw_model_output,
        or they'd silently be empty against the real evaluator despite
        passing against a stub that happens to copy a non-empty field."""
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())
        keys = {name for name, _ in result.raw_model_output}
        self.assertTrue(any(k.startswith("trained_") for k in keys), f"got keys: {keys}")
        self.assertIn("agreement_score", keys)

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
            self.assertIsNone(record["agreement_score"])


class TestEvaluatorIdentity(unittest.TestCase):
    def test_result_carries_hybrid_identity_not_the_sub_evaluators(self):
        req = _request()
        hybrid = _hybrid_with_stub(_stub_result_matching, os.devnull)
        result = hybrid.evaluate(req)
        self.assertEqual(result.evaluator_name, "hybrid-v1")
        self.assertEqual(result.evaluator_version, "1.0.0")


class TestDeterminism(unittest.TestCase):
    def test_same_request_produces_same_result(self):
        req = _request()
        hybrid = _hybrid_with_stub(_stub_result_disagreeing, os.devnull)
        r1 = hybrid.evaluate(req)
        r2 = hybrid.evaluate(req)
        self.assertEqual(r1.overall_score, r2.overall_score)
        self.assertEqual(r1.confidence, r2.confidence)


class TestRealEndToEndWiring(unittest.TestCase):
    """One integration-style test with the REAL TrainedEvaluator (tiny
    random backbone, same fixture as test_model_evaluator.py) to prove the
    actual wiring -- tokenization, forward pass, EvaluationResult
    construction -- works end-to-end without mocking anything."""

    def test_evaluate_with_real_trained_evaluator_does_not_raise(self):
        hybrid = HybridEvaluator(HeuristicEvaluator(), _real_trained_evaluator(), diagnostics_log_path=os.devnull)
        result = hybrid.evaluate(_request())
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.evaluator_name, "hybrid-v1")


if __name__ == "__main__":
    unittest.main()
