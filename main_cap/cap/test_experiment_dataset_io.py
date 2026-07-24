"""
Tests for experiment_dataset_io.py -- JSONL persistence round-trip fidelity.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import ConceptObservationStatus
from experiment_dataset_io import load_examples_jsonl, save_examples_jsonl
from generation_client import FakeGenerationClient
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from synthetic_generation_pipeline import generate_training_example
from training_example import QualityTier


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


if __name__ == "__main__":
    unittest.main()
