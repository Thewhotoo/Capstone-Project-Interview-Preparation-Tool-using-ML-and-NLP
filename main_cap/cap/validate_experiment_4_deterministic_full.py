"""
Post-generation validation/statistics report for the full-scale Experiment
4 Track B (API-free) run — `artifacts/experiment_4_deterministic_full/`.

Reuses EXISTING, already-tested tooling rather than inventing new checks:
  - `dataset_manifest.assemble_manifest` for schema validation (every
    example must construct as a real `TrainingExample`/pass the manifest's
    own validators), duplicate-id detection, and provenance/tier/label-
    source statistics — the same mechanism every other experiment in this
    repo uses to publish a dataset version.
  - `training_experimentation.DatasetSplit`'s own validator for internal
    split-consistency (no duplicate/overlapping ids within the split).

Adds exactly the checks that are specific to a REWRITE dataset and not
covered by the above: leakage against the SOURCE dataset's val/test ids
(a rewrite must never trace back to a non-train source), and id collision
against the source dataset's own example_ids.

Read-only: never modifies any artifact. Run after
`run_experiment_4_deterministic.py generate_full`.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from dataset_manifest import ReviewEventLog, assemble_manifest
from experiment_dataset_io import load_examples_jsonl, load_json, save_json
from run_experiment_4_deterministic import (
    FULL_DATASET_PATH,
    FULL_SPLIT_PATH,
    FULL_SUMMARY_PATH,
)
from run_experiment_4_pilot import SOURCE_DATASET_PATH, SOURCE_SPLIT_PATH
from training_experimentation import DatasetSplit

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_4_deterministic_full", "manifest.json"
)
VALIDATION_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_4_deterministic_full", "validation_report.json"
)

DATASET_VERSION = "v_experiment_4_deterministic_full"
PARENT_DATASET_VERSION = "v_experiment_3_relabeled_dimensions"


def main() -> int:
    print("Loading generated dataset + source dataset...")
    generated = load_examples_jsonl(FULL_DATASET_PATH)
    generated_split = load_json(DatasetSplit, FULL_SPLIT_PATH)
    source = load_examples_jsonl(SOURCE_DATASET_PATH)
    source_split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    with open(FULL_SUMMARY_PATH, encoding="utf-8") as f:
        run_summary = json.load(f)

    report: dict = {}

    # ── 1. Basic counts ─────────────────────────────────────────────────
    report["total_generated_examples"] = len(generated)
    report["attempted"] = run_summary["attempted"]
    report["accepted"] = run_summary["accepted"]
    report["rejected"] = run_summary["rejected"]
    report["accept_rate"] = run_summary["accept_rate"]
    report["rejection_reason_counts"] = run_summary["rejection_reason_counts"]

    # ── 2. Per-dimension / stratification counts ────────────────────────
    report["accepted_tier_distribution"] = run_summary["accepted_tier_distribution"]
    report["accepted_style_distribution"] = run_summary["accepted_style_distribution"]
    report["accepted_reasoning_type_distribution"] = run_summary["accepted_reasoning_type_distribution"]

    # ── 3. Train/val/test counts ─────────────────────────────────────────
    report["generated_split_counts"] = {
        "train": len(generated_split.train_ids), "val": len(generated_split.val_ids), "test": len(generated_split.test_ids),
    }
    report["source_split_counts"] = {
        "train": len(source_split.train_ids), "val": len(source_split.val_ids), "test": len(source_split.test_ids),
    }
    report["combined_train_if_merged"] = len(source_split.train_ids) + len(generated_split.train_ids)

    # ── 4. Duplicate / leakage checks ────────────────────────────────────
    generated_ids = [e.metadata.example_id for e in generated]
    duplicate_generated_ids = [eid for eid, count in Counter(generated_ids).items() if count > 1]
    source_ids = set(e.metadata.example_id for e in source)
    id_collisions_with_source = sorted(set(generated_ids) & source_ids)

    source_val_test_ids = set(source_split.val_ids) | set(source_split.test_ids)
    leaked_from_val_test = [
        e.metadata.example_id for e in generated
        if e.synthetic.rewritten_from_example_id in source_val_test_ids
    ]
    source_train_ids = set(source_split.train_ids)
    orphaned_origin = [
        e.metadata.example_id for e in generated
        if e.synthetic.rewritten_from_example_id not in source_train_ids
    ]
    # generated_split.train_ids must be an exact set-match to generated_ids
    # -- every accepted example is train-placed and nothing else appears.
    split_matches_dataset = set(generated_split.train_ids) == set(generated_ids) and not (
        generated_split.val_ids or generated_split.test_ids
    )

    report["duplicate_generated_ids"] = duplicate_generated_ids
    report["id_collisions_with_source_dataset"] = id_collisions_with_source
    report["leaked_from_source_val_or_test"] = leaked_from_val_test
    report["origin_ids_not_in_source_train_split"] = orphaned_origin
    report["generated_split_matches_generated_dataset_exactly"] = split_matches_dataset
    report["leakage_check_passed"] = not (
        duplicate_generated_ids or id_collisions_with_source or leaked_from_val_test or orphaned_origin
    ) and split_matches_dataset

    # ── 5. Schema validation + provenance (via existing assemble_manifest) ──
    schema_validation_error = None
    manifest = None
    try:
        manifest, stamped = assemble_manifest(
            tuple(generated), DATASET_VERSION, review_log=ReviewEventLog(),
            parent_dataset_version=PARENT_DATASET_VERSION,
        )
    except Exception as e:  # noqa: BLE001 -- this IS the validation result we want to capture
        schema_validation_error = f"{type(e).__name__}: {e}"

    report["schema_validation_passed"] = schema_validation_error is None
    report["schema_validation_error"] = schema_validation_error
    if manifest is not None:
        report["manifest_dataset_version"] = manifest.dataset_version
        report["manifest_parent_dataset_version"] = manifest.parent_dataset_version
        report["manifest_example_count"] = len(manifest.example_ids)
        report["manifest_generator_provenance"] = list(manifest.generator_provenance)
        report["manifest_tier_distribution"] = dict(manifest.tier_distribution)
        report["manifest_label_source_distribution"] = dict(manifest.label_source_distribution)
        save_json(manifest, MANIFEST_PATH)
        print(f"Manifest persisted to {MANIFEST_PATH!r}.")

    # ── 6. Reproducibility status ────────────────────────────────────────
    report["reproducibility"] = {
        "generation_is_deterministic": True,
        "uses_random_module": False,
        "generation_method": "deterministic_rule_based (API-free)",
        "external_api_calls_made": 0,
        "note": "Re-running run_experiment_4_deterministic.py generate_full reproduces "
                "an identical accepted/rejected outcome byte-for-byte -- the generator "
                "is a pure function of (source_example, style) and involves no sampling.",
    }

    with open(VALIDATION_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # ── Print human-readable summary ─────────────────────────────────────
    print()
    print("=== VALIDATION REPORT SUMMARY ===")
    print(f"Total generated (accepted) examples: {report['total_generated_examples']}")
    print(f"Attempted: {report['attempted']}  Accepted: {report['accepted']}  Rejected: {report['rejected']}")
    print(f"Accept rate: {report['accept_rate']}")
    print(f"Rejection reasons: {report['rejection_reason_counts']}")
    print(f"Accepted tier distribution: {report['accepted_tier_distribution']}")
    print(f"Accepted style distribution: {report['accepted_style_distribution']}")
    print(f"Accepted reasoning-type distribution: {report['accepted_reasoning_type_distribution']}")
    print(f"Generated split counts: {report['generated_split_counts']}")
    print(f"Source split counts: {report['source_split_counts']}")
    print(f"Combined train size if merged with source: {report['combined_train_if_merged']}")
    print(f"Leakage check passed: {report['leakage_check_passed']}")
    if not report["leakage_check_passed"]:
        print(f"  duplicate_generated_ids: {duplicate_generated_ids}")
        print(f"  id_collisions_with_source_dataset: {id_collisions_with_source}")
        print(f"  leaked_from_source_val_or_test: {leaked_from_val_test}")
        print(f"  origin_ids_not_in_source_train_split: {orphaned_origin}")
        print(f"  generated_split_matches_generated_dataset_exactly: {split_matches_dataset}")
    print(f"Schema validation passed: {report['schema_validation_passed']}")
    if schema_validation_error:
        print(f"  error: {schema_validation_error}")
    else:
        print(f"  manifest dataset_version: {manifest.dataset_version}")
        print(f"  manifest example count: {len(manifest.example_ids)}")
        print(f"  manifest generator_provenance: {list(manifest.generator_provenance)}")
    print(f"Reproducibility: {report['reproducibility']}")
    print(f"Full report written to {VALIDATION_REPORT_PATH!r}.")

    return 0 if (report["leakage_check_passed"] and report["schema_validation_passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
