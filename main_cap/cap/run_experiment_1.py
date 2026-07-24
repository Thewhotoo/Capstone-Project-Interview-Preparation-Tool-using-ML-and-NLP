"""
Experiment 1 — Anchor: Trained vs. Untrained vs. Trivial-Majority vs.
HeuristicEvaluator, plus the epoch curve (approved research plan, session 10,
first experiment in the 6-item plan; Experiment 0's reproducibility fixes
are what make this experiment's comparisons trustworthy in the first place).

TWO-PHASE, reflecting the approved local/Colab environment split:

  `python run_experiment_1.py generate`  -- LOCAL (Windows dev machine).
      Builds the anchor dataset from the 36-profile library
      (experiment_profile_library.py, unmodified), assembles the
      DatasetManifest (unmodified), computes the specification-level split
      (training_experimentation.split_dataset_by_group, unmodified), and
      persists EVERYTHING portably to ./artifacts/experiment_1/:
      dataset.jsonl, manifest.json, split.json. Uses FakeGenerationClient
      (approved standing decision — real Gemini generation remains a
      separate future experiment once quota allows it).

  `python run_experiment_1.py train`  -- COLAB-INTENDED, but fully
      portable: device is auto-detected (`torch.cuda.is_available()`), so
      this SAME script also runs correctly (just much slower) on the local
      CPU-only machine for smoke-testing. Loads the artifacts `generate`
      produced, builds dataloaders, and trains the REAL pretrained
      `microsoft/deberta-v3-base` backbone ONCE, checkpointing/benchmarking
      after every epoch via `train_model`'s `on_epoch_end` hook — this
      produces the entire epoch curve (including the untrained, epoch-0
      point) from a single training run rather than restarting from
      scratch per epoch count. Only the FINAL epoch's full weights are
      persisted to disk (a real `deberta-v3-base` checkpoint is large;
      every intermediate epoch's benchmark METRICS are persisted, not its
      weights).

NOT A NEW SUBSYSTEM: every step below calls existing, already-tested code
(`Planner`, `TopicPool`, `QuestionRealizer`, `CoverageStrategy`,
`synthetic_generation_pipeline`, `DatasetManifest`, `split_dataset_by_group`,
`train_model`, `run_benchmark`, `decide_promotion`, `evaluator_registry`).
The only NEW code this experiment relies on is session 10's portability
additions (`train_model`'s `random_seed`/`on_epoch_end`,
`build_dataloaders`'s `seed`, `TrainedEvaluator`'s device auto-detection,
`load_checkpoint_artifact`'s `map_location`, `experiment_dataset_io`'s
generic `save_json`/`load_json`) — all additive, all already tested.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

import torch

from coverage_strategy import plan_batch
from dataset_manifest import DatasetManifest, assemble_manifest
from experiment_dataset_io import load_examples_jsonl, load_json, save_examples_jsonl, save_json
from experiment_profile_library import all_experiment_profiles
from generation_client import FakeGenerationClient
from heuristic_evaluator import HeuristicEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import save_checkpoint_artifact
from model_dataset import build_dataloaders
from model_evaluator import TrainedEvaluator, promote_trained_model
from model_heads import train_model
from run_third_experiment import _TECHNOLOGY_CONCEPTS, build_pool_from_profiles
from synthetic_generation_pipeline import generate_training_example
from training_experimentation import (
    Checkpoint,
    DatasetSplit,
    ExperimentConfig,
    PromotionPolicy,
    assemble_checkpoint,
    compute_qwk,
    decide_promotion,
    grade_to_ordinal,
    run_benchmark,
    split_dataset_by_group,
)
from expected_concepts_registry import lookup, register_expected_concepts

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_1")

ANCHOR_BATCH_SIZE = 500
RANDOM_SEED = 42
DATASET_VERSION = "v_experiment_1_anchor_epoch_curve"
MODEL_VERSION = "deberta_v3_base_experiment_1"
MAX_LENGTH = 128
TRAIN_BATCH_SIZE = 4
NUM_EPOCHS = 5
LEARNING_RATE = 2e-5

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})
_NUM_ORDINAL_CLASSES = 5

DATASET_PATH = os.path.join(ARTIFACTS_DIR, "dataset.jsonl")
MANIFEST_PATH = os.path.join(ARTIFACTS_DIR, "manifest.json")
SPLIT_PATH = os.path.join(ARTIFACTS_DIR, "split.json")


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_experiment_expected_concepts() -> None:
    """Additive-only registry population, same pattern/data as
    run_third_experiment.py (reused, not duplicated -- this is reference
    DATA, not experiment logic)."""
    for name, concepts in _TECHNOLOGY_CONCEPTS.items():
        if not lookup(name):
            register_expected_concepts(name, concepts)


def _majority_grade(train_examples: tuple) -> str:
    """The trivial baseline: always predict whichever core grade is most
    common in the training set."""
    grades = [e.labels.overall_label.grade for e in train_examples if e.labels.overall_label.grade in _CORE_GRADES]
    return Counter(grades).most_common(1)[0][0]


def _trivial_baseline_qwk(test_examples: tuple, majority_grade: str) -> float:
    y_true = tuple(grade_to_ordinal(e.labels.overall_label.grade) for e in test_examples)
    y_pred = tuple(grade_to_ordinal(majority_grade) for _ in test_examples)
    return compute_qwk(y_true, y_pred, _NUM_ORDINAL_CLASSES)


# ═════════════════════════════════════════════════════════════════════════════
# Phase: generate (LOCAL)
# ═════════════════════════════════════════════════════════════════════════════


def phase_generate() -> int:
    _log("=== Experiment 1 / Phase: GENERATE (local) ===")
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    register_experiment_expected_concepts()
    profiles = all_experiment_profiles()
    pool, spec_group_key = build_pool_from_profiles(profiles)
    _log(f"Built a pool of {len(pool)} discussion units from {len(profiles)} candidate profiles.")

    coverage_plan = plan_batch(pool, batch_size=ANCHOR_BATCH_SIZE, batch_seed=f"experiment::{DATASET_VERSION}")
    tier_counts = Counter(t.value for t in coverage_plan.quality_tiers)
    _log(f"CoverageStrategy planned {len(coverage_plan.units)} recipes. Tier distribution: {dict(tier_counts)}")

    client = FakeGenerationClient()
    examples = []
    failures = 0
    for unit, tier in zip(coverage_plan.units, coverage_plan.quality_tiers):
        try:
            outcome = generate_training_example(
                recipe_id=unit.recipe_id, specification=unit.specification, question_text=unit.question_text,
                reasoning_type=unit.reasoning_type, expected_concepts=unit.expected_concepts,
                quality_tier=tier, client=client, generation_batch_id=DATASET_VERSION,
            )
            examples.append(outcome.example)
        except Exception:
            failures += 1
    _log(f"Generation complete: {len(examples)} accepted, {failures} rejected out of {len(coverage_plan.units)}.")
    if not examples:
        _log("BLOCKER: zero examples generated.")
        return 1

    manifest, stamped_examples = assemble_manifest(tuple(examples), dataset_version=DATASET_VERSION)
    by_id = {e.metadata.example_id: e for e in stamped_examples}
    _log(f"DatasetManifest: {len(manifest.example_ids)} examples, tier_distribution={dict(manifest.tier_distribution)}")

    # Specification-level split (session 8's fix, unmodified) -- this
    # anchor batch cycles the 362-specification pool to fill
    # ANCHOR_BATCH_SIZE examples, so the SAME leakage risk split_dataset_by_group
    # was built for applies here too: many examples share an underlying
    # specification at different quality tiers. Using plain example-level
    # split_dataset here would silently reintroduce exactly the flaw
    # session 8 fixed -- deliberately not done.
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


# ═════════════════════════════════════════════════════════════════════════════
# Phase: train (COLAB-INTENDED, portable)
# ═════════════════════════════════════════════════════════════════════════════


def phase_train() -> int:
    _log("=== Experiment 1 / Phase: TRAIN (Colab-intended; device auto-detected) ===")
    if not os.path.exists(DATASET_PATH):
        _log(f"BLOCKER: {DATASET_PATH!r} not found -- run 'generate' first (on the local machine).")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = load_examples_jsonl(DATASET_PATH)
    manifest = load_json(DatasetManifest, MANIFEST_PATH)
    split = load_json(DatasetSplit, SPLIT_PATH)
    by_id = {e.metadata.example_id: e for e in examples}
    _log(f"Loaded {len(examples)} examples (dataset_version={manifest.dataset_version!r}).")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=MAX_LENGTH)
    tokenizer = build_tokenizer(backbone_config)
    train_loader, val_loader, test_loader = build_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=TRAIN_BATCH_SIZE, seed=RANDOM_SEED,
    )
    _log(f"Dataloaders: train_batches={len(train_loader)}, val_batches={len(val_loader)}, test_batches={len(test_loader)}")

    test_examples = tuple(by_id[i] for i in split.test_ids)
    core_test_examples = tuple(e for e in test_examples if e.labels.overall_label.grade in _CORE_GRADES)
    train_examples = tuple(by_id[i] for i in split.train_ids)
    majority_grade = _majority_grade(train_examples)
    majority_qwk = _trivial_baseline_qwk(core_test_examples, majority_grade)
    _log(f"Trivial majority-class baseline: predicts {majority_grade!r} always -> QWK={majority_qwk:.4f} "
         f"({len(core_test_examples)}/{len(test_examples)} core-grade test examples).")

    baseline = HeuristicEvaluator()
    epoch_curve: list[dict] = []

    def on_epoch_end(epoch_index: int, model, train_loss, val_loss) -> None:
        label = "untrained (epoch 0)" if epoch_index == 0 else f"epoch {epoch_index}"
        _log(f"--- Benchmarking {label} ---")
        placeholder_config = ExperimentConfig(
            backbone_name=backbone_config.hf_model_id, random_seed=RANDOM_SEED, dataset_version=DATASET_VERSION,
            parameters={"epoch": epoch_index, "learning_rate": LEARNING_RATE, "batch_size": TRAIN_BATCH_SIZE},
        )
        checkpoint = assemble_checkpoint(
            model_version=f"{MODEL_VERSION}_epoch{epoch_index}", experiment_config=placeholder_config,
            artifact_uri=f"in-memory-epoch-{epoch_index}" if epoch_index < NUM_EPOCHS else "pending-final-save",
        )
        candidate = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)
        benchmark = run_benchmark(candidate, baseline, core_test_examples, dataset_version=DATASET_VERSION)

        _log(f"  candidate QWK={benchmark.candidate_qwk:.4f}  baseline QWK={benchmark.baseline_qwk:.4f}  "
             f"majority QWK={majority_qwk:.4f}  train_loss={train_loss}  val_loss={val_loss}")
        save_json(benchmark, os.path.join(ARTIFACTS_DIR, f"epoch_{epoch_index}_benchmark.json"))
        epoch_curve.append({
            "epoch": epoch_index, "train_loss": train_loss, "val_loss": val_loss,
            "candidate_qwk": benchmark.candidate_qwk, "baseline_qwk": benchmark.baseline_qwk,
            "majority_qwk": majority_qwk,
        })

        if epoch_index == NUM_EPOCHS:
            weights_path = os.path.join(ARTIFACTS_DIR, "final_checkpoint_weights.pt")
            save_checkpoint_artifact(model, weights_path)
            final_checkpoint = checkpoint.model_copy(update={"artifact_uri": weights_path})
            save_json(final_checkpoint, os.path.join(ARTIFACTS_DIR, "final_checkpoint.json"))

            decision = decide_promotion(final_checkpoint, benchmark, PromotionPolicy())
            save_json(decision, os.path.join(ARTIFACTS_DIR, "final_promotion_decision.json"))
            _log(f"  Final-epoch promotion decision: approved={decision.approved} -- {decision.rationale}")
            if decision.approved:
                promote_trained_model(final_checkpoint, decision, candidate, make_active=True)
                _log(f"  Promoted and registered as the active evaluator: {candidate.name}")

    t0 = time.time()
    train_model(
        train_loader, val_loader, backbone_config, num_epochs=NUM_EPOCHS, learning_rate=LEARNING_RATE,
        device=device, random_seed=RANDOM_SEED, on_epoch_end=on_epoch_end,
    )
    _log(f"Training + per-epoch benchmarking complete in {time.time() - t0:.1f}s.")

    with open(os.path.join(ARTIFACTS_DIR, "epoch_curve_summary.json"), "w", encoding="utf-8") as f:
        json.dump(epoch_curve, f, indent=2)
    _log(f"Epoch curve summary written to {os.path.join(ARTIFACTS_DIR, 'epoch_curve_summary.json')!r}.")

    _log("=== TRAIN PHASE COMPLETE ===")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("generate", "train"):
        print("Usage: python run_experiment_1.py [generate|train]", file=sys.stderr)
        return 2
    if sys.argv[1] == "generate":
        return phase_generate()
    return phase_train()


if __name__ == "__main__":
    sys.exit(main())
