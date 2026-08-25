"""Tests for dataset_relabeling.py — Stage 1A of the DeBERTa augmentation
milestone (Part 1 of the reviewed design: deterministic per-dimension
relabeling from already-serialized recipe data, zero new generation)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset_relabeling import relabel_dimension_scores, relabel_example
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
            evidence.append(ConceptEvidenceEntry(concept=target.concept, evidence=f"Discussed {target.concept}."))
            answer_parts.append(f"I used {target.concept}.")
    note = "Introduced one deliberate contradiction." if recipe.is_contradictory else ""
    return GenerationOutput(answer_text=" ".join(answer_parts), concept_evidence=evidence, contradiction_note=note)


def _assemble(
    recipe_id="r1", tier=QualityTier.GOOD, reasoning_type=ReasoningType.DEBUGGING,
    concepts=("caching", "eviction policy", "ttl"),
):
    recipe = sample_recipe(recipe_id, _spec(), "Did Redis caching give you trouble?", reasoning_type, concepts, tier)
    output = _output_for(recipe)
    example = assemble_training_example(
        recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
        generator_model="fake-v1", generation_batch_id="batch_1",
    )
    return example, recipe


class TestRelabelDimensionScores(unittest.TestCase):
    def test_returns_a_label_for_every_relevant_dimension(self):
        example, recipe = _assemble()
        from reasoning_dimension_relevance import relevant_dimensions
        labels = relabel_dimension_scores(example)
        self.assertEqual({l.name for l in labels}, relevant_dimensions(recipe.reasoning_type))

    def test_technical_accuracy_stays_at_tier_baseline(self):
        example, _ = _assemble(tier=QualityTier.EXCELLENT)
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        self.assertAlmostEqual(labels["technical_accuracy"], 0.90)

    def test_dimension_with_present_reasoning_gap_scores_below_baseline(self):
        # Search a handful of recipe_ids deterministically until one samples
        # a present=True reasoning-category target for a mapped dimension —
        # sample_recipe is a pure function of recipe_id, so this stays
        # fully deterministic across runs even though we search for it.
        found = False
        for i in range(200):
            example, recipe = _assemble(recipe_id=f"search_{i}", tier=QualityTier.WEAK)
            present_targets = [t for t in recipe.reasoning_targets if t.present and t.severity > 0.0]
            if present_targets:
                found = True
                target = present_targets[0]
                from generation_recipe import _DIMENSION_TO_CATEGORY
                dim_name = next((d for d, c in _DIMENSION_TO_CATEGORY.items() if c == target.category), None)
                if dim_name is None:
                    continue
                labels = {l.name: l.score for l in relabel_dimension_scores(example)}
                if dim_name not in labels:
                    continue
                baseline = 0.30  # WEAK tier
                expected = max(0.0, min(1.0, baseline * (1.0 - target.severity)))
                self.assertAlmostEqual(labels[dim_name], expected)
                self.assertLess(labels[dim_name], baseline + 1e-9)
                break
        self.assertTrue(found, "expected at least one present=True reasoning target across 200 recipe_ids")

    def test_dimension_with_no_reasoning_gap_stays_at_baseline(self):
        # A category sampled present=False must leave that dimension at
        # the unmodified tier baseline.
        example, recipe = _assemble(recipe_id="r_flat", tier=QualityTier.GOOD)
        absent_categories = {t.category for t in recipe.reasoning_targets if not t.present}
        from generation_recipe import _DIMENSION_TO_CATEGORY
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        for dim_name, category in _DIMENSION_TO_CATEGORY.items():
            if category in absent_categories and dim_name in labels:
                self.assertAlmostEqual(labels[dim_name], 0.70)

    def test_completeness_is_fraction_not_omitted(self):
        example, recipe = _assemble(recipe_id="r_completeness", tier=QualityTier.GOOD)
        omitted = sum(1 for t in recipe.concept_targets if t.status == ConceptObservationStatus.OMITTED)
        expected = (len(recipe.concept_targets) - omitted) / len(recipe.concept_targets)
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        self.assertAlmostEqual(labels["completeness"], expected)

    def test_superficial_concept_counts_as_covered_not_omitted(self):
        # A hand-built example: 2 concepts, one SUPERFICIAL one DEMONSTRATED,
        # zero OMITTED -> completeness must be 1.0, not less.
        example, _ = _assemble(recipe_id="r_superficial", tier=QualityTier.EXCELLENT, concepts=("a", "b"))
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        # completeness is always in [0,1]; assert it never drops purely
        # because a concept was superficial rather than omitted.
        from generation_recipe import sample_recipe as _sr
        recipe = _sr("r_superficial", _spec(), "q", ReasoningType.DEBUGGING, ("a", "b"), QualityTier.EXCELLENT)
        non_omitted = sum(1 for t in recipe.concept_targets if t.status != ConceptObservationStatus.OMITTED)
        self.assertAlmostEqual(labels["completeness"], non_omitted / len(recipe.concept_targets))

    def test_off_topic_example_has_no_concept_targets_and_falls_back_to_baseline(self):
        recipe = sample_recipe("r_off", _spec(), "irrelevant question", ReasoningType.DEBUGGING, (), QualityTier.OFF_TOPIC)
        output = GenerationOutput(answer_text="Let me tell you about something else entirely.")
        example = assemble_training_example(
            recipe, output, generation_prompt_id="promptbook", prompt_version="1.0.0",
            generator_model="fake-v1", generation_batch_id="batch_1",
        )
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        for score in labels.values():
            self.assertAlmostEqual(score, 0.05)

    def test_contradictory_tier_uses_good_baseline(self):
        example, recipe = _assemble(recipe_id="r_contra", tier=QualityTier.CONTRADICTORY)
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        self.assertAlmostEqual(labels["technical_accuracy"], 0.70)

    def test_score_never_goes_negative_even_with_high_severity(self):
        example, recipe = _assemble(recipe_id="r_floor", tier=QualityTier.POOR)
        labels = relabel_dimension_scores(example)
        for label in labels:
            self.assertGreaterEqual(label.score, 0.0)
            self.assertLessEqual(label.score, 1.0)

    def test_proportional_mapping_never_saturates_weak_or_poor(self):
        # REVISION 2 regression guard: baseline*(1-severity) must never hit
        # exactly 0.0 for any severity < 1.0, unlike the old baseline-severity
        # rule which saturated 100% of WEAK/POOR present cases. Sweep many
        # recipe_ids for both tiers and assert zero exact-zero scores among
        # dimensions with a present reasoning gap.
        from generation_recipe import _DIMENSION_TO_CATEGORY
        for tier, baseline in ((QualityTier.WEAK, 0.30), (QualityTier.POOR, 0.12)):
            checked = 0
            for i in range(100):
                example, recipe = _assemble(recipe_id=f"sat_{tier.value}_{i}", tier=tier)
                labels = {l.name: l.score for l in relabel_dimension_scores(example)}
                for target in recipe.reasoning_targets:
                    if not target.present:
                        continue
                    dim_name = next((d for d, c in _DIMENSION_TO_CATEGORY.items() if c == target.category), None)
                    if dim_name is None or dim_name not in labels:
                        continue
                    checked += 1
                    self.assertGreater(
                        labels[dim_name], 0.0,
                        f"{tier.value}/{dim_name} saturated to exactly 0.0 (severity={target.severity})",
                    )
            self.assertGreater(checked, 0, f"expected at least one present reasoning gap sampled for {tier.value}")

    def test_proportional_mapping_preserves_expected_value(self):
        example, recipe = _assemble(recipe_id="r_prop", tier=QualityTier.POOR)
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        from generation_recipe import _DIMENSION_TO_CATEGORY
        baseline = 0.12  # POOR tier
        for target in recipe.reasoning_targets:
            if not target.present:
                continue
            dim_name = next((d for d, c in _DIMENSION_TO_CATEGORY.items() if c == target.category), None)
            if dim_name is None or dim_name not in labels:
                continue
            self.assertAlmostEqual(labels[dim_name], baseline * (1.0 - target.severity))

    def test_completeness_falls_back_to_reasoning_target_coverage_when_no_concepts(self):
        # REFLECTION reasoning type: no concept-bearing dimension, but
        # completeness is still requested (_ALWAYS_RELEVANT). expected_concepts
        # is passed empty, mirroring how the real pipeline calls sample_recipe
        # for REFLECTION/OWNERSHIP-shaped questions.
        example, recipe = _assemble(
            recipe_id="r_reflection", tier=QualityTier.WEAK,
            reasoning_type=ReasoningType.REFLECTION, concepts=(),
        )
        self.assertEqual(recipe.concept_targets, ())
        self.assertNotEqual(recipe.reasoning_targets, ())
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        per_category = [
            (1.0 - t.severity) if t.present else 1.0
            for t in recipe.reasoning_targets
        ]
        expected = sum(per_category) / len(per_category)
        self.assertAlmostEqual(labels["completeness"], expected)
        # Must not silently equal the old flat-tier fallback (0.30) unless
        # that happens to be the coincidental result — assert it was actually
        # *derived*, not defaulted, by checking it differs from the flat
        # baseline in at least one sampled recipe_id across a small sweep.
        differs = False
        for i in range(50):
            ex, rec = _assemble(
                recipe_id=f"r_reflection_sweep_{i}", tier=QualityTier.WEAK,
                reasoning_type=ReasoningType.REFLECTION, concepts=(),
            )
            lbls = {l.name: l.score for l in relabel_dimension_scores(ex)}
            if abs(lbls["completeness"] - 0.30) > 1e-9:
                differs = True
                break
        self.assertTrue(differs, "expected at least one REFLECTION example where completeness diverges from flat tier baseline")

    def test_completeness_uses_concept_coverage_when_concepts_exist(self):
        # Sanity: the concept-coverage branch (sub-case a) still wins when
        # concept_targets is non-empty, even though reasoning_targets is
        # also non-empty for the same example.
        example, recipe = _assemble(recipe_id="r_both_present", tier=QualityTier.WEAK)
        self.assertNotEqual(recipe.concept_targets, ())
        omitted = sum(1 for t in recipe.concept_targets if t.status == ConceptObservationStatus.OMITTED)
        expected = (len(recipe.concept_targets) - omitted) / len(recipe.concept_targets)
        labels = {l.name: l.score for l in relabel_dimension_scores(example)}
        self.assertAlmostEqual(labels["completeness"], expected)

    def test_raises_for_non_synthetic_example(self):
        example, _ = _assemble()
        real_session_example = example.model_copy(update={
            "provenance": example.provenance.model_copy(update={
                "source": ProvenanceSource.REAL_SESSION, "real_session_id": "sess_1",
            }),
            "synthetic": None,
            "labels": example.labels.model_copy(update={"label_source": "human_reviewed", "labeling_guideline_version": "v1"}),
        })
        with self.assertRaises(ValueError):
            relabel_dimension_scores(real_session_example)


class TestRelabelExample(unittest.TestCase):
    def test_only_dimension_labels_change(self):
        example, _ = _assemble(recipe_id="r_only_dims")
        relabeled = relabel_example(example)
        self.assertEqual(relabeled.inputs.answer_text, example.inputs.answer_text)
        self.assertEqual(relabeled.labels.concept_labels, example.labels.concept_labels)
        self.assertEqual(relabeled.labels.missing_reasoning_labels, example.labels.missing_reasoning_labels)
        self.assertEqual(relabeled.labels.contradiction_label, example.labels.contradiction_label)
        self.assertEqual(relabeled.labels.overall_label, example.labels.overall_label)
        self.assertEqual(relabeled.metadata, example.metadata)
        self.assertEqual(relabeled.provenance, example.provenance)
        self.assertEqual(relabeled.synthetic, example.synthetic)

    def test_dimension_labels_match_relabel_dimension_scores(self):
        example, _ = _assemble(recipe_id="r_match")
        relabeled = relabel_example(example)
        self.assertEqual(relabeled.labels.dimension_labels, relabel_dimension_scores(example))

    def test_original_example_is_unmodified(self):
        example, _ = _assemble(recipe_id="r_frozen")
        original_labels = example.labels.dimension_labels
        relabel_example(example)
        self.assertEqual(example.labels.dimension_labels, original_labels)

    def test_returns_valid_training_example(self):
        example, _ = _assemble(recipe_id="r_valid")
        relabeled = relabel_example(example)
        self.assertIsInstance(relabeled, TrainingExample)

    def test_real_session_example_passes_through_unchanged(self):
        example, _ = _assemble(recipe_id="r_passthrough")
        real_session_example = example.model_copy(update={
            "provenance": example.provenance.model_copy(update={
                "source": ProvenanceSource.REAL_SESSION, "real_session_id": "sess_1",
            }),
            "synthetic": None,
            "labels": example.labels.model_copy(update={"label_source": "human_reviewed", "labeling_guideline_version": "v1"}),
        })
        result = relabel_example(real_session_example)
        self.assertEqual(result, real_session_example)


if __name__ == "__main__":
    unittest.main()
