"""
Experiment 2 -- Dataset Scaling: generates the ~2,480-example anchor-scale
dataset (500 -> 2,500 recipes) from the full 36-profile library, matching
Experiment 1's tier distribution/coverage strategy and persistence pattern,
so it can be copied to Colab for training the same way Experiment 1's
dataset was.

THIS IS AN EXPERIMENT SCRIPT, NOT A NEW SUBSYSTEM. Every step below calls
existing, already-tested code unchanged: `Planner`, `TopicPool`,
`QuestionRealizer`, `CoverageStrategy`, `synthetic_generation_pipeline`,
`DatasetManifest`, `split_dataset_by_group`, `experiment_dataset_io`,
`FakeGenerationClient`. `build_pool_from_profiles` and the technology/concept
registry data are imported from `run_third_experiment.py` (reused, not
duplicated) -- that script already proved this exact 2,500-recipe scale
works structurally (2,480 accepted / 20 rejected, zero split overlap,
1.3s to generate).

SCOPE: generation -> DatasetManifest -> specification-level split ->
persistence only, mirroring `run_experiment_1.py`'s `generate` phase.
Deliberately no training/benchmarking here -- that is a separate,
Colab-intended step (see `run_experiment_1.py`'s `train` phase for the
pattern a future `run_experiment_2.py train` would follow), out of scope
for this milestone.

Uses `FakeGenerationClient` (deterministic, network-free), same standing
decision as every prior experiment script -- real Gemini generation
remains a separate future experiment once quota allows it.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter

from coverage_strategy import plan_batch
from dataset_manifest import assemble_manifest
from experiment_dataset_io import save_examples_jsonl, save_json
from experiment_profile_library import all_experiment_profiles
from generation_client import FakeGenerationClient
from run_third_experiment import build_pool_from_profiles, register_experiment_expected_concepts
from synthetic_generation_pipeline import generate_training_example
from training_experimentation import split_dataset_by_group

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2")

BATCH_SIZE = 2500
DATASET_VERSION = "v_experiment_2_scaled_library"

DATASET_PATH = os.path.join(ARTIFACTS_DIR, "dataset.jsonl")
MANIFEST_PATH = os.path.join(ARTIFACTS_DIR, "manifest.json")
SPLIT_PATH = os.path.join(ARTIFACTS_DIR, "split.json")


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def phase_generate() -> int:
    _log("=== Experiment 2 / Phase: GENERATE (local) ===")
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    register_experiment_expected_concepts()
    profiles = all_experiment_profiles()
    pool, spec_group_key = build_pool_from_profiles(profiles)
    _log(f"Built a pool of {len(pool)} discussion units from {len(profiles)} candidate profiles.")

    if not pool:
        _log("BLOCKER: no discussion units were produced -- cannot generate a dataset.")
        return 1

    coverage_plan = plan_batch(pool, batch_size=BATCH_SIZE, batch_seed=f"experiment::{DATASET_VERSION}")
    tier_counts = Counter(t.value for t in coverage_plan.quality_tiers)
    _log(f"CoverageStrategy planned {len(coverage_plan.units)} recipes. Tier distribution: {dict(tier_counts)}")

    client = FakeGenerationClient()
    examples = []
    failures = 0
    total = len(coverage_plan.units)
    t0 = time.time()
    for i, (unit, tier) in enumerate(zip(coverage_plan.units, coverage_plan.quality_tiers), start=1):
        try:
            outcome = generate_training_example(
                recipe_id=unit.recipe_id, specification=unit.specification, question_text=unit.question_text,
                reasoning_type=unit.reasoning_type, expected_concepts=unit.expected_concepts,
                quality_tier=tier, client=client, generation_batch_id=DATASET_VERSION,
            )
            examples.append(outcome.example)
        except Exception:
            failures += 1
        if i % 500 == 0 or i == total:
            _log(f"  progress: {i}/{total} recipes processed ({len(examples)} accepted, {failures} rejected)")
    _log(f"Generation complete in {time.time() - t0:.1f}s: {len(examples)} accepted, {failures} rejected out of {total}.")
    if not examples:
        _log("BLOCKER: zero examples generated.")
        return 1

    manifest, stamped_examples = assemble_manifest(tuple(examples), dataset_version=DATASET_VERSION)
    by_id = {e.metadata.example_id: e for e in stamped_examples}
    _log(f"DatasetManifest: {len(manifest.example_ids)} examples, tier_distribution={dict(manifest.tier_distribution)}")

    # Specification-level split (session 8's fix, unmodified) -- this batch
    # cycles the 362-specification pool to fill BATCH_SIZE examples, so the
    # same leakage risk split_dataset_by_group was built for applies here
    # too: many examples share an underlying specification at different
    # quality tiers. Using plain example-level split_dataset here would
    # silently reintroduce exactly the flaw session 8 fixed -- deliberately
    # not done.
    example_ids = tuple(e.metadata.example_id for e in stamped_examples)
    group_of = {
        example_id: spec_group_key[id(by_id[example_id].inputs.specification)]
        for example_id in example_ids
    }
    split = split_dataset_by_group(example_ids, group_of, split_ratios=(0.7, 0.15, 0.15), seed=f"split::{DATASET_VERSION}")
    _log(f"Split sizes: train={len(split.train_ids)}, val={len(split.val_ids)}, test={len(split.test_ids)}")
    train_specs = {group_of[i] for i in split.train_ids}
    val_specs = {group_of[i] for i in split.val_ids}
    test_specs = {group_of[i] for i in split.test_ids}
    overlap = (train_specs & val_specs) | (train_specs & test_specs) | (val_specs & test_specs)
    _log(f"Unique specifications per split: train={len(train_specs)}, val={len(val_specs)}, test={len(test_specs)} "
         f"(overlap={len(overlap)}, must be 0)")
    if overlap:
        _log("BLOCKER: specification overlap detected across splits.")
        return 1
    if not split.train_ids or not split.val_ids or not split.test_ids:
        _log("BLOCKER: one of train/val/test is empty.")
        return 1

    save_examples_jsonl(stamped_examples, DATASET_PATH)
    save_json(manifest, MANIFEST_PATH)
    save_json(split, SPLIT_PATH)
    _log(f"Persisted dataset/manifest/split to {ARTIFACTS_DIR!r} -- ready to copy to Colab.")
    _log("=== GENERATE PHASE COMPLETE ===")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "generate":
        print("Usage: python run_experiment_2.py generate", file=sys.stderr)
        return 2
    return phase_generate()


if __name__ == "__main__":
    sys.exit(main())
