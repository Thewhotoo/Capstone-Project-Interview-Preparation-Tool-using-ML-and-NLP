"""
Experiment 4 — Prepare Training Data: combines the source dataset
(`v_experiment_3_relabeled_dimensions`, 2,479 examples) with the validated
API-free rewrite-augmentation output (`v_experiment_4_deterministic_full`,
3,185 examples) into ONE Colab-ready dataset for DeBERTa training/
retraining. Deterministic, read-only w.r.t. both inputs, zero external
API calls, zero GPU required (this step is pure I/O + validation).

NOT A NEW SUBSYSTEM: this is a thin orchestration script over already-
existing, already-tested machinery --
`experiment_dataset_io.{load_examples_jsonl, load_json, save_examples_jsonl, save_json}`,
`training_experimentation.DatasetSplit` (its own validator is what proves
no duplicate/overlapping ids), and `dataset_manifest.assemble_manifest`
(the same schema-validation/dedup/provenance-statistics mechanism every
other experiment's published dataset version already goes through).

WHY `allow_reversioning=True`: the 2,479 source examples already carry
`metadata.dataset_version="v_experiment_3_relabeled_dimensions"` (stamped
when that dataset was published). Combining them into a NEW lineage
(`v_experiment_4_combined`) is exactly the explicit, deliberate re-
versioning `assemble_manifest`'s docstring anticipates -- not an accident.
The augmented 3,185 examples are unversioned (never previously published),
so this is their first stamping.

SINGLE-PARENT LIMITATION (honest, not silently glossed over):
`DatasetManifest.parent_dataset_version` is a single `Optional[str]` field
-- it cannot represent "descends from two parents." Set to
`v_experiment_3_relabeled_dimensions` (the base lineage) below; the
augmented dataset's own provenance
(`generator_provenance=[("deterministic_rewrite","1.0.0")]`, visible in
the assembled manifest) is how the second lineage stays traceable, not a
second parent pointer.

NO LEAKAGE, BY CONSTRUCTION AND VERIFIED: combined val_ids/test_ids are
copied UNCHANGED from the source split (augmentation never touches them);
combined train_ids = source train_ids + augmented train_ids (the
augmented split has no val/test ids at all -- verified before combining,
not assumed). `DatasetSplit`'s own validator (no duplicate ids across or
within train/val/test) is the structural proof this holds.

Usage: `python run_experiment_4_prepare_training_data.py`
"""

from __future__ import annotations

import json
import os
import sys
import time

from dataset_manifest import ReviewEventLog, assemble_manifest
from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from model_dataset import score_to_tier
from model_evaluator import _CONCEPT_STATUS_ORDER, _ORDINAL_GRADES
from model_heads import _MISSING_REASONING_CATEGORIES, _NUM_ORDINAL_CLASSES_DEFAULT
from reasoning_dimension_relevance import ALL_DIMENSIONS
from run_experiment_4_pilot import SOURCE_DATASET_PATH, SOURCE_SPLIT_PATH
from training_experimentation import DatasetSplit

_HERE = os.path.dirname(os.path.abspath(__file__))

AUGMENTED_DATASET_PATH = os.path.join(_HERE, "artifacts", "experiment_4_deterministic_full", "dataset.jsonl")
AUGMENTED_SPLIT_PATH = os.path.join(_HERE, "artifacts", "experiment_4_deterministic_full", "split.json")

OUTPUT_DIR = os.path.join(_HERE, "artifacts", "experiment_4_combined")
DATASET_PATH = os.path.join(OUTPUT_DIR, "dataset.jsonl")
SPLIT_PATH = os.path.join(OUTPUT_DIR, "split.json")
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "manifest.json")
LABEL_MAPPINGS_PATH = os.path.join(OUTPUT_DIR, "label_mappings.json")
PREPARE_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "prepare_summary.json")

