"""
Tests for the four_dim_overall_v4_5000 Claude-authored dataset harness
(v4_5000_dataset.py / v4_5000_build.py / v4_5000_scaffold.py).

Deterministic, no network, no Gemini: semantic dedup uses an INJECTED embed
function so SBERT is never loaded in tests.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import v4_5000_build
import v4_5000_dataset as ds
import v4_5000_scaffold as scaffold
from evaluation_dimensions import CANONICAL_DIMENSIONS
from model_dataset import score_to_tier

_KEYS = tuple(d.value for d in CANONICAL_DIMENSIONS)


def _rec(**over):
    base = dict(
        id="t1", group_id="g1", category="project_deep_dive", reasoning_type="explanation",
        grounding={"title": "P", "summary": "s", "technologies": ["FastAPI", "PostgreSQL"], "concepts": ["c"]},
        question="How does it work?", expected_concepts=["a", "b"],
        answer="I built the routing layer over PostgreSQL and used FastAPI to expose it cleanly.",
        dimensions={"technical_correctness": 4, "depth_specificity": 3, "relevance_completeness": 4, "grounding_ownership": 3},
        humanized=False, hard_case=None,
    )
    base.update(over)
    return ds.AuthoredRecord.model_validate(base)


class TestOverallTargetPolicy(unittest.TestCase):
    """Overall target = equal-weight mean of the four dim tiers -> score_to_tier
    (the EXISTING policy, not a new weighting scheme)."""

    def test_derive_overall_score_is_equal_weight_mean(self):
        dims = {"technical_correctness": 4, "depth_specificity": 2, "relevance_completeness": 4, "grounding_ownership": 2}
        self.assertAlmostEqual(ds.derive_overall_score(dims), (4 + 2 + 4 + 2) / 16.0)

    def test_derive_overall_tier_matches_score_to_tier(self):
        for dims in (
            {"technical_correctness": 4, "depth_specificity": 4, "relevance_completeness": 4, "grounding_ownership": 4},
            {"technical_correctness": 1, "depth_specificity": 1, "relevance_completeness": 1, "grounding_ownership": 1},
            {"technical_correctness": 3, "depth_specificity": 2, "relevance_completeness": 1, "grounding_ownership": 3},
            {"technical_correctness": 0, "depth_specificity": 1, "relevance_completeness": 0, "grounding_ownership": 1},
        ):
            self.assertEqual(ds.derive_overall_tier(dims), score_to_tier(ds.derive_overall_score(dims)))

    def test_target_is_consistent_with_overall_dataset_policy(self):
        # overall_dataset.overall_score_to_tier(overall_label.score) must equal
        # our derived tier -- the harness and the trainer must agree.
        from overall_dataset import overall_score_to_tier
        dims = {"technical_correctness": 4, "depth_specificity": 1, "relevance_completeness": 3, "grounding_ownership": 2}
        ex = ds.record_to_training_example(_rec(dimensions=dims), "batch_test")
        self.assertEqual(overall_score_to_tier(ex.labels.overall_label.score), ds.derive_overall_tier(dims))


class TestRecordValidation(unittest.TestCase):
    def test_valid_record_accepted(self):
        self.assertTrue(ds.validate_record(_rec()).accepted)

    def test_banned_quality_phrase_in_answer_rejected(self):
        v = ds.validate_record(_rec(answer="This is a high-quality answer that I demonstrated well over PostgreSQL."))
        self.assertFalse(v.accepted)
        self.assertTrue(any("banned_quality_phrase" in r for r in v.reasons))

    def test_hallucinated_technology_rejected(self):
        # Answer names MongoDB, which is a known-vocab tech NOT in the grounding.
        v = ds.validate_record(_rec(answer="I stored everything in MongoDB and queried it directly for the feature."))
        self.assertFalse(v.accepted)
        self.assertTrue(any("hallucinated_technology" in r for r in v.reasons))

    def test_malformed_answer_rejected(self):
        v = ds.validate_record(_rec(answer="ok"))
        self.assertFalse(v.accepted)
        self.assertIn("malformed_or_empty_answer", v.reasons)

    def test_bad_dimension_keys_rejected_by_schema(self):
        with self.assertRaises(Exception):
            _rec(dimensions={"technical_correctness": 4})

    def test_out_of_range_tier_rejected_by_schema(self):
        with self.assertRaises(Exception):
            _rec(dimensions={k: 9 for k in _KEYS})


class TestRecordToTrainingExample(unittest.TestCase):
    def test_produces_valid_training_example_with_four_canonical_labels(self):
        ex = ds.record_to_training_example(_rec(), "batch_0001")
        names = {dl.name for dl in ex.labels.dimension_labels}
        self.assertEqual(names, set(_KEYS))
        self.assertEqual(ex.metadata.example_id, "v4c_t1")

    def test_provenance_is_synthetic_and_labels_are_synthetic_ground_truth(self):
        # Honest provenance: Claude-authored -> SYNTHETIC, never human_reviewed.
        ex = ds.record_to_training_example(_rec(), "batch_0001")
        self.assertEqual(ex.provenance.source.value, "synthetic")
        self.assertEqual(ex.labels.label_source, "synthetic_ground_truth")
        self.assertEqual(ex.synthetic.generator_model, "claude-authored")

    def test_group_id_becomes_source_id_for_leak_free_split(self):
        ex = ds.record_to_training_example(_rec(group_id="mygroup"), "batch_0001")
        self.assertEqual(ex.inputs.specification.source_id, "mygroup")


class TestSemanticDedup(unittest.TestCase):
    def test_semantic_duplicate_pairs_with_injected_embed(self):
        import numpy as np

        def fake_embed(texts):
            # answers 0 and 2 identical vector -> near-dup; 1 orthogonal.
            table = {"same": [1.0, 0.0], "other": [0.0, 1.0]}
            return np.array([table["same"] if t != "unique" else table["other"] for t in texts])

        answers = ["same", "unique", "same"]
        hits = ds.semantic_duplicate_pairs(answers, threshold=0.99, embed_fn=fake_embed)
        pairs = {(i, j) for i, j, _ in hits}
        self.assertIn((0, 2), pairs)
        self.assertNotIn((0, 1), pairs)


class TestScaffold(unittest.TestCase):
    def test_make_slot_is_deterministic(self):
        a = scaffold.make_slot(42)
        b = scaffold.make_slot(42)
        self.assertEqual(a, b)

    def test_slots_span_many_distinct_groups(self):
        groups = {scaffold.make_slot(i).group_id for i in range(300)}
        # Deterministic combinatorial space must yield many independent groups.
        self.assertGreater(len(groups), 150)

    def test_slot_enums_are_valid(self):
        from question_families import ReasoningType
        from question_specification import QuestionCategory
        for i in range(50):
            s = scaffold.make_slot(i)
            QuestionCategory(s.category)          # raises if invalid
            ReasoningType(s.reasoning_type)        # raises if invalid

    def test_approximate_group_space_is_large(self):
        self.assertGreater(scaffold.approximate_group_space(), 5000)


class TestAssembleEndToEnd(unittest.TestCase):
    def _write_batch(self, batches_dir, records):
        os.makedirs(batches_dir, exist_ok=True)
        with open(os.path.join(batches_dir, "batch_0001.jsonl"), "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def _base_record(self, i, group=None, answer=None):
        return dict(
            id=f"a{i}", group_id=group or f"grp_{i}", category="project_deep_dive", reasoning_type="explanation",
            grounding={"title": f"Proj {i}", "summary": f"summary {i}", "technologies": ["FastAPI"], "concepts": []},
            question=f"How does project {i} work in detail?",
            expected_concepts=["design"],
            answer=answer or f"I designed project {i} with a clear routing layer and explained the flow end to end thoroughly here.",
            dimensions={"technical_correctness": 3, "depth_specificity": 3, "relevance_completeness": 3, "grounding_ownership": 3},
            humanized=(i % 4 == 0),
        )

    def test_assemble_preserves_frozen_and_is_leak_free(self):
        import numpy as np

        def fake_embed(texts):
            # every text orthogonal-ish -> no semantic dups among authored
            return np.eye(len(texts))[:, :max(2, len(texts))]

        with tempfile.TemporaryDirectory() as tmp:
            batches = os.path.join(tmp, "batches")
            self._write_batch(batches, [self._base_record(i) for i in range(12)])
            orig = v4_5000_build.BATCHES_DIR
            v4_5000_build.BATCHES_DIR = batches
            try:
                assembled = v4_5000_build.assemble(semantic_dedup=True, embed_fn=fake_embed)
            finally:
                v4_5000_build.BATCHES_DIR = orig

            # frozen 220 preserved
            self.assertTrue(assembled.reports["frozen_preservation"]["all_frozen_present"])
            self.assertEqual(assembled.reports["counts"]["frozen"], 220)
            # authored added
            self.assertEqual(assembled.reports["counts"]["total"], 220 + 12)
            # no cross-split leakage on any key
            leak = assembled.reports["leakage"]
            for k in ("cross_split_source_ids", "cross_split_questions", "cross_split_answers", "cross_split_qa"):
                self.assertTrue(leak[k]["clean"], f"{k} leaked")
            # V4 disjoint
            self.assertEqual(leak["v4_example_id_overlap"], [])
            self.assertEqual(leak["v4_source_id_overlap"], [])
            self.assertEqual(leak["v4_qa_overlap_count"], 0)

    def test_exact_duplicate_answer_is_dropped(self):
        import numpy as np

        def fake_embed(texts):
            return np.eye(len(texts))[:, :max(2, len(texts))]

        with tempfile.TemporaryDirectory() as tmp:
            batches = os.path.join(tmp, "batches")
            recs = [self._base_record(i) for i in range(4)]
            # plant an exact (question, answer) duplicate of record a0 under a new id/group
            dup = self._base_record(99, group="grp_dup")
            dup["question"] = recs[0]["question"]
            dup["answer"] = recs[0]["answer"]
            recs.append(dup)
            self._write_batch(batches, recs)
            orig = v4_5000_build.BATCHES_DIR
            v4_5000_build.BATCHES_DIR = batches
            try:
                assembled = v4_5000_build.assemble(semantic_dedup=True, embed_fn=fake_embed)
            finally:
                v4_5000_build.BATCHES_DIR = orig
            self.assertGreaterEqual(assembled.reports["dedup"]["exact_qa_duplicates_dropped"], 1)

    def test_provenance_accounting_adds_up(self):
        import numpy as np

        def fake_embed(texts):
            return np.eye(len(texts))[:, :max(2, len(texts))]

        with tempfile.TemporaryDirectory() as tmp:
            batches = os.path.join(tmp, "batches")
            self._write_batch(batches, [self._base_record(i) for i in range(8)])
            orig = v4_5000_build.BATCHES_DIR
            v4_5000_build.BATCHES_DIR = batches
            try:
                assembled = v4_5000_build.assemble(semantic_dedup=True, embed_fn=fake_embed)
            finally:
                v4_5000_build.BATCHES_DIR = orig
            prov = assembled.reports["counts"]["provenance"]
            self.assertEqual(sum(prov.values()), assembled.reports["counts"]["total"])
            self.assertEqual(prov["frozen_hand_authored"], 220)


if __name__ == "__main__":
    unittest.main()
