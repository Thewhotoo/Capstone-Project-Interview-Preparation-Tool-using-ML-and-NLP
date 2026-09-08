"""
Four-Dimension Experiment Split — Phase 3.

Loads the FROZEN 170-example curated core pool (100 repaired seed + 50
hand-authored + 20 targeted coverage, all under `main_cap/cap/artifacts/`,
gitignored) as real `TrainingExample` objects with canonical four-dimension
labels, and builds the group-aware train/val/test split via the existing,
UNMODIFIED `training_experimentation.split_dataset_by_group` — this module
adds no new splitting logic, it only adapts the artifact schema into
`TrainingExample` so the existing splitter/collator/model path can consume
it.

READ-ONLY with respect to the artifacts: nothing here ever writes to
`seed_dataset_v1/`, `hand_authored_50/`, or `gap_coverage_20/`. Labels come
from each batch's independently, profile-blind JUDGED companion file (never
from `target_profile`, which is generation/authoring intent only — the same
"labels come from the judge, not the target" discipline `four_dim_dataset.py`
already enforces for the LLM-generation pipeline; this module is the
equivalent adapter for the hand-authored artifact pool).

`ContradictionLabel`/`OverallLabel.grade` are populated with an honest
not-applicable placeholder, not a fabricated value — neither field is
consumed by the four-dimension collation/training path
(`model_dataset.collate_fn` only reads `dimension_labels`,
`missing_reasoning_labels`, and `concept_labels`), so a placeholder here
never leaks into a training signal.
"""

from __future__ import annotations

import json
import os
from typing import Iterable

from evaluation_dimensions import all_keys as canonical_dimension_keys
from question_families import ReasoningType
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
)

CANONICAL_DIMENSION_KEYS: tuple[str, ...] = canonical_dimension_keys()
_MAX_TIER = 4.0

_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")

# (raw jsonl, judged jsonl, batch label) for the three FROZEN pools making up
# the 170-example core dataset. Order here has no effect on the resulting
# split (split_dataset_by_group shuffles by a stable hash of the seed, not
# input order), it only fixes iteration order for reporting.
CORE_POOLS: tuple[tuple[str, str, str], ...] = (
    (
        os.path.join(_ARTIFACTS_DIR, "seed_dataset_v1", "seed_v1_3_repaired.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "seed_dataset_v1", "seed_v1_3_judged.jsonl"),
        "seed_v1",
    ),
    (
        os.path.join(_ARTIFACTS_DIR, "hand_authored_50", "hand_authored_50_v1.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "hand_authored_50", "hand_authored_50_v1_judged.jsonl"),
        "hand_authored_50",
    ),
    (
        os.path.join(_ARTIFACTS_DIR, "gap_coverage_20", "gap20_v1.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "gap_coverage_20", "gap20_v1_judged.jsonl"),
        "gap_coverage_20",
    ),
)


def _read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def _to_training_example(raw: dict, judged: dict, batch: str) -> TrainingExample:
    spec = QuestionSpecification(
        id=raw["example_id"], category=QuestionCategory(raw["category"]), text_seed=raw["title"],
        grounding=Grounding(project=ProjectGrounding(
            title=raw["title"], technologies=tuple(raw["technologies"]), concepts=(),
        )),
        source_type=SourceType.PROJECT, source_id=raw["source_id"],
        source_field="interview_seeds", reason="curated_core_pool",
    )
    dims = judged["judged_dimension_labels"]
    dimension_labels = tuple(
        DimensionLabel(name=name, score=round(dims[name] / _MAX_TIER, 4)) for name in CANONICAL_DIMENSION_KEYS
    )
    overall_score = round(sum(dims.values()) / (len(CANONICAL_DIMENSION_KEYS) * _MAX_TIER), 4)
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=raw["example_id"], created_at="2026-09-08T00:00:00+00:00"),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION, collection_batch_id=batch, real_session_id="n/a",
        ),
        inputs=TrainingExampleInputs(
            specification=spec, question_text=raw["question"],
            reasoning_type=ReasoningType(raw["reasoning_type"]), answer_text=raw["answer"],
            expected_concepts=tuple(raw.get("expected_concepts", ())),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        labels=TrainingExampleLabels(
            label_source="human_reviewed", labeling_guideline_version=judged.get("judge_version", "n/a"),
            dimension_labels=dimension_labels,
            # Not applicable to the hand-authored core pool / not consumed by
            # the four-dimension training path -- honest placeholders, not
            # fabricated signal (see module docstring).
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(score=overall_score, grade="n/a", rationale="loaded from curated core pool"),
        ),
    )


def load_core_pool() -> tuple[TrainingExample, ...]:
    """Loads all 170 FROZEN core-pool examples (read-only) as real
    `TrainingExample`s with canonical four-dimension labels sourced from
    each batch's independently judged companion file. Raises if any batch's
    raw/judged files disagree on membership (`example_id` mismatch) rather
    than silently dropping or misaligning a record."""
    examples: list[TrainingExample] = []
    for raw_path, judged_path, batch in CORE_POOLS:
        raw_by_id = {r["example_id"]: r for r in _read_jsonl(raw_path)}
        judged_rows = _read_jsonl(judged_path)
        judged_ids = {j["example_id"] for j in judged_rows}
        if judged_ids != set(raw_by_id):
            raise ValueError(
                f"{batch}: raw/judged example_id sets disagree "
                f"(raw-only: {sorted(set(raw_by_id) - judged_ids)[:5]}, "
                f"judged-only: {sorted(judged_ids - set(raw_by_id))[:5]})"
            )
        for judged in judged_rows:
            examples.append(_to_training_example(raw_by_id[judged["example_id"]], judged, batch))
    return tuple(examples)


def group_of_by_source_id(examples: Iterable[TrainingExample]) -> dict[str, str]:
    """example_id -> source_id, the group key `split_dataset_by_group`
    partitions on -- every example sharing a project/source stays entirely
    within one split."""
    return {e.metadata.example_id: e.inputs.specification.source_id for e in examples}
