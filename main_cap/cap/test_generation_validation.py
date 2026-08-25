"""Tests for generation_validation.py — Promptbook RFC Section 9."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from generation_validation import (
    check_concept_count,
    check_contradiction_consistency,
    check_hallucinated_technology,
    check_malformed_output,
    check_reasoning_mismatch,
    validate_generation,
)
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import QualityTier


def _spec(technologies=("Python", "Redis")):
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=technologies, concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _recipe(tier=QualityTier.GOOD, concepts=("caching",), technologies=("Python", "Redis")):
    return sample_recipe("r1", _spec(technologies), "Q?", ReasoningType.DEBUGGING, concepts, tier)


class TestMalformedOutput(unittest.TestCase):
    def test_empty_answer_rejected(self):
        self.assertTrue(check_malformed_output(GenerationOutput(answer_text="")))

    def test_too_short_answer_rejected(self):
        self.assertTrue(check_malformed_output(GenerationOutput(answer_text="Yes.")))

    def test_normal_answer_accepted(self):
        self.assertEqual(check_malformed_output(GenerationOutput(answer_text="I fixed a caching bug by adding TTLs.")), ())


class TestHallucinatedTechnology(unittest.TestCase):
    def test_ungrounded_technology_rejected(self):
        recipe = _recipe(technologies=("Python", "Redis"))
        output = GenerationOutput(answer_text="I actually used MongoDB for this instead of Redis.")
        self.assertTrue(check_hallucinated_technology(output, recipe))

    def test_grounded_technology_accepted(self):
        recipe = _recipe(technologies=("Python", "Redis"))
        output = GenerationOutput(answer_text="I used Redis for caching with a TTL policy.")
        self.assertEqual(check_hallucinated_technology(output, recipe), ())


class TestConceptCount(unittest.TestCase):
    def test_demonstrated_target_without_evidence_rejected(self):
        recipe = _recipe(tier=QualityTier.EXCELLENT, concepts=("caching",))
        demonstrated = any(t.status.value == "demonstrated" for t in recipe.concept_targets)
        if demonstrated:
            output = GenerationOutput(answer_text="I built this feature.", concept_evidence=[])
            self.assertTrue(check_concept_count(output, recipe))

    def test_omitted_target_with_evidence_rejected(self):
        recipe = _recipe(tier=QualityTier.POOR, concepts=("caching",))
        omitted = [t for t in recipe.concept_targets if t.status.value == "omitted"]
        if omitted:
            output = GenerationOutput(
                answer_text="I built this feature.",
                concept_evidence=[ConceptEvidenceEntry(concept="caching", evidence="Used caching extensively.")],
            )
            self.assertTrue(check_concept_count(output, recipe))

    def test_omitted_target_mentioned_in_answer_rejected(self):
        recipe = _recipe(tier=QualityTier.POOR, concepts=("caching",))
        omitted = [t for t in recipe.concept_targets if t.status.value == "omitted"]
        if omitted:
            output = GenerationOutput(answer_text="I did use caching for this part of the system.", concept_evidence=[])
            self.assertTrue(check_concept_count(output, recipe))

    def test_consistent_output_accepted(self):
        recipe = _recipe(tier=QualityTier.EXCELLENT, concepts=("caching",))
        target = recipe.concept_targets[0]
        if target.status.value in ("demonstrated", "superficial"):
            output = GenerationOutput(
                answer_text="I used caching heavily in this project.",
                concept_evidence=[ConceptEvidenceEntry(concept="caching", evidence="I used caching heavily.")],
            )
        else:
            output = GenerationOutput(answer_text="I focused on other parts of the system entirely.", concept_evidence=[])
        self.assertEqual(check_concept_count(output, recipe), ())


class TestReasoningMismatch(unittest.TestCase):
    def test_major_gap_contradicted_by_strong_markers_rejected(self):
        recipe = _recipe(tier=QualityTier.POOR, concepts=())
        major_present = [t for t in recipe.reasoning_targets if t.present and t.severity >= 0.67]
        if major_present:
            target = major_present[0]
            markers = {
                "tradeoff": "I compared this versus an alternative and chose it instead of the other option.",
                "architecture": "The architecture has three layers and each component is a separate service module.",
                "debugging": "I found a bug, it broke in production, and I fixed the root cause.",
                "testing": "I wrote unit tests and integration tests and verified everything.",
                "scalability": "This needed to scale under high load with concurrent throughput.",
                "ownership": "I designed this, I built this, and I was responsible for it.",
            }.get(target.category)
            if markers:
                output = GenerationOutput(answer_text=markers)
                self.assertTrue(check_reasoning_mismatch(output, recipe))

    def test_no_major_gaps_never_flags(self):
        recipe = _recipe(tier=QualityTier.EXCELLENT, concepts=())
        output = GenerationOutput(answer_text="I did some work on this project.")
        # EXCELLENT tier has low present-probability at high severity; if
        # nothing major is present, nothing should ever be flagged.
        major_present = [t for t in recipe.reasoning_targets if t.present and t.severity >= 0.67]
        if not major_present:
            self.assertEqual(check_reasoning_mismatch(output, recipe), ())


class TestContradictionConsistency(unittest.TestCase):
    def test_contradictory_recipe_requires_note(self):
        recipe = _recipe(tier=QualityTier.CONTRADICTORY)
        output = GenerationOutput(answer_text="A fluent, otherwise consistent answer.", contradiction_note="")
        self.assertTrue(check_contradiction_consistency(output, recipe))

    def test_non_contradictory_recipe_forbids_note(self):
        recipe = _recipe(tier=QualityTier.GOOD)
        output = GenerationOutput(answer_text="A normal answer.", contradiction_note="Something conflicts.")
        self.assertTrue(check_contradiction_consistency(output, recipe))

    def test_matching_state_accepted(self):
        recipe = _recipe(tier=QualityTier.GOOD)
        output = GenerationOutput(answer_text="A normal answer.", contradiction_note="")
        self.assertEqual(check_contradiction_consistency(output, recipe), ())


class TestValidateGeneration(unittest.TestCase):
    def test_off_topic_recipe_skips_concept_and_reasoning_checks(self):
        recipe = _recipe(tier=QualityTier.OFF_TOPIC, concepts=())
        output = GenerationOutput(answer_text="Let me tell you about something else entirely, a hobby of mine.")
        verdict = validate_generation(output, recipe)
        self.assertTrue(verdict.accepted)

    def test_malformed_output_fails_whole_verdict(self):
        recipe = _recipe(tier=QualityTier.GOOD, concepts=())
        verdict = validate_generation(GenerationOutput(answer_text=""), recipe)
        self.assertFalse(verdict.accepted)
        self.assertTrue(verdict.rejection_reasons)


if __name__ == "__main__":
    unittest.main()
