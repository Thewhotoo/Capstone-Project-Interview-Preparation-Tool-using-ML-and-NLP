"""
Tests for concept_analysis.py — the shared lexical concept detector used by
BOTH the Improved Answer generator and the dashboard Concept Coverage metric.

Verifies:
  - concept_coverage_percent reflects lexically-expressed concepts,
  - it returns None when there is no concept pool (experience/certification),
  - missing_concepts and concept_coverage_percent agree (same detector),
  - inflected/partial expression counts (security<-secure, sensor<-sensors, ...).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concept_analysis import concept_coverage_percent, concept_pool, missing_concepts
from evaluation_result import (
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
    MissingReasoningItem,
)
from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_specification import (
    CertificationGrounding,
    ExperienceGrounding,
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


def _experience_question():
    spec = QuestionSpecification(
        id="e", category=QuestionCategory.EXPERIENCE, text_seed=None,
        grounding=Grounding(experience=ExperienceGrounding(role="Backend Engineer", company="Acme")),
        source_type=SourceType.EXPERIENCE, source_id="Backend Engineer", source_field="summary", reason="test",
    )
    return InterviewQuestion(
        question_text="q", transition_text="", specification=spec, family="responsibilities",
        reasoning_type=ReasoningType.OWNERSHIP, project_reference=None, is_followup=False, turn_number=1,
    )


def _certification_question():
    spec = QuestionSpecification(
        id="c", category=QuestionCategory.CERTIFICATION, text_seed=None,
        grounding=Grounding(certification=CertificationGrounding(name="AWS SAA")),
        source_type=SourceType.CERTIFICATION, source_id="AWS SAA", source_field="name", reason="test",
    )
    return InterviewQuestion(
        question_text="q", transition_text="", specification=spec, family="motivation",
        reasoning_type=ReasoningType.REFLECTION, project_reference=None, is_followup=False, turn_number=1,
    )


def _result():
    return EvaluationResult(
        result_id="e", request_id="r", evaluation_timestamp="2026-01-01T00:00:00+00:00",
        specification_id="t", source_id="s", category="project_deep_dive",
        reasoning_type=ReasoningType.EXPLANATION, evaluator_name="x", evaluator_version="1",
        dimensions=(DimensionScore(name="technical_accuracy", raw_score=0.5, weight_used=1.0,
                                   confidence=0.7, confidence_source=ConfidenceSource.MODEL),),
        overall_score=0.5, grade="adequate", confidence=0.7, confidence_source=ConfidenceSource.MODEL,
        confidence_rationale="e", reasoning="r", concept_coverage=(), missing_reasoning=(),
    )


class TestCoveragePercent(unittest.TestCase):
    def test_none_when_no_pool_experience(self):
        self.assertIsNone(concept_coverage_percent(_experience_question(), _result(), "I built APIs and led the team."))

    def test_none_when_no_pool_certification(self):
        self.assertIsNone(concept_coverage_percent(_certification_question(), _result(), "I studied cloud architecture."))

    def test_zero_when_nothing_expressed(self):
        q = _project_question()  # pool: Network Design, Network Security, Data Transmission
        pct = concept_coverage_percent(q, _result(), "I just plugged in some cables and it worked.")
        self.assertEqual(pct, 0.0)

    def test_full_when_all_expressed(self):
        q = _project_question()
        ans = "I focused on the network design, made security a priority, and encrypted all data transmission."
        self.assertEqual(concept_coverage_percent(q, _result(), ans), 100.0)

    def test_partial_via_inflections(self):
        # "designed" -> Network Design, "securely" -> Network Security, but no
        # data-transmission word -> 2/3 = 66.7%.
        q = _project_question()
        ans = "I designed the layout and made sure everything ran securely across the sites."
        self.assertEqual(concept_coverage_percent(q, _result(), ans), 66.7)

    def test_agrees_with_missing_concepts(self):
        # covered count from percent must equal pool minus missing.
        q = _project_question()
        ans = "I designed the layout and made sure everything ran securely across the sites."
        pool = concept_pool(q, _result())
        missing = missing_concepts(q, _result(), ans.lower(), limit=99)
        covered = len(pool) - len(missing)
        expected_pct = round(100.0 * covered / len(pool), 1)
        self.assertEqual(concept_coverage_percent(q, _result(), ans), expected_pct)


if __name__ == "__main__":
    unittest.main()
