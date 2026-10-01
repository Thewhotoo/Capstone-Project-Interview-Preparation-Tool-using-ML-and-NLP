"""
Tests for `heuristic_diagnostics.py` — the four-canonical-dimension
diagnostic engine (V3 Single-Overall-Score Architecture).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_dimensions import CANONICAL_DIMENSIONS, LEGACY_DIMENSION_MAP
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS, HeuristicDiagnosticsEngine, _LEGACY_GROUP_BY_CANONICAL
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType

_ENGINE = HeuristicDiagnosticsEngine()


def _request(answer_text: str, question_text: str = "How did you scale the pipeline?") -> EvaluationRequest:
    spec = QuestionSpecification(
        id="spec1", category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(
            title="CloudScaler", summary="An autoscaling platform.",
            technologies=("Kubernetes", "Redis"), concepts=("autoscaling",),
        )),
        source_type=SourceType.PROJECT, source_id="proj1", source_field="projects", reason="test",
    )
    return EvaluationRequest(
        request_id="req1", requested_at="2026-01-01T00:00:00+00:00",
        specification=spec, question_text=question_text, reasoning_type=ReasoningType.EXPLANATION,
        answer_text=answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


class TestExactlyFourCanonicalDimensions(unittest.TestCase):
    """Test 4: heuristic engine returns exactly four canonical dimensions."""

    def test_returns_exactly_four_dimensions(self):
        dimensions = _ENGINE.compute(_request("I designed and built a Redis-based caching layer."))
        self.assertEqual(len(dimensions), 4)

    def test_dimension_names_are_exactly_the_canonical_set_in_order(self):
        dimensions = _ENGINE.compute(_request("A reasonably detailed answer about the architecture."))
        self.assertEqual(tuple(d.name for d in dimensions), CANONICAL_DIMENSION_KEYS)
        self.assertEqual(set(d.name for d in dimensions), {d.value for d in CANONICAL_DIMENSIONS})

    def test_never_produces_a_legacy_dimension_name(self):
        legacy_names = {name for names in LEGACY_DIMENSION_MAP.values() for name in names}
        dimensions = _ENGINE.compute(_request("Some answer."))
        produced = {d.name for d in dimensions}
        self.assertEqual(produced & legacy_names, set())

    def test_grouping_matches_legacy_dimension_map_exactly(self):
        # The grouping used to aggregate legacy signals into each canonical
        # dimension must be EXACTLY evaluation_dimensions.LEGACY_DIMENSION_MAP
        # -- never a separately-invented mapping that could drift.
        for dim in CANONICAL_DIMENSIONS:
            self.assertEqual(_LEGACY_GROUP_BY_CANONICAL[dim.value], LEGACY_DIMENSION_MAP[dim])

    def test_every_dimension_score_is_a_valid_dimension_score(self):
        dimensions = _ENGINE.compute(_request("We used caching to reduce database load significantly."))
        for d in dimensions:
            self.assertGreaterEqual(d.raw_score, 0.0)
            self.assertLessEqual(d.raw_score, 1.0)
            self.assertGreaterEqual(d.confidence, 0.0)
            self.assertLessEqual(d.confidence, 1.0)


class TestHeuristicIndependentOfDeBERTa(unittest.TestCase):
    """Test 5: heuristic scores are independent of the DeBERTa overall
    prediction — this engine takes only an EvaluationRequest, never a
    model/logits/prediction, and is fully deterministic given that request
    alone."""

    def test_compute_signature_has_no_model_or_score_dependency(self):
        import inspect
        sig = inspect.signature(HeuristicDiagnosticsEngine.compute)
        params = list(sig.parameters)
        self.assertEqual(params, ["self", "request"])

    def test_module_never_imports_overall_score_model_or_torch(self):
        import ast
        import inspect
        import heuristic_diagnostics
        source = inspect.getsource(heuristic_diagnostics)
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        self.assertNotIn("torch", imported_modules)
        self.assertNotIn("overall_score_model", imported_modules)
        self.assertNotIn("model_heads", imported_modules)
        self.assertNotIn("model_backbone", imported_modules)

    def test_same_request_always_yields_identical_scores(self):
        request = _request("I designed and built the ingestion pipeline using Kafka.")
        first = _ENGINE.compute(request)
        second = _ENGINE.compute(request)
        self.assertEqual(
            [(d.name, d.raw_score) for d in first],
            [(d.name, d.raw_score) for d in second],
        )

    def test_all_four_dimensions_have_contributes_to_overall_false(self):
        # Diagnostic-only guarantee -- must never be summed into any
        # overall_score by a downstream consumer.
        dimensions = _ENGINE.compute(_request("Some answer with reasonable detail about the system."))
        for d in dimensions:
            self.assertFalse(d.contributes_to_overall)


class TestClaims(unittest.TestCase):
    def test_claims_reference_only_canonical_dimension_names(self):
        dimensions = _ENGINE.compute(_request("I designed the caching layer to reduce latency significantly."))
        strengths, weaknesses = _ENGINE.claims(dimensions)
        for claim in (*strengths, *weaknesses):
            self.assertIn(claim.dimension, CANONICAL_DIMENSION_KEYS)

    def test_claims_are_never_empty(self):
        dimensions = _ENGINE.compute(_request("ok"))
        strengths, weaknesses = _ENGINE.claims(dimensions)
        self.assertGreater(len(strengths), 0)
        self.assertGreater(len(weaknesses), 0)


if __name__ == "__main__":
    unittest.main()
