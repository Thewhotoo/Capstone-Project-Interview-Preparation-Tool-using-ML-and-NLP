"""
Tests for the V4 diagnostic dataset (`artifacts/v4_diagnostic/`).

READ-ONLY: exercises `build_v4_diagnostic.build()`, `v4_input_builder`, and
`validate_v4_diagnostic.validate()` in-process (no subprocess, no file
writes required for the assertions themselves) plus one check that the
already-generated `v4_diagnostic_58.jsonl` on disk matches the builder's
current in-memory output. Never touches any file under `seed_dataset_v1/`,
`hand_authored_50/`, `gap_coverage_20/`, `v2_targeted_50/`, `v3_grounding/`,
`four_dim_experiment_v1/`, `four_dim_experiment_v2/`, or any training
pipeline module — this is a standalone diagnostic dataset, not part of the
V1/V2/V3 training pipeline (see module docstrings in
`build_v4_diagnostic.py` for the isolation guarantees this asserts).
"""
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_V4_DIR = os.path.join(_HERE, "artifacts", "v4_diagnostic")
sys.path.insert(0, _HERE)
sys.path.insert(0, _V4_DIR)

import build_v4_diagnostic  # noqa: E402
import validate_v4_diagnostic  # noqa: E402
from v4_input_builder import FORBIDDEN_INPUT_LEAK_FIELDS, build_v4_model_input  # noqa: E402

CANONICAL_DIMENSIONS = (
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
)


class TestV4DiagnosticBuild(unittest.TestCase):
    def setUp(self):
        self.examples = build_v4_diagnostic.build()

    def test_exactly_58_examples(self):
        self.assertEqual(len(self.examples), 58)

    def test_category_counts_match_design(self):
        expected = {
            "relevance_alignment": 16,
            "multipart_completeness": 9,
            "technical_correctness": 12,
            "depth_control": 6,
            "grounding_ownership": 9,
            "cross_dimension": 6,
        }
        counts = {}
        for ex in self.examples:
            counts[ex["diagnostic_category"]] = counts.get(ex["diagnostic_category"], 0) + 1
        self.assertEqual(counts, expected)

    def test_all_gold_labels_present_and_in_range(self):
        for ex in self.examples:
            for dim in CANONICAL_DIMENSIONS:
                self.assertIn(dim, ex["gold_labels"], ex["example_id"])
                v = ex["gold_labels"][dim]
                self.assertIsInstance(v, int, f"{ex['example_id']}.{dim}")
                self.assertGreaterEqual(v, 0, f"{ex['example_id']}.{dim}")
                self.assertLessEqual(v, 4, f"{ex['example_id']}.{dim}")

    def test_unique_example_ids(self):
        ids = [ex["example_id"] for ex in self.examples]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_duplicate_question_answer_pairs(self):
        pairs = [(ex["question"], ex["answer"]) for ex in self.examples]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_no_duplicate_answers_at_all(self):
        # V4's design never intentionally reuses answer text (unlike some
        # naturalistic pools) -- every one of the 58 answers should be
        # distinct.
        answers = [ex["answer"] for ex in self.examples]
        self.assertEqual(len(answers), len(set(answers)))

    def test_every_example_has_diagnostic_category_and_pair_group(self):
        for ex in self.examples:
            self.assertTrue(ex.get("diagnostic_category"))
            self.assertTrue(ex.get("pair_group_id"))

    def test_pair_groups_share_question_and_context(self):
        groups = {}
        for ex in self.examples:
            groups.setdefault(ex["pair_group_id"], []).append(ex)
        self.assertEqual(len(groups), 20)
        for group_id, members in groups.items():
            self.assertGreaterEqual(len(members), 2, group_id)
            questions = {m["question"] for m in members}
            titles = {m["grounding"]["title"] for m in members}
            source_ids = {m["source_id"] for m in members}
            self.assertEqual(len(questions), 1, f"{group_id}: question mismatch")
            self.assertEqual(len(titles), 1, f"{group_id}: grounding.title mismatch")
            self.assertEqual(len(source_ids), 1, f"{group_id}: source_id mismatch")

    def test_multipart_examples_have_two_expected_concepts(self):
        for ex in self.examples:
            if ex["diagnostic_category"] == "multipart_completeness":
                self.assertGreaterEqual(len(ex["expected_concepts"]), 2, ex["example_id"])

    def test_all_source_ids_are_hypothetical_and_prefixed(self):
        for ex in self.examples:
            self.assertTrue(ex["source_id"].startswith("v4h_"), ex["example_id"])
            self.assertTrue(ex["hypothetical_source"], ex["example_id"])

    def test_no_source_id_or_example_id_collision_with_frozen_pools(self):
        frozen_source_ids, frozen_example_ids = validate_v4_diagnostic._load_frozen_pool_ids()
        v4_source_ids = {ex["source_id"] for ex in self.examples}
        v4_example_ids = {ex["example_id"] for ex in self.examples}
        self.assertEqual(v4_source_ids & frozen_source_ids, set())
        self.assertEqual(v4_example_ids & frozen_example_ids, set())


