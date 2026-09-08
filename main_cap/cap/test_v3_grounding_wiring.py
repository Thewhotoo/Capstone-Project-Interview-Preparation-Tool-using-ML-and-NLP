"""
Tests for the V3 grounding-artifact wiring (Phase 6 of the V3 data repair).

Covers exactly the categories requested when wiring
`artifacts/v3_grounding/grounding_proposals.jsonl` into the real
training/inference input construction via `grounding_lookup.py` +
`four_dim_experiment_split._to_training_example`:

  A. Training path      -- enriched example gets its exact proposal text,
                            expected_concepts stay separate, Q/A unchanged.
  B. Inference path      -- same example, byte-identical serialized input.
  C. Unenriched example  -- baseline (title+technologies only) preserved.
  D. Leakage              -- no answer text, no self-evidence, no first-person,
                            no gold labels/rubric language in any grounding text.
  E. Split integrity      -- 166/27/27 unchanged, no new/deleted examples,
                            source_id/group assignments unchanged.

Uses the real 220-example V2 pool and a real tokenizer with a tiny
randomly-initialized backbone (same convention as
`test_four_dim_experiment_split.py` / `test_four_dim_migration.py`) --
never a full pretrained-weights download, never trains anything.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from four_dim_experiment_split import CANONICAL_DIMENSION_KEYS
from four_dim_experiment_v2_split import load_v2_pool
from grounding_lookup import grounding_proposal_for, grounding_summary_for
from model_backbone import (
    BackboneConfig,
    build_dimension_pair,
    build_tiny_random_encoder,
    build_tokenizer,
    grounding_to_text,
)
from model_dataset import collate_fn
from model_evaluator import TrainedEvaluator
from model_heads import MultiTaskModel
from question_specification import Grounding, ProjectGrounding
from training_experimentation import Checkpoint, ExperimentConfig, assemble_checkpoint

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOKENIZER = build_tokenizer(BackboneConfig())
_BACKBONE_CONFIG = BackboneConfig(max_length=256)

# Loaded once -- pure JSON parsing + pydantic construction, no model/tokenizer.
_POOL = load_v2_pool()
_BY_ID = {e.metadata.example_id: e for e in _POOL}

_PROPOSALS_PATH = os.path.join(_HERE, "artifacts", "v3_grounding", "grounding_proposals.jsonl")
with open(_PROPOSALS_PATH, encoding="utf-8") as _f:
    _PROPOSALS = [json.loads(l) for l in _f if l.strip()]
_ENRICHED_IDS = {p["example_id"] for p in _PROPOSALS}

_RAW_POOL_FILES = [
    os.path.join(_HERE, "artifacts", "seed_dataset_v1", "seed_v1_3_repaired.jsonl"),
    os.path.join(_HERE, "artifacts", "hand_authored_50", "hand_authored_50_v1.jsonl"),
    os.path.join(_HERE, "artifacts", "gap_coverage_20", "gap20_v1.jsonl"),
    os.path.join(_HERE, "artifacts", "v2_targeted_50", "v2_targeted_50_v1.jsonl"),
]
_RAW_BY_ID = {}
for _path in _RAW_POOL_FILES:
    with open(_path, encoding="utf-8") as _fh:
        for _line in _fh:
            _line = _line.strip()
            if not _line:
                continue
            _rec = json.loads(_line)
            _RAW_BY_ID[_rec["example_id"]] = _rec

FIRST_PERSON = re.compile(r"\b(I|I've|I'd|I'll|my|My|mine|we|We|we've|We've|our|Our|us|Us)\b(?!/O)")
GOLD_LABEL_WORDS = re.compile(
    r"\b(gold|tier|score|technical_correctness|depth_specificity|"
    r"relevance_completeness|grounding_ownership|rubric|correct answer|"
    r"should mention|should say)\b",
    re.IGNORECASE,
)


def _checkpoint() -> Checkpoint:
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="four_dim_v2")
    return assemble_checkpoint(model_version="m_v3_grounding_test", experiment_config=config, artifact_uri="in-memory-test-artifact")


def _evaluator() -> TrainedEvaluator:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone, dimension_names=CANONICAL_DIMENSION_KEYS)
    return TrainedEvaluator(_checkpoint(), model, _TOKENIZER, _BACKBONE_CONFIG)


# ═════════════════════════════════════════════════════════════════════════
# A. Training path
# ═════════════════════════════════════════════════════════════════════════
class TestTrainingPathEnrichedExample(unittest.TestCase):
    EXAMPLE_ID = "seed_v1_005"  # ShardDB, HIGH-confidence, mutual 3-way cluster

    def test_example_is_enriched_in_the_artifact(self):
        self.assertIn(self.EXAMPLE_ID, _ENRICHED_IDS)

    def test_pool_example_carries_the_exact_proposal_grounding_text(self):
        proposal = grounding_proposal_for(self.EXAMPLE_ID)
        example = _BY_ID[self.EXAMPLE_ID]
        self.assertEqual(
            example.inputs.specification.grounding.project.summary,
            proposal["grounding_text"],
        )

    def test_collate_fn_context_includes_the_exact_grounding_text(self):
        example = _BY_ID[self.EXAMPLE_ID]
        proposal = grounding_proposal_for(self.EXAMPLE_ID)
        # collate_fn must run without error on an enriched example (exercises
        # the real tokenization path end to end, not just the text builder).
        collate_fn([example], _TOKENIZER, _BACKBONE_CONFIG, dimension_names=CANONICAL_DIMENSION_KEYS)
        # Verify the exact text_a collate_fn builds internally, via the same
        # public builder call it makes (build_dimension_pair + grounding_to_text).
        context_text, _ = build_dimension_pair(
            example.inputs.question_text,
            grounding_to_text(example.inputs.specification.grounding),
            example.inputs.expected_concepts,
            example.inputs.answer_text,
        )
        self.assertIn(proposal["grounding_text"], context_text)
        self.assertIn("RELEVANT CONTEXT:", context_text)

    def test_expected_concepts_remain_present_and_separate_from_grounding(self):
        example = _BY_ID[self.EXAMPLE_ID]
        raw = _RAW_BY_ID[self.EXAMPLE_ID]
        self.assertEqual(tuple(example.inputs.expected_concepts), tuple(raw.get("expected_concepts", ())))
        proposal = grounding_proposal_for(self.EXAMPLE_ID)
        for concept in example.inputs.expected_concepts:
            self.assertNotIn(concept, proposal["grounding_text"])

    def test_question_and_answer_text_unchanged_vs_raw_source(self):
        example = _BY_ID[self.EXAMPLE_ID]
        raw = _RAW_BY_ID[self.EXAMPLE_ID]
        self.assertEqual(example.inputs.question_text, raw["question"])
        self.assertEqual(example.inputs.answer_text, raw["answer"])


# ═════════════════════════════════════════════════════════════════════════
# B. Inference path
# ═════════════════════════════════════════════════════════════════════════
class TestInferencePathMatchesTraining(unittest.TestCase):
    EXAMPLE_ID = "seed_v1_005"

    def test_evaluation_request_reuses_the_same_specification_object(self):
        example = _BY_ID[self.EXAMPLE_ID]
        request = EvaluationRequest(
            request_id=f"t_{self.EXAMPLE_ID}", requested_at="2026-09-09T00:00:00+00:00",
            specification=example.inputs.specification, question_text=example.inputs.question_text,
            reasoning_type=example.inputs.reasoning_type, answer_text=example.inputs.answer_text,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=example.inputs.expected_concepts,
        )
        self.assertIs(request.specification, example.inputs.specification)

    def test_serialized_context_byte_identical_between_training_and_inference_construction(self):
        example = _BY_ID[self.EXAMPLE_ID]
        request = EvaluationRequest(
            request_id=f"t_{self.EXAMPLE_ID}", requested_at="2026-09-09T00:00:00+00:00",
            specification=example.inputs.specification, question_text=example.inputs.question_text,
            reasoning_type=example.inputs.reasoning_type, answer_text=example.inputs.answer_text,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=example.inputs.expected_concepts,
        )
        # training-time construction (exactly what model_dataset.collate_fn does)
        train_text_a, train_text_b = build_dimension_pair(
            example.inputs.question_text,
            grounding_to_text(example.inputs.specification.grounding),
            example.inputs.expected_concepts,
            example.inputs.answer_text,
        )
        # inference-time construction (exactly what model_evaluator.TrainedEvaluator.evaluate does)
        infer_text_a, infer_text_b = build_dimension_pair(
            request.question_text,
            grounding_to_text(request.specification.grounding),
            request.expected_concepts,
            request.answer_text,
        )
        self.assertEqual(train_text_a, infer_text_a)
        self.assertEqual(train_text_b, infer_text_b)

    def test_evaluator_runs_end_to_end_on_an_enriched_example(self):
        example = _BY_ID[self.EXAMPLE_ID]
        request = EvaluationRequest(
            request_id=f"smoke_{self.EXAMPLE_ID}", requested_at="2026-09-09T00:00:00+00:00",
            specification=example.inputs.specification, question_text=example.inputs.question_text,
            reasoning_type=example.inputs.reasoning_type, answer_text=example.inputs.answer_text,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=example.inputs.expected_concepts,
        )
        result = _evaluator().evaluate(request)
        self.assertEqual({d.name for d in result.dimensions}, set(CANONICAL_DIMENSION_KEYS))


# ═════════════════════════════════════════════════════════════════════════
# C. Unenriched example (single-example project) preserves baseline
# ═════════════════════════════════════════════════════════════════════════
class TestUnenrichedExamplePreservesBaseline(unittest.TestCase):
    EXAMPLE_ID = "gap20_v1_000"  # AuthGatekeeper -- single-example project

    def test_single_example_project_has_no_proposal(self):
        self.assertNotIn(self.EXAMPLE_ID, _ENRICHED_IDS)
        self.assertIsNone(grounding_proposal_for(self.EXAMPLE_ID))
        self.assertEqual(grounding_summary_for(self.EXAMPLE_ID), "")

    def test_specification_summary_is_empty_default(self):
        example = _BY_ID[self.EXAMPLE_ID]
        self.assertEqual(example.inputs.specification.grounding.project.summary, "")

    def test_grounding_to_text_matches_pre_v3_title_plus_technologies_baseline(self):
        example = _BY_ID[self.EXAMPLE_ID]
        raw = _RAW_BY_ID[self.EXAMPLE_ID]
        actual = grounding_to_text(example.inputs.specification.grounding)
        baseline_spec = Grounding(project=ProjectGrounding(
            title=raw["title"], technologies=tuple(raw["technologies"]), concepts=(),
        ))
        expected = grounding_to_text(baseline_spec)
        self.assertEqual(actual, expected)
        self.assertNotIn("RELEVANT CONTEXT", actual)  # no section label leaks into the flattened text itself

    def test_context_text_relevant_context_section_contains_only_title_and_technologies(self):
        # RELEVANT CONTEXT is still present (title/technologies are non-empty,
        # exactly like the pre-V3 baseline) -- what matters is that no
        # grounding SUMMARY sentence was added for this unenriched example.
        example = _BY_ID[self.EXAMPLE_ID]
        raw = _RAW_BY_ID[self.EXAMPLE_ID]
        context_text, _ = build_dimension_pair(
            example.inputs.question_text,
            grounding_to_text(example.inputs.specification.grounding),
            example.inputs.expected_concepts,
            example.inputs.answer_text,
        )
        expected_section = f"RELEVANT CONTEXT:\n{raw['title']} {' '.join(raw['technologies'])}"
        self.assertIn(expected_section, context_text)

    def test_all_18_single_example_projects_are_unenriched(self):
        single_example_ids = {
            "gap20_v1_000", "gap20_v1_012", "v2t50_v1_003", "gap20_v1_008",
            "gap20_v1_003", "gap20_v1_009", "gap20_v1_005", "v2t50_v1_045",
            "gap20_v1_007", "gap20_v1_010", "gap20_v1_004", "v2t50_v1_000",
            "gap20_v1_002", "v2t50_v1_002", "gap20_v1_006", "gap20_v1_013",
            "gap20_v1_001", "gap20_v1_011",
        }
        self.assertEqual(single_example_ids & _ENRICHED_IDS, set())
        for eid in single_example_ids:
            self.assertEqual(_BY_ID[eid].inputs.specification.grounding.project.summary, "")


# ═════════════════════════════════════════════════════════════════════════
# D. Leakage
# ═════════════════════════════════════════════════════════════════════════
class TestNoLeakageInWiredGrounding(unittest.TestCase):
    def test_no_answer_text_enters_grounding_for_any_enriched_example(self):
        for eid in _ENRICHED_IDS:
            example = _BY_ID[eid]
            summary = example.inputs.specification.grounding.project.summary
            answer = example.inputs.answer_text
            self.assertNotIn(summary, answer, msg=f"{eid}: grounding is a substring of its own answer")
            self.assertNotIn(answer, summary, msg=f"{eid}: answer is a substring of its own grounding")

    def test_no_evidence_from_the_receiving_example_itself(self):
        for p in _PROPOSALS:
            self.assertNotIn(p["example_id"], p["evidence_example_ids"], msg=f"{p['example_id']}: self-cited")

    def test_no_first_person_language_in_any_wired_grounding(self):
        for eid in _ENRICHED_IDS:
            summary = _BY_ID[eid].inputs.specification.grounding.project.summary
            self.assertIsNone(FIRST_PERSON.search(summary), msg=f"{eid}: first-person found in {summary!r}")

    def test_no_gold_label_or_rubric_language_in_any_wired_grounding(self):
        for eid in _ENRICHED_IDS:
            summary = _BY_ID[eid].inputs.specification.grounding.project.summary
            self.assertIsNone(GOLD_LABEL_WORDS.search(summary), msg=f"{eid}: rubric/gold language found in {summary!r}")

    def test_evidence_ids_all_share_the_receiving_examples_source_id(self):
        for p in _PROPOSALS:
            receiving_source_id = _RAW_BY_ID[p["example_id"]]["source_id"]
            for eid in p["evidence_example_ids"]:
                self.assertEqual(
                    _RAW_BY_ID[eid]["source_id"], receiving_source_id,
                    msg=f"{p['example_id']}: evidence {eid} has a different source_id",
                )


# ═════════════════════════════════════════════════════════════════════════
# E. Split integrity
# ═════════════════════════════════════════════════════════════════════════
class TestSplitIntegrityUnaffectedByGroundingWiring(unittest.TestCase):
    def _split_json(self):
        path = os.path.join(_HERE, "artifacts", "four_dim_experiment_v2", "split.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_split_sizes_exactly_166_27_27(self):
        split = self._split_json()
        self.assertEqual(len(split["train_ids"]), 166)
        self.assertEqual(len(split["val_ids"]), 27)
        self.assertEqual(len(split["test_ids"]), 27)

    def test_split_seed_and_pool_size_unchanged(self):
        split = self._split_json()
        self.assertEqual(split["seed"], "four_dim_v2_split_348")
        self.assertEqual(split["total_pool_size"], 220)

    def test_pool_still_exactly_220_examples_no_new_no_deleted(self):
        self.assertEqual(len(_POOL), 220)
        split = self._split_json()
        split_ids = set(split["train_ids"]) | set(split["val_ids"]) | set(split["test_ids"])
        pool_ids = {e.metadata.example_id for e in _POOL}
        self.assertEqual(split_ids, pool_ids)

    def test_no_source_id_overlap_across_splits(self):
        split = self._split_json()
        source_of = {e.metadata.example_id: e.inputs.specification.source_id for e in _POOL}
        train_sources = {source_of[i] for i in split["train_ids"]}
        val_sources = {source_of[i] for i in split["val_ids"]}
        test_sources = {source_of[i] for i in split["test_ids"]}
        self.assertEqual(train_sources & val_sources, set())
        self.assertEqual(train_sources & test_sources, set())
        self.assertEqual(val_sources & test_sources, set())

    def test_grounding_wiring_did_not_touch_split_json_on_disk(self):
        import subprocess
        repo_root = os.path.dirname(os.path.dirname(_HERE))
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "main_cap/cap/artifacts/four_dim_experiment_v2/split.json"],
            cwd=repo_root, capture_output=True, text=True,
        )
        self.assertEqual(proc.stdout.strip(), "")


# ═════════════════════════════════════════════════════════════════════════
# F. Tokenization audit
# ═════════════════════════════════════════════════════════════════════════
class TestTokenizationAuditReport(unittest.TestCase):
    """Not a pass/fail correctness check on the count itself (some
    over-length examples pre-date this wiring) -- asserts the audit report
    exists, is internally consistent, and flags newly-affected examples."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(_HERE, "artifacts", "v3_grounding", "tokenization_audit.json")
        with open(path, encoding="utf-8") as f:
            cls.report = json.load(f)

    def test_report_covers_all_220_examples(self):
        self.assertEqual(self.report["total_examples"], 220)

    def test_before_wiring_only_one_example_exceeded_256(self):
        # gap20_v1_017 was already over 256 tokens pre-V3 (long answer alone),
        # independent of any grounding addition.
        self.assertEqual(self.report["before_wiring"]["exceeding_256"], ["gap20_v1_017"])

    def test_grounding_no_longer_pushes_any_example_over_256(self):
        # 2026-09-09 fix: gap20_v1_014 / gap20_v1_016 grounding fragments were
        # tightened (verbosity only, no evidence removed) specifically to
        # eliminate this. Both remain enriched -- their combined token count
        # just now fits within the unchanged 256-token max_length.
        self.assertEqual(self.report["newly_exceeding_256_due_to_grounding"], [])

    def test_after_wiring_only_the_original_pre_existing_example_exceeds_256(self):
        # gap20_v1_017 was already over 256 before any V3 grounding existed
        # (it is itself unenriched -- a long answer alone, unrelated to this
        # fix) and is deliberately left as pre-existing, acceptable truncation.
        self.assertEqual(self.report["after_wiring"]["exceeding_256"], ["gap20_v1_017"])

    def test_gap20_v1_014_and_016_are_still_enriched_and_now_under_256(self):
        for eid in ("gap20_v1_014", "gap20_v1_016"):
            self.assertIn(eid, _ENRICHED_IDS)
            row = next(r for r in self.report["rows"] if r["example_id"] == eid)
            self.assertLessEqual(row["after"], 256)


if __name__ == "__main__":
    unittest.main()
