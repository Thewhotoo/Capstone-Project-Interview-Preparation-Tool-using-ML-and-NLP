"""
Experiment 2 — Tuned Training Configuration: the single, coherent
hyperparameter change motivated directly by the corrected Experiment 2
baseline (session 11: validation-driven checkpoint selection), which showed
validation QWK still rising/plateauing through epoch 5 (0.4932 -> 0.5320 ->
0.5286 -> 0.5412 -> 0.5418) while TEST QWK peaks at epoch 3 and then falls
(0.3727 -> 0.4378 -> 0.4450 -> 0.4235 -> 0.4199). Validation and test
diverge starting exactly where training has accumulated many gradient steps
at a constant, undecayed learning rate -- the same mechanism already
identified (Experiment 2 root-cause analysis) as the leading explanation
for Experiment 2's instability relative to Experiment 1.

WHAT CHANGES (one coherent configuration, not a sweep):
  - TRAIN_BATCH_SIZE: kept at 4 (the original Experiment 2 baseline value).
    An earlier revision of this configuration doubled it to 8 to reduce
    step-count noise, but that run hit a CUDA out-of-memory error on the
    T4 GPU it was run on; batch=4 is the only batch size confirmed to fit,
    so it was reverted. The step-count-noise mechanism this was meant to
    address is instead addressed by the LR schedule below, which lets the
    model settle late in training regardless of how many steps it takes.
  - Linear warmup + linear decay to zero (`train_model`'s new, additive
    `use_lr_decay`/`num_warmup_steps`, session 11): the model never
    previously spent any time at a LOW learning rate late in training --
    this is what let it keep drifting after its best test-generalizing
    point (epoch 3). Decaying to ~0 by the end of the schedule gives the
    model a chance to settle rather than keep oscillating. A short (10%)
    warmup is the standard, low-risk complement to decay for a pretrained
    transformer, preventing a large early gradient kick to weights that are
    already well-initialized from pretraining.
  - `weight_decay=0.01` made EXPLICIT (was already AdamW's implicit
    default -- no magnitude change, just documented as an intentional part
    of this configuration rather than a silent default).
  - LEARNING_RATE, NUM_EPOCHS, backbone, optimizer type, benchmarking
    methodology (test-set reporting + validation-set checkpoint selection,
    session 11), promotion policy, and the dataset are ALL unchanged from
    the just-established baseline.

WHAT DOES NOT CHANGE, DELIBERATELY:
  - Early stopping is NOT added. It would conflict with a schedule whose
    decay curve is computed against a FIXED total-step horizon
    (num_epochs * steps_per_epoch) -- stopping early would cut training off
    before the LR reaches its low, stabilizing tail, undermining the exact
    mechanism this configuration relies on. It is also functionally
    redundant here: best-checkpoint-by-validation-QWK persistence (already
    implemented) already guarantees the best epoch survives regardless of
    how long training continues past it.
  - Peak LEARNING_RATE is unchanged (2e-5). Nothing in the evidence points
    at the peak magnitude itself being wrong (epoch-1/2 progress was
    healthy); the evidenced problem is the ABSENCE of decay over a long
    constant-LR run, which is what this configuration fixes.

DATASET: unchanged. Reads `artifacts/experiment_2/{dataset.jsonl,
manifest.json, split.json}` (Experiment 2's already-generated dataset,
generation pipeline untouched). Writes ALL of its own outputs (epoch curve,
per-epoch benchmarks, best checkpoint, promotion decision) to a SEPARATE
`artifacts/experiment_2_tuned/` directory so the just-established
validation-driven baseline in `artifacts/experiment_2/` is never
overwritten.

NOT A NEW SUBSYSTEM: reuses `train_model`, `build_dataloaders`,
`TrainedEvaluator`, `run_benchmark`, `decide_promotion`,
`promote_trained_model` unchanged (`train_model`'s only change is the new,
additive, default-off `weight_decay`/`num_warmup_steps`/`use_lr_decay`
parameters -- see `model_heads.py`; every existing caller that omits them
gets bit-for-bit the same behavior as before).
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
from model_checkpoint_io import load_checkpoint_artifact, save_checkpoint_artifact
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

# Source dataset: Experiment 2's already-generated artifacts (unchanged, read-only here).
DATASET_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2")
# Output: a separate directory so the validation-driven baseline is never overwritten.
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2_tuned")

RANDOM_SEED = 42
DATASET_VERSION = "v_experiment_2_scaled_library"  # unchanged -- same dataset, must match manifest/checkpoint.
MODEL_VERSION = "deberta_v3_base_experiment_2_tuned"
MAX_LENGTH = 128

# --- The one coherent tuned configuration ---
TRAIN_BATCH_SIZE = 4          # reverted from 8 -- batch=8 hit CUDA OOM on the T4 GPU; batch=4 is the
                               # value already known to fit (it's Experiment 2 baseline's batch size)
NUM_EPOCHS = 5                 # unchanged -- val QWK already plateaus by epoch 4-5 in the baseline
LEARNING_RATE = 2e-5           # unchanged peak LR -- no evidence the magnitude itself is wrong
WEIGHT_DECAY = 0.01            # unchanged value, now explicit (was AdamW's implicit default)
WARMUP_RATIO = 0.1             # standard 10% linear warmup
USE_LR_DECAY = True            # new: linear warmup + linear decay to zero over the full schedule

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})
_NUM_ORDINAL_CLASSES = 5

DATASET_PATH = os.path.join(DATASET_ARTIFACTS_DIR, "dataset.jsonl")
MANIFEST_PATH = os.path.join(DATASET_ARTIFACTS_DIR, "manifest.json")
SPLIT_PATH = os.path.join(DATASET_ARTIFACTS_DIR, "split.json")


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
# Phase: train (COLAB-INTENDED, portable) — same procedure as
# run_experiment_2_train.py's phase_train, with the tuned configuration above.
# ═════════════════════════════════════════════════════════════════════════════


def phase_train() -> int:
    _log("=== Experiment 2 (Tuned) / Phase: TRAIN (Colab-intended; device auto-detected) ===")
    if not os.path.exists(DATASET_PATH):
        _log(f"BLOCKER: {DATASET_PATH!r} not found -- run 'run_experiment_2.py generate' first (on the local machine).")
        return 1
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = load_examples_jsonl(DATASET_PATH)
    manifest = load_json(DatasetManifest, MANIFEST_PATH)
    split = load_json(DatasetSplit, SPLIT_PATH)
    by_id = {e.metadata.example_id: e for e in examples}
    _log(f"Loaded {len(examples)} examples (dataset_version={manifest.dataset_version!r}) from {DATASET_ARTIFACTS_DIR!r}.")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=MAX_LENGTH)
    tokenizer = build_tokenizer(backbone_config)
    train_loader, val_loader, test_loader = build_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=TRAIN_BATCH_SIZE, seed=RANDOM_SEED,
    )
    _log(f"Dataloaders: train_batches={len(train_loader)}, val_batches={len(val_loader)}, test_batches={len(test_loader)}")

    total_steps = NUM_EPOCHS * len(train_loader)
    num_warmup_steps = int(WARMUP_RATIO * total_steps)
    _log(f"LR schedule: linear warmup for {num_warmup_steps}/{total_steps} steps, "
         f"then linear decay to 0 (peak lr={LEARNING_RATE}, weight_decay={WEIGHT_DECAY}).")

    test_examples = tuple(by_id[i] for i in split.test_ids)
    core_test_examples = tuple(e for e in test_examples if e.labels.overall_label.grade in _CORE_GRADES)
    val_examples = tuple(by_id[i] for i in split.val_ids)
    core_val_examples = tuple(e for e in val_examples if e.labels.overall_label.grade in _CORE_GRADES)
    train_examples = tuple(by_id[i] for i in split.train_ids)
    majority_grade = _majority_grade(train_examples)
    majority_qwk = _trivial_baseline_qwk(core_test_examples, majority_grade)
    _log(f"Trivial majority-class baseline: predicts {majority_grade!r} always -> QWK={majority_qwk:.4f} "
         f"({len(core_test_examples)}/{len(test_examples)} core-grade test examples).")
    _log(f"Checkpoint selection will use {len(core_val_examples)}/{len(val_examples)} core-grade "
         f"VALIDATION examples (never the test set) -- test remains reserved for final reporting/promotion gating.")

    baseline = HeuristicEvaluator()
    epoch_curve: list[dict] = []

    # Best-checkpoint tracking (unchanged mechanism from the validation-driven
    # baseline): exactly ONE checkpoint kept on disk, overwritten in place on
    # each new best VALIDATION QWK.
    best_weights_path = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
    best_checkpoint_path = os.path.join(ARTIFACTS_DIR, "best_checkpoint.json")
    best: dict = {"val_qwk": -1.0, "epoch": None, "checkpoint": None, "test_benchmark": None}

    def on_epoch_end(epoch_index: int, model, train_loss, val_loss) -> None:
        label = "untrained (epoch 0)" if epoch_index == 0 else f"epoch {epoch_index}"
        _log(f"--- Benchmarking {label} ---")
        placeholder_config = ExperimentConfig(
            backbone_name=backbone_config.hf_model_id, random_seed=RANDOM_SEED, dataset_version=DATASET_VERSION,
            parameters={
                "epoch": epoch_index, "learning_rate": LEARNING_RATE, "batch_size": TRAIN_BATCH_SIZE,
                "weight_decay": WEIGHT_DECAY, "num_warmup_steps": num_warmup_steps, "use_lr_decay": USE_LR_DECAY,
            },
        )
        checkpoint = assemble_checkpoint(
            model_version=f"{MODEL_VERSION}_epoch{epoch_index}", experiment_config=placeholder_config,
            artifact_uri=f"in-memory-epoch-{epoch_index}",
        )
        candidate = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)

        # Reporting benchmark: test set, feeds epoch_curve_summary.json / epoch_N_benchmark.json.
        benchmark = run_benchmark(candidate, baseline, core_test_examples, dataset_version=DATASET_VERSION)

        # Selection benchmark: validation set, used ONLY to decide which checkpoint is "best".
        val_benchmark = run_benchmark(candidate, baseline, core_val_examples, dataset_version=DATASET_VERSION)

        _log(f"  test QWK={benchmark.candidate_qwk:.4f}  val QWK={val_benchmark.candidate_qwk:.4f}  "
             f"baseline QWK={benchmark.baseline_qwk:.4f}  majority QWK={majority_qwk:.4f}  "
             f"train_loss={train_loss}  val_loss={val_loss}")
        save_json(benchmark, os.path.join(ARTIFACTS_DIR, f"epoch_{epoch_index}_benchmark.json"))
        epoch_curve.append({
            "epoch": epoch_index, "train_loss": train_loss, "val_loss": val_loss,
            "candidate_qwk": benchmark.candidate_qwk, "baseline_qwk": benchmark.baseline_qwk,
            "majority_qwk": majority_qwk, "val_qwk": val_benchmark.candidate_qwk,
        })

        if val_benchmark.candidate_qwk > best["val_qwk"]:
            save_checkpoint_artifact(model, best_weights_path)
            best_checkpoint = checkpoint.model_copy(update={"artifact_uri": best_weights_path})
            save_json(best_checkpoint, best_checkpoint_path)
            best.update({"val_qwk": val_benchmark.candidate_qwk, "epoch": epoch_index,
                         "checkpoint": best_checkpoint, "test_benchmark": benchmark})
            _log(f"  New best checkpoint: {label} (val QWK={val_benchmark.candidate_qwk:.4f}, "
                 f"test QWK={benchmark.candidate_qwk:.4f}) -- overwrote {best_weights_path!r}.")

    t0 = time.time()
    train_model(
        train_loader, val_loader, backbone_config, num_epochs=NUM_EPOCHS, learning_rate=LEARNING_RATE,
        device=device, random_seed=RANDOM_SEED, on_epoch_end=on_epoch_end,
        weight_decay=WEIGHT_DECAY, num_warmup_steps=num_warmup_steps, use_lr_decay=USE_LR_DECAY,
    )
    _log(f"Training + per-epoch benchmarking complete in {time.time() - t0:.1f}s.")

    with open(os.path.join(ARTIFACTS_DIR, "epoch_curve_summary.json"), "w", encoding="utf-8") as f:
        json.dump(epoch_curve, f, indent=2)
    _log(f"Epoch curve summary written to {os.path.join(ARTIFACTS_DIR, 'epoch_curve_summary.json')!r}.")

    # Promotion evaluates the BEST (by validation QWK) checkpoint, gated on
    # its TEST benchmark -- identical discipline to the validation-driven
    # baseline this configuration is being compared against.
    _log(f"Best checkpoint: epoch {best['epoch']} (val QWK={best['val_qwk']:.4f}, "
         f"test QWK={best['test_benchmark'].candidate_qwk:.4f}).")
    best_model = load_checkpoint_artifact(best_weights_path, backbone_config, map_location=device)
    best_candidate = TrainedEvaluator(best["checkpoint"], best_model, tokenizer, backbone_config)

    decision = decide_promotion(best["checkpoint"], best["test_benchmark"], PromotionPolicy())
    save_json(decision, os.path.join(ARTIFACTS_DIR, "final_promotion_decision.json"))
    _log(f"Promotion decision (best checkpoint by val QWK, epoch {best['epoch']}, "
         f"gated on test QWK={best['test_benchmark'].candidate_qwk:.4f}): "
         f"approved={decision.approved} -- {decision.rationale}")
    if decision.approved:
        promote_trained_model(best["checkpoint"], decision, best_candidate, make_active=True)
        _log(f"Promoted and registered as the active evaluator: {best_candidate.name}")

    _log("=== TRAIN PHASE COMPLETE ===")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "train":
        print("Usage: python run_experiment_2_train_tuned.py train", file=sys.stderr)
        return 2
    return phase_train()


if __name__ == "__main__":
    sys.exit(main())
