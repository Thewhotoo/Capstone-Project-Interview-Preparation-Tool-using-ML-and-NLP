"""
Dataset loader for the v4_1003 single-overall training experiment (isolated,
additive; introduces no new schema). Reads the ALREADY-ASSEMBLED
`four_dim_overall_v4_5000` dataset artifacts (`dataset/examples.jsonl` +
`dataset/split.json`, produced by `v4_5000_build.py assemble` and never
touched by this package) and adapts them into the exact same
`(tuple[TrainingExample, ...], DatasetSplit)` shape
`run_overall_single_training.py`'s `train()` already builds from
`four_dim_experiment_v2_split.load_v2_pool()` + the frozen V2 split file --
so `overall_dataset.build_overall_dataloaders` and everything downstream of
it runs completely unmodified against the new, larger dataset.

Also loads the raw authored `batches/*.jsonl` metadata (hard_case,
humanized, project_family, question_form, intent, humanization_style) —
NOT used for training (the model only ever sees question/grounding/
expected_concepts/answer via `overall_dataset.collate_fn`), only for the
qualitative breakdown analysis in `evaluate_overall.py`. Frozen-pool
examples (ids not present in any batch file) simply have no such metadata
and are reported as `provenance="frozen"`.

Read-only. Never writes to `artifacts/four_dim_overall_v4_5000/`.
"""

from __future__ import annotations

import glob
import json
import os

from training_example import TrainingExample
from training_experimentation import DatasetSplit

_HERE = os.path.dirname(os.path.abspath(__file__))
CAP_DIR = os.path.dirname(_HERE)  # main_cap/cap

DATASET_VERSION = "four_dim_overall_v4_5000"
DATASET_DIR = os.path.join(CAP_DIR, "artifacts", DATASET_VERSION, "dataset")
BATCHES_DIR = os.path.join(CAP_DIR, "artifacts", DATASET_VERSION, "batches")

EXAMPLES_PATH = os.path.join(DATASET_DIR, "examples.jsonl")
SPLIT_PATH = os.path.join(DATASET_DIR, "split.json")

EXPECTED_TOTAL = 1003
EXPECTED_FROZEN = 220
EXPECTED_COUNTS = (702, 150, 151)  # (train, val, test)


def load_examples(path: str = EXAMPLES_PATH) -> tuple[TrainingExample, ...]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path!r} not found. artifacts/ is .gitignore'd -- this file is NOT pulled in "
            "by `git clone`. Upload dataset/examples.jsonl (and dataset/split.json) into "
            "this exact path before running training/evaluation. See colab_training/README.md."
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
        raise FileNotFoundError(
            f"{path!r} not found. See colab_training/README.md for the required upload step."
        )
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return DatasetSplit(
        train_ids=tuple(raw["train_ids"]), val_ids=tuple(raw["val_ids"]), test_ids=tuple(raw["test_ids"]),
    )


def verify_dataset_integrity(examples: tuple[TrainingExample, ...], split: DatasetSplit) -> None:
    """Hard-stops (raises) rather than silently continuing on any mismatch —
    per explicit instruction: never train against a dataset that doesn't
    match the audited, frozen 1,003-example state."""
    if len(examples) != EXPECTED_TOTAL:
        raise SystemExit(
            f"BLOCKER: expected {EXPECTED_TOTAL} examples in {EXAMPLES_PATH!r}, got {len(examples)}. "
            "Refusing to train against an unexpected dataset. Re-run "
            "`python v4_5000_build.py assemble` in the source environment and re-upload."
        )
    actual_counts = (len(split.train_ids), len(split.val_ids), len(split.test_ids))
    if actual_counts != EXPECTED_COUNTS:
        raise SystemExit(
            f"BLOCKER: expected split counts {EXPECTED_COUNTS} (train/val/test), got {actual_counts}. "
            f"Refusing to train against an unexpected split."
        )
    by_id = {e.metadata.example_id: e for e in examples}
    all_ids = split.train_ids + split.val_ids + split.test_ids
    missing = [i for i in all_ids if i not in by_id]
    if missing:
        raise SystemExit(f"BLOCKER: {len(missing)} split id(s) not found in examples: {missing[:5]}")
    frozen_ids = [eid for eid in by_id if eid.startswith("seed_v1") or eid.startswith("v2t50") or eid.startswith("hand50") or eid.startswith("gap20")]
    if len(frozen_ids) != EXPECTED_FROZEN:
        raise SystemExit(
            f"BLOCKER: expected {EXPECTED_FROZEN} frozen-pool examples by id prefix, found {len(frozen_ids)}. "
            "This does not necessarily mean the frozen pool is corrupted (id-prefix detection is a heuristic, "
            "not the same byte-identity check `v4_5000_build.py assemble`'s frozen_preservation_report.json "
            "performs) -- but it means this environment's dataset does not match the audited state. STOP and "
            "re-verify against the source environment's `reports/frozen_preservation_report.json` before training."
        )


def assert_no_group_leakage(examples: tuple[TrainingExample, ...], split: DatasetSplit) -> None:
    """Same check `run_overall_single_training.py` runs before training the
    220-example baseline, reused verbatim (by source_id, the group-aware
    unit `v4_5000_dataset.py`'s own split already guarantees is disjoint --
    this is a second, independent confirmation at train time, not a
    re-derivation)."""
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


def load_batch_metadata(batches_dir: str = BATCHES_DIR) -> dict[str, dict]:
    """example_id ('v4c_<authored id>' or a frozen-pool id) -> metadata dict
    (hard_case/humanized/project_family/question_form/intent/
    humanization_style/word_count/answer/question). Read-only; used ONLY for
    post-hoc qualitative breakdown analysis in `evaluate_overall.py`, never
    for training (the model never sees these fields)."""
    meta: dict[str, dict] = {}
    if not os.path.isdir(batches_dir):
        return meta
    for path in sorted(glob.glob(os.path.join(batches_dir, "batch_*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                eid = f"v4c_{rec['id']}"
                meta[eid] = {
                    "hard_case": rec.get("hard_case"),
                    "humanized": rec.get("humanized", False),
                    "humanization_style": rec.get("humanization_style", ""),
                    "project_family": rec.get("project_family", ""),
                    "question_form": rec.get("question_form", ""),
                    "intent": rec.get("intent", ""),
                    "batch_id": os.path.basename(path)[:-len(".jsonl")],
                    "word_count": len((rec.get("answer") or "").split()),
                }
    return meta
