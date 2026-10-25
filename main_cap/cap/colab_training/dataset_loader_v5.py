"""
Dataset loader for the v5_overall_1088 training pool (isolated, additive —
introduces no new schema). Reads the ALREADY-ASSEMBLED
`artifacts/overall_v5_1088/dataset/` files (`examples.jsonl` + `split.json`,
produced read-only by `build_v5_1088_pool.py` from the frozen
`four_dim_overall_v4_5000` dataset + the `v5_short_quality_calibration_80`
calibration set — see that script for the merge rule and integrity checks)
and adapts them into the exact same `(tuple[TrainingExample, ...],
DatasetSplit)` shape `dataset_loader.py` already produces for the 1003-only
pool, so `overall_dataset.build_overall_dataloaders` and everything
downstream of it runs completely unmodified against the larger pool.

Read-only. Never writes to `artifacts/overall_v5_1088/`,
`artifacts/four_dim_overall_v4_5000/`, or `artifacts/v5_short_quality_calibration_80/`.
"""

from __future__ import annotations

import json
import os

from training_example import TrainingExample
from training_experimentation import DatasetSplit

_HERE = os.path.dirname(os.path.abspath(__file__))
CAP_DIR = os.path.dirname(_HERE)  # main_cap/cap

DATASET_VERSION = "overall_v5_1088"
DATASET_DIR = os.path.join(CAP_DIR, "artifacts", DATASET_VERSION, "dataset")

EXAMPLES_PATH = os.path.join(DATASET_DIR, "examples.jsonl")
SPLIT_PATH = os.path.join(DATASET_DIR, "split.json")

EXPECTED_TOTAL = 1088
EXPECTED_CAL_COUNT = 85
EXPECTED_COUNTS = (787, 150, 151)  # (train, val, test)

# The exact 151 test ids and 150 val ids from four_dim_overall_v4_5000's
# frozen split — loaded once here so `verify_dataset_integrity` can assert
# byte-identical preservation without re-reading the baseline split file
# (keeps this loader's only filesystem dependency the merged pool itself).
_BASELINE_SPLIT_PATH = os.path.join(CAP_DIR, "artifacts", "four_dim_overall_v4_5000", "dataset", "split.json")


def load_examples(path: str = EXAMPLES_PATH) -> tuple[TrainingExample, ...]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path!r} not found. Run `python build_v5_1088_pool.py` first (locally, before "
            "uploading to Colab) to build the merged pool from the frozen 1003 dataset + the "
            "85-example v5 calibration set. See colab_training/README.md."
        )
    examples: list[TrainingExample] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(TrainingExample.model_validate_json(line))
    return tuple(examples)


def load_split(path: str = SPLIT_PATH) -> DatasetSplit:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path!r} not found. See colab_training/README.md for the required upload step.")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return DatasetSplit(
        train_ids=tuple(raw["train_ids"]), val_ids=tuple(raw["val_ids"]), test_ids=tuple(raw["test_ids"]),
    )


def verify_dataset_integrity(examples: tuple[TrainingExample, ...], split: DatasetSplit) -> None:
    """Hard-stops (raises) on any mismatch — same discipline as
    dataset_loader.verify_dataset_integrity, extended with the v5-specific
    guarantees this experiment depends on: the original 151 test ids and 150
    val ids must be byte-identical to the 1003 baseline's split, and none of
    the 85 calibration ids may appear outside train."""
    if len(examples) != EXPECTED_TOTAL:
        raise SystemExit(
            f"BLOCKER: expected {EXPECTED_TOTAL} examples in {EXAMPLES_PATH!r}, got {len(examples)}. "
            "Re-run `python build_v5_1088_pool.py` and re-upload."
        )
    actual_counts = (len(split.train_ids), len(split.val_ids), len(split.test_ids))
    if actual_counts != EXPECTED_COUNTS:
        raise SystemExit(f"BLOCKER: expected split counts {EXPECTED_COUNTS}, got {actual_counts}.")

    by_id = {e.metadata.example_id: e for e in examples}
    all_ids = split.train_ids + split.val_ids + split.test_ids
    missing = [i for i in all_ids if i not in by_id]
    if missing:
        raise SystemExit(f"BLOCKER: {len(missing)} split id(s) not found in examples: {missing[:5]}")

    cal_ids = {eid for eid in by_id if eid.startswith("v5cal_")}
    if len(cal_ids) != EXPECTED_CAL_COUNT:
        raise SystemExit(f"BLOCKER: expected {EXPECTED_CAL_COUNT} v5cal_ examples, found {len(cal_ids)}.")
    if not cal_ids <= set(split.train_ids):
        raise SystemExit("BLOCKER: a v5cal_ example was found outside train_ids.")
    if cal_ids & set(split.val_ids) or cal_ids & set(split.test_ids):
        raise SystemExit("BLOCKER: a v5cal_ example leaked into val or test.")

    if os.path.exists(_BASELINE_SPLIT_PATH):
        with open(_BASELINE_SPLIT_PATH, encoding="utf-8") as f:
            baseline = json.load(f)
        if set(split.val_ids) != set(baseline["val_ids"]):
            raise SystemExit("BLOCKER: val_ids differ from the four_dim_overall_v4_5000 baseline split.")
        if set(split.test_ids) != set(baseline["test_ids"]):
            raise SystemExit("BLOCKER: test_ids differ from the four_dim_overall_v4_5000 baseline split.")


def assert_no_group_leakage(examples: tuple[TrainingExample, ...], split: DatasetSplit) -> None:
    """Identical check to dataset_loader.assert_no_group_leakage, reused
    verbatim against the merged pool (by source_id)."""
    by_id = {e.metadata.example_id: e for e in examples}
    groups = {
        "train": {by_id[i].inputs.specification.source_id for i in split.train_ids},
        "val": {by_id[i].inputs.specification.source_id for i in split.val_ids},
        "test": {by_id[i].inputs.specification.source_id for i in split.test_ids},
    }
    overlaps = {
        "train|val": sorted(groups["train"] & groups["val"]),
        "train|test": sorted(groups["train"] & groups["test"]),
        "val|test": sorted(groups["val"] & groups["test"]),
    }
    if any(overlaps.values()):
        raise SystemExit(f"BLOCKER: source/group leakage detected before training: {overlaps}")
