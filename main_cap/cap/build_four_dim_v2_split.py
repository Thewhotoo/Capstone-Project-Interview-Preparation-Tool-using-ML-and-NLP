"""
Phase 5 — build the group-aware train/val/test split of the 220-example V2
pool (frozen 170 core + finalized v2_targeted_50), validate it for leakage,
and write a deterministic report + manifest artifact. Run-once script
(mirrors `build_four_dim_split_v1.py`'s own convention) -- reuses
`four_dim_experiment_v2_split` (pool adapter) and the existing, UNMODIFIED
`training_experimentation.split_dataset_by_group`. No new splitting logic.

Writes to `main_cap/cap/artifacts/four_dim_experiment_v2/` (gitignored,
same convention as every other dataset artifact): `split.json`,
`distribution_report.json`, `README.md`.

Never touches the frozen 170-pool, the V1 split, or the v2_targeted_50
artifact files themselves -- read-only with respect to all of them.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from four_dim_experiment_split import CANONICAL_DIMENSION_KEYS, load_core_pool
from four_dim_experiment_v2_split import group_of_by_source_id, load_v2_pool, load_v2_targeted_50
from training_experimentation import split_dataset_by_group

SPLIT_RATIOS = (0.75, 0.12, 0.13)
# Chosen deterministically -- see README "Seed selection" for the search
# procedure (800 deterministic candidate seeds scored on size closeness,
# per-split TC/relevance tier diversity in val AND test independently
# (not just combined), and v2_targeted_50 representation/phenomenon
# diversity in val and test; this seed was the top-scoring candidate).
SEED = "four_dim_v2_split_348"

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT_DIR = os.path.join(_HERE, "artifacts", "four_dim_experiment_v2")
_V2_TARGETED_RAW = os.path.join(_HERE, "artifacts", "v2_targeted_50", "v2_targeted_50_v1.jsonl")


def _dimension_distribution(examples_subset) -> dict[str, dict[int, int]]:
    dist = {name: {t: 0 for t in range(5)} for name in CANONICAL_DIMENSION_KEYS}
    for ex in examples_subset:
        by_name = {dl.name: dl.score for dl in ex.labels.dimension_labels}
        for name in CANONICAL_DIMENSION_KEYS:
            tier = round(by_name[name] * 4)
            dist[name][tier] += 1
    return dist


def _v2_targeted_coverage_categories() -> dict:
    with open(_V2_TARGETED_RAW, encoding="utf-8") as f:
        return {json.loads(l)["example_id"]: json.loads(l)["coverage_category"] for l in f}


def _seed_hard_cases() -> dict:
    path = os.path.join(_HERE, "artifacts", "seed_dataset_v1", "seed_v1_3_repaired.jsonl")
    with open(path, encoding="utf-8") as f:
        return {
            r["example_id"]: r["hard_case"]
            for r in (json.loads(l) for l in f)
            if r.get("hard_case")
        }


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

    # group_key IS source_id in this pool -- reported separately anyway per
    # the task's explicit "assert 0 shared group_key" requirement, even
    # though it is definitionally identical to the source_id check above.
    group_overlap = source_overlap

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
        and all(not v for v in group_overlap.values())
        and all(not v for v in question_overlap.values())
        and all(not v for v in answer_overlap.values())
        and not rewrite_lineage_examples
        and not missing_four
        and not out_of_range
    )

    return {
        "source_id_overlap": source_overlap,
        "group_key_overlap": group_overlap,
        "question_overlap": question_overlap,
        "answer_overlap": answer_overlap,
        "rewrite_lineage_leakage": rewrite_lineage_examples,
        "examples_missing_all_four_labels": missing_four,
        "labels_out_of_range": out_of_range,
        "PASS": all_clean,
    }


def main() -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)

    # Explicit, separate confirmation that the frozen 170 and v2_targeted_50
    # each load at their expected size BEFORE combining -- so any future
    # accidental modification of either source is caught here, not silently
    # absorbed into "220".
    core = load_core_pool()
    assert len(core) == 170, f"expected 170 frozen core-pool examples, got {len(core)}"
    targeted = load_v2_targeted_50()
    assert len(targeted) == 50, f"expected 50 finalized v2_targeted_50 examples, got {len(targeted)}"

    examples = load_v2_pool()
    assert len(examples) == 220, f"expected 220 V2 pool examples, got {len(examples)}"

    group_of = group_of_by_source_id(examples)
    example_ids = tuple(e.metadata.example_id for e in examples)
    split = split_dataset_by_group(example_ids, group_of, SPLIT_RATIOS, SEED)

    by_id = {e.metadata.example_id: e for e in examples}
    subsets = {"train": split.train_ids, "val": split.val_ids, "test": split.test_ids}

    leakage = _validate_leakage(examples, split)
    if not leakage["PASS"]:
        raise SystemExit(f"LEAKAGE VALIDATION FAILED, refusing to write split artifact: {leakage}")

    v2_cov = _v2_targeted_coverage_categories()
    hard_cases = _seed_hard_cases()

    report = {
        "experiment_name": "four_dim_experiment_v2",
        "seed": SEED,
        "split_ratios_target": SPLIT_RATIOS,
        "total_pool_size": len(examples),
        "pool_composition": {"frozen_170_core": 170, "v2_targeted_50": 50},
        "construction_method": (
            "split_dataset_by_group (training_experimentation.py, unmodified) over the 220-example "
            "V2 pool, grouped by source_id; seed chosen by scoring 800 deterministic candidates on "
            "size closeness + per-split (val and test independently) technical_correctness/"
            "relevance_completeness tier diversity + v2_targeted_50 representation/phenomenon "
            "diversity in val and test."
        ),
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
        "v2_targeted_50_representation": {
            name: {
                "count": sum(1 for i in ids if i in v2_cov),
                "coverage_categories": dict(Counter(v2_cov[i] for i in ids if i in v2_cov)),
            }
            for name, ids in subsets.items()
        },
        "hard_case_coverage": {
            name: {
                "letters": sorted({hard_cases[i] for i in ids if i in hard_cases}),
                "count": sum(1 for i in ids if i in hard_cases),
            }
            for name, ids in subsets.items()
        },
        "leakage_validation": leakage,
    }

    with open(os.path.join(_OUT_DIR, "split.json"), "w", encoding="utf-8") as f:
        json.dump({
            "experiment_name": "four_dim_experiment_v2", "seed": SEED, "split_ratios": SPLIT_RATIOS,
            "total_pool_size": len(examples),
            "train_ids": list(split.train_ids), "val_ids": list(split.val_ids), "test_ids": list(split.test_ids),
        }, f, indent=2)

    with open(os.path.join(_OUT_DIR, "distribution_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps({
        "total_pool_size": len(examples), "counts": report["counts"], "group_counts": report["group_counts"],
        "v2_targeted_50_representation": {k: v["count"] for k, v in report["v2_targeted_50_representation"].items()},
        "leakage_PASS": leakage["PASS"],
    }, indent=2))


if __name__ == "__main__":
    main()
