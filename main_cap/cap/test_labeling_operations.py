"""
Tests for labeling_operations.py — the reviewer-workflow subsystem built on
top of dataset_manifest.ReviewEvent/ReviewEventLog. Includes the import-graph
assertion enforcing this module's approved independence from every
production generation/evaluation/conversation/planning module.
"""

import ast
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset_manifest import ReviewEvent, ReviewEventLog, ReviewEventType
import labeling_operations as labeling_operations_module
from labeling_operations import (
    DuplicateReviewerError,
    LabelingConfig,
    LabelingReviewEventType,
    ReviewerMetrics,
    ReviewerRegistry,
    ReviewerRole,
    ReviewState,
    UnauthorizedReviewActionError,
    UnknownReviewerError,
    apply_relabel,
    compute_review_state,
    compute_reviewer_metrics,
    record_review,
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


class TestLabelingOperationsStaysWithinItsOwnBoundary(unittest.TestCase):
    FORBIDDEN_MODULES = {
        "synthetic_generation_pipeline", "coverage_strategy",
        "generation_client", "generation_recipe", "generation_validation",
        "prompt_assembler", "prompt_controllers",
        "evaluator", "evaluator_registry", "heuristic_evaluator", "evaluation_engine",
        "conversation_engine", "conversation_memory", "discussion_policy", "planner", "topic_pool",
    }

    def test_labeling_operations_never_imports_production_modules(self):
        self.assertFalse(_module_imports(labeling_operations_module) & self.FORBIDDEN_MODULES)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _labels(label_source: str = "human_reviewed", guideline_version: str = "g1") -> TrainingExampleLabels:
    return TrainingExampleLabels(
        label_source=label_source,
        labeling_guideline_version=guideline_version if label_source == "human_reviewed" else None,
        dimension_labels=(DimensionLabel(name="depth", score=0.7),),
        contradiction_label=ContradictionLabel(contradiction_present=False),
        overall_label=OverallLabel(score=0.7, grade="good", rationale="Solid answer."),
    )


def _real_session_example(example_id: str = "real_1") -> TrainingExample:
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
        labels=_labels(),
    )


def _synthetic_example(example_id: str = "synth_1") -> TrainingExample:
    from generation_client import FakeGenerationClient
    from synthetic_generation_pipeline import generate_training_example
    from training_example import QualityTier

    outcome = generate_training_example(
        recipe_id=example_id, specification=_spec(), question_text="Did Redis caching give you trouble?",
        reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
        quality_tier=QualityTier.GOOD, client=FakeGenerationClient(), generation_batch_id="batch_1",
    )
    return outcome.example


class TestReviewerRegistry(unittest.TestCase):
    def test_register_and_lookup(self):
        registry = ReviewerRegistry()
        registry.register("alice", ReviewerRole.ANNOTATOR)
        self.assertEqual(registry.role_of("alice"), ReviewerRole.ANNOTATOR)
        self.assertIsNone(registry.role_of("nobody"))

    def test_rejects_duplicate_registration(self):
        registry = ReviewerRegistry()
        registry.register("alice", ReviewerRole.ANNOTATOR)
        with self.assertRaises(DuplicateReviewerError):
            registry.register("alice", ReviewerRole.ADJUDICATOR)

    def test_update_role_promotes_existing_reviewer(self):
        registry = ReviewerRegistry()
        registry.register("alice", ReviewerRole.ANNOTATOR)
        registry.update_role("alice", ReviewerRole.ADJUDICATOR)
        self.assertEqual(registry.role_of("alice"), ReviewerRole.ADJUDICATOR)

    def test_update_role_rejects_unknown_reviewer(self):
        registry = ReviewerRegistry()
        with self.assertRaises(UnknownReviewerError):
            registry.update_role("ghost", ReviewerRole.ANNOTATOR)

    def test_reviewers_with_role(self):
        registry = ReviewerRegistry()
        registry.register("alice", ReviewerRole.ANNOTATOR)
        registry.register("bob", ReviewerRole.ADJUDICATOR)
        registry.register("carol", ReviewerRole.ANNOTATOR)
        self.assertEqual(registry.reviewers_with_role(ReviewerRole.ANNOTATOR), ("alice", "carol"))
        self.assertEqual(registry.reviewers_with_role(ReviewerRole.ADJUDICATOR), ("bob",))