class TestV4ModelInputBuilderLeakage(unittest.TestCase):
    """Confirms `rationale`, `gold_labels`, `diagnostic_category`, and
    `pair_group_id` never reach the built model-input text -- the explicit
    "rationales are metadata only" requirement."""

    def setUp(self):
        self.examples = build_v4_diagnostic.build()

    def test_forbidden_fields_never_in_built_input(self):
        for ex in self.examples:
            text_a, text_b = build_v4_model_input(ex)
            full_input = text_a + "\n" + text_b
            for field in FORBIDDEN_INPUT_LEAK_FIELDS:
                self.assertNotIn(field, full_input.split(), f"{ex['example_id']}: {field}")
            for dim, rationale_text in ex["rationale"].items():
                self.assertNotIn(rationale_text, full_input, f"{ex['example_id']}: rationale[{dim}]")

    def test_question_and_answer_present_in_built_input(self):
        for ex in self.examples:
            text_a, text_b = build_v4_model_input(ex)
            self.assertIn(ex["question"], text_a)
            self.assertEqual(text_b, ex["answer"])

    def test_grounding_summary_always_empty(self):
        # By design: V4 carries no grounding-enrichment text, only
        # title/technologies, so it can never leak an answer or a
        # first-person ownership claim through the grounding channel.
        for ex in self.examples:
            self.assertEqual(ex["grounding"]["summary"], "")


class TestV4ValidationReport(unittest.TestCase):
    def test_full_validation_passes(self):
        examples = build_v4_diagnostic.build()
        report = validate_v4_diagnostic.validate(examples)
        failed = [c for c in report["checks"] if c["status"] != "PASS"]
        self.assertEqual(failed, [], failed)
        self.assertTrue(report["all_passed"])

    def test_generated_jsonl_on_disk_matches_builder_output(self):
        # Guards against the on-disk artifact drifting from the builder
        # script without being regenerated.
        path = os.path.join(_V4_DIR, "v4_diagnostic_58.jsonl")
        if not os.path.exists(path):
            self.skipTest("v4_diagnostic_58.jsonl not yet generated")
        with open(path, encoding="utf-8") as f:
            on_disk = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(on_disk, build_v4_diagnostic.build())


class TestV4NotWiredIntoTrainingPipeline(unittest.TestCase):
    """V4 must remain an isolated diagnostic benchmark: no training-pipeline
    module may import or reference it."""

    def test_four_dim_experiment_split_does_not_reference_v4(self):
        import four_dim_experiment_split
        source_path = four_dim_experiment_split.__file__
        with open(source_path, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("v4_diagnostic", content)
        self.assertNotIn("v4h_", content)

    def test_run_four_dim_training_does_not_reference_v4(self):
        import run_four_dim_training
        source_path = run_four_dim_training.__file__
        with open(source_path, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("v4_diagnostic", content)
        self.assertNotIn("v4h_", content)


if __name__ == "__main__":
    unittest.main()
