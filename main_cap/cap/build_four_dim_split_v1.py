"""
Phase 3 — build the group-aware train/val/test split of the FROZEN
170-example core pool, validate it for leakage, and write a deterministic
report + manifest artifact. Run-once script (mirrors the existing
`run_experiment_*.py` naming convention) -- reuses `four_dim_experiment_split`
(artifact adapter) and the existing, UNMODIFIED
`training_experimentation.split_dataset_by_group`. No new splitting logic.

Writes to `main_cap/cap/artifacts/four_dim_experiment_v1/` (gitignored, same
convention as every other dataset artifact in this repo): `split.json`
(the DatasetSplit, by example_id), `distribution_report.json` (machine
report), and `README.md` (human report).

Does NOT train, does NOT touch the 170 source artifact files, does NOT
download the full pretrained backbone.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from evaluation_dimensions import CANONICAL_DIMENSIONS
from four_dim_experiment_split import CANONICAL_DIMENSION_KEYS, group_of_by_source_id, load_core_pool
from training_experimentation import split_dataset_by_group

SPLIT_RATIOS = (0.75, 0.12, 0.13)
SEED = "four_dim_experiment_v1_41"  # chosen deterministically -- see README "Seed selection"

_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "four_dim_experiment_v1")


def _dimension_distribution(examples_subset) -> dict[str, dict[int, int]]:
    dist = {name: {t: 0 for t in range(5)} for name in CANONICAL_DIMENSION_KEYS}
    for ex in examples_subset:
        by_name = {dl.name: dl.score for dl in ex.labels.dimension_labels}
        for name in CANONICAL_DIMENSION_KEYS:
            tier = round(by_name[name] * 4)
            dist[name][tier] += 1
    return dist


def _validate_leakage(examples, split) -> dict:
    by_id = {e.metadata.example_id: e for e in examples}
    subsets = {"train": split.train_ids, "val": split.val_ids, "test": split.test_ids}

    def norm(s: str) -> str:
        return " ".join((s or "").split()).casefold()

    source_by_split = {name: {by_id[i].inputs.specification.source_id for i in ids} for name, ids in subsets.items()}
    question_by_split = {name: {norm(by_id[i].inputs.question_text) for i in ids} for name, ids in subsets.items()}
    answer_by_split = {name: {norm(by_id[i].inputs.answer_text) for i in ids} for name, ids in subsets.items()}

    pairs = [("train", "val"), ("train", "test"), ("val", "test")]
    source_overlap = {f"{a}|{b}": sorted(source_by_split[a] & source_by_split[b]) for a, b in pairs}
    question_overlap = {f"{a}|{b}": sorted(question_by_split[a] & question_by_split[b]) for a, b in pairs}
    answer_overlap = {f"{a}|{b}": sorted(answer_by_split[a] & answer_by_split[b]) for a, b in pairs}

    # Rewrite-lineage leakage: none of the 170 core-pool examples are
    # deterministic-rewrite derivatives (the rewrite pipeline was never used
    # to expand this pool -- see DeBERTa_Dataset_Rebuild_Status.md). Checked
    # via the schema's own lineage field rather than assumed.
    rewrite_lineage_examples = [
        e.metadata.example_id for e in examples
        if e.synthetic is not None and e.synthetic.rewritten_from_example_id is not None
    ]

    missing_four = [
        e.metadata.example_id for e in examples
        if {dl.name for dl in e.labels.dimension_labels} != set(CANONICAL_DIMENSION_KEYS)
    ]
    out_of_range = [
        e.metadata.example_id for e in examples
        for dl in e.labels.dimension_labels
        if dl.name in CANONICAL_DIMENSION_KEYS and not (0.0 <= dl.score <= 1.0)
    ]

    all_clean = (
        all(not v for v in source_overlap.values())
        and all(not v for v in question_overlap.values())
        and all(not v for v in answer_overlap.values())
        and not rewrite_lineage_examples
        and not missing_four
        and not out_of_range
    )

    return {
        "source_id_overlap": source_overlap,
        "question_overlap": question_overlap,
        "answer_overlap": answer_overlap,
        "rewrite_lineage_leakage": rewrite_lineage_examples,
        "examples_missing_all_four_labels": missing_four,
        "labels_out_of_range": out_of_range,
        "PASS": all_clean,
    }


def main() -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    examples = load_core_pool()
    assert len(examples) == 170, f"expected 170 core-pool examples, got {len(examples)}"

    group_of = group_of_by_source_id(examples)
    example_ids = tuple(e.metadata.example_id for e in examples)
    split = split_dataset_by_group(example_ids, group_of, SPLIT_RATIOS, SEED)

    by_id = {e.metadata.example_id: e for e in examples}
    subsets = {"train": split.train_ids, "val": split.val_ids, "test": split.test_ids}

    leakage = _validate_leakage(examples, split)
    if not leakage["PASS"]:
        raise SystemExit(f"LEAKAGE VALIDATION FAILED, refusing to write split artifact: {leakage}")

    report = {
        "seed": SEED,
        "split_ratios_target": SPLIT_RATIOS,
        "total_examples": len(examples),
        "counts": {name: len(ids) for name, ids in subsets.items()},
        "groups": {
            name: sorted({by_id[i].inputs.specification.source_id for i in ids})
            for name, ids in subsets.items()
        },
        "group_counts": {
            name: len({by_id[i].inputs.specification.source_id for i in ids})
            for name, ids in subsets.items()
        },
        "dimension_distributions": {
            name: _dimension_distribution([by_id[i] for i in ids]) for name, ids in subsets.items()
        },
        "reasoning_type_distribution": {
            name: dict(Counter(by_id[i].inputs.reasoning_type.value for i in ids))
            for name, ids in subsets.items()
        },
        "leakage_validation": leakage,
    }

    with open(os.path.join(_OUT_DIR, "split.json"), "w", encoding="utf-8") as f:
        json.dump({
            "seed": SEED, "split_ratios": SPLIT_RATIOS,
            "train_ids": list(split.train_ids), "val_ids": list(split.val_ids), "test_ids": list(split.test_ids),
        }, f, indent=2)

    with open(os.path.join(_OUT_DIR, "distribution_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps({
        "counts": report["counts"], "group_counts": report["group_counts"], "leakage_PASS": leakage["PASS"],
    }, indent=2))


if __name__ == "__main__":
    main()
