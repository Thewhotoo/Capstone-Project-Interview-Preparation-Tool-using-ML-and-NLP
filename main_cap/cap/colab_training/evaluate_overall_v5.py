"""
Evaluation A — ORIGINAL 151-EXAMPLE HELD-OUT TEST for the v5_1088 checkpoint
(COLAB-INTENDED, GPU recommended, CPU works for inference).

Same shape as evaluate_overall.py, pointed at the v5_1088 checkpoint/dataset,
plus the explicit length-bias measurements this experiment specifically asks
for: word-count <-> predicted-overall correlation and word-count <-> absolute-
error correlation on the SAME 151 test examples used for the 1003 baseline
(dataset_loader_v5.verify_dataset_integrity already asserts these 151 ids are
byte-identical to the 1003 baseline's split before this script runs).

READ-ONLY / INFERENCE-ONLY. Writes exactly one new file:
<artifacts_dir>/evaluate_overall_v5_report.json.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
CAP_DIR = os.path.dirname(_HERE)
sys.path.insert(0, CAP_DIR)

from dataset_loader_v5 import load_examples, load_split, verify_dataset_integrity  # noqa: E402
from model_backbone import BackboneConfig, build_tokenizer  # noqa: E402
from overall_dataset import build_overall_dataloaders  # noqa: E402
from overall_score_model import load_overall_checkpoint_artifact  # noqa: E402
from training_experimentation import compute_qwk  # noqa: E402

NUM_CLASSES = 5

ARTIFACTS_DIR = os.path.join(CAP_DIR, "artifacts", "overall_single_v5_1088")
DEFAULT_WEIGHTS_PATH = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
DEFAULT_CHECKPOINT_JSON = os.path.join(ARTIFACTS_DIR, "best_checkpoint.json")

BASELINE_1003_COMPARISON = {
    "model_version": "deberta_v3_base_overall_single_v4_1003_epoch7",
    "test_qwk": 0.8451, "test_accuracy": 0.5894, "test_mae": 0.4305, "test_within_1_accuracy": 0.9801,
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _pearson(xs: list[float], ys: list[float]):
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / ((vx ** 0.5) * (vy ** 0.5))


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
        "per_tier_counts_true": dict(sorted(Counter(y_true).items())),
        "per_tier_counts_pred": dict(sorted(Counter(y_pred).items())),
    }


def _collect_predictions_with_ids(model, loader, device: str) -> list[dict]:
    from model_heads import coral_predict
    model.eval()
    rows: list[dict] = []
    with torch.no_grad():
        for batch in loader:
            ids = batch["main_input_ids"].to(device)
            mask = batch["main_attention_mask"].to(device)
            logits = model(ids, mask)
            preds = coral_predict(logits).cpu().tolist()
            targets = batch["overall_target"].tolist()
            for eid, t, p in zip(batch["example_ids"], targets, preds):
                rows.append({"example_id": eid, "true": int(t), "pred": int(p)})
    return rows


def _breakdown(rows: list[dict], key_fn) -> dict:
    groups: dict = defaultdict(list)
    for r in rows:
        groups[key_fn(r)].append(r)
    out = {}
    for k, grp in groups.items():
        if len(grp) < 2:
            out[str(k)] = {"n": len(grp), "note": "too few examples for a stable QWK"}
            continue
        out[str(k)] = _overall_metrics([g["true"] for g in grp], [g["pred"] for g in grp])
    return out


def run(weights_path: str = DEFAULT_WEIGHTS_PATH, checkpoint_json: str = DEFAULT_CHECKPOINT_JSON) -> int:
    if not os.path.exists(weights_path):
        _log(f"BLOCKER: {weights_path!r} not found. Run train_overall_v5.py train first (on Colab), "
             f"download the checkpoint back, or pass --weights pointing at it.")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = load_examples()
    split = load_split()
    verify_dataset_integrity(examples, split)  # asserts val/test byte-identical to 1003 baseline

    checkpoint_meta = {}
    if os.path.exists(checkpoint_json):
        with open(checkpoint_json, encoding="utf-8") as f:
            checkpoint_meta = json.load(f)

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256)
    tokenizer = build_tokenizer(backbone_config)
    _, val_loader, test_loader = build_overall_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=8, seed=None,
    )

    model = load_overall_checkpoint_artifact(weights_path, backbone_config, map_location=device)

    val_rows = _collect_predictions_with_ids(model, val_loader, device)
    val_metrics = _overall_metrics([r["true"] for r in val_rows], [r["pred"] for r in val_rows])
    _log(f"VALIDATION: qwk={val_metrics['qwk']} n={val_metrics['n']}")

    test_rows = _collect_predictions_with_ids(model, test_loader, device)
    test_metrics = _overall_metrics([r["true"] for r in test_rows], [r["pred"] for r in test_rows])
    _log(f"FINAL TEST (n={test_metrics['n']}): qwk={test_metrics['qwk']} acc={test_metrics['accuracy']} "
         f"mae={test_metrics['mae']} within1={test_metrics['within_1_accuracy']}")

    # ── enrich with word_count for length-bias measurements ────────────────
    by_id_example = {e.metadata.example_id: e for e in examples}
    for r in test_rows:
        ex = by_id_example[r["example_id"]]
        r["word_count"] = len((ex.inputs.answer_text or "").split())
        r["abs_error"] = abs(r["true"] - r["pred"])

    median_wc = statistics.median(r["word_count"] for r in test_rows)
    length_breakdown = _breakdown(
        test_rows, lambda r: "short (<=median)" if r["word_count"] <= median_wc else "long (>median)",
    )

    length_pred_corr = _pearson([float(r["word_count"]) for r in test_rows], [float(r["pred"]) for r in test_rows])
    length_error_corr = _pearson([float(r["word_count"]) for r in test_rows], [float(r["abs_error"]) for r in test_rows])

    length_bias = {
        "word_count_vs_predicted_overall_pearson": round(length_pred_corr, 4) if length_pred_corr is not None else None,
        "word_count_vs_absolute_error_pearson": round(length_error_corr, 4) if length_error_corr is not None else None,
        "median_word_count_in_test": median_wc,
        "by_length_bucket": length_breakdown,
        "interpretation": (
            "word_count_vs_predicted_overall_pearson close to 0 means the model is NOT using answer "
            "length as a shortcut for predicting overall quality on this held-out test set. Compare "
            "against the 1003-only baseline's equivalent measurement (not previously computed -- see "
            "report) and against the known 0.720 length/tier correlation in the *training* labels."
        ),
    }

    report = {
        "experiment": "v5_1088 (1003 baseline + 85 v5_short_quality_calibration_80, appended to train only)",
        "checkpoint": {"weights_path": weights_path, "checkpoint_json": checkpoint_json, "meta": checkpoint_meta},
        "validation_results": val_metrics,
        "final_test_results": test_metrics,
        "baseline_1003_comparison": BASELINE_1003_COMPARISON,
        "test_set_identity": "SAME 151 example_ids as the 1003 baseline's frozen test split (verified byte-identical).",
        "length_bias": length_bias,
        "per_example_test_predictions": test_rows,
    }

    out_path = os.path.join(os.path.dirname(weights_path), "evaluate_overall_v5_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _log(f"Wrote {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS_PATH)
    parser.add_argument("--checkpoint-json", default=DEFAULT_CHECKPOINT_JSON)
    args = parser.parse_args()
    return run(args.weights, args.checkpoint_json)


if __name__ == "__main__":
    sys.exit(main())
