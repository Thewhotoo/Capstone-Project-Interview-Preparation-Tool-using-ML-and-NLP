"""
Tests for experiment_dataset_io.py -- JSONL persistence round-trip fidelity.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from generation_client import FakeGenerationClient
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from synthetic_generation_pipeline import generate_training_example
from training_example import QualityTier
from training_experimentation import (
    BenchmarkResult,
    Checkpoint,
    ExperimentConfig,
    PromotionDecision,
    assemble_checkpoint,
)


def _spec() -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=Grounding(project=ProjectGrounding(
            title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="RD Platform", source_field="interview_seeds", reason="test",
    )


def _examples(n: int) -> tuple:
    examples = []
    for i in range(n):
        outcome = generate_training_example(
            recipe_id=f"r{i}", specification=_spec(), question_text="Did Redis caching give you trouble?",
            reasoning_type=ReasoningType.DEBUGGING, expected_concepts=("caching",),
            quality_tier=QualityTier.GOOD, client=FakeGenerationClient(), generation_batch_id="batch_1",
        )
        examples.append(outcome.example)
    return tuple(examples)


class TestSaveAndLoadExamplesJsonl(unittest.TestCase):
    def test_round_trips_examples_exactly(self):
        examples = _examples(5)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dataset.jsonl")
            returned_path = save_examples_jsonl(examples, path)
            self.assertEqual(returned_path, path)
            self.assertTrue(os.path.exists(path))

            reloaded = load_examples_jsonl(path)
            self.assertEqual(len(reloaded), len(examples))
            for original, loaded in zip(examples, reloaded):
                self.assertEqual(original, loaded)

    def test_one_example_per_line(self):
        examples = _examples(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dataset.jsonl")
            save_examples_jsonl(examples, path)
            with open(path, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
            self.assertEqual(len(lines), 3)

    def test_rejects_empty_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dataset.jsonl")
            with self.assertRaises(ValueError):
                save_examples_jsonl((), path)

    def test_load_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.jsonl")
            open(path, "w").close()
            with self.assertRaises(ValueError):
                load_examples_jsonl(path)

    def test_load_skips_blank_lines(self):
        examples = _examples(2)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dataset.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(examples[0].model_dump_json())
                f.write("\n\n")
                f.write(examples[1].model_dump_json())
                f.write("\n")
            reloaded = load_examples_jsonl(path)
            self.assertEqual(len(reloaded), 2)


class TestSaveAndLoadJson(unittest.TestCase):
    """Generic single-document persistence (session 10, Colab portability)
    -- exercised against several different frozen Pydantic artifact types
    to confirm it's genuinely type-agnostic, not just working for one."""

    def test_round_trips_a_checkpoint(self):
        config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="v1")
        checkpoint = assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="s3://bucket/m1")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.json")
            returned_path = save_json(checkpoint, path)
            self.assertEqual(returned_path, path)
            reloaded = load_json(Checkpoint, path)
            self.assertEqual(reloaded, checkpoint)

    def test_round_trips_a_benchmark_result(self):
        benchmark = BenchmarkResult(
            benchmark_id="bench_1", created_at="2026-07-24T00:00:00+00:00", dataset_version="v1",
            example_count=10, candidate_evaluator_name="candidate", candidate_evaluator_version="1.0",
            baseline_evaluator_name="baseline", baseline_evaluator_version="1.0",
            candidate_qwk=0.5, baseline_qwk=0.1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "benchmark.json")
            save_json(benchmark, path)
            reloaded = load_json(BenchmarkResult, path)
            self.assertEqual(reloaded, benchmark)

    def test_round_trips_a_promotion_decision(self):
        decision = PromotionDecision(
            approved=True, rationale="cleared the bar", checkpoint_model_version="m1", benchmark_id="bench_1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "decision.json")
            save_json(decision, path)
            reloaded = load_json(PromotionDecision, path)
            self.assertEqual(reloaded, decision)

    def test_load_json_revalidates_not_just_deserializes(self):
        # A malformed document (missing required fields) must fail through
        # the model's own validator, not silently produce a broken object.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"approved": true}')  # missing required fields
            with self.assertRaises(Exception):
                load_json(PromotionDecision, path)


if __name__ == "__main__":
    unittest.main()