COMBINED_DATASET_VERSION = "v_experiment_4_combined"
SOURCE_DATASET_VERSION = "v_experiment_3_relabeled_dimensions"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def build_label_mappings() -> dict:
    """Machine-readable snapshot of every label mapping the training
    heads/dataset adapter (`model_heads.py`, `model_dataset.py`,
    `model_evaluator.py`) already use as Python constants -- exported here
    as plain JSON so it can be inspected/diffed without importing this
    repo's code, and so a consistency test can catch drift between this
    file and the actual constants (see
    test_run_experiment_4_prepare_training_data.py)."""
    return {
        "dimension_names": list(ALL_DIMENSIONS),
        "missing_reasoning_categories": list(_MISSING_REASONING_CATEGORIES),
        "concept_status_order": [s.value for s in _CONCEPT_STATUS_ORDER],
        "num_ordinal_classes": _NUM_ORDINAL_CLASSES_DEFAULT,
        "ordinal_class_index_to_grade": list(_ORDINAL_GRADES),
        "dimension_score_to_tier_cutpoints": {
            "excellent": {"min_score": 0.80, "tier_index": 4},
            "good": {"min_score": 0.60, "tier_index": 3},
            "adequate": {"min_score": 0.40, "tier_index": 2},
            "weak": {"min_score": 0.25, "tier_index": 1},
            "poor": {"min_score": 0.0, "tier_index": 0},
        },
        "backbone": {"hf_model_id": "microsoft/deberta-v3-base", "pooling": "cls"},
        "task_formulation": {
            "main_input": "tokenizer(question_text, answer_text) sentence-pair",
            "concept_input": "tokenizer(answer_text, concept) sentence-pair, one per expected concept",
            "per_dimension_head": "CORAL rank-consistent ordinal regression, 5 classes",
            "missing_reasoning_head": "shared multi-label presence (BCE) + masked severity regression (smooth-L1)",
            "concept_head": "3-class classification (demonstrated/superficial/omitted)",
        },
    }


def main() -> int:
    _log("=== Experiment 4 / Phase: PREPARE TRAINING DATA (I/O only, no GPU, no API calls) ===")
    for path in (SOURCE_DATASET_PATH, SOURCE_SPLIT_PATH, AUGMENTED_DATASET_PATH, AUGMENTED_SPLIT_PATH):
        if not os.path.exists(path):
            _log(f"BLOCKER: {path!r} not found.")
            return 1
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    source_examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    source_split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    augmented_examples = load_examples_jsonl(AUGMENTED_DATASET_PATH)
    augmented_split = load_json(DatasetSplit, AUGMENTED_SPLIT_PATH)
    _log(f"Source: {len(source_examples)} examples (train={len(source_split.train_ids)}/"
         f"val={len(source_split.val_ids)}/test={len(source_split.test_ids)}).")
    _log(f"Augmented: {len(augmented_examples)} examples (train={len(augmented_split.train_ids)}/"
         f"val={len(augmented_split.val_ids)}/test={len(augmented_split.test_ids)}).")

    if augmented_split.val_ids or augmented_split.test_ids:
        _log("BLOCKER: augmented split unexpectedly contains val/test ids -- augmentation must be train-only.")
        return 1

    combined_examples = source_examples + augmented_examples
    combined_split = DatasetSplit(
        train_ids=source_split.train_ids + augmented_split.train_ids,
        val_ids=source_split.val_ids,
        test_ids=source_split.test_ids,
    )  # raises if any duplicate/overlapping id exists -- the leakage proof.
    _log(f"Combined: {len(combined_examples)} examples "
         f"(train={len(combined_split.train_ids)}/val={len(combined_split.val_ids)}/test={len(combined_split.test_ids)}).")

    manifest, stamped_examples = assemble_manifest(
        combined_examples, COMBINED_DATASET_VERSION, review_log=ReviewEventLog(),
        parent_dataset_version=SOURCE_DATASET_VERSION, allow_reversioning=True,
    )
    _log(f"Manifest assembled: dataset_version={manifest.dataset_version!r}, "
         f"{len(manifest.example_ids)} examples, generator_provenance={list(manifest.generator_provenance)}.")

    save_examples_jsonl(stamped_examples, DATASET_PATH)
    save_json(combined_split, SPLIT_PATH)
    save_json(manifest, MANIFEST_PATH)

    label_mappings = build_label_mappings()
    with open(LABEL_MAPPINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(label_mappings, f, indent=2)

    summary = {
        "combined_dataset_version": COMBINED_DATASET_VERSION,
        "source_dataset_version": SOURCE_DATASET_VERSION,
        "source_example_count": len(source_examples),
        "augmented_example_count": len(augmented_examples),
        "combined_example_count": len(combined_examples),
        "combined_split_counts": {
            "train": len(combined_split.train_ids), "val": len(combined_split.val_ids), "test": len(combined_split.test_ids),
        },
        "generator_provenance": list(manifest.generator_provenance),
        "tier_distribution": dict(manifest.tier_distribution),
        "label_source_distribution": dict(manifest.label_source_distribution),
    }
    with open(PREPARE_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    _log(f"Wrote dataset/split/manifest/label_mappings/summary to {OUTPUT_DIR!r}.")
    _log("=== PREPARE TRAINING DATA COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
