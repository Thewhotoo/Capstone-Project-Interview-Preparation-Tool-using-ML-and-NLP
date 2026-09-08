"""
Tests for the four-dimension migration (Phase 2): `model_dataset.py`'s
collation and `model_evaluator.py`'s inference path both now support the
canonical four dimensions (`evaluation_dimensions.CANONICAL_DIMENSIONS`) as
an explicit, additive opt-in via `dimension_names=CANONICAL_DIMENSION_KEYS`
-- the legacy 12-dimension scheme remains the untouched default everywhere,
covered by the existing `test_model_dataset.py` / `test_model_heads.py` /
`test_model_evaluator.py` suites (still passing unmodified). This file
covers ONLY the new canonical-scheme behavior, plus one end-to-end smoke
test using a real example from the 170-example curated pool.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from evaluation_dimensions import CANONICAL_DIMENSIONS
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from model_backbone import BackboneConfig, build_tiny_random_encoder, build_tokenizer
from model_dataset import CANONICAL_DIMENSION_KEYS, build_dataloaders, collate_fn
from model_evaluator import TrainedEvaluator
from model_heads import MultiTaskModel, compute_batch_loss, train_model
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from reasoning_dimension_relevance import ALL_DIMENSIONS
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
)
from training_experimentation import Checkpoint, DatasetSplit, ExperimentConfig, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=32)

# The exact expected canonical order per evaluation_dimensions.CANONICAL_DIMENSIONS.
_EXPECTED_ORDER = (
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
)


class TestCanonicalDimensionKeysConstant(unittest.TestCase):
    def test_canonical_dimension_keys_match_evaluation_dimensions_order(self):
        self.assertEqual(CANONICAL_DIMENSION_KEYS, _EXPECTED_ORDER)
        self.assertEqual(CANONICAL_DIMENSION_KEYS, tuple(d.value for d in CANONICAL_DIMENSIONS))

    def test_canonical_keys_disjoint_from_legacy_names(self):
        # The four canonical names must not collide with any legacy name --
        # collate_fn's use_legacy_relevance branch relies on this.
        self.assertFalse(set(CANONICAL_DIMENSION_KEYS) & set(ALL_DIMENSIONS))


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _canonical_example(example_id: str, scores=(0.8, 0.6, 0.9, 0.4)) -> TrainingExample:
    """A TrainingExample whose dimension_labels use the four CANONICAL
    names, in canonical order -- mirrors how `four_dim_dataset.
    build_four_dim_example` actually labels a real four-dimension example
    (`DimensionLabel(name=dim.value, score=...)` for each canonical dim)."""
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=example_id, created_at="2026-07-24T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION, collection_batch_id="b1", real_session_id="s1",
        ),
        inputs=TrainingExampleInputs(
            specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, answer_text="I worked through a cache invalidation bug.",
            expected_concepts=("caching",),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version="g1",
            dimension_labels=tuple(
                DimensionLabel(name=name, score=score) for name, score in zip(_EXPECTED_ORDER, scores)
            ),
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=sum(scores) / len(scores), grade="good", rationale="test"),
        ),
    )


# ── Task 5.1-5.4: dataset collation ──────────────────────────────────────────


class TestCollateFnCanonicalScheme(unittest.TestCase):
    def test_returns_exactly_four_dimensions(self):
        batch = [_canonical_example("a")]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertEqual(collated["dimension_targets"].shape, (1, 4))
        self.assertEqual(collated["dimension_mask"].shape, (1, 4))

    def test_dimension_order_is_exactly_canonical(self):
        # Distinct scores at each of the four positions, chosen so their
        # tiers are all different -> the column order is unambiguous.
        batch = [_canonical_example("a", scores=(0.10, 0.35, 0.65, 0.95))]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        targets = collated["dimension_targets"][0].tolist()
        # score_to_tier cutpoints: 0.10->0, 0.35->1, 0.65->3, 0.95->4
        self.assertEqual(targets, [0, 1, 3, 4])

    def test_all_targets_are_valid_ordinal_tiers(self):
        batch = [_canonical_example("a"), _canonical_example("b", scores=(0.0, 1.0, 0.5, 0.25))]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        for value in collated["dimension_targets"].flatten().tolist():
            self.assertIn(value, range(5))

    def test_mask_is_presence_only_not_reasoning_type_relevance(self):
        # DEBUGGING reasoning_type would exclude e.g. "resume_grounding" under
        # the LEGACY relevance table, but ALL four canonical dimensions must
        # be masked in (they apply to every question intent by design).
        batch = [_canonical_example("a")]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertTrue(torch.all(collated["dimension_mask"][0] == 1.0))

    def test_missing_label_is_masked_out(self):
        example = _canonical_example("a")
        # Drop the grounding_ownership label entirely.
        trimmed_labels = tuple(dl for dl in example.labels.dimension_labels if dl.name != "grounding_ownership")
        example = example.model_copy(update={
            "labels": example.labels.model_copy(update={"dimension_labels": trimmed_labels}),
        })
        collated = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        ground_index = CANONICAL_DIMENSION_KEYS.index("grounding_ownership")
        self.assertEqual(collated["dimension_mask"][0, ground_index].item(), 0.0)

    def test_legacy_default_is_completely_unaffected(self):
        # No dimension_names passed -> exactly today's legacy shape/behavior.
        from test_model_dataset import _example as legacy_example  # reuse the existing fixture
        batch = [legacy_example("a")]
        collated = collate_fn(batch, _TOKENIZER, _BACKBONE_CONFIG)
        self.assertEqual(collated["dimension_targets"].shape, (1, len(ALL_DIMENSIONS)))

    def test_contextual_input_unchanged_between_legacy_and_canonical_calls(self):
        # The (question, answer) tokenization must not depend on which
        # dimension scheme is being collated -- Step 2's contextual input
        # builder is shared and untouched by this migration.
        example = _canonical_example("a")
        legacy_collated = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=ALL_DIMENSIONS)
        canonical_collated = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertEqual(
            legacy_collated["main_input_ids"].tolist(), canonical_collated["main_input_ids"].tolist(),
        )


class TestBuildDataloadersCanonicalScheme(unittest.TestCase):
    def test_dataloader_produces_four_dimension_batches(self):
        examples = tuple(_canonical_example(f"ex_{i}") for i in range(4))
        split = DatasetSplit(train_ids=tuple(f"ex_{i}" for i in range(4)), val_ids=(), test_ids=())
        train_loader, _, _ = build_dataloaders(
            examples, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=2,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        batch = next(iter(train_loader))
        self.assertEqual(batch["dimension_targets"].shape[1], 4)


# ── Task 5.5-5.6: model head integration ─────────────────────────────────────


class TestMultiTaskModelCanonicalScheme(unittest.TestCase):
    def _model(self) -> MultiTaskModel:
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        return MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)

    def test_creates_exactly_four_ordinal_heads(self):
        model = self._model()
        self.assertEqual(set(model.dimension_heads.heads.keys()), set(CANONICAL_DIMENSION_KEYS))
        self.assertEqual(len(model.dimension_heads.heads), 4)

    def test_forward_pass_produces_four_dimension_outputs(self):
        from model_backbone import tokenize_pair
        model = self._model()
        encoding = tokenize_pair(_TOKENIZER, "question", "answer", max_length=16)
        batch = _TOKENIZER.pad([encoding], return_tensors="pt")
        outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])
        self.assertEqual(set(outputs["dimension_logits"].keys()), set(CANONICAL_DIMENSION_KEYS))
        for name in CANONICAL_DIMENSION_KEYS:
            self.assertEqual(outputs["dimension_logits"][name].shape, (1, 4))  # 5 classes -> 4 CORAL thresholds

    def test_compute_batch_loss_runs_end_to_end_on_canonical_batch(self):
        model = self._model()
        batch = collate_fn(
            [_canonical_example("a"), _canonical_example("b")], _TOKENIZER, _BACKBONE_CONFIG,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        loss = compute_batch_loss(model, batch)
        self.assertTrue(torch.isfinite(loss))


class TestTrainModelCanonicalScheme(unittest.TestCase):
    def test_train_model_builds_a_four_head_model(self):
        examples = tuple(_canonical_example(f"ex_{i}") for i in range(4))
        split = DatasetSplit(train_ids=tuple(f"ex_{i}" for i in range(4)), val_ids=(), test_ids=())
        train_loader, val_loader, _ = build_dataloaders(
            examples, split, _TOKENIZER, _BACKBONE_CONFIG, batch_size=2,
            dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = train_model(
            train_loader, None, BackboneConfig(max_length=32), num_epochs=1,
            backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS,
        )
        self.assertEqual(set(model.dimension_names), set(CANONICAL_DIMENSION_KEYS))
        self.assertEqual(len(model.dimension_heads.heads), 4)


# ── Task 5.7-5.8: evaluator ───────────────────────────────────────────────────


def _checkpoint() -> Checkpoint:
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="four_dim_v1")
    return assemble_checkpoint(model_version="m_four_dim", experiment_config=config, artifact_uri="in-memory-test-artifact")


def _canonical_evaluator() -> TrainedEvaluator:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
    return TrainedEvaluator(_checkpoint(), model, _TOKENIZER, BackboneConfig(max_length=32))


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        request_id="r1", requested_at="2026-07-24T00:00:00+00:00",
        specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING,
        answer_text="I worked through a cache invalidation bug using Redis carefully.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=("caching",),
    )


class TestTrainedEvaluatorCanonicalScheme(unittest.TestCase):
    def test_declares_exactly_the_four_canonical_dimensions(self):
        evaluator = _canonical_evaluator()
        self.assertEqual(set(evaluator.declared_dimensions), set(CANONICAL_DIMENSION_KEYS))

    def test_evaluate_returns_exactly_four_canonical_dimension_results(self):
        evaluator = _canonical_evaluator()
        result = evaluator.evaluate(_request())
        self.assertEqual({d.name for d in result.dimensions}, set(CANONICAL_DIMENSION_KEYS))
        self.assertEqual(len(result.dimensions), 4)

    def test_no_legacy_dimension_names_appear_in_canonical_output(self):
        evaluator = _canonical_evaluator()
        result = evaluator.evaluate(_request())
        produced = {d.name for d in result.dimensions}
        self.assertFalse(produced & set(ALL_DIMENSIONS))

    def test_canonical_dimensions_all_contribute_and_weight_sums_to_one(self):
        evaluator = _canonical_evaluator()
        result = evaluator.evaluate(_request())
        contributing = [d for d in result.dimensions if d.contributes_to_overall]
        self.assertEqual(len(contributing), 4)
        self.assertAlmostEqual(sum(d.weight_used for d in contributing), 1.0, places=2)

    def test_legacy_evaluator_still_declares_legacy_dimensions_unchanged(self):
        # Same construction pattern as test_model_evaluator.py's own
        # _trained_evaluator() -- no dimension_names passed -> legacy model.
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone)
        evaluator = TrainedEvaluator(_checkpoint(), model, _TOKENIZER, BackboneConfig(max_length=32))
        self.assertEqual(set(evaluator.declared_dimensions), set(ALL_DIMENSIONS))
        result = evaluator.evaluate(_request())
        produced = {d.name for d in result.dimensions}
        self.assertTrue(produced.issubset(set(ALL_DIMENSIONS)))
        self.assertFalse(produced & set(CANONICAL_DIMENSION_KEYS))


# ── Task 5.9: a real 170-pool example through the full collate path ─────────


def _load_one_real_170_example() -> TrainingExample:
    """Loads exactly one record from the real, judged 20-example targeted
    coverage batch (part of the 170-example curated pool) and maps it into a
    genuine `TrainingExample` with canonical dimension_labels -- the same
    shape a real four-dimension dataset-assembly step would produce, without
    modifying the artifact itself (read-only)."""
    base = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.join(base, "artifacts", "gap_coverage_20", "gap20_v1.jsonl")
    judged_path = os.path.join(base, "artifacts", "gap_coverage_20", "gap20_v1_judged.jsonl")
    with open(raw_path, encoding="utf-8") as f:
        raw = json.loads(f.readline())
    with open(judged_path, encoding="utf-8") as f:
        judged = json.loads(f.readline())
    assert raw["example_id"] == judged["example_id"]

    spec = QuestionSpecification(
        id=raw["example_id"], category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=raw["title"],
        grounding=Grounding(project=ProjectGrounding(
            title=raw["title"], technologies=tuple(raw["technologies"]), concepts=(),
        )),
        source_type=SourceType.PROJECT, source_id=raw["source_id"], source_field="interview_seeds", reason="test",
    )
    dims = judged["judged_dimension_labels"]
    dimension_labels = tuple(
        DimensionLabel(name=name, score=dims[name] / 4.0) for name in _EXPECTED_ORDER
    )
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=raw["example_id"], created_at="2026-09-08T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION, collection_batch_id="gap_coverage_20", real_session_id="n/a",
        ),
        inputs=TrainingExampleInputs(
            specification=spec, question_text=raw["question"],
            reasoning_type=ReasoningType(raw["reasoning_type"]), answer_text=raw["answer"],
            expected_concepts=tuple(raw["expected_concepts"]),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version="gap20_manual_judge_v1",
            dimension_labels=dimension_labels,
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=sum(dims.values()) / (4 * 4.0), grade="good", rationale="test"),
        ),
    )


class TestRealDatasetExampleThroughCollatePath(unittest.TestCase):
    """dataset -> collate -> model input -> four-head output, using one
    genuine record from the 170-example curated pool (read-only)."""

    def test_real_example_collates_to_four_canonical_targets(self):
        example = _load_one_real_170_example()
        collated = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        self.assertEqual(collated["dimension_targets"].shape, (1, 4))
        self.assertTrue(torch.all(collated["dimension_mask"][0] == 1.0))
        for value in collated["dimension_targets"][0].tolist():
            self.assertIn(value, range(5))

    def test_real_example_produces_four_head_model_output(self):
        example = _load_one_real_170_example()
        collated = collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
        model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
        outputs = model.forward_dimensions(collated["main_input_ids"], collated["main_attention_mask"])
        self.assertEqual(set(outputs["dimension_logits"].keys()), set(CANONICAL_DIMENSION_KEYS))
        loss = compute_batch_loss(model, collated)
        self.assertTrue(torch.isfinite(loss))


if __name__ == "__main__":
    unittest.main()
