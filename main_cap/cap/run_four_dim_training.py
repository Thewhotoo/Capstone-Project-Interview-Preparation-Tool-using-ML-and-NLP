"""
Four-Dimension Training — Phase 4 (COLAB-INTENDED, GPU-required).

The canonical four-dimension training entry point: fresh
`microsoft/deberta-v3-base` + four canonical CORAL ordinal heads
(`dimension_names=CANONICAL_DIMENSION_KEYS`), trained on the FROZEN
group-aware split at `artifacts/four_dim_experiment_v1/split.json`
(128 train / 20 val / 22 test), never the old 12-dimension checkpoint.

UNLIKE this codebase's existing "Colab-intended, portable" training
scripts (`run_experiment_1/2/4_train.py`, which auto-detect device and
silently fall back to CPU for local smoke-testing), this script **requires
CUDA and fails clearly if it is unavailable** — a deliberate, explicit
change for this experiment: a real training attempt on this project's
7.5GB-RAM local machine was found to exceed available memory and stall
under disk paging (see `docs/architecture/DeBERTa_Dataset_Rebuild_Status.md`'s
Phase 4 checkpoint for the measured failure). Local execution of this
script is for `--dry-run` only (see below); real training must happen on a
GPU-backed Colab runtime.

NOT A NEW SUBSYSTEM: reuses, unmodified, `model_dataset.build_dataloaders`/
`collate_fn`, `model_heads.train_model`/`MultiTaskModel`/`coral_predict`,
`model_checkpoint_io.save_checkpoint_artifact`/`load_checkpoint_artifact`,
`model_evaluator.TrainedEvaluator`, `training_experimentation.assemble_checkpoint`/
`compute_qwk`, `four_dim_experiment_split.load_core_pool`. The only new code
is this script's own orchestration and per-dimension metric computation
(`compute_qwk` itself is reused, not reimplemented; `run_benchmark`/
`decide_promotion` are NOT reused since they operate on the legacy single
`overall_label.grade`, not per-dimension ordinal predictions).

USAGE:
    python run_four_dim_training.py --dry-run [v1|v2]  # LOCAL, safe: environment
                                                  # report only, no download,
                                                  # no training, always exits
                                                  # before requiring CUDA.
    python run_four_dim_training.py train [v1|v2]      # COLAB (GPU runtime
                                                  # required): the real
                                                  # experiment. See
                                                  # COLAB_RUN.md.

EXPERIMENT SELECTOR (additive, Phase 6): the optional second argument
selects which frozen pool+split to train on -- `v1` (default, IDENTICAL
behavior to every prior call site that omits it: the frozen 170-example
pool, `artifacts/four_dim_experiment_v1/split.json`, output to
`artifacts/four_dim_training_v1/`) or `v2` (the 220-example V2 pool,
`artifacts/four_dim_experiment_v2/split.json`, output to
`artifacts/four_dim_training_v2/`). Both experiments use the EXACT SAME
architecture, contextual input builder, loss, and hyperparameters (`CONFIG`
below) -- only the pool/split/output-directory/model-version differ. This
is the smallest additive change that supports V2 without touching V1
behavior at all: omitting the argument, or passing `v1` explicitly, is
byte-for-byte identical to this script before this change.

See docs/architecture/DeBERTa_Dataset_Rebuild_Status.md,
artifacts/four_dim_experiment_v1/README.md, and
artifacts/four_dim_experiment_v2/README.md for the frozen dataset/splits
this script consumes.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from collections import Counter

import torch

from evaluation_dimensions import all_keys as canonical_dimension_keys
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from four_dim_experiment_split import load_core_pool
from four_dim_experiment_v2_split import load_v2_pool
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact, save_checkpoint_artifact
from model_dataset import build_dataloaders
from model_evaluator import TrainedEvaluator
from model_heads import coral_predict, train_model
from training_experimentation import DatasetSplit, ExperimentConfig, assemble_checkpoint, compute_qwk

CANONICAL_DIMENSION_KEYS: tuple[str, ...] = canonical_dimension_keys()
NUM_CLASSES = 5

_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Experiment selector (additive, Phase 6) ──────────────────────────────
# "v1" preserves every path/loader/count from before this change exactly.
# "v2" points at the approved 220-example pool + its own split/output dir.
# Nothing else (architecture, contextual input, loss, CONFIG hyperparameters
# below) differs between the two -- see module docstring.
EXPERIMENTS = {
    "v1": dict(
        load_pool=load_core_pool,
        split_json_path=os.path.join(_HERE, "artifacts", "four_dim_experiment_v1", "split.json"),
        artifacts_dir=os.path.join(_HERE, "artifacts", "four_dim_training_v1"),
        expected_total=170, expected_counts=(128, 20, 22),
        dataset_split_identifier="four_dim_experiment_v1",
        split_seed="four_dim_experiment_v1_41",
        model_version="deberta_v3_base_four_dim_training_v1",
        label="Four-Dimension Training V1",
    ),
    "v2": dict(
        load_pool=load_v2_pool,
        split_json_path=os.path.join(_HERE, "artifacts", "four_dim_experiment_v2", "split.json"),
        artifacts_dir=os.path.join(_HERE, "artifacts", "four_dim_training_v2"),
        expected_total=220, expected_counts=(166, 27, 27),
        dataset_split_identifier="four_dim_experiment_v2",
        split_seed="four_dim_v2_split_348",
        model_version="deberta_v3_base_four_dim_training_v2",
        label="Four-Dimension Training V2",
    ),
}

# ── Training configuration (recorded verbatim in the checkpoint + report) ───
# Sized for a Colab T4-class GPU (~16GB), NOT for local CPU execution --
# see the module docstring for why local execution is dry-run-only.
# SHARED, UNCHANGED ACROSS v1/v2 -- only dataset_split_identifier/split_seed/
# model_version vary by experiment (see EXPERIMENTS above); every other key
# is the literal, identical V1 recipe, per the "same architecture + same
# recipe + more data" experimental control.
CONFIG = {
    "base_model": "microsoft/deberta-v3-base",
    "fresh_initialization": True,
    "random_seed": 42,
    "learning_rate": 2e-5,
    "batch_size": 8,
    "gradient_accumulation_steps": 1,
    "num_epochs": 8,
    "max_length": 256,
    "optimizer": "AdamW (torch.optim.AdamW, default betas/eps)",
    "scheduler": "none (constant learning rate; use_lr_decay=False)",
    "weight_decay": 0.01,
    "warmup_steps": 0,
    "dropout": (
        "not explicitly configured -- uses microsoft/deberta-v3-base's own HF config "
        "default (hidden_dropout_prob=0.1, attention_probs_dropout_prob=0.1)"
    ),
    "early_stopping": (
        "no automatic loop-break is implemented in the existing training infrastructure "
        "(train_model runs a fixed num_epochs); best-checkpoint-BY-VALIDATION-mean-QWK "
        "selection (same precedent as run_experiment_1.py's best-by-val-QWK checkpointing) "
        "is used as the practical equivalent -- every epoch is benchmarked on validation, "
        "and only the single best epoch's weights are kept. The untrained (epoch 0) point "
        "is benchmarked but deliberately excluded from best-checkpoint selection."
    ),
}


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def environment_report() -> dict:
    import transformers
    report = {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }
    return report


def require_cuda_or_exit(report: dict) -> None:
    """Fails CLEARLY and immediately if CUDA is unavailable, rather than
    silently falling back to CPU (this script's deliberate deviation from
    the rest of this codebase's "Colab-intended, portable" training
    scripts -- see module docstring)."""
    if not report["cuda_available"]:
        _log("BLOCKER: CUDA is not available in this runtime.")
        _log("This script refuses to train on CPU (a real attempt on a 7.5GB-RAM local "
             "machine stalled under disk paging -- see the module docstring). "
             "Run this script in a GPU-backed Google Colab runtime instead; see COLAB_RUN.md.")
        sys.exit(1)


def _load_frozen_split(split_json_path: str) -> DatasetSplit:
    with open(split_json_path, encoding="utf-8") as f:
        raw = json.load(f)
    return DatasetSplit(
        train_ids=tuple(raw["train_ids"]), val_ids=tuple(raw["val_ids"]), test_ids=tuple(raw["test_ids"]),
    )


# ── Per-dimension metrics (new; compute_qwk itself is reused) ───────────────

def _collect_predictions(model, loader, device: str) -> dict[str, tuple[list[int], list[int]]]:
    """Runs `model` over every batch in `loader` ONCE and returns, per
    canonical dimension, the (y_true, y_pred) ordinal-tier lists -- masked
    to only the labeled entries (dimension_mask), same discipline the
    training loss itself uses."""
    model.eval()
    y_true: dict[str, list[int]] = {name: [] for name in CANONICAL_DIMENSION_KEYS}
    y_pred: dict[str, list[int]] = {name: [] for name in CANONICAL_DIMENSION_KEYS}
    with torch.no_grad():
        for batch in loader:
            ids = batch["main_input_ids"].to(device)
            mask = batch["main_attention_mask"].to(device)
            outputs = model.forward_dimensions(ids, mask)
            targets = batch["dimension_targets"]
            dmask = batch["dimension_mask"]
            for j, name in enumerate(CANONICAL_DIMENSION_KEYS):
                preds = coral_predict(outputs["dimension_logits"][name]).cpu().tolist()
                valid = (dmask[:, j] > 0).tolist()
                for p, t, v in zip(preds, targets[:, j].tolist(), valid):
                    if v:
                        y_pred[name].append(int(p))
                        y_true[name].append(int(t))
    return {name: (y_true[name], y_pred[name]) for name in CANONICAL_DIMENSION_KEYS}


def _dimension_metrics(y_true: list[int], y_pred: list[int]) -> dict:
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
        "mae": round(mae, 4), "qwk": round(qwk, 4),
        "confusion_matrix": confusion,
        "true_distribution": dict(sorted(Counter(y_true).items())),
        "pred_distribution": dict(sorted(Counter(y_pred).items())),
    }


def _all_dimension_metrics(model, loader, device: str) -> dict[str, dict]:
    collected = _collect_predictions(model, loader, device)
    return {name: _dimension_metrics(*collected[name]) for name, (yt, yp) in collected.items()}


def _mean_qwk(metrics_by_dim: dict[str, dict]) -> float:
    return sum(m["qwk"] for m in metrics_by_dim.values()) / len(metrics_by_dim)


def _aggregate_secondary_score(metrics_by_dim: dict[str, dict]) -> dict:
    """Aggregate/overall performance, reported ONLY as a secondary summary
    -- never the primary result (per-dimension metrics are primary)."""
    return {
        "mean_accuracy": round(sum(m["accuracy"] for m in metrics_by_dim.values()) / len(metrics_by_dim), 4),
        "mean_within_1_accuracy": round(sum(m["within_1_accuracy"] for m in metrics_by_dim.values()) / len(metrics_by_dim), 4),
        "mean_mae": round(sum(m["mae"] for m in metrics_by_dim.values()) / len(metrics_by_dim), 4),
        "mean_qwk": round(_mean_qwk(metrics_by_dim), 4),
    }


# ── dry-run (LOCAL, safe) ─────────────────────────────────────────────────

def dry_run(experiment: str = "v1") -> int:
    """LOCAL, safe: reports the environment and confirms the selected
    experiment's frozen pool+split is loadable, but never downloads the
    real backbone and never trains. Structural correctness of every piece
    this script calls is covered by the existing test suite (tiny random
    backbone, no network weights) -- run that separately; this is just an
    environment/data sanity check."""
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
    _log(f"[{experiment}] canonical dimensions: {len(CANONICAL_DIMENSION_KEYS)} -- {CANONICAL_DIMENSION_KEYS}")
    _log("--dry-run complete: no download, no training. "
         f"CUDA available here: {report['cuda_available']} (irrelevant for dry-run).")
    return 0


# ── train (COLAB, GPU required) ──────────────────────────────────────────

def _assert_no_group_leakage(examples, split) -> None:
    """Pre-training defense-in-depth re-check (the split artifact was
    already leakage-validated at construction time -- this re-confirms it
    against the ACTUAL examples about to be trained on, in case the wrong
    split/pool combination was ever passed)."""
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


def train(experiment: str = "v1") -> int:
    cfg = EXPERIMENTS[experiment]
    report = environment_report()
    _log(f"Environment report: {json.dumps(report, indent=2)}")
    require_cuda_or_exit(report)
    device = "cuda"

    artifacts_dir = cfg["artifacts_dir"]
    os.makedirs(artifacts_dir, exist_ok=True)
    _log(f"=== {cfg['label']} (experiment={experiment}, device={device}, GPU={report['gpu_name']}) ===")
    _log(f"Config: {json.dumps(CONFIG, indent=2)}")
    _log(f"Experiment: dataset_split_identifier={cfg['dataset_split_identifier']!r} "
         f"split_seed={cfg['split_seed']!r} model_version={cfg['model_version']!r}")

    examples = cfg["load_pool"]()
    if len(examples) != cfg["expected_total"]:
        _log(f"BLOCKER: expected {cfg['expected_total']} pool examples, got {len(examples)}")
        return 1
    split = _load_frozen_split(cfg["split_json_path"])
    expected_tr, expected_va, expected_te = cfg["expected_counts"]
    actual = (len(split.train_ids), len(split.val_ids), len(split.test_ids))
    _log(f"Frozen split loaded from {cfg['split_json_path']!r}: "
         f"train={actual[0]} val={actual[1]} test={actual[2]} (expected {(expected_tr, expected_va, expected_te)})")
    if actual != (expected_tr, expected_va, expected_te):
        _log(f"BLOCKER: split counts do not match the approved {experiment} split -- refusing to train.")
        return 1
    _log(f"canonical dimensions: {len(CANONICAL_DIMENSION_KEYS)} -- {CANONICAL_DIMENSION_KEYS}")
    _assert_no_group_leakage(examples, split)

    backbone_config = BackboneConfig(hf_model_id=CONFIG["base_model"], max_length=CONFIG["max_length"])
    tokenizer = build_tokenizer(backbone_config)
    train_loader, val_loader, test_loader = build_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=CONFIG["batch_size"],
        seed=CONFIG["random_seed"], dimension_names=CANONICAL_DIMENSION_KEYS,
    )
    _log(f"Dataloaders: train_batches={len(train_loader)} val_batches={len(val_loader)} test_batches={len(test_loader)}")

    best_weights_path = os.path.join(artifacts_dir, "best_checkpoint_weights.pt")
    best_checkpoint_path = os.path.join(artifacts_dir, "best_checkpoint.json")
    epoch_curve: list[dict] = []
    best = {"val_mean_qwk": -1.0, "epoch": None, "checkpoint": None, "val_metrics": None}

    experiment_config = ExperimentConfig(
        backbone_name=backbone_config.hf_model_id, random_seed=CONFIG["random_seed"],
        dataset_version=cfg["dataset_split_identifier"],
        parameters={
            **{k: (v if isinstance(v, (str, int, float, bool)) else str(v)) for k, v in CONFIG.items()},
            "split_seed": cfg["split_seed"], "experiment": experiment,
            "environment": json.dumps(report),
        },
    )

    def on_epoch_end(epoch_index: int, model, train_loss, val_loss) -> None:
        label = "untrained (epoch 0)" if epoch_index == 0 else f"epoch {epoch_index}"
        val_metrics = _all_dimension_metrics(model, val_loader, device)
        mean_qwk = _mean_qwk(val_metrics)
        _log(f"--- {label}: train_loss={train_loss} val_loss={val_loss} val_mean_QWK={mean_qwk:.4f} ---")
        for name, m in val_metrics.items():
            _log(f"    {name}: acc={m['accuracy']:.3f} within1={m['within_1_accuracy']:.3f} "
                 f"mae={m['mae']:.3f} qwk={m['qwk']:.3f} (n={m['n']})")
        epoch_curve.append({
            "epoch": epoch_index, "train_loss": train_loss, "val_loss": val_loss,
            "val_mean_qwk": round(mean_qwk, 4), "val_metrics": val_metrics,
        })
        if epoch_index > 0 and mean_qwk > best["val_mean_qwk"]:
            save_checkpoint_artifact(model, best_weights_path)
            checkpoint = assemble_checkpoint(
                model_version=f"{cfg['model_version']}_epoch{epoch_index}",
                experiment_config=experiment_config, artifact_uri=best_weights_path,
            )
            with open(best_checkpoint_path, "w", encoding="utf-8") as f:
                f.write(checkpoint.model_dump_json(indent=2))
            best.update({
                "val_mean_qwk": mean_qwk, "epoch": epoch_index, "checkpoint": checkpoint, "val_metrics": val_metrics,
            })
            _log(f"    New best checkpoint: {label} (val mean QWK={mean_qwk:.4f}) -- saved to {best_weights_path!r}")

    t0 = time.time()
    train_model(
        train_loader, val_loader, backbone_config, num_epochs=CONFIG["num_epochs"],
        learning_rate=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"],
        device=device, random_seed=CONFIG["random_seed"], on_epoch_end=on_epoch_end,
        dimension_names=CANONICAL_DIMENSION_KEYS,
    )
    duration_s = time.time() - t0
    _log(f"Training complete in {duration_s:.1f}s ({duration_s/60:.1f} min).")

    with open(os.path.join(artifacts_dir, "epoch_curve.json"), "w", encoding="utf-8") as f:
        json.dump(epoch_curve, f, indent=2)

    if best["epoch"] is None:
        _log("BLOCKER: no epoch ever improved on the untrained baseline -- refusing to select a best checkpoint.")
        return 1
    _log(f"Best checkpoint: epoch {best['epoch']} (val mean QWK={best['val_mean_qwk']:.4f}).")

    # ── TEST SET -- touched exactly once, after checkpoint selection ────────
    best_model = load_checkpoint_artifact(
        best_weights_path, backbone_config, dimension_names=CANONICAL_DIMENSION_KEYS, map_location=device,
    )
    test_metrics = _all_dimension_metrics(best_model, test_loader, device)
    _log(f"TEST metrics (best checkpoint, epoch {best['epoch']}):")
    for name, m in test_metrics.items():
        _log(f"    {name}: acc={m['accuracy']:.3f} within1={m['within_1_accuracy']:.3f} "
             f"mae={m['mae']:.3f} qwk={m['qwk']:.3f} (n={m['n']})")

    with open(os.path.join(artifacts_dir, "test_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({
            "best_epoch": best["epoch"], "val_mean_qwk": round(best["val_mean_qwk"], 4),
            "val_metrics": best["val_metrics"], "test_metrics": test_metrics,
            "val_secondary_aggregate": _aggregate_secondary_score(best["val_metrics"]),
            "test_secondary_aggregate": _aggregate_secondary_score(test_metrics),
            "training_duration_seconds": round(duration_s, 1), "config": CONFIG, "environment": report,
        }, f, indent=2)

    # ── Qualitative error-analysis data (raw predictions, for offline review) ──
    by_id = {e.metadata.example_id: e for e in examples}
    test_predictions = _collect_predictions(best_model, test_loader, device)
    qualitative = []
    for i, example_id in enumerate(split.test_ids):
        example = by_id[example_id]
        row = {"example_id": example_id, "question": example.inputs.question_text, "answer": example.inputs.answer_text}
        for name in CANONICAL_DIMENSION_KEYS:
            yt, yp = test_predictions[name]
            if i < len(yt):
                row[f"{name}_true"] = yt[i]
                row[f"{name}_pred"] = yp[i]
        qualitative.append(row)
    with open(os.path.join(artifacts_dir, "test_predictions.json"), "w", encoding="utf-8") as f:
        json.dump(qualitative, f, indent=2)

    # ── Evaluator smoke test ─────────────────────────────────────────────────
    _log("--- Evaluator smoke test ---")
    evaluator = TrainedEvaluator(best["checkpoint"], best_model, tokenizer, backbone_config)
    smoke_results = []
    for example_id in split.test_ids[:3]:
        example = by_id[example_id]
        request = EvaluationRequest(
            request_id=f"smoke_{example_id}", requested_at="2026-09-08T00:00:00+00:00",
            specification=example.inputs.specification, question_text=example.inputs.question_text,
            reasoning_type=example.inputs.reasoning_type, answer_text=example.inputs.answer_text,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=example.inputs.expected_concepts,
        )
        result = evaluator.evaluate(request)
        produced = {d.name for d in result.dimensions}
        smoke_results.append({
            "example_id": example_id, "dimension_count": len(result.dimensions),
            "dimension_names": sorted(produced), "is_exactly_canonical": produced == set(CANONICAL_DIMENSION_KEYS),
            "predictions": {d.name: d.raw_score for d in result.dimensions},
            "confidences_finite": all(d.confidence == d.confidence and abs(d.confidence) != float("inf") for d in result.dimensions),
            "overall_score": result.overall_score,
        })
        _log(f"    {example_id}: dims={sorted(produced)} overall_score={result.overall_score}")
    with open(os.path.join(artifacts_dir, "evaluator_smoke_test.json"), "w", encoding="utf-8") as f:
        json.dump(smoke_results, f, indent=2)

    _log(f"=== {cfg['label'].upper()} COMPLETE ===")
    _log(f"Copy back to the repository: {artifacts_dir!r}")
    return 0


def main() -> int:
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("--dry-run", "train"):
        print("Usage: python run_four_dim_training.py [--dry-run|train] [v1|v2]", file=sys.stderr)
        return 2
    experiment = sys.argv[2] if len(sys.argv) == 3 else "v1"
    if experiment not in EXPERIMENTS:
        print(f"Unknown experiment {experiment!r}; must be one of {sorted(EXPERIMENTS)}", file=sys.stderr)
        return 2
    if sys.argv[1] == "--dry-run":
        return dry_run(experiment)
    return train(experiment)


if __name__ == "__main__":
    sys.exit(main())
