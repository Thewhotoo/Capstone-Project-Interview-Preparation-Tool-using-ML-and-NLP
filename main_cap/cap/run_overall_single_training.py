"""
Overall Single-Score Training — V3 Single-Overall-Score Architecture
(isolated, additive, COLAB-INTENDED, GPU-required).

The training entry point for the NEW simplified evaluator architecture:
fresh `microsoft/deberta-v3-base` + ONE CORAL ordinal head
(`overall_score_model.OverallScoreModel`), trained to predict a single
overall 0-4 score, on the SAME 220-example leakage-controlled V2 pool and
FROZEN 166/27/27 split every four-dimension experiment (v2/v3/A0/A1/A2/B0)
already uses (`artifacts/four_dim_experiment_v2/split.json` — never
regenerated, never touched by this script).

NOT A NEW SUBSYSTEM: reuses, unmodified, `overall_dataset.
build_overall_dataloaders`/`collate_fn`, `overall_score_model.
train_overall_model`/`OverallScoreModel`/`coral_predict` (via
`model_heads`), `overall_score_model.save_overall_checkpoint_artifact`/
`load_overall_checkpoint_artifact`, `training_experimentation.
assemble_checkpoint`/`compute_qwk`, `four_dim_experiment_v2_split.
load_v2_pool`. The only new code is this script's own orchestration.

ISOLATION FROM EVERY EXISTING ARTIFACT (explicit, load-bearing): this
script NEVER writes to `deployed_model/`, `deployed_model_a2/`, or any
`artifacts/four_dim_training_*`/`artifacts/four_dim_training_v3_exp*`
directory. Its own output directory is `artifacts/overall_single_v3/`, a
brand-new, never-before-used path. Nothing this script does can overwrite
the A2/B0 checkpoints or any other prior experiment's artifacts.

DOES NOT DEPLOY ANYTHING: this script produces a checkpoint file on disk
only. It does not call `evaluator_registry.register_evaluator`, does not
touch `deployment_evaluator.py`, and does not change which evaluator the
live application serves.

Same hard-CUDA-required discipline as `run_four_dim_training.py` (see that
module's docstring for the measured local-CPU-OOM rationale this mirrors):
    python run_overall_single_training.py --dry-run   # LOCAL, safe
    python run_overall_single_training.py train        # COLAB (GPU required)
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from collections import Counter

import torch

from four_dim_experiment_v2_split import load_v2_pool
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS  # noqa: F401 -- re-exported for callers/tests only
from model_backbone import BackboneConfig, build_tokenizer
from overall_dataset import build_overall_dataloaders
from overall_score_model import (
    load_overall_checkpoint_artifact,
    save_overall_checkpoint_artifact,
    train_overall_model,
)
from training_experimentation import DatasetSplit, ExperimentConfig, assemble_checkpoint, compute_qwk

NUM_CLASSES = 5

_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Single experiment: "v3_overall_single" ───────────────────────────────
# Same 220-example pool + same frozen V2 split as v2/v3/A0/A1/A2/B0 -- the
# ONLY thing that differs is the ARCHITECTURE (one shared overall CORAL
# head instead of four per-dimension heads) and the training TARGET (the
# derived overall label, see overall_dataset.py's module docstring for the
# exact, documented policy). Its own, brand-new, isolated artifacts_dir.
EXPERIMENTS = {
    "v3_overall_single": dict(
        load_pool=load_v2_pool,
        split_json_path=os.path.join(_HERE, "artifacts", "four_dim_experiment_v2", "split.json"),
        artifacts_dir=os.path.join(_HERE, "artifacts", "overall_single_v3"),
        expected_total=220, expected_counts=(166, 27, 27),
        dataset_split_identifier="four_dim_experiment_v2",
        split_seed="four_dim_v2_split_348",
        model_version="deberta_v3_base_overall_single_v3",
        label="Overall Single-Score Training V3 (one CORAL head, unweighted loss)",
    ),
}

# ── Training configuration — as specified for this redesign ─────────────
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


def _load_frozen_split(split_json_path: str) -> DatasetSplit:
    with open(split_json_path, encoding="utf-8") as f:
        raw = json.load(f)
    return DatasetSplit(
        train_ids=tuple(raw["train_ids"]), val_ids=tuple(raw["val_ids"]), test_ids=tuple(raw["test_ids"]),
    )


def _assert_no_group_leakage(examples, split) -> None:
    by_id = {e.metadata.example_id: e for e in examples}
    groups = {
        "train": {by_id[i].inputs.specification.source_id for i in split.train_ids},
        "val": {by_id[i].inputs.specification.source_id for i in split.val_ids},
        "test": {by_id[i].inputs.specification.source_id for i in split.test_ids},
    }
    overlaps = {
        "train|val": sorted(groups["train"] & groups["val"]),
        "train|test": sorted(groups["train"] & groups["test"]),
        "val|test": sorted(groups["val"] & groups["test"]),
    }
    if any(overlaps.values()):
        raise SystemExit(f"BLOCKER: source/group leakage detected before training: {overlaps}")
    _log(f"Leakage check: 0 shared source_id across train/val/test (groups: "
         f"train={len(groups['train'])} val={len(groups['val'])} test={len(groups['test'])}).")


# ── Overall-score metrics (compute_qwk itself is reused, not reimplemented) ──

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

def dry_run(experiment: str = "v3_overall_single") -> int:
    """LOCAL, safe: confirms the frozen pool+split loads and reports the
    environment. Never downloads the real backbone, never trains."""
    cfg = EXPERIMENTS[experiment]
    report = environment_report()
    _log(f"Environment report: {json.dumps(report, indent=2)}")
    examples = cfg["load_pool"]()
    split = _load_frozen_split(cfg["split_json_path"])
    _log(f"[{experiment}] {cfg['label']} pool: {len(examples)} examples. Split: "
         f"train={len(split.train_ids)} val={len(split.val_ids)} test={len(split.test_ids)}")
    if len(examples) != cfg["expected_total"]:
        _log(f"BLOCKER: expected {cfg['expected_total']} pool examples, got {len(examples)}")
        return 1
    expected_tr, expected_va, expected_te = cfg["expected_counts"]
    actual = (len(split.train_ids), len(split.val_ids), len(split.test_ids))
    if actual != (expected_tr, expected_va, expected_te):
        _log(f"BLOCKER: expected split counts {(expected_tr, expected_va, expected_te)}, got {actual}")
        return 1
    _log("--dry-run complete: no download, no training. "
         f"CUDA available here: {report['cuda_available']} (irrelevant for dry-run).")
    return 0


# ── train (COLAB, GPU required) ──────────────────────────────────────────

def train(experiment: str = "v3_overall_single") -> int:
    cfg = EXPERIMENTS[experiment]
    report = environment_report()
    _log(f"Environment report: {json.dumps(report, indent=2)}")
    require_cuda_or_exit(report)
    device = "cuda"

    artifacts_dir = cfg["artifacts_dir"]
    os.makedirs(artifacts_dir, exist_ok=True)
    _log(f"=== {cfg['label']} (experiment={experiment}, device={device}, GPU={report['gpu_name']}) ===")
    _log(f"Config: {json.dumps(CONFIG, indent=2)}")

    examples = cfg["load_pool"]()
    if len(examples) != cfg["expected_total"]:
        _log(f"BLOCKER: expected {cfg['expected_total']} pool examples, got {len(examples)}")
        return 1
    split = _load_frozen_split(cfg["split_json_path"])
    expected_tr, expected_va, expected_te = cfg["expected_counts"]
    actual = (len(split.train_ids), len(split.val_ids), len(split.test_ids))
    if actual != (expected_tr, expected_va, expected_te):
        _log(f"BLOCKER: split counts do not match the approved {experiment} split -- refusing to train.")
        return 1
    _assert_no_group_leakage(examples, split)

    backbone_config = BackboneConfig(hf_model_id=CONFIG["base_model"], max_length=CONFIG["max_length"])
    tokenizer = build_tokenizer(backbone_config)
    train_loader, val_loader, test_loader = build_overall_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=CONFIG["batch_size"], seed=CONFIG["random_seed"],
    )
    _log(f"Dataloaders: train_batches={len(train_loader)} val_batches={len(val_loader)} test_batches={len(test_loader)}")

    best_weights_path = os.path.join(artifacts_dir, "best_checkpoint_weights.pt")
    best_checkpoint_path = os.path.join(artifacts_dir, "best_checkpoint.json")
    epoch_curve: list[dict] = []
    best = {"val_qwk": -1.0, "epoch": None, "checkpoint": None, "val_metrics": None}

    experiment_config = ExperimentConfig(
        backbone_name=backbone_config.hf_model_id, random_seed=CONFIG["random_seed"],
        dataset_version=cfg["dataset_split_identifier"],
        parameters={
            **{k: (v if isinstance(v, (str, int, float, bool)) else str(v)) for k, v in CONFIG.items()},
            "split_seed": cfg["split_seed"], "experiment": experiment,
            "environment": json.dumps(report), "architecture": "single_coral_head_overall_score",
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
                model_version=f"{cfg['model_version']}_epoch{epoch_index}",
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

    with open(os.path.join(artifacts_dir, "epoch_curve.json"), "w", encoding="utf-8") as f:
        json.dump(epoch_curve, f, indent=2)

    if best["epoch"] is None:
        _log("BLOCKER: no epoch ever improved on the untrained baseline -- refusing to select a best checkpoint.")
        return 1
    _log(f"Best checkpoint: epoch {best['epoch']} (val QWK={best['val_qwk']:.4f}).")

    best_model = load_overall_checkpoint_artifact(best_weights_path, backbone_config, map_location=device)
    test_y_true, test_y_pred = _collect_predictions(best_model, test_loader, device)
    test_metrics = _overall_metrics(test_y_true, test_y_pred)
    _log(f"TEST metrics (best checkpoint, epoch {best['epoch']}): {test_metrics['qwk']:.4f} QWK")

    with open(os.path.join(artifacts_dir, "test_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({
            "best_epoch": best["epoch"], "val_qwk": best["val_qwk"],
            "val_metrics": best["val_metrics"], "test_metrics": test_metrics,
            "training_duration_seconds": round(duration_s, 1), "config": CONFIG, "environment": report,
        }, f, indent=2)

    _log(f"=== {cfg['label'].upper()} COMPLETE ===")
    _log(f"Copy back to the repository: {artifacts_dir!r}")
    return 0


def main() -> int:
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("--dry-run", "train"):
        print(f"Usage: python run_overall_single_training.py [--dry-run|train] [{'|'.join(sorted(EXPERIMENTS))}]", file=sys.stderr)
        return 2
    experiment = sys.argv[2] if len(sys.argv) == 3 else "v3_overall_single"
    if experiment not in EXPERIMENTS:
        print(f"Unknown experiment {experiment!r}; must be one of {sorted(EXPERIMENTS)}", file=sys.stderr)
        return 2
    if sys.argv[1] == "--dry-run":
        return dry_run(experiment)
    return train(experiment)


if __name__ == "__main__":
    sys.exit(main())
