"""
Tests for dataset_manifest.py — Dataset Manifest RFC (DatasetManifest +
ReviewEvent as one cohesive subsystem). Includes the import-graph assertion
enforcing this module's approved independence from every production
generation/evaluation/conversation/planning module.
"""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset_manifest import (
    AlreadyVersionedError,
    DatasetManifest,
    ReviewEvent,
    ReviewEventLog,
    ReviewEventType,
    ReviewSummary,
    assemble_manifest,
    supersede,
)
import dataset_manifest as dataset_manifest_module
from generation_client import FakeGenerationClient
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from synthetic_generation_pipeline import generate_training_example
from training_example import QualityTier, TrainingExample


def _module_imports(module) -> set:
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestManifestStaysWithinItsOwnBoundary(unittest.TestCase):
    FORBIDDEN_MODULES = {
        "synthetic_generation_pipeline", "coverage_strategy",
        "generation_client", "generation_recipe", "generation_validation",
        "prompt_assembler", "prompt_controllers",
        "evaluator", "evaluator_registry", "heuristic_evaluator", "evaluation_engine",
        "conversation_engine", "conversation_memory", "discussion_policy", "planner", "topic_pool",
    }

    def test_dataset_manifest_never_imports_generation_or_production_modules(self):
        self.assertFalse(_module_imports(dataset_manifest_module) & self.FORBIDDEN_MODULES)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _make_example(recipe_id: str, quality_tier: QualityTier = QualityTier.GOOD) -> TrainingExample:
    outcome = generate_training_example(
        recipe_id=recipe_id, specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
        quality_tier=quality_tier, client=FakeGenerationClient(), generation_batch_id="batch_1",
    )
    return outcome.example


class TestReviewEvent(unittest.TestCase):
    def _event(self, **overrides) -> ReviewEvent:
        fields = dict(
            event_id="ev_1", example_id="ex_1", event_type=ReviewEventType.APPROVED,
            reviewer_id="reviewer_1", created_at="2026-07-24T00:00:00+00:00",
            rationale="Meets the rubric.",
        )
        fields.update(overrides)
        return ReviewEvent(**fields)

    def test_valid_event_constructs(self):
        self._event()  # must not raise

    def test_rejects_empty_rationale(self):
        with self.assertRaises(ValueError):
            self._event(rationale="")

    def test_rejects_empty_event_type(self):
        with self.assertRaises(ValueError):
            self._event(event_type="")

    def test_event_type_is_an_open_string_not_an_enum(self):
        # Any non-empty string is accepted -- no closed vocabulary enforced.
        self._event(event_type="a_future_labeling_ops_action_not_yet_named")


class TestReviewEventLog(unittest.TestCase):
    def test_record_and_lookup(self):
        log = ReviewEventLog()
        e1 = ReviewEvent(
            event_id="ev_1", example_id="ex_1", event_type=ReviewEventType.APPROVED,
            reviewer_id="r1", created_at="2026-07-24T00:00:00+00:00", rationale="ok",
        )
        e2 = ReviewEvent(
            event_id="ev_2", example_id="ex_2", event_type=ReviewEventType.FLAGGED,
            reviewer_id="r1", created_at="2026-07-24T00:00:01+00:00", rationale="needs a look",
        )
        log.record(e1)
        log.record(e2)
        self.assertEqual(log.events_for("ex_1"), (e1,))
        self.assertEqual(log.events_for("ex_2"), (e2,))
        self.assertEqual(log.events_for("ex_missing"), ())
        self.assertEqual(log.all_events(), (e1, e2))

    def test_log_exposes_no_removal_or_update_method(self):
        # Append-only is structural: no method exists that could mutate a
        # previously recorded entry.
        self.assertFalse(hasattr(ReviewEventLog, "remove"))
        self.assertFalse(hasattr(ReviewEventLog, "update"))
        self.assertFalse(hasattr(ReviewEventLog, "clear"))


class TestReviewSummary(unittest.TestCase):
    def test_valid_summary_constructs(self):
        ReviewSummary(total_examples=5, reviewed_examples=2, pending_examples=3)

    def test_rejects_mismatched_totals(self):
        with self.assertRaises(ValueError):
            ReviewSummary(total_examples=5, reviewed_examples=2, pending_examples=2)

    def test_rejects_reviewed_exceeding_total(self):
        with self.assertRaises(ValueError):
            ReviewSummary(total_examples=2, reviewed_examples=5, pending_examples=0)

    def test_rejects_negative_counts(self):
        with self.assertRaises(ValueError):
            ReviewSummary(total_examples=-1, reviewed_examples=0, pending_examples=0)


class TestDatasetManifestValidation(unittest.TestCase):
    def _summary(self, total: int) -> ReviewSummary:
        return ReviewSummary(total_examples=total, reviewed_examples=0, pending_examples=total)

    def test_rejects_empty_example_ids(self):
        with self.assertRaises(ValueError):
            DatasetManifest(
                dataset_version="v1", created_at="2026-07-24T00:00:00+00:00",
                example_ids=(), review_summary=self._summary(0),
            )

    def test_rejects_duplicate_example_ids(self):
        with self.assertRaises(ValueError):
            DatasetManifest(
                dataset_version="v1", created_at="2026-07-24T00:00:00+00:00",
                example_ids=("a", "a"), review_summary=self._summary(2),
            )

    def test_rejects_parent_equal_to_self(self):
        with self.assertRaises(ValueError):
            DatasetManifest(
                dataset_version="v1", created_at="2026-07-24T00:00:00+00:00",
                parent_dataset_version="v1", example_ids=("a",), review_summary=self._summary(1),
            )

    def test_rejects_superseded_by_equal_to_self(self):
        with self.assertRaises(ValueError):
            DatasetManifest(
                dataset_version="v1", created_at="2026-07-24T00:00:00+00:00",
                superseded_by="v1", example_ids=("a",), review_summary=self._summary(1),
            )

    def test_rejects_review_summary_total_mismatch(self):
        with self.assertRaises(ValueError):
            DatasetManifest(
                dataset_version="v1", created_at="2026-07-24T00:00:00+00:00",
                example_ids=("a", "b"), review_summary=self._summary(1),
            )


