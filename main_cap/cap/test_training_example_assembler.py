"""Tests for training_example_assembler.py — Dataset Design RFC Section 4/7."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import ProvenanceSource, QualityTier, TrainingExample
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


def _output_for(recipe):
    evidence = []
    answer_parts = ["I worked on this directly."]
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept} in depth."))
            answer_parts.append(f"I used {target.concept}.")
    note = ""
    if recipe.is_contradictory:
        note = "Introduced one deliberate contradiction."
    return GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence, contradiction_note=note)


class TestAssembleTrainingExample(unittest.TestCase):
    def _assemble(self, tier=QualityTier.GOOD, concepts=("caching",)):
        recipe = sample_recipe("r1", _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING, concepts, tier)
        output = _output_for(recipe)
        return assemble_training_example(
            recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
            generator_model="fake-v1", generation_batch_id="batch_1",
        ), recipe, output

    def test_produces_valid_training_example(self):
        example, _, _ = self._assemble()
        self.assertIsInstance(example, TrainingExample)

    def test_provenance_is_synthetic(self):
        example, _, _ = self._assemble()
        self.assertEqual(example.provenance.source, ProvenanceSource.SYNTHETIC)
        self.assertEqual(example.provenance.collection_batch_id, "batch_1")

    def test_label_source_is_synthetic_ground_truth(self):
        example, _, _ = self._assemble()
        self.assertEqual(example.labels.label_source, "synthetic_ground_truth")

    def test_answer_text_propagates_from_output(self):
        example, _, output = self._assemble()
        self.assertEqual(example.inputs.answer_text, output.answer_text)

    def test_synthetic_meta_matches_recipe(self):
        example, recipe, _ = self._assemble()
        self.assertEqual(example.synthetic.intended_quality_tier, recipe.quality_tier)
        self.assertEqual(example.synthetic.generation_prompt_id, "promptbook")
        self.assertEqual(example.synthetic.diversity_seed, recipe.diversity_seed)

    def test_concept_labels_match_recipe_targets(self):
        example, recipe, _ = self._assemble()
        self.assertEqual({c.concept for c in example.labels.concept_labels}, {t.concept for t in recipe.concept_targets})
        for label in example.labels.concept_labels:
            target = next(t for t in recipe.concept_targets if t.concept == label.concept)
            self.assertEqual(label.status, target.status)

    def test_missing_reasoning_labels_only_for_present_targets(self):
        example, recipe, _ = self._assemble(tier=QualityTier.POOR, concepts=())
        present_categories = {t.category for t in recipe.reasoning_targets if t.present}
        self.assertEqual({l.category for l in example.labels.missing_reasoning_labels}, present_categories)

    def test_higher_tier_produces_higher_overall_score(self):
        excellent, _, _ = self._assemble(tier=QualityTier.EXCELLENT)
        poor, _, _ = self._assemble(tier=QualityTier.POOR)
        self.assertGreater(excellent.labels.overall_label.score, poor.labels.overall_label.score)

    def test_contradiction_label_reflects_recipe(self):
        example, recipe, _ = self._assemble(tier=QualityTier.CONTRADICTORY)
        self.assertTrue(example.labels.contradiction_label.contradiction_present)
        self.assertEqual(example.labels.contradiction_label.contradiction_type, recipe.contradiction_type)

    def test_non_contradictory_has_no_contradiction_label(self):
        example, _, _ = self._assemble(tier=QualityTier.GOOD)
        self.assertFalse(example.labels.contradiction_label.contradiction_present)

    def test_off_topic_has_no_concept_or_reasoning_labels(self):
        example, _, _ = self._assemble(tier=QualityTier.OFF_TOPIC, concepts=())
        self.assertEqual(example.labels.concept_labels, ())
        self.assertEqual(example.labels.missing_reasoning_labels, ())

    def test_dataset_version_unset_until_manifest_assembly(self):
        example, _, _ = self._assemble()
        self.assertIsNone(example.metadata.dataset_version)

    def test_privacy_defaults_no_pii_anonymized(self):
        example, _, _ = self._assemble()
        self.assertFalse(example.privacy.contains_pii)
        self.assertTrue(example.privacy.anonymized)


if __name__ == "__main__":
    unittest.main()
