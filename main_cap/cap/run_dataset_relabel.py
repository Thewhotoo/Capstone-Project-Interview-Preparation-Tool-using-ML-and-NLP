"""
Dataset Relabeling — Stage 1A of the DeBERTa Augmentation milestone.

Reads Experiment 2's already-generated dataset (`artifacts/experiment_2/`),
applies `dataset_relabeling.relabel_example` to every example (Part 1 of the
reviewed design: deterministic per-dimension scores from each example's own
already-serialized recipe data — zero new generation, zero new text),
re-assembles a `DatasetManifest` under a new `dataset_version` lineaged to
the original, and persists the result to `artifacts/experiment_3_relabeled/`.

SCOPE, EXACTLY AS SPECIFIED FOR STAGE 1A: relabeling, dataset generation,
dataset versioning, and manifest assembly ONLY. This script does not
retrain, does not evaluate, and does not import `model_dataset.py`/
`model_heads.py`/anything trainer-related — Stage 1B is a separate,
deliberately later step.

THE SPLIT IS REUSED, NOT RECOMPUTED: `DatasetSplit` partitions by
`TrainingExample.metadata.example_id` alone (training_experimentation.py),
and relabeling never adds, removes, or renames an example — every
example_id in the relabeled set is identical to Experiment 2's. Recomputing
the split would be redundant work and would risk silently producing a
different partition; copying it forward instead guarantees the exact same
specification-grouped, leakage-free split this dataset was already
validated against.

Usage: `python run_dataset_relabel.py relabel`
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter

from dataset_manifest import assemble_manifest
from dataset_relabeling import relabel_example
from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from training_experimentation import DatasetSplit

SOURCE_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_3_relabeled")

SOURCE_DATASET_VERSION = "v_experiment_2_scaled_library"
DATASET_VERSION = "v_experiment_3_relabeled_dimensions"

SOURCE_DATASET_PATH = os.path.join(SOURCE_ARTIFACTS_DIR, "dataset.jsonl")
SOURCE_SPLIT_PATH = os.path.join(SOURCE_ARTIFACTS_DIR, "split.json")

DATASET_PATH = os.path.join(ARTIFACTS_DIR, "dataset.jsonl")
MANIFEST_PATH = os.path.join(ARTIFACTS_DIR, "manifest.json")
SPLIT_PATH = os.path.join(ARTIFACTS_DIR, "split.json")
RELABEL_SUMMARY_PATH = os.path.join(ARTIFACTS_DIR, "relabel_summary.json")


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _dimension_score_deltas(before, after) -> list[dict]:
    """Per-example, per-dimension (name, old_score, new_score) rows for
    every dimension whose score actually changed — the evidence base for
    'explain exactly what changed', not a claim, a computed diff."""
    rows = []
    for old_ex, new_ex in zip(before, after):
        old_by_name = {d.name: d.score for d in old_ex.labels.dimension_labels}
        new_by_name = {d.name: d.score for d in new_ex.labels.dimension_labels}
        for name, new_score in new_by_name.items():
            old_score = old_by_name.get(name)
            if old_score is not None and abs(old_score - new_score) > 1e-9:
                rows.append({
                    "example_id": new_ex.metadata.example_id, "dimension": name,
                    "old_score": old_score, "new_score": new_score,
                })
    return rows


def phase_relabel() -> int:
    _log("=== Dataset Relabeling / Phase: RELABEL (Stage 1A) ===")
    if not os.path.exists(SOURCE_DATASET_PATH):
        _log(f"BLOCKER: {SOURCE_DATASET_PATH!r} not found -- run 'run_experiment_2.py generate' first.")
        return 1
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    _log(f"Loaded {len(examples)} examples from {SOURCE_DATASET_PATH!r}.")

    non_synthetic = sum(1 for e in examples if e.synthetic is None)
    if non_synthetic:
        _log(f"NOTE: {non_synthetic} example(s) have no synthetic metadata and will pass through unchanged.")

    relabeled = tuple(relabel_example(e) for e in examples)
    _log(f"Relabeled {len(relabeled)} examples (dimension_labels recomputed from each example's own recipe data).")

    deltas = _dimension_score_deltas(examples, relabeled)
    changed_examples = len({row["example_id"] for row in deltas})
    _log(f"Score changes: {len(deltas)} individual dimension scores changed across {changed_examples}/{len(examples)} examples.")
    by_dimension = Counter(row["dimension"] for row in deltas)
    _log(f"Changes by dimension: {dict(sorted(by_dimension.items()))}")

    # Re-stamp under a new dataset_version. Every example already carries
    # SOURCE_DATASET_VERSION from Experiment 2's own assembly -- this is a
    # deliberate re-versioning (design decision 3, dataset_manifest.py),
    # not an oversight, so allow_reversioning=True is passed explicitly.
    manifest, stamped = assemble_manifest(
        relabeled, dataset_version=DATASET_VERSION,
        parent_dataset_version=SOURCE_DATASET_VERSION, allow_reversioning=True,
    )
    _log(f"DatasetManifest assembled: {len(manifest.example_ids)} examples, "
         f"tier_distribution={dict(manifest.tier_distribution)}, "
         f"label_source_distribution={dict(manifest.label_source_distribution)}.")

    # Sanity: relabeling must never add, remove, or reorder examples.
    original_ids = {e.metadata.example_id for e in examples}
    stamped_ids = {e.metadata.example_id for e in stamped}
    if original_ids != stamped_ids:
        _log("BLOCKER: relabeled example_id set does not match the source set.")
        return 1

    split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    split_ids = set(split.train_ids) | set(split.val_ids) | set(split.test_ids)
    if split_ids != stamped_ids:
        _log("BLOCKER: source split's example_ids do not match the relabeled dataset's example_ids.")
        return 1
    _log(f"Split reused unchanged from {SOURCE_SPLIT_PATH!r}: "
         f"train={len(split.train_ids)}, val={len(split.val_ids)}, test={len(split.test_ids)}.")

    save_examples_jsonl(stamped, DATASET_PATH)
    save_json(manifest, MANIFEST_PATH)
    save_json(split, SPLIT_PATH)

    import json
    with open(RELABEL_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "source_dataset_version": SOURCE_DATASET_VERSION, "dataset_version": DATASET_VERSION,
            "total_examples": len(examples), "examples_with_changed_scores": changed_examples,
            "total_score_changes": len(deltas), "changes_by_dimension": dict(sorted(by_dimension.items())),
            "sample_changes": deltas[:20],
        }, f, indent=2)
    _log(f"Persisted dataset/manifest/split/relabel_summary to {ARTIFACTS_DIR!r}.")
    _log("=== RELABEL PHASE COMPLETE ===")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "relabel":
        print("Usage: python run_dataset_relabel.py relabel", file=sys.stderr)
        return 2
    return phase_relabel()


if __name__ == "__main__":
    sys.exit(main())
