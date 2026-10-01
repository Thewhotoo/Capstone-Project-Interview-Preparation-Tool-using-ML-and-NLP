"""Tests for evaluation_result.py — Phase 3."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from evaluation_result import (
    ConceptObservation,
    ConceptObservationStatus,
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
    EvidenceLinkedClaim,
    MissingReasoningCategory,
    MissingReasoningItem,
)
from question_families import ReasoningType


def _dimension(**overrides):
    defaults = dict(name="technical_accuracy", raw_score=0.8, weight_used=0.5,
                     confidence=0.7, confidence_source=ConfidenceSource.HEURISTIC)
    defaults.update(overrides)
    return DimensionScore(**defaults)


def _result(**overrides):
    defaults = dict(
        result_id="eval_1", request_id="req_1", evaluation_timestamp="2026-01-01T00:00:00+00:00",
        specification_id="topic_0", source_id="My Project", category="project_overview",
        reasoning_type=ReasoningType.RECALL,
        evaluator_name="heuristic-v1", evaluator_version="1.0.0",
        dimensions=(_dimension(),),
        overall_score=0.8, grade="good", confidence=0.7,
        confidence_source=ConfidenceSource.HEURISTIC, confidence_rationale="Because reasons.",
        reasoning="technical_accuracy: 80%",
    )
    defaults.update(overrides)
    return EvaluationResult(**defaults)


class TestDimensionScore(unittest.TestCase):
    def test_construction(self):
        d = _dimension()
        self.assertEqual(d.name, "technical_accuracy")

    def test_raw_score_out_of_bounds_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _dimension(raw_score=1.5)
        with self.assertRaises(pydantic.ValidationError):
            _dimension(raw_score=-0.1)

    def test_negative_weight_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _dimension(weight_used=-1.0)

    def test_empty_name_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _dimension(name="")

    def test_frozen(self):
        d = _dimension()
        with self.assertRaises(pydantic.ValidationError):
            d.raw_score = 0.1

    def test_contributes_to_overall_defaults_true(self):
        self.assertTrue(_dimension().contributes_to_overall)


class TestEvidenceLinkedClaim(unittest.TestCase):
    def test_requires_evidence(self):
        with self.assertRaises(pydantic.ValidationError):
            EvidenceLinkedClaim(claim="Strong.", dimension="technical_accuracy", evidence="")

    def test_construction(self):
        c = EvidenceLinkedClaim(claim="Strong.", dimension="technical_accuracy", evidence="Scored 90%.")
        self.assertEqual(c.dimension, "technical_accuracy")


class TestMissingReasoningItem(unittest.TestCase):
    def test_construction(self):
        item = MissingReasoningItem(
            category=MissingReasoningCategory.TRADEOFF, explanation="no alternatives discussed",
            expected_because="the question asked about trade-offs", evidence="answer never compared options",
            severity=0.6,
        )
        self.assertEqual(item.category, "tradeoff")

    def test_severity_bounds(self):
        with self.assertRaises(pydantic.ValidationError):
            MissingReasoningItem(category="x", explanation="x", expected_because="x", evidence="x", severity=1.5)

    def test_open_category_accepts_new_values_without_schema_change(self):
        """Task requirement: extensible without a schema change — any
        non-empty string is a valid category."""
        item = MissingReasoningItem(
            category="a_brand_new_category_nobody_anticipated",
            explanation="x", expected_because="x", evidence="x", severity=0.5,
        )
        self.assertEqual(item.category, "a_brand_new_category_nobody_anticipated")


class TestConceptObservation(unittest.TestCase):
    """Expected Concepts revision (approved) — WHAT was/wasn't discussed,
    deliberately separate from MissingReasoningItem's HOW."""

    def test_demonstrated_requires_evidence(self):
        obs = ConceptObservation(
            concept="dependency injection", status=ConceptObservationStatus.DEMONSTRATED,
            evidence="I used FastAPI's Depends() to inject the database session.",
            confidence=0.8, confidence_source=ConfidenceSource.HEURISTIC,
        )
        self.assertEqual(obs.status, ConceptObservationStatus.DEMONSTRATED)

    def test_demonstrated_without_evidence_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            ConceptObservation(
                concept="dependency injection", status=ConceptObservationStatus.DEMONSTRATED,
                evidence=None, confidence=0.8, confidence_source=ConfidenceSource.HEURISTIC,
            )

    def test_superficial_without_evidence_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            ConceptObservation(
                concept="ASGI", status=ConceptObservationStatus.SUPERFICIAL,
                evidence="", confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
            )

    def test_omitted_requires_no_evidence(self):
        obs = ConceptObservation(
            concept="routing", status=ConceptObservationStatus.OMITTED,
            evidence=None, confidence=0.6, confidence_source=ConfidenceSource.HEURISTIC,
        )
        self.assertIsNone(obs.evidence)

    def test_omitted_with_evidence_rejected(self):
        """Never invented — nothing can be cited for something never
        mentioned."""
        with self.assertRaises(pydantic.ValidationError):
            ConceptObservation(
                concept="routing", status=ConceptObservationStatus.OMITTED,
                evidence="some evidence", confidence=0.6, confidence_source=ConfidenceSource.HEURISTIC,
            )

    def test_empty_concept_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            ConceptObservation(
                concept="", status=ConceptObservationStatus.OMITTED,
                confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
            )

    def test_frozen(self):
        obs = ConceptObservation(
            concept="routing", status=ConceptObservationStatus.OMITTED,
            confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
        )
        with self.assertRaises(pydantic.ValidationError):
            obs.status = ConceptObservationStatus.DEMONSTRATED

    def test_status_is_closed_enum_not_open_string(self):
        """Unlike MissingReasoningCategory/ConfidenceSource, this is a
        closed, fixed 3-state taxonomy."""
        with self.assertRaises(pydantic.ValidationError):
            ConceptObservation(
                concept="routing", status="not_a_real_status",
                confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
            )


