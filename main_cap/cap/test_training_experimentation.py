"""
Tests for training_experimentation.py — the infrastructure-only Training &
Experimentation subsystem (experiment metadata, deterministic splitting,
checkpoint lineage, QWK benchmarking, promotion policy). Includes the
import-graph assertion enforcing this module's approved independence from
generation/conversation/planning modules and from evaluator_registry/
heuristic_evaluator/dataset_manifest (none of which this module needs).
"""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import training_experimentation as training_experimentation_module
from training_experimentation import (
    BenchmarkResult,
    Checkpoint,
    DatasetSplit,
    ExperimentConfig,
    PromotionDecision,
    PromotionPolicy,
    assemble_checkpoint,
    compute_qwk,
    decide_promotion,
    grade_to_ordinal,
    run_benchmark,
    split_dataset,
    split_dataset_by_group,
    supersede_checkpoint,
)
from evaluation_result import (
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
)
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
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


def _module_imports(module) -> set:
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestTrainingExperimentationStaysWithinItsOwnBoundary(unittest.TestCase):
    FORBIDDEN_MODULES = {
        "synthetic_generation_pipeline", "coverage_strategy",
        "generation_client", "generation_recipe", "generation_validation",
        "prompt_assembler", "prompt_controllers", "labeling_operations",
        "conversation_engine", "conversation_memory", "discussion_policy", "planner", "topic_pool",
        "discussion_engine", "evaluator_registry", "dataset_manifest", "heuristic_evaluator",
    }

    def test_never_imports_forbidden_modules(self):
        self.assertFalse(_module_imports(training_experimentation_module) & self.FORBIDDEN_MODULES)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _training_example(example_id: str, grade: str, score: float = 0.5) -> TrainingExample:
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=example_id, created_at="2026-07-24T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION, collection_batch_id="session_batch_1",
            real_session_id="session_1",
        ),
        inputs=TrainingExampleInputs(
            specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, answer_text="I worked through a cache invalidation bug.",
            expected_concepts=("caching",),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version="g1",
            dimension_labels=(DimensionLabel(name="depth", score=score),),
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=score, grade=grade, rationale="test"),
        ),
    )


class _FixedGradeEvaluator:
    """Deterministic Evaluator-protocol test double — always predicts
    `grade`, regardless of the request."""

    declared_dimensions = ("depth",)
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False

    def __init__(self, name: str, version: str, grade: str):
        self.name = name
        self.version = version
        self._grade = grade

    def evaluate(self, request) -> EvaluationResult:
        return EvaluationResult(
            result_id=f"result_{request.request_id}", request_id=request.request_id,
            evaluation_timestamp="2026-07-24T00:00:00+00:00",
            specification_id=request.specification.id, source_id=request.specification.source_id,
            category=request.specification.category.value, reasoning_type=request.reasoning_type,
            evaluator_name=self.name, evaluator_version=self.version,
            dimensions=(DimensionScore(
                name="depth", raw_score=0.5, weight_used=1.0, confidence=0.5,
                confidence_source=ConfidenceSource.HEURISTIC,
            ),),
            overall_score=0.5, grade=self._grade, confidence=0.5,
            confidence_source=ConfidenceSource.HEURISTIC, confidence_rationale="fixed test double",
            reasoning="fixed test double always predicts the same grade",
        )