def _event(example_id, reviewer_id, event_type, rationale="ok", event_id=None, created_at=None):
    return ReviewEvent(
        event_id=event_id or f"ev_{reviewer_id}_{event_type}_{created_at or '0'}",
        example_id=example_id, event_type=event_type, reviewer_id=reviewer_id,
        created_at=created_at or "2026-07-24T00:00:00+00:00", rationale=rationale,
    )


class TestComputeReviewState(unittest.TestCase):
    def test_no_events_is_pending(self):
        self.assertEqual(compute_review_state(()), ReviewState.PENDING)

    def test_single_verdict_is_in_review(self):
        events = (_event("ex1", "alice", ReviewEventType.APPROVED),)
        self.assertEqual(compute_review_state(events), ReviewState.IN_REVIEW)

    def test_two_agreeing_verdicts_is_approved(self):
        events = (
            _event("ex1", "alice", ReviewEventType.APPROVED),
            _event("ex1", "bob", ReviewEventType.APPROVED),
        )
        self.assertEqual(compute_review_state(events), ReviewState.APPROVED)

    def test_two_agreeing_rejections_is_rejected(self):
        events = (
            _event("ex1", "alice", ReviewEventType.REJECTED),
            _event("ex1", "bob", ReviewEventType.REJECTED),
        )
        self.assertEqual(compute_review_state(events), ReviewState.REJECTED)

    def test_disagreeing_verdicts_needs_adjudication(self):
        events = (
            _event("ex1", "alice", ReviewEventType.APPROVED),
            _event("ex1", "bob", ReviewEventType.REJECTED),
        )
        self.assertEqual(compute_review_state(events), ReviewState.NEEDS_ADJUDICATION)

    def test_flag_forces_needs_adjudication_even_with_agreement(self):
        events = (
            _event("ex1", "alice", ReviewEventType.APPROVED),
            _event("ex1", "bob", ReviewEventType.APPROVED),
            _event("ex1", "carol", ReviewEventType.FLAGGED),
        )
        self.assertEqual(compute_review_state(events), ReviewState.NEEDS_ADJUDICATION)

    def test_adjudicated_overrides_everything(self):
        events = (
            _event("ex1", "alice", ReviewEventType.APPROVED),
            _event("ex1", "bob", ReviewEventType.REJECTED),
            _event("ex1", "carol", ReviewEventType.FLAGGED),
            _event("ex1", "dave", LabelingReviewEventType.ADJUDICATED),
        )
        self.assertEqual(compute_review_state(events), ReviewState.ADJUDICATED)

    def test_reviewer_may_revise_own_verdict_latest_wins(self):
        events = (
            _event("ex1", "alice", ReviewEventType.REJECTED, created_at="2026-07-24T00:00:00+00:00"),
            _event("ex1", "alice", ReviewEventType.APPROVED, created_at="2026-07-24T00:01:00+00:00"),
            _event("ex1", "bob", ReviewEventType.APPROVED, created_at="2026-07-24T00:02:00+00:00"),
        )
        self.assertEqual(compute_review_state(events), ReviewState.APPROVED)

    def test_required_agreement_reviewers_is_configurable(self):
        events = (
            _event("ex1", "alice", ReviewEventType.APPROVED),
            _event("ex1", "bob", ReviewEventType.APPROVED),
        )
        config = LabelingConfig(required_agreement_reviewers=3)
        self.assertEqual(compute_review_state(events, config), ReviewState.IN_REVIEW)

    def test_rejects_invalid_config(self):
        with self.assertRaises(ValueError):
            LabelingConfig(required_agreement_reviewers=0)