class TestConceptCoverageOnResult(unittest.TestCase):
    def test_defaults_empty(self):
        self.assertEqual(_result().concept_coverage, ())

    def test_accepts_observations(self):
        obs = ConceptObservation(
            concept="routing", status=ConceptObservationStatus.OMITTED,
            confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC,
        )
        result = _result(concept_coverage=(obs,))
        self.assertEqual(result.concept_coverage, (obs,))

    def test_is_separate_from_missing_reasoning(self):
        """concept_coverage and missing_reasoning are structurally distinct
        fields — WHAT vs HOW."""
        result = _result()
        self.assertNotEqual(EvaluationResult.model_fields["concept_coverage"].annotation,
                             EvaluationResult.model_fields["missing_reasoning"].annotation)


class TestEvaluationResultConstruction(unittest.TestCase):
    def test_constructs_with_minimum_fields(self):
        result = _result()
        self.assertEqual(result.overall_score, 0.8)
        self.assertEqual(result.grade, "good")

    def test_schema_and_strategy_version_defaults(self):
        """schema_version bumped v1 -> v2 for the approved Expected Concepts
        revision; evaluation_strategy_version stays v1 — concept_coverage
        doesn't change the composite formula/dimension set/rubric, only
        adds a parallel explainability structure (RFC's explicit
        distinction between the two version axes)."""
        result = _result()
        self.assertEqual(result.schema_version, "v2")
        self.assertEqual(result.evaluation_strategy_version, "v1")

    def test_requires_at_least_one_dimension(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(dimensions=())

    def test_overall_score_bounds(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(overall_score=1.5)

    def test_no_model_answer_field_exists(self):
        """RFC Revision 2 Section 3: model_answer deliberately removed."""
        result = _result()
        self.assertFalse(hasattr(result, "model_answer"))

    def test_dimension_lookup_helper(self):
        result = _result()
        self.assertIsNotNone(result.dimension("technical_accuracy"))
        self.assertIsNone(result.dimension("nonexistent"))


class TestNoOpaqueScores(unittest.TestCase):
    """Goal 4: no opaque percentages — enforced at construction time."""

    def test_empty_reasoning_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(reasoning="")

    def test_empty_confidence_rationale_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(confidence_rationale="")

    def test_empty_confidence_source_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(confidence_source="")


class TestRecommendedAction(unittest.TestCase):
    def test_valid_actions_accepted(self):
        for action in ("probe_deeper", "clarify", "move_on", "skip"):
            _result(recommended_action=action)  # must not raise

    def test_invalid_action_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _result(recommended_action="do_something_invalid")

    def test_none_is_valid(self):
        result = _result(recommended_action=None)
        self.assertIsNone(result.recommended_action)


class TestImmutability(unittest.TestCase):
    def test_cannot_reassign_overall_score(self):
        result = _result()
        with self.assertRaises(pydantic.ValidationError):
            result.overall_score = 0.1

    def test_cannot_reassign_dimensions(self):
        result = _result()
        with self.assertRaises(pydantic.ValidationError):
            result.dimensions = ()


class TestSerialization(unittest.TestCase):
    def test_round_trip_json(self):
        result = _result()
        restored = EvaluationResult.model_validate_json(result.model_dump_json())
        self.assertEqual(result, restored)

    def test_round_trip_dict(self):
        result = _result()
        restored = EvaluationResult.model_validate(result.model_dump())
        self.assertEqual(result, restored)


if __name__ == "__main__":
    unittest.main()
