"""Tests for deterministic_rewrite.py — Experiment 4 (Rewrite Augmentation)
Track B: the API-free rewrite generator."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from deterministic_rewrite import apply_style_transform, generate_deterministic_rewrite
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
    tier=QualityTier.GOOD, concepts=("caching", "eviction policy"), recipe_id="r1",
    answer_text=None,
) -> TrainingExample:
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING, concepts, tier)
    if answer_text is not None:
        answer_parts = [answer_text]
    else:
        answer_parts = [
            "Basically, I actually worked on this directly and it was really useful."
        ]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept} carefully in the implementation.")
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


class TestApplyStyleTransform(unittest.TestCase):
    def test_concise_never_lengthens_text(self):
        answer = "Basically, I actually worked on this directly and it was really useful for the team."
        result = apply_style_transform(answer, "concise", "seed1")
        self.assertLessEqual(len(result.split()), len(answer.split()))

    def test_concise_removes_known_filler_words(self):
        answer = "Basically, I actually solved the bug and it was really tricky."
        result = apply_style_transform(answer, "concise", "seed1")
        self.assertNotIn("Basically", result)
        self.assertNotIn("actually", result.lower())
        self.assertNotIn("really", result.lower())

    def test_conversational_applies_contractions_and_starter(self):
        answer = "I do not think it is easy, but I am confident it will work."
        result = apply_style_transform(answer, "conversational", "seed1")
        self.assertIn("don't", result)
        self.assertTrue(result.startswith(("So, ", "Basically, ", "You know, ", "I mean, ")))

    def test_reflective_adds_opener_and_closer(self):
        answer = "I built the caching layer using Redis."
        result = apply_style_transform(answer, "reflective", "seed1")
        self.assertGreater(len(result), len(answer))
        self.assertTrue(result.startswith(("Looking back", "Reflecting on it", "In hindsight", "Thinking about it now")))

    def test_deterministic_same_input_same_output(self):
        answer = "I built the caching layer using Redis and it worked well."
        for style in ("concise", "conversational", "reflective"):
            a = apply_style_transform(answer, style, "same_seed")
            b = apply_style_transform(answer, style, "same_seed")
            self.assertEqual(a, b)

    def test_different_seeds_can_vary_connective_choice(self):
        answer = "I built the caching layer using Redis and it worked well."
        results = {apply_style_transform(answer, "reflective", f"seed_{i}") for i in range(20)}
        # Not every seed needs to differ, but across 20 seeds we should see
        # more than one opener chosen -- otherwise the "deterministic
        # variety" mechanism is dead code.
        self.assertGreater(len(results), 1)

    def test_unsupported_style_raises(self):
        with self.assertRaises(ValueError):
            apply_style_transform("Some answer text.", "verbose", "seed1")


class TestGenerateDeterministicRewrite(unittest.TestCase):
    def test_returns_generation_output_with_transformed_text(self):
        source = _source_example(concepts=("caching",))
        output = generate_deterministic_rewrite(source, "concise")
        self.assertIsInstance(output, GenerationOutput)
        self.assertTrue(output.answer_text.strip())

    def test_concept_evidence_carried_forward_from_source_labels(self):
        source = _source_example(concepts=("caching", "eviction policy"))
        output = generate_deterministic_rewrite(source, "conversational")
        source_concepts = {
            label.concept for label in source.labels.concept_labels
            if label.status != ConceptObservationStatus.OMITTED
        }
        output_concepts = {e.concept for e in output.concept_evidence}
        self.assertEqual(source_concepts, output_concepts)
        for entry in output.concept_evidence:
            matching = next(l for l in source.labels.concept_labels if l.concept == entry.concept)
            self.assertEqual(entry.evidence, matching.evidence)

    def test_omitted_concepts_never_get_evidence(self):
        source = _source_example(concepts=("caching", "eviction policy"))
        output = generate_deterministic_rewrite(source, "concise")
        omitted = {
            label.concept for label in source.labels.concept_labels
            if label.status == ConceptObservationStatus.OMITTED
        }
        output_concepts = {e.concept for e in output.concept_evidence}
        self.assertTrue(omitted.isdisjoint(output_concepts))


if __name__ == "__main__":
    unittest.main()
