"""
Experiment 4 Pilot — Rewrite Augmentation Stage (dataset-generation pipeline
only; no training happens here, per this repository's standing scope
boundary).

Selects a small, stratified, deterministic pilot of source examples from
`v_experiment_3_relabeled_dimensions` (TRAIN split only — val/test stay
pristine regardless of pilot outcome), generates 3 style-variant rewrites of
each via `rewrite_generation_pipeline.py`, and persists the result to
`artifacts/experiment_4_pilot/` (gitignored, same convention as every other
experiment's artifacts).

PILOT SIZE (approved this session): 40 source examples x 3 styles
(concise, conversational, reflective) = 120 rewrite attempts, expected
~80-120 accepted examples after validation attrition.

SELECTION IS FULLY DETERMINISTIC, NO RANDOM MODULE: stratified across the 5
graded quality tiers (excellent/good/adequate/weak/poor -- off_topic and
contradictory are excluded from the pilot, since style variation is largely
moot for those two modes) x the 6 reasoning types actually present in this
dataset (recall/explanation/application/reflection/ownership/decision_making
-- see experiment_3_reproducibility/COMPARISON.md Section 5: debugging and
scalability never appear in this dataset's specification mix). One example
per (tier, reasoning_type) bucket is selected first (sorted by example_id,
first in each bucket -- deterministic, no RNG); a second pass over the same
bucket order fills the remaining slots up to exactly 40.

SPLIT PLACEMENT: every rewrite is recorded as belonging to the SAME split
side (train) as its source -- trivially true here since only train-split
sources are selected for the pilot, but recorded explicitly in the output
manifest for when this scales beyond a train-only pilot.

Usage: `python run_experiment_4_pilot.py select`   -- selection only, no
                                                        API calls, safe to
                                                        run repeatedly
       `python run_experiment_4_pilot.py generate`  -- selection + real
                                                        Gemini calls (costs
                                                        API quota); requires
                                                        GEMINI_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from rewrite_generation_pipeline import RewriteRejectedError, RewriteUnit, rewrite_batch
from training_example import QualityTier, TrainingExample
from training_experimentation import DatasetSplit

SOURCE_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_3_relabeled")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_4_pilot")

SOURCE_DATASET_PATH = os.path.join(SOURCE_ARTIFACTS_DIR, "dataset.jsonl")
SOURCE_SPLIT_PATH = os.path.join(SOURCE_ARTIFACTS_DIR, "split.json")

SELECTION_PATH = os.path.join(ARTIFACTS_DIR, "pilot_selection.json")
DATASET_PATH = os.path.join(ARTIFACTS_DIR, "dataset.jsonl")
PILOT_SPLIT_PATH = os.path.join(ARTIFACTS_DIR, "split.json")
PILOT_SUMMARY_PATH = os.path.join(ARTIFACTS_DIR, "pilot_summary.json")

PILOT_SOURCE_COUNT = 40
PILOT_STYLES: tuple[str, ...] = ("concise", "conversational", "reflective")

# Fixed, deterministic iteration order -- not derived from any RNG.
_TIER_ORDER: tuple[QualityTier, ...] = (
    QualityTier.EXCELLENT, QualityTier.GOOD, QualityTier.ADEQUATE, QualityTier.WEAK, QualityTier.POOR,
)


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def select_pilot_sources(examples: tuple[TrainingExample, ...], split: DatasetSplit, count: int) -> tuple[TrainingExample, ...]:
    """Deterministic stratified selection (module docstring) -- sorted
    bucketing, no `random` module anywhere. Restricted to the TRAIN split
    and the 5 graded tiers only."""
    train_ids = set(split.train_ids)
    by_bucket: dict[tuple[str, str], list[TrainingExample]] = defaultdict(list)
    for example in examples:
        if example.metadata.example_id not in train_ids:
            continue
        if example.synthetic is None:
            continue
        tier = example.synthetic.intended_quality_tier
        if tier not in _TIER_ORDER:
            continue
        key = (tier.value, example.inputs.reasoning_type.value)
        by_bucket[key].append(example)

    for bucket in by_bucket.values():
        bucket.sort(key=lambda e: e.metadata.example_id)

    reasoning_types = sorted({rt for (_, rt) in by_bucket.keys()})
    bucket_order = [(tier.value, rt) for tier in _TIER_ORDER for rt in reasoning_types if (tier.value, rt) in by_bucket]

    selected: list[TrainingExample] = []
    seen_ids: set[str] = set()
    pass_index = 0
    while len(selected) < count and pass_index < max((len(b) for b in by_bucket.values()), default=0):
        for key in bucket_order:
            if len(selected) >= count:
                break
            bucket = by_bucket[key]
            if pass_index < len(bucket):
                candidate = bucket[pass_index]
                if candidate.metadata.example_id not in seen_ids:
                    selected.append(candidate)
                    seen_ids.add(candidate.metadata.example_id)
        pass_index += 1

    return tuple(selected)


def phase_select() -> int:
    _log("=== Experiment 4 Pilot / Phase: SELECT (no API calls) ===")
    if not os.path.exists(SOURCE_DATASET_PATH):
        _log(f"BLOCKER: {SOURCE_DATASET_PATH!r} not found -- run run_dataset_relabel.py relabel first.")
        return 1
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    _log(f"Loaded {len(examples)} examples, split train={len(split.train_ids)}/val={len(split.val_ids)}/test={len(split.test_ids)}.")

    selected = select_pilot_sources(examples, split, PILOT_SOURCE_COUNT)
    _log(f"Selected {len(selected)} pilot source examples (target {PILOT_SOURCE_COUNT}).")

    tier_counts = defaultdict(int)
    reasoning_counts = defaultdict(int)
    for ex in selected:
        tier_counts[ex.synthetic.intended_quality_tier.value] += 1
        reasoning_counts[ex.inputs.reasoning_type.value] += 1
    _log(f"Tier distribution: {dict(sorted(tier_counts.items()))}")
    _log(f"Reasoning-type distribution: {dict(sorted(reasoning_counts.items()))}")

    with open(SELECTION_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "source_dataset_version": "v_experiment_3_relabeled_dimensions",
            "pilot_source_count": len(selected),
            "pilot_styles": list(PILOT_STYLES),
            "expected_rewrite_attempts": len(selected) * len(PILOT_STYLES),
            "selected_example_ids": [e.metadata.example_id for e in selected],
            "tier_distribution": dict(sorted(tier_counts.items())),
            "reasoning_type_distribution": dict(sorted(reasoning_counts.items())),
        }, f, indent=2)
    _log(f"Persisted selection to {SELECTION_PATH!r}.")
    _log("=== SELECT PHASE COMPLETE (no cost incurred) ===")
    return 0


def phase_generate() -> int:
    _log("=== Experiment 4 Pilot / Phase: GENERATE (real Gemini calls -- costs API quota) ===")
    if not os.path.exists(SOURCE_DATASET_PATH):
        _log(f"BLOCKER: {SOURCE_DATASET_PATH!r} not found -- run run_dataset_relabel.py relabel first.")
        return 1
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    examples = load_examples_jsonl(SOURCE_DATASET_PATH)
    split = load_json(DatasetSplit, SOURCE_SPLIT_PATH)
    selected = select_pilot_sources(examples, split, PILOT_SOURCE_COUNT)
    _log(f"Selected {len(selected)} pilot source examples.")

    from generation_client import GeminiGenerationClient
    from rewrite_verifier_client import GeminiSemanticVerifierClient

    client = GeminiGenerationClient()
    verifier_client = GeminiSemanticVerifierClient()
    generation_batch_id = f"experiment_4_pilot_{int(time.time())}"

    units = tuple(
        RewriteUnit(source_example=source, style=style)
        for source in selected
        for style in PILOT_STYLES
    )
    _log(f"Requesting {len(units)} rewrite attempts ({len(selected)} sources x {len(PILOT_STYLES)} styles).")

    accepted: list[TrainingExample] = []
    rejected: list[dict] = []
    attempts_histogram: dict[int, int] = defaultdict(int)

    errored: list[dict] = []
    for i, unit in enumerate(units, start=1):
        try:
            outcome = rewrite_batch((unit,), client, verifier_client, generation_batch_id)[0]
            accepted.append(outcome.example)
            attempts_histogram[outcome.attempts] += 1
        except RewriteRejectedError as e:
            rejected.append({
                "source_example_id": e.source_example_id, "style": e.style,
                "attempts": e.attempts, "last_reasons": list(e.last_reasons),
            })
            _log(f"  [{i}/{len(units)}] REJECTED: {e}")
        except Exception as e:
            # A single unit's transient failure (network error, an
            # unparseable-after-retries verifier response, etc.) must never
            # crash the whole batch -- log it, record it distinctly from a
            # deliberate validation rejection, and move on to the next unit.
            # (Found the hard way: a pilot run against real Gemini crashed
            # here on unit 1/120 before this was added.)
            errored.append({
                "source_example_id": unit.source_example.metadata.example_id, "style": unit.style,
                "error": f"{type(e).__name__}: {e}",
            })
            _log(f"  [{i}/{len(units)}] ERRORED: {type(e).__name__}: {e}")
        if i % 20 == 0 or i == len(units):
            _log(f"  progress: {i}/{len(units)} attempted "
                 f"({len(accepted)} accepted, {len(rejected)} rejected, {len(errored)} errored)")

    _log(f"Generation complete: {len(accepted)} accepted, {len(rejected)} rejected, {len(errored)} errored out of {len(units)}.")
    if not accepted:
        _log("BLOCKER: zero rewrites accepted.")
        return 1

    save_examples_jsonl(tuple(accepted), DATASET_PATH)

    # Every rewrite belongs to the same split side as its source -- direct
    # lookup, not a recomputed grouping (see module docstring).
    rewrite_train_ids = tuple(e.metadata.example_id for e in accepted)  # all sources are train-split by selection
    pilot_split = DatasetSplit(train_ids=rewrite_train_ids)
    save_json(pilot_split, PILOT_SPLIT_PATH)

    with open(PILOT_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "pilot_source_count": len(selected), "pilot_styles": list(PILOT_STYLES),
            "attempted": len(units), "accepted": len(accepted), "rejected": len(rejected), "errored": len(errored),
            "accept_rate": round(len(accepted) / len(units), 4),
            "attempts_histogram": {str(k): v for k, v in sorted(attempts_histogram.items())},
            "rejections": rejected,
            "errors": errored,
        }, f, indent=2)
    _log(f"Persisted dataset/split/summary to {ARTIFACTS_DIR!r}.")
    _log("=== GENERATE PHASE COMPLETE ===")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("select", "generate"):
        print("Usage: python run_experiment_4_pilot.py [select|generate]", file=sys.stderr)
        return 2
    return phase_select() if sys.argv[1] == "select" else phase_generate()


if __name__ == "__main__":
    sys.exit(main())
