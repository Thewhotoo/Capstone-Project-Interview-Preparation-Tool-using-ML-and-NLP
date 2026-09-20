"""
Overall Single-Score Training — v5_overall_1088 experiment (isolated,
additive, COLAB-INTENDED, GPU-required).

Controlled comparison against the deployed 1003-only baseline
(`deberta_v3_base_overall_single_v4_1003_epoch7`: val QWK 0.8619, test QWK
0.8451, test accuracy 0.5894, test MAE 0.4305, test within-1 0.9801 — see
`artifacts/overall_single_v4_1003/test_metrics.json`). Everything below is
IDENTICAL to `train_overall.py` (architecture, seed, optimizer, LR, batch
size, epochs, max_length, weight_decay, scheduler, dropout, loss) except:

    1. DATASET: `artifacts/overall_v5_1088/dataset/` (1003 baseline examples
       + 85 v5_short_quality_calibration_80 examples), built read-only by
       `../build_v5_1088_pool.py`, instead of the 1003-only pool.
    2. SPLIT: val_ids/test_ids are BYTE-IDENTICAL to the 1003 baseline's
       702/150/151 split (150 val, 151 test) — only train grows, from 702 to
       787 (702 + 85 calibration examples). Verified by
       `dataset_loader_v5.verify_dataset_integrity` before training starts.
    3. Its own isolated output directory (`artifacts/overall_single_v5_1088/`)
       and model_version prefix (`deberta_v3_base_overall_single_v5_1088`),
       so this NEVER overwrites the v4_1003 checkpoint.

This keeps the old-vs-new comparison on the 151-example test set strictly
apples-to-apples: same test examples, same architecture, same
hyperparameters — the ONLY variable is 85 additional calibration examples in
train.

DOES NOT DEPLOY ANYTHING. Produces checkpoint files on disk only. Does not
touch `deployed_model_overall_single_v3/`, `evaluator_registry.py`,
`deployment_evaluator.py`, or any production file.

Usage (identical shape to train_overall.py):
    python train_overall_v5.py --dry-run   # LOCAL, safe, no download, no training
    python train_overall_v5.py train        # COLAB (GPU required)
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from collections import Counter

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
CAP_DIR = os.path.dirname(_HERE)
sys.path.insert(0, CAP_DIR)

from dataset_loader_v5 import (  # noqa: E402
    EXPECTED_CAL_COUNT,
    EXPECTED_COUNTS,
    EXPECTED_TOTAL,
    assert_no_group_leakage,
    load_examples,
    load_split,
    verify_dataset_integrity,
)
from model_backbone import BackboneConfig, build_tokenizer  # noqa: E402
from overall_dataset import build_overall_dataloaders  # noqa: E402
from overall_score_model import (  # noqa: E402
    load_overall_checkpoint_artifact,
    save_overall_checkpoint_artifact,
    train_overall_model,
)
from training_experimentation import ExperimentConfig, assemble_checkpoint, compute_qwk  # noqa: E402

NUM_CLASSES = 5

ARTIFACTS_DIR = os.path.join(CAP_DIR, "artifacts", "overall_single_v5_1088")
MODEL_VERSION_PREFIX = "deberta_v3_base_overall_single_v5_1088"
DATASET_VERSION_IDENTIFIER = "overall_v5_1088"
SPLIT_SEED = "four_dim_overall_v4_5000_split"  # val/test inherited verbatim from this seed's split

# ── Training configuration — IDENTICAL to train_overall.py / CONFIG. Not
# changed for this experiment: the entire point is that dataset composition
# is the only variable. ──
CONFIG = {
    "base_model": "microsoft/deberta-v3-base",
    "fresh_initialization": True,
    "random_seed": 42,
    "learning_rate": 2e-5,
    "batch_size": 8,
    "num_epochs": 8,
    "max_length": 256,
    "optimizer": "AdamW (torch.optim.AdamW, default betas/eps)",
    "scheduler": "none (constant learning rate)",
    "weight_decay": 0.01,
    "loss": "unweighted CORAL (coral_loss, no pos_weight -- no A1/A2 loss weighting)",
    "dropout": (
        "not explicitly configured -- uses microsoft/deberta-v3-base's own HF config "
        "default (hidden_dropout_prob=0.1, attention_probs_dropout_prob=0.1)"
    ),
}


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def environment_report() -> dict:
    import transformers
    return {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }


def require_cuda_or_exit(report: dict) -> None:
    if not report["cuda_available"]:
        _log("BLOCKER: CUDA is not available in this runtime.")
        _log("This script refuses to train on CPU. Run it in a GPU-backed Colab runtime instead.")
        sys.exit(1)


def _collect_predictions(model, loader, device: str) -> tuple[list[int], list[int]]:
    from model_heads import coral_predict
    model.eval()
    y_true: list[int] = []
    y_pred: list[int] = []
    with torch.no_grad():
        for batch in loader:
            ids = batch["main_input_ids"].to(device)
            mask = batch["main_attention_mask"].to(device)
            logits = model(ids, mask)
            preds = coral_predict(logits).cpu().tolist()
            targets = batch["overall_target"].tolist()
            y_pred.extend(int(p) for p in preds)
            y_true.extend(int(t) for t in targets)
    return y_true, y_pred


def _overall_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    n = len(y_true)
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n
    within1 = sum(1 for t, p in zip(y_true, y_pred) if abs(t - p) <= 1) / n
    mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n
    qwk = compute_qwk(tuple(y_true), tuple(y_pred), NUM_CLASSES)
    confusion = [[0] * NUM_CLASSES for _ in range(NUM_CLASSES)]
    for t, p in zip(y_true, y_pred):
        confusion[t][p] += 1
    return {
        "n": n, "accuracy": round(accuracy, 4), "within_1_accuracy": round(within1, 4),
        "mae": round(mae, 4), "qwk": round(qwk, 4), "confusion_matrix": confusion,
        "true_distribution": dict(sorted(Counter(y_true).items())),
        "pred_distribution": dict(sorted(Counter(y_pred).items())),
    }


# ── dry-run (LOCAL, safe) ─────────────────────────────────────────────────

def dry_run() -> int:
    report = environment_report()
    _log(f"Environment report: {json.dumps(report, indent=2)}")
    examples = load_examples()
    split = load_split()
    verify_dataset_integrity(examples, split)
    assert_no_group_leakage(examples, split)
    cal_in_train = sum(1 for i in split.train_ids if i.startswith("v5cal_"))
    _log(f"Dataset OK: {len(examples)} examples (expected {EXPECTED_TOTAL}). "
         f"Split: train={len(split.train_ids)} val={len(split.val_ids)} test={len(split.test_ids)} "
         f"(expected {EXPECTED_COUNTS}). Calibration examples in train: {cal_in_train} "
         f"(expected {EXPECTED_CAL_COUNT}). Calibration examples in val/test: 0 (verified).")
    _log("--dry-run complete: no download, no training. "
         f"CUDA available here: {report['cuda_available']} (irrelevant for dry-run).")
    return 0


# ── train (COLAB, GPU required) ──────────────────────────────────────────

def train() -> int:
    report = environment_report()
    _log(f"Environment report: {json.dumps(report, indent=2)}")
    require_cuda_or_exit(report)
    device = "cuda"

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    _log(f"=== Overall Single-Score Training v5_1088 (device={device}, GPU={report['gpu_name']}) ===")
    _log(f"Config: {json.dumps(CONFIG, indent=2)}")

    examples = load_examples()
    split = load_split()
    verify_dataset_integrity(examples, split)
    assert_no_group_leakage(examples, split)
    _log(f"Dataset verified: {len(examples)} examples, split train={len(split.train_ids)} "
         f"val={len(split.val_ids)} test={len(split.test_ids)}. 0 group leakage across splits.")

    backbone_config = BackboneConfig(hf_model_id=CONFIG["base_model"], max_length=CONFIG["max_length"])
    tokenizer = build_tokenizer(backbone_config)
    train_loader, val_loader, test_loader = build_overall_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=CONFIG["batch_size"], seed=CONFIG["random_seed"],
    )
    _log(f"Dataloaders: train_batches={len(train_loader)} val_batches={len(val_loader)} test_batches={len(test_loader)}")

    best_weights_path = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
    best_checkpoint_path = os.path.join(ARTIFACTS_DIR, "best_checkpoint.json")
    epoch_curve: list[dict] = []
    best = {"val_qwk": -1.0, "epoch": None, "checkpoint": None, "val_metrics": None}

    experiment_config = ExperimentConfig(
        backbone_name=backbone_config.hf_model_id, random_seed=CONFIG["random_seed"],
        dataset_version=DATASET_VERSION_IDENTIFIER,
        parameters={
            **{k: (v if isinstance(v, (str, int, float, bool)) else str(v)) for k, v in CONFIG.items()},
            "split_seed": SPLIT_SEED, "experiment": "v5_1088_overall_single",
            "environment": json.dumps(report), "architecture": "single_coral_head_overall_score",
            "dataset_size": len(examples), "baseline_count": 1003, "calibration_count": 85,
            "baseline_comparison": (
                "deberta_v3_base_overall_single_v4_1003_epoch7 (1003 examples, test QWK 0.8451, "
                "SAME 151 test ids, SAME 150 val ids)"
            ),
        },
    )

    def on_epoch_end(epoch_index: int, model, train_loss, val_loss) -> None:
        label = "untrained (epoch 0)" if epoch_index == 0 else f"epoch {epoch_index}"
        y_true, y_pred = _collect_predictions(model, val_loader, device)
        val_metrics = _overall_metrics(y_true, y_pred)
        _log(f"--- {label}: train_loss={train_loss} val_loss={val_loss} val_qwk={val_metrics['qwk']:.4f} ---")
        epoch_curve.append({
            "epoch": epoch_index, "train_loss": train_loss, "val_loss": val_loss, "val_metrics": val_metrics,
        })
        if epoch_index > 0 and val_metrics["qwk"] > best["val_qwk"]:
            save_overall_checkpoint_artifact(model, best_weights_path)
            checkpoint = assemble_checkpoint(
                model_version=f"{MODEL_VERSION_PREFIX}_epoch{epoch_index}",
                experiment_config=experiment_config, artifact_uri=best_weights_path,
            )
            with open(best_checkpoint_path, "w", encoding="utf-8") as f:
                f.write(checkpoint.model_dump_json(indent=2))
            best.update({"val_qwk": val_metrics["qwk"], "epoch": epoch_index, "checkpoint": checkpoint, "val_metrics": val_metrics})
            _log(f"    New best checkpoint: {label} (val QWK={val_metrics['qwk']:.4f}) -- saved to {best_weights_path!r}")

    t0 = time.time()
    train_overall_model(
        train_loader, val_loader, backbone_config, num_epochs=CONFIG["num_epochs"],
        learning_rate=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"],
        device=device, random_seed=CONFIG["random_seed"], on_epoch_end=on_epoch_end,
    )
    duration_s = time.time() - t0
    _log(f"Training complete in {duration_s:.1f}s ({duration_s/60:.1f} min).")

    with open(os.path.join(ARTIFACTS_DIR, "epoch_curve.json"), "w", encoding="utf-8") as f:
        json.dump(epoch_curve, f, indent=2)

    if best["epoch"] is None:
        _log("BLOCKER: no epoch ever improved on the untrained baseline -- refusing to select a best checkpoint.")
        return 1
    _log(f"Best checkpoint: epoch {best['epoch']} (val QWK={best['val_qwk']:.4f}). "
         f"Model selection used VALIDATION QWK only -- test set was not touched during training.")

    best_model = load_overall_checkpoint_artifact(best_weights_path, backbone_config, map_location=device)
    test_y_true, test_y_pred = _collect_predictions(best_model, test_loader, device)
    test_metrics = _overall_metrics(test_y_true, test_y_pred)
    _log(f"TEST metrics (best checkpoint, epoch {best['epoch']}, evaluated ONCE): {test_metrics['qwk']:.4f} QWK")

    with open(os.path.join(ARTIFACTS_DIR, "test_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({
            "best_epoch": best["epoch"], "val_qwk": best["val_qwk"],
            "val_metrics": best["val_metrics"], "test_metrics": test_metrics,
            "training_duration_seconds": round(duration_s, 1), "config": CONFIG, "environment": report,
            "dataset_version": DATASET_VERSION_IDENTIFIER, "dataset_size": len(examples),
            "split_counts": {"train": len(split.train_ids), "val": len(split.val_ids), "test": len(split.test_ids)},
            "baseline_comparison": {
                "model_version": "deberta_v3_base_overall_single_v4_1003_epoch7",
                "dataset_size": 1003, "test_qwk": 0.8451, "val_qwk": 0.8619,
                "test_accuracy": 0.5894, "test_within_1_accuracy": 0.9801, "test_mae": 0.4305,
            },
        }, f, indent=2)

    _log("=== OVERALL SINGLE-SCORE TRAINING V5_1088 COMPLETE ===")
    _log(f"Download this directory back from Colab: {ARTIFACTS_DIR!r}")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("--dry-run", "train"):
        print("Usage: python train_overall_v5.py [--dry-run|train]", file=sys.stderr)
        return 2
    if sys.argv[1] == "--dry-run":
        return dry_run()
    return train()


if __name__ == "__main__":
    sys.exit(main())