class TestRecordReview(unittest.TestCase):
    def test_records_event_and_appends_to_log(self):
        log = ReviewEventLog()
        event = record_review(
            log, example_id="ex1", reviewer_id="alice", event_type=ReviewEventType.APPROVED,
            rationale="Meets rubric.",
        )
        self.assertEqual(log.all_events(), (event,))
        self.assertTrue(event.event_id)
        self.assertTrue(event.created_at)

    def test_adjudicated_requires_registry_and_adjudicator_role(self):
        log = ReviewEventLog()
        with self.assertRaises(UnauthorizedReviewActionError):
            record_review(
                log, example_id="ex1", reviewer_id="alice", event_type=LabelingReviewEventType.ADJUDICATED,
                rationale="Resolving disagreement.",
            )

        registry = ReviewerRegistry()
        registry.register("alice", ReviewerRole.ANNOTATOR)
        with self.assertRaises(UnauthorizedReviewActionError):
            record_review(
                log, example_id="ex1", reviewer_id="alice", event_type=LabelingReviewEventType.ADJUDICATED,
                rationale="Resolving disagreement.", reviewer_registry=registry,
            )

        registry.update_role("alice", ReviewerRole.ADJUDICATOR)
        event = record_review(
            log, example_id="ex1", reviewer_id="alice", event_type=LabelingReviewEventType.ADJUDICATED,
            rationale="Resolving disagreement.", reviewer_registry=registry,
        )
        self.assertEqual(event.event_type, LabelingReviewEventType.ADJUDICATED)

    def test_non_gated_event_types_require_no_registry(self):
        log = ReviewEventLog()
        record_review(
            log, example_id="ex1", reviewer_id="alice", event_type=ReviewEventType.APPROVED,
            rationale="Looks good.",
        )  # must not raise


class TestComputeReviewerMetrics(unittest.TestCase):
    def test_counts_and_agreement(self):
        log = ReviewEventLog()
        record_review(log, "ex1", "alice", ReviewEventType.APPROVED, "ok")
        record_review(log, "ex1", "bob", ReviewEventType.APPROVED, "ok")
        record_review(log, "ex2", "alice", ReviewEventType.REJECTED, "bad")
        record_review(log, "ex2", "bob", ReviewEventType.APPROVED, "fine")  # disagreement with alice

        metrics = compute_reviewer_metrics(log, "alice")
        self.assertEqual(metrics.total_events, 2)
        self.assertEqual(dict(metrics.event_type_counts), {"approved": 1, "rejected": 1})
        self.assertEqual(metrics.agreement_count, 1)
        self.assertEqual(metrics.disagreement_count, 1)

    def test_no_other_reviewer_counts_neither_way(self):
        log = ReviewEventLog()
        record_review(log, "ex1", "alice", ReviewEventType.APPROVED, "ok")
        metrics = compute_reviewer_metrics(log, "alice")
        self.assertEqual(metrics.agreement_count, 0)
        self.assertEqual(metrics.disagreement_count, 0)

    def test_unknown_reviewer_has_zero_metrics(self):
        log = ReviewEventLog()
        metrics = compute_reviewer_metrics(log, "ghost")
        self.assertEqual(metrics.total_events, 0)
        self.assertEqual(metrics.event_type_counts, ())


class TestApplyRelabel(unittest.TestCase):
    def test_relabels_real_session_example(self):
        original = _real_session_example()
        new_labels = _labels(guideline_version="ignored-because-forced")
        relabeled = apply_relabel(original, new_labels, labeling_guideline_version="guideline_v2")

        self.assertEqual(relabeled.labels.label_source, "human_reviewed")
        self.assertEqual(relabeled.labels.labeling_guideline_version, "guideline_v2")
        self.assertIsNot(relabeled, original)
        # Original object is untouched.
        self.assertEqual(original.labels.labeling_guideline_version, "g1")

    def test_rejects_synthetic_provenance_example(self):
        synthetic = _synthetic_example()
        with self.assertRaises(ValueError):
            apply_relabel(synthetic, _labels(), labeling_guideline_version="guideline_v2")

    def test_rejects_empty_labeling_guideline_version(self):
        original = _real_session_example()
        with self.assertRaises(ValueError):
            apply_relabel(original, _labels(), labeling_guideline_version="   ")


if __name__ == "__main__":
    unittest.main()