class TestAssembleManifest(unittest.TestCase):
    def test_stamps_examples_and_builds_manifest(self):
        examples = (
            _make_example("r1", QualityTier.EXCELLENT),
            _make_example("r2", QualityTier.GOOD),
            _make_example("r3", QualityTier.POOR),
        )
        manifest, stamped = assemble_manifest(examples, dataset_version="v1")

        self.assertEqual(len(stamped), 3)
        for original, s in zip(examples, stamped):
            self.assertIsNone(original.metadata.dataset_version)  # original untouched
            self.assertEqual(s.metadata.dataset_version, "v1")
            self.assertEqual(s.metadata.example_id, original.metadata.example_id)

        self.assertEqual(set(manifest.example_ids), {s.metadata.example_id for s in stamped})
        self.assertEqual(manifest.dataset_version, "v1")
        self.assertEqual(dict(manifest.label_source_distribution), {"synthetic_ground_truth": 3})
        tier_counts = dict(manifest.tier_distribution)
        self.assertEqual(tier_counts.get("excellent"), 1)
        self.assertEqual(tier_counts.get("good"), 1)
        self.assertEqual(tier_counts.get("poor"), 1)
        self.assertEqual(len(manifest.generator_provenance), 1)  # same prompt id/version for all three
        self.assertEqual(manifest.review_summary.total_examples, 3)
        self.assertEqual(manifest.review_summary.reviewed_examples, 0)
        self.assertEqual(manifest.review_summary.pending_examples, 3)

    def test_derives_review_summary_from_log(self):
        examples = (_make_example("r1"), _make_example("r2"), _make_example("r3"))
        log = ReviewEventLog()
        log.record(ReviewEvent(
            event_id="ev_1", example_id=examples[0].metadata.example_id, event_type=ReviewEventType.APPROVED,
            reviewer_id="r1", created_at="2026-07-24T00:00:00+00:00", rationale="looks right",
        ))
        log.record(ReviewEvent(
            event_id="ev_2", example_id=examples[1].metadata.example_id, event_type=ReviewEventType.FLAGGED,
            reviewer_id="r1", created_at="2026-07-24T00:00:01+00:00", rationale="check concept labels",
        ))
        manifest, _ = assemble_manifest(examples, dataset_version="v1", review_log=log)

        self.assertEqual(manifest.review_summary.total_examples, 3)
        self.assertEqual(manifest.review_summary.reviewed_examples, 2)
        self.assertEqual(manifest.review_summary.pending_examples, 1)
        self.assertEqual(dict(manifest.review_summary.event_type_counts), {"approved": 1, "flagged": 1})

    def test_rejects_empty_examples(self):
        with self.assertRaises(ValueError):
            assemble_manifest((), dataset_version="v1")

    def test_rejects_empty_dataset_version(self):
        with self.assertRaises(ValueError):
            assemble_manifest((_make_example("r1"),), dataset_version="   ")

    def test_default_policy_rejects_already_versioned_examples(self):
        examples = (_make_example("r1"),)
        _, stamped = assemble_manifest(examples, dataset_version="v1")
        with self.assertRaises(AlreadyVersionedError) as ctx:
            assemble_manifest(stamped, dataset_version="v2")
        self.assertEqual(ctx.exception.example_ids, (stamped[0].metadata.example_id,))

    def test_allow_reversioning_permits_re_stamping(self):
        examples = (_make_example("r1"),)
        _, stamped_v1 = assemble_manifest(examples, dataset_version="v1")
        manifest_v2, stamped_v2 = assemble_manifest(stamped_v1, dataset_version="v2", allow_reversioning=True)
        self.assertEqual(stamped_v2[0].metadata.dataset_version, "v2")
        self.assertEqual(manifest_v2.dataset_version, "v2")
        # v1's stamped object is untouched by the v2 assembly.
        self.assertEqual(stamped_v1[0].metadata.dataset_version, "v1")

    def test_parent_dataset_version_is_recorded(self):
        examples = (_make_example("r1"),)
        manifest, _ = assemble_manifest(examples, dataset_version="v2", parent_dataset_version="v1")
        self.assertEqual(manifest.parent_dataset_version, "v1")


class TestSupersede(unittest.TestCase):
    def test_supersede_returns_new_manifest_with_pointer_set(self):
        examples = (_make_example("r1"),)
        manifest_v1, _ = assemble_manifest(examples, dataset_version="v1")
        manifest_v1_superseded = supersede(manifest_v1, "v2")
        self.assertIsNone(manifest_v1.superseded_by)  # original untouched
        self.assertEqual(manifest_v1_superseded.superseded_by, "v2")
        self.assertEqual(manifest_v1_superseded.dataset_version, "v1")

    def test_rejects_double_supersession(self):
        examples = (_make_example("r1"),)
        manifest_v1, _ = assemble_manifest(examples, dataset_version="v1")
        once = supersede(manifest_v1, "v2")
        with self.assertRaises(ValueError):
            supersede(once, "v3")

    def test_rejects_self_supersession(self):
        examples = (_make_example("r1"),)
        manifest_v1, _ = assemble_manifest(examples, dataset_version="v1")
        with self.assertRaises(ValueError):
            supersede(manifest_v1, "v1")


if __name__ == "__main__":
    unittest.main()