class TestExperimentConfig(unittest.TestCase):
    def test_valid_config_constructs_with_default_split(self):
        config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=42, dataset_version="v1")
        self.assertEqual(config.split_ratios, (0.7, 0.15, 0.15))
        self.assertEqual(config.formulation, "ordinal_regression")

    def test_parameters_accept_mixed_value_types(self):
        config = ExperimentConfig(
            backbone_name="microsoft/deberta-v3-base", random_seed=42, dataset_version="v1",
            parameters={"learning_rate": 2e-5, "epochs": 3, "use_fp16": True, "notes": "baseline run"},
        )
        self.assertEqual(config.parameters["epochs"], 3)
        self.assertTrue(config.parameters["use_fp16"])

    def test_rejects_empty_backbone_name(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(backbone_name="  ", random_seed=42, dataset_version="v1")

    def test_rejects_split_ratios_not_summing_to_one(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(
                backbone_name="b", random_seed=1, dataset_version="v1", split_ratios=(0.5, 0.5, 0.5),
            )

    def test_rejects_negative_split_ratio(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(
                backbone_name="b", random_seed=1, dataset_version="v1", split_ratios=(1.1, -0.1, 0.0),
            )


class TestDatasetSplit(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            DatasetSplit()

    def test_rejects_overlap(self):
        with self.assertRaises(ValueError):
            DatasetSplit(train_ids=("a", "b"), val_ids=("b",), test_ids=())


class TestSplitDataset(unittest.TestCase):
    def _ids(self, n: int) -> tuple:
        return tuple(f"ex_{i}" for i in range(n))

    def test_deterministic_given_identical_inputs(self):
        ids = self._ids(50)
        split_a = split_dataset(ids, (0.7, 0.15, 0.15), seed="seed_1")
        split_b = split_dataset(ids, (0.7, 0.15, 0.15), seed="seed_1")
        self.assertEqual(split_a, split_b)

    def test_different_seed_can_change_split(self):
        ids = self._ids(50)
        split_a = split_dataset(ids, (0.7, 0.15, 0.15), seed="seed_1")
        split_b = split_dataset(ids, (0.7, 0.15, 0.15), seed="seed_2")
        self.assertNotEqual(split_a, split_b)

    def test_split_is_exhaustive_and_respects_ratios_approximately(self):
        ids = self._ids(100)
        split = split_dataset(ids, (0.7, 0.15, 0.15), seed="seed_x")
        self.assertEqual(len(split.train_ids), 70)
        self.assertEqual(len(split.val_ids), 15)
        self.assertEqual(len(split.test_ids), 15)
        self.assertEqual(set(split.train_ids) | set(split.val_ids) | set(split.test_ids), set(ids))

    def test_rejects_empty_example_ids(self):
        with self.assertRaises(ValueError):
            split_dataset((), (0.7, 0.15, 0.15), seed="seed_1")

    def test_rejects_duplicate_example_ids(self):
        with self.assertRaises(ValueError):
            split_dataset(("a", "a"), (0.7, 0.15, 0.15), seed="seed_1")

    def test_rejects_bad_ratios(self):
        with self.assertRaises(ValueError):
            split_dataset(self._ids(10), (0.5, 0.5, 0.5), seed="seed_1")


class TestSplitDatasetByGroup(unittest.TestCase):
    def _grouped_ids(self, n_groups: int, per_group: int) -> tuple[tuple, dict]:
        """`n_groups` groups of `per_group` examples each -- mirrors
        multiple TrainingExamples generated from the same specification at
        different quality tiers."""
        ids = []
        group_of = {}
        for g in range(n_groups):
            for i in range(per_group):
                example_id = f"group{g}_ex{i}"
                ids.append(example_id)
                group_of[example_id] = f"spec_{g}"
        return tuple(ids), group_of

    def test_never_splits_a_group_across_subsets(self):
        ids, group_of = self._grouped_ids(n_groups=20, per_group=5)
        split = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_1")
        train_groups = {group_of[i] for i in split.train_ids}
        val_groups = {group_of[i] for i in split.val_ids}
        test_groups = {group_of[i] for i in split.test_ids}
        # No group appears in more than one subset.
        self.assertEqual(train_groups & val_groups, set())
        self.assertEqual(train_groups & test_groups, set())
        self.assertEqual(val_groups & test_groups, set())
        # Every member of a group landed in the SAME subset as the rest of that group.
        for group_id in train_groups | val_groups | test_groups:
            members = {i for i in ids if group_of[i] == group_id}
            self.assertTrue(
                members <= set(split.train_ids) or members <= set(split.val_ids) or members <= set(split.test_ids)
            )

    def test_deterministic_given_identical_inputs(self):
        ids, group_of = self._grouped_ids(n_groups=10, per_group=3)
        split_a = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_1")
        split_b = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_1")
        self.assertEqual(split_a, split_b)

    def test_different_seed_can_change_split(self):
        ids, group_of = self._grouped_ids(n_groups=10, per_group=3)
        split_a = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_1")
        split_b = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_2")
        self.assertNotEqual(split_a, split_b)

    def test_split_is_exhaustive(self):
        ids, group_of = self._grouped_ids(n_groups=20, per_group=5)
        split = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_x")
        self.assertEqual(set(split.train_ids) | set(split.val_ids) | set(split.test_ids), set(ids))
        self.assertEqual(len(split.train_ids) + len(split.val_ids) + len(split.test_ids), len(ids))

    def test_single_example_groups_behaves_like_split_dataset_grouping(self):
        # When every group has exactly one member, group-level splitting
        # degenerates to (approximately) example-level splitting.
        ids, group_of = self._grouped_ids(n_groups=100, per_group=1)
        split = split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_x")
        self.assertEqual(len(split.train_ids), 70)
        self.assertEqual(len(split.val_ids), 15)
        self.assertEqual(len(split.test_ids), 15)

    def test_rejects_missing_group_of_entry(self):
        ids, group_of = self._grouped_ids(n_groups=5, per_group=2)
        del group_of["group0_ex0"]
        with self.assertRaises(ValueError):
            split_dataset_by_group(ids, group_of, (0.7, 0.15, 0.15), seed="seed_1")

    def test_rejects_empty_example_ids(self):
        with self.assertRaises(ValueError):
            split_dataset_by_group((), {}, (0.7, 0.15, 0.15), seed="seed_1")

    def test_rejects_duplicate_example_ids(self):
        with self.assertRaises(ValueError):
            split_dataset_by_group(("a", "a"), {"a": "g1"}, (0.7, 0.15, 0.15), seed="seed_1")

    def test_rejects_bad_ratios(self):
        ids, group_of = self._grouped_ids(n_groups=5, per_group=2)
        with self.assertRaises(ValueError):
            split_dataset_by_group(ids, group_of, (0.5, 0.5, 0.5), seed="seed_1")


class TestCheckpoint(unittest.TestCase):
    def _config(self, dataset_version="v1") -> ExperimentConfig:
        return ExperimentConfig(backbone_name="b", random_seed=1, dataset_version=dataset_version)

    def test_assemble_checkpoint_success(self):
        checkpoint = assemble_checkpoint(
            model_version="m1", experiment_config=self._config(), artifact_uri="s3://bucket/m1",
        )
        self.assertEqual(checkpoint.dataset_version, "v1")
        self.assertIsNone(checkpoint.superseded_by)

    def test_rejects_dataset_version_mismatch(self):
        with self.assertRaises(ValueError):
            Checkpoint(
                model_version="m1", created_at="2026-07-24T00:00:00+00:00",
                dataset_version="v2", experiment_config=self._config(dataset_version="v1"),
                artifact_uri="s3://bucket/m1",
            )

    def test_rejects_parent_equal_to_self(self):
        with self.assertRaises(ValueError):
            Checkpoint(
                model_version="m1", created_at="2026-07-24T00:00:00+00:00",
                dataset_version="v1", experiment_config=self._config(), artifact_uri="s3://bucket/m1",
                parent_model_version="m1",
            )

    def test_rejects_superseded_by_equal_to_self(self):
        with self.assertRaises(ValueError):
            Checkpoint(
                model_version="m1", created_at="2026-07-24T00:00:00+00:00",
                dataset_version="v1", experiment_config=self._config(), artifact_uri="s3://bucket/m1",
                superseded_by="m1",
            )


class TestSupersedeCheckpoint(unittest.TestCase):
    def _checkpoint(self) -> Checkpoint:
        config = ExperimentConfig(backbone_name="b", random_seed=1, dataset_version="v1")
        return assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="s3://bucket/m1")

    def test_returns_new_checkpoint_with_pointer_set(self):
        checkpoint = self._checkpoint()
        superseded = supersede_checkpoint(checkpoint, "m2")
        self.assertIsNone(checkpoint.superseded_by)
        self.assertEqual(superseded.superseded_by, "m2")
        self.assertEqual(superseded.model_version, "m1")

    def test_rejects_double_supersession(self):
        checkpoint = supersede_checkpoint(self._checkpoint(), "m2")
        with self.assertRaises(ValueError):
            supersede_checkpoint(checkpoint, "m3")

    def test_rejects_self_supersession(self):
        with self.assertRaises(ValueError):
            supersede_checkpoint(self._checkpoint(), "m1")


class TestGradeToOrdinal(unittest.TestCase):
    def test_ordinal_mapping(self):
        self.assertEqual(grade_to_ordinal("poor"), 0)
        self.assertEqual(grade_to_ordinal("weak"), 1)
        self.assertEqual(grade_to_ordinal("adequate"), 2)
        self.assertEqual(grade_to_ordinal("good"), 3)
        self.assertEqual(grade_to_ordinal("excellent"), 4)

    def test_rejects_off_topic_and_contradictory(self):
        with self.assertRaises(ValueError):
            grade_to_ordinal("off_topic")
        with self.assertRaises(ValueError):
            grade_to_ordinal("contradictory")

    def test_rejects_unrecognized_grade(self):
        with self.assertRaises(ValueError):
            grade_to_ordinal("superb")


class TestComputeQwk(unittest.TestCase):
    def test_perfect_agreement_is_one(self):
        y = (0, 1, 2, 3, 4, 2, 1)
        self.assertAlmostEqual(compute_qwk(y, y, 5), 1.0)

    def test_degenerate_single_class_is_one(self):
        y = (2, 2, 2, 2)
        self.assertAlmostEqual(compute_qwk(y, y, 5), 1.0)

    def test_disagreement_scores_lower_than_agreement(self):
        y_true = (0, 1, 2, 3, 4)
        y_pred_good = (0, 1, 2, 3, 4)
        y_pred_bad = (4, 3, 2, 1, 0)
        self.assertGreater(compute_qwk(y_true, y_pred_good, 5), compute_qwk(y_true, y_pred_bad, 5))

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            compute_qwk((0, 1), (0,), 5)

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            compute_qwk((), (), 5)

    def test_rejects_out_of_range_label(self):
        with self.assertRaises(ValueError):
            compute_qwk((0, 5), (0, 1), 5)


class TestRunBenchmark(unittest.TestCase):
    def test_candidate_and_baseline_scored_against_ground_truth(self):
        examples = (
            _training_example("ex1", "excellent"),
            _training_example("ex2", "good"),
            _training_example("ex3", "poor"),
        )
        perfect_candidate = _FixedGradeEvaluator("perfect", "1.0", grade="excellent")
        # not actually "perfect" against every label, but deterministic and
        # distinct from the always-wrong baseline below.
        wrong_baseline = _FixedGradeEvaluator("baseline", "1.0", grade="poor")

        result = run_benchmark(perfect_candidate, wrong_baseline, examples, dataset_version="v1")
        self.assertEqual(result.example_count, 3)
        self.assertEqual(result.candidate_evaluator_name, "perfect")
        self.assertEqual(result.baseline_evaluator_name, "baseline")
        self.assertTrue(-1.0 <= result.candidate_qwk <= 1.0)
        self.assertTrue(-1.0 <= result.baseline_qwk <= 1.0)

    def test_rejects_empty_examples(self):
        with self.assertRaises(ValueError):
            run_benchmark(
                _FixedGradeEvaluator("a", "1.0", "good"), _FixedGradeEvaluator("b", "1.0", "good"),
                (), dataset_version="v1",
            )


class TestDecidePromotion(unittest.TestCase):
    def _checkpoint(self, dataset_version="v1") -> Checkpoint:
        config = ExperimentConfig(backbone_name="b", random_seed=1, dataset_version=dataset_version)
        return assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="s3://bucket/m1")

    def _benchmark(self, candidate_qwk, baseline_qwk, dataset_version="v1") -> BenchmarkResult:
        return BenchmarkResult(
            benchmark_id="bench_1", created_at="2026-07-24T00:00:00+00:00", dataset_version=dataset_version,
            example_count=10, candidate_evaluator_name="candidate", candidate_evaluator_version="1.0",
            baseline_evaluator_name="baseline", baseline_evaluator_version="1.0",
            candidate_qwk=candidate_qwk, baseline_qwk=baseline_qwk,
        )

    def test_approves_when_candidate_meets_threshold(self):
        decision = decide_promotion(self._checkpoint(), self._benchmark(0.6, 0.5))
        self.assertTrue(decision.approved)

    def test_rejects_when_candidate_below_threshold(self):
        decision = decide_promotion(self._checkpoint(), self._benchmark(0.4, 0.5))
        self.assertFalse(decision.approved)

    def test_respects_minimum_qwk_improvement_policy(self):
        policy = PromotionPolicy(minimum_qwk_improvement=0.1)
        decision = decide_promotion(self._checkpoint(), self._benchmark(0.55, 0.5), policy=policy)
        self.assertFalse(decision.approved)  # 0.55 < 0.5 + 0.1

    def test_rejects_mismatched_dataset_version(self):
        with self.assertRaises(ValueError):
            decide_promotion(self._checkpoint(dataset_version="v1"), self._benchmark(0.6, 0.5, dataset_version="v2"))

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            PromotionPolicy(minimum_qwk_improvement=5.0)


if __name__ == "__main__":
    unittest.main()
