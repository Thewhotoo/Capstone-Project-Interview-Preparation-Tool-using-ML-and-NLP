"""
Experiment 4 Deterministic Rewrite Run — Rewrite Augmentation Stage,
API-FREE variant (Track B: no Gemini/OpenAI/external LLM API anywhere in
this path). Dataset-generation pipeline only; no training happens here,
per this repository's standing scope boundary.

Two scales, sharing all the same selection/generation machinery:
  - PILOT scale (`select`/`generate`): the original 40-source x 3-style
    validation run from the prior session. Mirrors
    `run_experiment_4_pilot.py`'s shape and selection logic EXACTLY (same
    `select_pilot_sources`, same stratification, same size/styles) so the
    two are directly comparable. Left untouched/unscaled so its already-
    validated result stays reproducible on its own.
  - FULL scale (`select_full`/`generate_full`): every eligible TRAIN-split
    source (all 5 graded quality tiers, off_topic/contradictory excluded
    same as the pilot) x the same 3 styles -- the actual production
    augmentation run. Writes to a SEPARATE artifacts directory
    (`experiment_4_deterministic_full/`) so pilot and full-scale outputs,
    and the untouched source dataset, never collide or get confused for
    one another.

The only thing that differs from the Gemini path
(`run_experiment_4_pilot.py`) is the generation method:
`deterministic_rewrite_pipeline.deterministic_rewrite_batch` (pure text
transforms + SBERT verifier) instead of
`rewrite_generation_pipeline.rewrite_batch` (Gemini). Same validation (all
7 QA checks, `rewrite_validation.validate_rewrite`), same assembly
(`rewrite_assembler.assemble_rewritten_example`), same acceptance bar.

PROVENANCE (Track B requirement): every accepted example's
`synthetic.generation_prompt_id` is `"deterministic_rewrite"` (never
`"rewrite_promptbook"`, the Gemini path's id). The run itself draws only
from this repository's own already-existing, already-labeled dataset
(`v_experiment_3_relabeled_dimensions`) -- no external data fetched, so
there is no separate license/source to record beyond what
`experiment_3_reproducibility/` already documents for that dataset.

Usage: `python run_experiment_4_deterministic.py select`        -- pilot-scale selection only
       `python run_experiment_4_deterministic.py generate`      -- pilot-scale, real API-free generation
       `python run_experiment_4_deterministic.py select_full`   -- full-scale selection only
       `python run_experiment_4_deterministic.py generate_full` -- full-scale, real API-free generation
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

from deterministic_rewrite_pipeline import deterministic_rewrite_batch
from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from rewrite_generation_pipeline import RewriteRejectedError, RewriteUnit
from run_experiment_4_pilot import (
    PILOT_SOURCE_COUNT,
    PILOT_STYLES,
    SOURCE_DATASET_PATH,
    SOURCE_SPLIT_PATH,
    select_pilot_sources,
)
from training_example import TrainingExample
from training_experimentation import DatasetSplit

_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Pilot scale (unchanged from the prior session) ─────────────────────────
ARTIFACTS_DIR = os.path.join(_HERE, "artifacts", "experiment_4_deterministic")
SELECTION_PATH = os.path.join(ARTIFACTS_DIR, "selection.json")
DATASET_PATH = os.path.join(ARTIFACTS_DIR, "dataset.jsonl")
SPLIT_PATH = os.path.join(ARTIFACTS_DIR, "split.json")
SUMMARY_PATH = os.path.join(ARTIFACTS_DIR, "run_summary.json")

# ── Full scale (new) ────────────────────────────────────────────────────────
FULL_ARTIFACTS_DIR = os.path.join(_HERE, "artifacts", "experiment_4_deterministic_full")
FULL_SELECTION_PATH = os.path.join(FULL_ARTIFACTS_DIR, "selection.json")
FULL_DATASET_PATH = os.path.join(FULL_ARTIFACTS_DIR, "dataset.jsonl")
FULL_SPLIT_PATH = os.path.join(FULL_ARTIFACTS_DIR, "split.json")
FULL_SUMMARY_PATH = os.path.join(FULL_ARTIFACTS_DIR, "run_summary.json")

# Larger than any realistic eligible-source count -- select_pilot_sources
# (module docstring: stratified bucketing, deterministic, no RNG) simply
# returns every eligible source when the requested count exceeds what's
# available, so this constant means "all eligible train-split sources
# across the 5 graded tiers," not a hardcoded target.
FULL_SOURCE_COUNT = 1_000_000


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _run_select(source_count: int, artifacts_dir: str, selection_path: str, label: str) -> int:
    _log(f"=== Experiment 4 Deterministic / Phase: SELECT ({label}, no API calls, none ever needed) ===")
    if not os.path.exists(SOURCE_DATASET_PATH):
        _log(f"BLOCKER: {SOURCE_DATASET_PATH!r} not found -- run run_dataset_relabel.py relabel first.")
        return 1
    os.makedirs(artifacts_dir, exist_ok=True)

    examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    _log(f"Loaded {len(examples)} examples, split train={len(split.train_ids)}/val={len(split.val_ids)}/test={len(split.test_ids)}.")

    selected = select_pilot_sources(examples, split, source_count)
    _log(f"Selected {len(selected)} source examples (target {source_count}).")

    tier_counts = defaultdict(int)
    reasoning_counts = defaultdict(int)
    for ex in selected:
        tier_counts[ex.synthetic.intended_quality_tier.value] += 1
        reasoning_counts[ex.inputs.reasoning_type.value] += 1

    with open(selection_path, "w", encoding="utf-8") as f:
        json.dump({
            "source_dataset_version": "v_experiment_3_relabeled_dimensions",
            "source_count": len(selected),
            "styles": list(PILOT_STYLES),
            "expected_rewrite_attempts": len(selected) * len(PILOT_STYLES),
            "selected_example_ids": [e.metadata.example_id for e in selected],
            "tier_distribution": dict(sorted(tier_counts.items())),
            "reasoning_type_distribution": dict(sorted(reasoning_counts.items())),
        }, f, indent=2)
    _log(f"Persisted selection to {selection_path!r}.")
    _log(f"=== SELECT PHASE COMPLETE ({label}) ===")
    return 0


def _run_generate(
    source_count: int, artifacts_dir: str, dataset_path: str, split_path: str, summary_path: str,
    batch_prefix: str, label: str,
) -> int:
    _log(f"=== Experiment 4 Deterministic / Phase: GENERATE ({label}, API-free -- zero external calls) ===")
    if not os.path.exists(SOURCE_DATASET_PATH):
        _log(f"BLOCKER: {SOURCE_DATASET_PATH!r} not found -- run run_dataset_relabel.py relabel first.")
        return 1
    os.makedirs(artifacts_dir, exist_ok=True)

    examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    selected = select_pilot_sources(examples, split, source_count)
    _log(f"Selected {len(selected)} source examples.")

    generation_batch_id = f"{batch_prefix}_{int(time.time())}"

    units = tuple(
        RewriteUnit(source_example=source, style=style)
        for source in selected
        for style in PILOT_STYLES
    )
    _log(f"Requesting {len(units)} rewrite attempts ({len(selected)} sources x {len(PILOT_STYLES)} styles).")

    accepted: list[TrainingExample] = []
    rejected: list[dict] = []

    for i, unit in enumerate(units, start=1):
        try:
            outcome = deterministic_rewrite_batch((unit,), generation_batch_id)[0]
            accepted.append(outcome.example)
        except RewriteRejectedError as e:
            rejected.append({
                "source_example_id": e.source_example_id, "style": e.style,
                "last_reasons": list(e.last_reasons),
            })
        if i % 200 == 0 or i == len(units):
            _log(f"  progress: {i}/{len(units)} attempted ({len(accepted)} accepted, {len(rejected)} rejected)")

    _log(f"Generation complete: {len(accepted)} accepted, {len(rejected)} rejected out of {len(units)}.")
    if not accepted:
        _log("BLOCKER: zero rewrites accepted.")
        return 1

    save_examples_jsonl(tuple(accepted), dataset_path)

    # Every rewrite belongs to the same split side as its source (train,
    # by construction of select_pilot_sources) -- direct lookup, never a
    # recomputed grouping (same rule the Gemini pilot driver documents).
    rewrite_train_ids = tuple(e.metadata.example_id for e in accepted)
    run_split = DatasetSplit(train_ids=rewrite_train_ids)
    save_json(run_split, split_path)

    rejection_reason_counts: dict[str, int] = defaultdict(int)
    for r in rejected:
        for reason in r["last_reasons"]:
            rejection_reason_counts[reason.split(":")[0]] += 1

    tier_counts_accepted = defaultdict(int)
    style_counts_accepted = defaultdict(int)
    reasoning_counts_accepted = defaultdict(int)
    for e in accepted:
        tier_counts_accepted[e.synthetic.intended_quality_tier.value] += 1
        style_counts_accepted[e.synthetic.rewrite_style] += 1
        reasoning_counts_accepted[e.inputs.reasoning_type.value] += 1

    style_rejection_counts: dict[str, int] = defaultdict(int)
    for r in rejected:
        style_rejection_counts[r["style"]] += 1

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "generation_method": "deterministic_rule_based (API-free)",
            "generation_batch_id": generation_batch_id,
            "source_count": len(selected), "styles": list(PILOT_STYLES),
            "attempted": len(units), "accepted": len(accepted), "rejected": len(rejected),
            "accept_rate": round(len(accepted) / len(units), 4),
            "accepted_tier_distribution": dict(sorted(tier_counts_accepted.items())),
            "accepted_style_distribution": dict(sorted(style_counts_accepted.items())),
            "accepted_reasoning_type_distribution": dict(sorted(reasoning_counts_accepted.items())),
            "rejected_style_distribution": dict(sorted(style_rejection_counts.items())),
            "rejection_reason_counts": dict(sorted(rejection_reason_counts.items())),
            "rejections": rejected,
        }, f, indent=2)
    _log(f"Persisted dataset/split/summary to {artifacts_dir!r}.")
    _log(f"=== GENERATE PHASE COMPLETE ({label}, zero external API calls made) ===")
    return 0


def phase_select() -> int:
    return _run_select(PILOT_SOURCE_COUNT, ARTIFACTS_DIR, SELECTION_PATH, "pilot")


def phase_generate() -> int:
    return _run_generate(
        PILOT_SOURCE_COUNT, ARTIFACTS_DIR, DATASET_PATH, SPLIT_PATH, SUMMARY_PATH,
        "experiment_4_deterministic", "pilot",
    )


def phase_select_full() -> int:
    return _run_select(FULL_SOURCE_COUNT, FULL_ARTIFACTS_DIR, FULL_SELECTION_PATH, "FULL")


def phase_generate_full() -> int:
    return _run_generate(
        FULL_SOURCE_COUNT, FULL_ARTIFACTS_DIR, FULL_DATASET_PATH, FULL_SPLIT_PATH, FULL_SUMMARY_PATH,
        "experiment_4_deterministic_full", "FULL",
    )


_PHASES = {
    "select": phase_select,
    "generate": phase_generate,
    "select_full": phase_select_full,
    "generate_full": phase_generate_full,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in _PHASES:
        print(f"Usage: python run_experiment_4_deterministic.py [{'|'.join(_PHASES)}]", file=sys.stderr)
        return 2
    return _PHASES[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
