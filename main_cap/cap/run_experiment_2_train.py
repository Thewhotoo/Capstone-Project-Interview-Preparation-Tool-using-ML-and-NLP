"""
Experiment 2 — Train: the same anchor training/benchmarking/promotion
procedure as `run_experiment_1.py`'s `train` phase, run unchanged against
the larger ~2,480-example Experiment 2 dataset (`run_experiment_2.py`'s
`generate` output). The only experimental variable is the dataset itself —
every hyperparameter, the backbone, the optimizer, the benchmarking
methodology, and the promotion/checkpoint/registration logic are identical
to Experiment 1.

`python run_experiment_2_train.py train`  -- COLAB-INTENDED, but fully
    portable: device is auto-detected (`torch.cuda.is_available()`), so
    this SAME script also runs correctly (just much slower) on the local
    CPU-only machine for smoke-testing. Loads the artifacts
    `run_experiment_2.py generate` produced from `artifacts/experiment_2/`,
    builds dataloaders, and trains the REAL pretrained
    `microsoft/deberta-v3-base` backbone ONCE, checkpointing/benchmarking
    after every epoch via `train_model`'s `on_epoch_end` hook — producing
    the entire epoch curve (including the untrained, epoch-0 point) from a
    single training run.

NOT A NEW SUBSYSTEM, NOT A MODIFICATION: `run_experiment_1.py` is untouched.
This is a new, additive script that reuses the exact same already-tested
production code (`train_model`, `build_dataloaders`, `TrainedEvaluator`,
`run_benchmark`, `decide_promotion`, `promote_trained_model`,
`save_checkpoint_artifact`, `evaluator_registry`) with only the dataset
location, dataset version, and model version swapped for Experiment 2.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

import torch

from dataset_manifest import DatasetManifest
from experiment_dataset_io import load_examples_jsonl, load_json, save_json
from heuristic_evaluator import HeuristicEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import save_checkpoint_artifact
from model_dataset import build_dataloaders
from model_evaluator import TrainedEvaluator, promote_trained_model
from model_heads import train_model
from training_experimentation import (
    DatasetSplit,
    ExperimentConfig,
    PromotionPolicy,
    assemble_checkpoint,
    compute_qwk,
    decide_promotion,
    grade_to_ordinal,
    run_benchmark,
)

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2")

RANDOM_SEED = 42
DATASET_VERSION = "v_experiment_2_scaled_library"
MODEL_VERSION = "deberta_v3_base_experiment_2"
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
# Phase: train (COLAB-INTENDED, portable) — identical procedure to
# run_experiment_1.py's phase_train, pointed at Experiment 2's artifacts.
# ═════════════════════════════════════════════════════════════════════════════


def phase_train() -> int:
    _log("=== Experiment 2 / Phase: TRAIN (Colab-intended; device auto-detected) ===")
    if not os.path.exists(DATASET_PATH):
        _log(f"BLOCKER: {DATASET_PATH!r} not found -- run 'run_experiment_2.py generate' first (on the local machine).")
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
    if len(sys.argv) != 2 or sys.argv[1] != "train":
        print("Usage: python run_experiment_2_train.py train", file=sys.stderr)
        return 2
    return phase_train()


if __name__ == "__main__":
    sys.exit(main())
