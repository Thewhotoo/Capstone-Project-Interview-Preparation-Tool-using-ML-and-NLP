"""
Tests for concept_analysis.py.

`concept_coverage_percent` — the dashboard's Concept Coverage % — is
verified separately from the rest of the module (`concept_pool`,
`missing_concepts`, still lexical-overlap based, still used by the Improved
Answer feature): it must be derived DETERMINISTICALLY from
`EvaluationResult.concept_coverage`'s own per-concept statuses (the exact
list already shown to the user), never from an independent re-scan of the
answer text. Direct regression for a real production bug: the old
lexical-rescan implementation let the same all-"omitted" concept_coverage
array produce a different percentage (20%/40%/0%) on different turns.

Verifies:
  - 0/N demonstrated (all omitted) -> 0%,
  - N/N demonstrated (all covered) -> 100%,
  - a mixed demonstrated/superficial/omitted set -> the documented
    deterministic weighted percentage (demonstrated=1.0, superficial=0.5,
    omitted=0.0),
  - an empty concept_coverage (no pool for this turn, e.g.
    experience/certification) -> None, never 0%,
  - the percentage and the visible per-concept breakdown can never disagree
    (recomputing by hand from the same list always matches).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concept_analysis import concept_coverage_percent, missing_concepts
from evaluation_result import (
    ConceptObservation,
    ConceptObservationStatus,
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
)
from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _project_question(title="Military Communication Network", technologies=("Cisco Packet Tracer",),
                      concepts=("Network Design", "Network Security", "Data Transmission")):
    spec = QuestionSpecification(
        id="t", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=None,
        grounding=Grounding(project=ProjectGrounding(
            title=title, technologies=tuple(technologies), concepts=tuple(concepts))),
        source_type=SourceType.PROJECT, source_id=title, source_field="summary", reason="test",
    )
    return InterviewQuestion(
        question_text="q", transition_text="", specification=spec, family="architecture",
        reasoning_type=ReasoningType.EXPLANATION, project_reference=title, is_followup=False, turn_number=1,
    )


def _result(concept_coverage: tuple = ()):
    return EvaluationResult(
        result_id="e", request_id="r", evaluation_timestamp="2026-01-01T00:00:00+00:00",
        specification_id="t", source_id="s", category="project_deep_dive",
        reasoning_type=ReasoningType.EXPLANATION, evaluator_name="x", evaluator_version="1",
        dimensions=(DimensionScore(name="technical_accuracy", raw_score=0.5, weight_used=1.0,
                                   confidence=0.7, confidence_source=ConfidenceSource.MODEL),),
        overall_score=0.5, grade="adequate", confidence=0.7, confidence_source=ConfidenceSource.MODEL,
        confidence_rationale="e", reasoning="r", concept_coverage=concept_coverage, missing_reasoning=(),
    )


def _obs(concept: str, status: ConceptObservationStatus, evidence=None) -> ConceptObservation:
    return ConceptObservation(
        concept=concept, status=status,
        evidence=evidence if status != ConceptObservationStatus.OMITTED else None,
        confidence=0.8, confidence_source=ConfidenceSource.HEURISTIC,
    )


class TestConceptPoolAndMissingConcepts(unittest.TestCase):
    """`concept_pool`/`missing_concepts` (the lexical-overlap detector) are
    unchanged by the `concept_coverage_percent` fix below -- still used by
    `strong_answer.build_improved_answer`. Kept covered here."""

    def test_zero_when_nothing_expressed(self):
        q = _project_question()  # pool: Network Design, Network Security, Data Transmission
        missing = missing_concepts(q, _result(), "I just plugged in some cables and it worked.", limit=99)
        self.assertEqual(len(missing), 3)

    def test_full_when_all_expressed(self):
        q = _project_question()
        ans = "I focused on the network design, made security a priority, and encrypted all data transmission."
        self.assertEqual(missing_concepts(q, _result(), ans, limit=99), [])

    def test_partial_via_inflections(self):
        # "designed" -> Network Design, "securely" -> Network Security, but no
        # data-transmission word -> 1 concept still missing.
        q = _project_question()
        ans = "I designed the layout and made sure everything ran securely across the sites."
        missing = missing_concepts(q, _result(), ans, limit=99)
        self.assertEqual(missing, ["Data Transmission"])


class TestCoveragePercent(unittest.TestCase):
    """`concept_coverage_percent` -- the dashboard's Concept Coverage % --
    must be a deterministic function of `result.concept_coverage`'s own
    per-concept statuses. Direct regression for the production bug: the
    same all-omitted list used to produce different percentages on
    different turns because the old implementation ignored this list
    entirely and re-scanned the raw answer text with a separate detector."""

    def test_none_when_pool_is_empty(self):
        # No concept pool at all for this turn (e.g. experience/
        # certification) -- must be None, never a fabricated 0%.
        self.assertIsNone(concept_coverage_percent(_result(concept_coverage=())))

    def test_zero_when_all_omitted(self):
        result = _result(concept_coverage=(
            _obs("ASGI", ConceptObservationStatus.OMITTED),
            _obs("routing", ConceptObservationStatus.OMITTED),
            _obs("modularity", ConceptObservationStatus.OMITTED),
            _obs("dependency injection", ConceptObservationStatus.OMITTED),
            _obs("async request handling", ConceptObservationStatus.OMITTED),
        ))
        self.assertEqual(concept_coverage_percent(result), 0.0)

    def test_full_when_all_demonstrated(self):
        result = _result(concept_coverage=(
            _obs("ASGI", ConceptObservationStatus.DEMONSTRATED, "used ASGI throughout"),
            _obs("routing", ConceptObservationStatus.DEMONSTRATED, "defined explicit routes"),
        ))
        self.assertEqual(concept_coverage_percent(result), 100.0)

    def test_mixed_statuses_produce_documented_deterministic_percentage(self):
        # demonstrated=1.0, superficial=0.5, omitted=0.0 -- (1.0+0.5+0.0)/3 = 50.0%.
        result = _result(concept_coverage=(
            _obs("ASGI", ConceptObservationStatus.DEMONSTRATED, "used ASGI throughout"),
            _obs("routing", ConceptObservationStatus.SUPERFICIAL, "related terminology found"),
            _obs("modularity", ConceptObservationStatus.OMITTED),
        ))
        self.assertEqual(concept_coverage_percent(result), 50.0)

    def test_percentage_always_matches_hand_computed_breakdown(self):
        # The percentage must always be reproducible by hand from the exact
        # statuses in the visible concept_coverage list -- never a separate
        # number. Same all-omitted list, checked twice (equivalent to
        # different turns), must always produce the same percentage.
        statuses = (
            _obs("ASGI", ConceptObservationStatus.OMITTED),
            _obs("routing", ConceptObservationStatus.OMITTED),
            _obs("modularity", ConceptObservationStatus.OMITTED),
            _obs("dependency injection", ConceptObservationStatus.OMITTED),
            _obs("async request handling", ConceptObservationStatus.OMITTED),
        )
        credit = {ConceptObservationStatus.DEMONSTRATED: 1.0, ConceptObservationStatus.SUPERFICIAL: 0.5,
                  ConceptObservationStatus.OMITTED: 0.0}
        expected = round(100.0 * sum(credit[o.status] for o in statuses) / len(statuses), 1)
        self.assertEqual(concept_coverage_percent(_result(concept_coverage=statuses)), expected)
        self.assertEqual(concept_coverage_percent(_result(concept_coverage=statuses)), expected)


if __name__ == "__main__":
    unittest.main()
