"""Tests for rewrite_assembler.py — Experiment 4 (Rewrite Augmentation) Stage."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from generation_recipe import sample_recipe
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from rewrite_assembler import assemble_rewritten_example
from rewrite_prompt_assembler import REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION
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


def _source_example(tier=QualityTier.GOOD, concepts=("caching", "eviction policy"), recipe_id="r1") -> TrainingExample:
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", ReasoningType.DEBUGGING, concepts, tier)
    answer_parts = ["I worked on this directly."]
    evidence = []
    for target in recipe.concept_targets:
        if target.status != ConceptObservationStatus.OMITTED:
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept}.")
    note = "Introduced one deliberate contradiction." if recipe.is_contradictory else ""
    output = GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence, contradiction_note=note)
    return assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )


def _rewrite_output_for(source: TrainingExample, text: str) -> GenerationOutput:
    evidence = [
        ConceptEvidenceEntry(concept=t.concept, evidence=f"Discussed {t.concept} again, differently.")
        for t in source.synthetic.intended_concept_inclusion
        if t.status != ConceptObservationStatus.OMITTED
    ]
    return GenerationOutput(answer_text=text, concept_evidence=evidence, contradiction_note="")


class TestAssembleRewrittenExample(unittest.TestCase):
    def test_dimension_labels_copied_verbatim(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.labels.dimension_labels, source.labels.dimension_labels)

    def test_missing_reasoning_labels_copied_verbatim(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.labels.missing_reasoning_labels, source.labels.missing_reasoning_labels)

    def test_overall_label_copied_verbatim(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.labels.overall_label, source.labels.overall_label)

    def test_answer_text_is_the_rewrite_not_the_source(self):
        source = _source_example()
        output = _rewrite_output_for(source, "A totally differently phrased answer.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.inputs.answer_text, "A totally differently phrased answer.")
        self.assertNotEqual(rewrite.inputs.answer_text, source.inputs.answer_text)

    def test_provenance_fields_set_correctly(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "reflective", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.synthetic.rewritten_from_example_id, source.metadata.example_id)
        self.assertEqual(rewrite.synthetic.rewrite_style, "reflective")
        self.assertEqual(rewrite.synthetic.generation_prompt_id, REWRITE_GENERATION_PROMPT_ID)
        self.assertEqual(rewrite.synthetic.prompt_version, REWRITE_PROMPT_VERSION)
        self.assertEqual(rewrite.provenance.source, ProvenanceSource.SYNTHETIC)
        self.assertEqual(rewrite.provenance.collection_batch_id, "rewrite_batch_1")

    def test_new_example_id_distinct_from_source(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertNotEqual(rewrite.metadata.example_id, source.metadata.example_id)
        self.assertTrue(rewrite.metadata.example_id.startswith("rewrite_"))

    def test_specification_question_reasoning_type_expected_concepts_preserved(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.inputs.specification, source.inputs.specification)
        self.assertEqual(rewrite.inputs.question_text, source.inputs.question_text)
        self.assertEqual(rewrite.inputs.reasoning_type, source.inputs.reasoning_type)
        self.assertEqual(rewrite.inputs.expected_concepts, source.inputs.expected_concepts)

    def test_concept_labels_rebuilt_from_rewrite_evidence(self):
        source = _source_example(concepts=("caching",))
        custom_evidence = [ConceptEvidenceEntry(concept="caching", evidence="A brand new explanation of caching.")]
        output = GenerationOutput(answer_text="I used caching differently this time.", concept_evidence=custom_evidence)
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        caching_label = next(l for l in rewrite.labels.concept_labels if l.concept == "caching")
        self.assertEqual(caching_label.evidence, "A brand new explanation of caching.")

    def test_raises_for_non_synthetic_source(self):
        source = _source_example()
        real_session = source.model_copy(update={
            "provenance": source.provenance.model_copy(update={"source": "real_session", "real_session_id": "s1"}),
            "synthetic": None,
            "labels": source.labels.model_copy(update={"label_source": "human_reviewed", "labeling_guideline_version": "v1"}),
        })
        output = _rewrite_output_for(source, "irrelevant")
        with self.assertRaises(ValueError):
            assemble_rewritten_example(
                real_session, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
                "fake-v1", "rewrite_batch_1",
            )

    def test_privacy_copied_verbatim(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertEqual(rewrite.privacy, source.privacy)

    def test_returns_valid_training_example(self):
        source = _source_example()
        output = _rewrite_output_for(source, "I handled this myself directly.")
        rewrite = assemble_rewritten_example(
            source, output, "concise", REWRITE_GENERATION_PROMPT_ID, REWRITE_PROMPT_VERSION,
            "fake-v1", "rewrite_batch_1",
        )
        self.assertIsInstance(rewrite, TrainingExample)


if __name__ == "__main__":
    unittest.main()
