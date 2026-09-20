"""
Builds the v5_overall_1088 training pool — READ-ONLY merge of:
    four_dim_overall_v4_5000 (the frozen 1,003-example dataset + its frozen
    702/150/151 split), and
    v5_short_quality_calibration_80 (the 85-example calibration set, ids
    v5cal_001..v5cal_085).

Neither source is ever opened for writing. This script only ever writes
under artifacts/overall_v5_1088/ — a new, isolated directory.

MERGE RULE (the "safest possible" addition, minimizing the diff against the
frozen baseline): the 85 calibration examples are appended to TRAIN ONLY.
val_ids and test_ids are copied byte-for-byte from the original split.json —
untouched, unreordered, unfiltered. This guarantees:
    - the exact original 151 test ids are preserved (Requirement 7)
    - the exact original 150 val ids are preserved (Requirement 8)
    - none of the 85 calibration examples can ever land in test (Requirement 9)
    - the only thing that changes vs. the 1003 baseline's dataloaders is a
      larger, higher-diversity TRAIN set — nothing about val/test changes,
      so the old-vs-new 151-test comparison is apples-to-apples.

No Gemini / external LLM / network call anywhere in this file.
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

SRC_1003_DIR = os.path.join(_HERE, "artifacts", "four_dim_overall_v4_5000", "dataset")
SRC_CAL_DIR = os.path.join(_HERE, "artifacts", "v5_short_quality_calibration_80", "dataset")

OUT_DIR = os.path.join(_HERE, "artifacts", "overall_v5_1088", "dataset")

EXPECTED_1003_TOTAL = 1003
EXPECTED_1003_SPLIT = (702, 150, 151)
EXPECTED_CAL_TOTAL = 85


def _load_jsonl(path: str) -> list[dict]:
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main() -> int:
    examples_1003 = _load_jsonl(os.path.join(SRC_1003_DIR, "examples.jsonl"))
    with open(os.path.join(SRC_1003_DIR, "split.json"), encoding="utf-8") as f:
        split_1003 = json.load(f)
    examples_cal = _load_jsonl(os.path.join(SRC_CAL_DIR, "examples.jsonl"))

    assert len(examples_1003) == EXPECTED_1003_TOTAL, (
        f"BLOCKER: expected {EXPECTED_1003_TOTAL} examples in the frozen 1003 dataset, "
        f"got {len(examples_1003)}. Refusing to build the pool."
    )
    actual_split_counts = (len(split_1003["train_ids"]), len(split_1003["val_ids"]), len(split_1003["test_ids"]))
    assert actual_split_counts == EXPECTED_1003_SPLIT, (
        f"BLOCKER: expected split counts {EXPECTED_1003_SPLIT}, got {actual_split_counts}."
    )
    assert len(examples_cal) == EXPECTED_CAL_TOTAL, (
        f"BLOCKER: expected {EXPECTED_CAL_TOTAL} calibration examples, got {len(examples_cal)}."
    )

    ids_1003 = {e["metadata"]["example_id"] for e in examples_1003}
    ids_cal = {e["metadata"]["example_id"] for e in examples_cal}
    overlap = ids_1003 & ids_cal
    assert not overlap, f"BLOCKER: example_id collision between 1003 and calibration sets: {overlap}"

    source_ids_1003 = {e["inputs"]["specification"]["source_id"] for e in examples_1003}
    source_ids_cal = {e["inputs"]["specification"]["source_id"] for e in examples_cal}
    source_overlap = source_ids_1003 & source_ids_cal
    assert not source_overlap, f"BLOCKER: source_id collision (group leakage risk): {source_overlap}"

    # ── merged pool: 1003 examples + 85 calibration examples, untouched ────
    merged_examples = examples_1003 + examples_cal

    # ── merged split: val/test copied verbatim; train = original train + all 85 cal ids ──
    train_ids = tuple(split_1003["train_ids"]) + tuple(sorted(ids_cal))
    val_ids = tuple(split_1003["val_ids"])
    test_ids = tuple(split_1003["test_ids"])

    # ── integrity checks (fail loudly rather than silently building a bad pool) ──
    assert set(val_ids) == set(split_1003["val_ids"]) and len(val_ids) == 150, "val_ids must be untouched (150)"
    assert set(test_ids) == set(split_1003["test_ids"]) and len(test_ids) == 151, "test_ids must be untouched (151)"
    assert ids_cal <= set(train_ids), "all 85 calibration ids must be in train"
    assert not (ids_cal & set(val_ids)), "no calibration id may appear in val"
    assert not (ids_cal & set(test_ids)), "no calibration id may appear in test"
    assert len(set(train_ids)) == len(train_ids), "train_ids must be unique (no duplicate ids)"
    assert len(train_ids) + len(val_ids) + len(test_ids) == len(merged_examples), (
        "split must cover every merged example exactly once"
    )
    all_split_ids = set(train_ids) | set(val_ids) | set(test_ids)
    all_example_ids = {e["metadata"]["example_id"] for e in merged_examples}
    assert all_split_ids == all_example_ids, "split ids and example ids must match exactly"

    # ── group-aware leakage check across the merged split (by source_id) ───
    by_id = {e["metadata"]["example_id"]: e for e in merged_examples}
    groups = {
        "train": {by_id[i]["inputs"]["specification"]["source_id"] for i in train_ids},
        "val": {by_id[i]["inputs"]["specification"]["source_id"] for i in val_ids},
        "test": {by_id[i]["inputs"]["specification"]["source_id"] for i in test_ids},
    }
    cross_overlaps = {
        "train|val": sorted(groups["train"] & groups["val"]),
        "train|test": sorted(groups["train"] & groups["test"]),
        "val|test": sorted(groups["val"] & groups["test"]),
    }
    assert not any(cross_overlaps.values()), f"BLOCKER: group leakage across merged split: {cross_overlaps}"

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "examples.jsonl"), "w", encoding="utf-8") as f:
        for e in merged_examples:
            f.write(json.dumps(e) + "\n")

    merged_split = {
        "train_ids": list(train_ids), "val_ids": list(val_ids), "test_ids": list(test_ids),
        "ratios": split_1003["ratios"], "seed": split_1003["seed"],
        "note": (
            "v5_overall_1088: val_ids/test_ids copied byte-for-byte from "
            "four_dim_overall_v4_5000/dataset/split.json. train_ids = original 702 "
            "train ids + all 85 v5_short_quality_calibration_80 ids (v5cal_001..v5cal_085). "
            "No calibration id appears in val or test."
        ),
    }
    with open(os.path.join(OUT_DIR, "split.json"), "w", encoding="utf-8") as f:
        json.dump(merged_split, f, indent=2)

    manifest = {
        "dataset_version": "overall_v5_1088",
        "total_examples": len(merged_examples),
        "sources": {
            "four_dim_overall_v4_5000": {"count": len(examples_1003), "role": "frozen baseline, untouched"},
            "v5_short_quality_calibration_80": {"count": len(examples_cal), "role": "appended to train only"},
        },
        "split_counts": {"train": len(train_ids), "val": len(val_ids), "test": len(test_ids)},
        "val_ids_identical_to_1003_baseline": set(val_ids) == set(split_1003["val_ids"]),
        "test_ids_identical_to_1003_baseline": set(test_ids) == set(split_1003["test_ids"]),
        "calibration_ids_in_train_only": True,
        "group_leakage_across_split": cross_overlaps,
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))
    print(f"\nWrote merged pool to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
