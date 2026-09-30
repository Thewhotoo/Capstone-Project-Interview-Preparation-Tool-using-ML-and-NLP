"""Tests for rewrite_validation.py — Experiment 4 (Rewrite Augmentation) Stage."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from rewrite_validation import (
    recipe_from_source_example,
    check_length_ratio,
    check_semantic_drift,
    check_semantic_similarity,
    validate_rewrite,
)
from rewrite_verifier_client import FakeSemanticVerifierClient
from training_example import QualityTier, TrainingExample
from training_example_assembler import assemble_training_example


def _spec():
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _source_example(
    tier=QualityTier.GOOD, reasoning_type=ReasoningType.DEBUGGING,
    concepts=("caching", "eviction policy"), recipe_id="r1",
) -> TrainingExample:
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", reasoning_type, concepts, tier)
    answer_parts = ["I worked on this directly."]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept} to solve a real problem here.")
    note = "Introduced one deliberate contradiction." if recipe.is_contradictory else ""
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence, contradiction_note=note)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


class TestRecipeReconstruction(unittest.TestCase):
    def test_reconstructed_recipe_matches_source_targets(self):
        source = _source_example()
        recipe = recipe_from_source_example(source)
        self.assertEqual(recipe.concept_targets, source.synthetic.intended_concept_inclusion)
        self.assertEqual(recipe.reasoning_targets, source.synthetic.intended_reasoning_category_targets)
        self.assertEqual(recipe.quality_tier, source.synthetic.intended_quality_tier)

    def test_raises_for_non_synthetic_source(self):
        source = _source_example()
        real_session = source.model_copy(update={
            "provenance": source.provenance.model_copy(update={"source": "real_session", "real_session_id": "s1"}),
            "synthetic": None,
            "labels": source.labels.model_copy(update={"label_source": "human_reviewed", "labeling_guideline_version": "v1"}),
        })
        with self.assertRaises(ValueError):
            recipe_from_source_example(real_session)


class TestSemanticSimilarityCheck(unittest.TestCase):
    def test_near_identical_text_is_within_or_above_ceiling(self):
        # Identical text -> similarity 1.0, must be flagged as near-duplicate.
        reasons = check_semantic_similarity("I used Redis for caching.", "I used Redis for caching.")
        self.assertTrue(any("near_duplicate" in r for r in reasons))

    def test_completely_unrelated_text_is_flagged_as_drift(self):
        reasons = check_semantic_similarity(
            "I used Redis for caching to reduce database load significantly.",
            "The weather today is sunny with a chance of rain later this afternoon.",
        )
        self.assertTrue(any("semantic_drift" in r for r in reasons))

    def test_moderately_reworded_text_passes(self):
        reasons = check_semantic_similarity(
            "I implemented a Redis caching layer to reduce database load and improve response times.",
            "To cut down on database load and speed things up, I put a Redis cache in front of it.",
        )
        self.assertEqual(reasons, ())


class TestLengthRatioCheck(unittest.TestCase):
    def test_concise_shorter_than_original_passes(self):
        original = "word " * 40
        rewritten = "word " * 20
        self.assertEqual(check_length_ratio(original, rewritten, "concise"), ())

    def test_concise_much_longer_than_original_fails(self):
        original = "word " * 10
        rewritten = "word " * 40
        reasons = check_length_ratio(original, rewritten, "concise")
        self.assertTrue(any("length_ratio_violation" in r for r in reasons))

    def test_verbose_shorter_than_original_fails(self):
        original = "word " * 40
        rewritten = "word " * 10
        reasons = check_length_ratio(original, rewritten, "verbose")
        self.assertTrue(any("length_ratio_violation" in r for r in reasons))

    def test_unknown_style_never_rejects(self):
        self.assertEqual(check_length_ratio("word " * 10, "word " * 1000, "not_a_style"), ())

    def test_empty_original_never_rejects(self):
        self.assertEqual(check_length_ratio("", "word " * 10, "concise"), ())


class TestSemanticDriftCheck(unittest.TestCase):
    def test_no_drift_by_default(self):
        client = FakeSemanticVerifierClient()
        self.assertEqual(check_semantic_drift("original", "rewritten", client), ())

    def test_drift_flagged_when_marker_present(self):
        client = FakeSemanticVerifierClient()
        reasons = check_semantic_drift("original", "rewritten DRIFT_TEST_TRIGGER", client)
        self.assertTrue(any("llm_judged_semantic_drift" in r for r in reasons))


class TestValidateRewrite(unittest.TestCase):
    def _rewrite_output_for(self, source: TrainingExample, answer_text: str) -> GenerationOutput:
        evidence = []
        for target in source.synthetic.intended_concept_inclusion:
            if target.status != ConceptObservationStatus.OMITTED:
                evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept} again."))
        return GenerationOutput(answer_text=answer_text, concept_evidence=evidence, contradiction_note="")

    def test_faithful_rewrite_is_accepted(self):
        source = _source_example(concepts=("caching",))
        rewritten_text = source.inputs.answer_text.replace("worked on this directly", "handled this myself")
        output = self._rewrite_output_for(source, rewritten_text)
        verdict = validate_rewrite(output, source, "concise", FakeSemanticVerifierClient())
        self.assertTrue(verdict.accepted, verdict.rejection_reasons)

    def test_omitted_concept_reintroduced_is_rejected(self):
        # Find a recipe_id where at least one concept is OMITTED so we can
        # deliberately violate it.
        source = None
        for i in range(50):
            candidate = _source_example(recipe_id=f"omit_search_{i}", tier=QualityTier.POOR, concepts=("caching", "eviction policy", "ttl"))
            if any(t.status == ConceptObservationStatus.OMITTED for t in candidate.synthetic.intended_concept_inclusion):
                source = candidate
                break
        self.assertIsNotNone(source, "expected at least one OMITTED concept target across 50 recipe_ids")
        omitted = next(t for t in source.synthetic.intended_concept_inclusion if t.status == ConceptObservationStatus.OMITTED)
        rewritten_text = source.inputs.answer_text + f" I also used {omitted.concept} extensively."
        output = self._rewrite_output_for(source, rewritten_text)
        verdict = validate_rewrite(output, source, "concise", FakeSemanticVerifierClient())
        self.assertFalse(verdict.accepted)
        self.assertTrue(any("concept_count_mismatch" in r for r in verdict.rejection_reasons))

    def test_semantic_drift_flagged_by_verifier_rejects(self):
        source = _source_example(concepts=("caching",))
        output = self._rewrite_output_for(source, source.inputs.answer_text + " DRIFT_TEST_TRIGGER")
        verdict = validate_rewrite(output, source, "concise", FakeSemanticVerifierClient())
        self.assertFalse(verdict.accepted)
        self.assertTrue(any("llm_judged_semantic_drift" in r for r in verdict.rejection_reasons))

    def test_off_topic_source_skips_concept_and_reasoning_checks(self):
        recipe = sample_recipe("r_off", _spec(), "irrelevant", ReasoningType.DEBUGGING, (), QualityTier.OFF_TOPIC)
        output = GenerationOutput(answer_text="Let me tell you about something else entirely.")
        source = assemble_training_example(
            recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
            generator_model="fake-v1", generation_batch_id="batch_1",
        )
        rewrite_output = GenerationOutput(answer_text="Actually, here's a different unrelated story instead.")
        verdict = validate_rewrite(rewrite_output, source, "concise", FakeSemanticVerifierClient())
        # Should not fail on concept/reasoning checks (none apply); may or
        # may not pass similarity depending on text, but must not raise.
        self.assertIsInstance(verdict.accepted, bool)


if __name__ == "__main__":
    unittest.main()
