"""
Four-Dimension V2 Experiment Pool — Phase 5.

Combines the FROZEN 170-example core pool (unchanged, loaded via
`four_dim_experiment_split.load_core_pool()` -- that module and the
underlying 170 examples/V1 split are never modified here) with the
finalized 50-example `v2_targeted_50` boundary-targeted batch into the
220-example V2 pool. Read-only with respect to every source artifact.

Reuses `four_dim_experiment_split._to_training_example` (the same
artifact-schema-to-TrainingExample adapter used for the 170-pool) rather
than duplicating it, since `v2_targeted_50` uses the identical flat
hand-authored schema (same field names, same judged-companion-file
convention).
"""

from __future__ import annotations

import json
import os
from typing import Iterable

from four_dim_experiment_split import (
    CANONICAL_DIMENSION_KEYS,
    _to_training_example,
    load_core_pool,
)
from training_example import TrainingExample

_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")

V2_TARGETED_RAW = os.path.join(_ARTIFACTS_DIR, "v2_targeted_50", "v2_targeted_50_v1.jsonl")
V2_TARGETED_JUDGED = os.path.join(_ARTIFACTS_DIR, "v2_targeted_50", "v2_targeted_50_v1_judged.jsonl")


def _read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_v2_targeted_50() -> tuple[TrainingExample, ...]:
    """Loads the finalized 50-example v2_targeted_50 batch (read-only) as
    real `TrainingExample`s, same adapter/labeling convention as the
    170-pool loader."""
    raw_by_id = {r["example_id"]: r for r in _read_jsonl(V2_TARGETED_RAW)}
    judged_rows = _read_jsonl(V2_TARGETED_JUDGED)
    judged_ids = {j["example_id"] for j in judged_rows}
    if judged_ids != set(raw_by_id):
        raise ValueError(
            f"v2_targeted_50: raw/judged example_id sets disagree "
            f"(raw-only: {sorted(set(raw_by_id) - judged_ids)[:5]}, "
            f"judged-only: {sorted(judged_ids - set(raw_by_id))[:5]})"
        )
    return tuple(
        _to_training_example(raw_by_id[judged["example_id"]], judged, "v2_targeted_50")
        for judged in judged_rows
    )


def load_v2_pool() -> tuple[TrainingExample, ...]:
    """The full 220-example V2 pool: the frozen 170 (unchanged) + the
    finalized v2_targeted_50 (50). Raises on any example_id collision
    across the two sources rather than silently deduplicating."""
    core = load_core_pool()
    targeted = load_v2_targeted_50()
    combined = core + targeted
    ids = [e.metadata.example_id for e in combined]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate example_id(s) across the V2 pool: {dupes}")
    return combined


def group_of_by_source_id(examples: Iterable[TrainingExample]) -> dict[str, str]:
    """example_id -> source_id, the group key the splitter partitions on."""
    return {e.metadata.example_id: e.inputs.specification.source_id for e in examples}
