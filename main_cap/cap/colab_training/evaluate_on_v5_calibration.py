"""
Evaluation C — V5 CALIBRATION SET (85 examples) evaluation for the v5_1088
checkpoint -- READ-ONLY, INFERENCE-ONLY (COLAB-INTENDED, GPU recommended,
CPU works).

Reads `artifacts/v5_short_quality_calibration_80/dataset/examples.jsonl`
directly (TrainingExample schema, same as the 1003 dataset -- NOT the
V4-diagnostic dict schema), runs inference with the same production
functions evaluate_on_v4_v5.py uses (grounding_to_text/build_dimension_pair/
tokenize_pair), and reports:
    - overall QWK/accuracy/MAE/within-1 on the full 85-example set
    - breakdown by length bucket (short/medium/long, same thresholds as
      validate_v5_short_quality_calibration_80.py: <=35 / 36-80 / 81+ words)
    - breakdown by authored category (1-11, from dataset/row_categories.json)
    - the explicit length-shortcut check this experiment is FOR: word_count
      vs predicted_overall Pearson correlation, and word_count vs
      absolute_error Pearson correlation, computed on this set's predictions
      (NOT the training labels' 0.0195 correlation -- that was a LABEL
      property; this is a MODEL BEHAVIOR property, only knowable after
      inference)
    - explicit inspection of the 14 short-Tier-4 and 8 Tier-3 label
      examples' predictions specifically, since those were the ones flagged
      for human review

Does NOT modify the calibration dataset or any of its files. Writes exactly
one new file: `<artifacts_dir>/v5_calibration_report.json`.
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

from model_backbone import BackboneConfig, build_dimension_pair, build_tokenizer, grounding_to_text, tokenize_pair  # noqa: E402
from model_dataset import score_to_tier  # noqa: E402
from model_heads import coral_predict  # noqa: E402
from overall_score_model import load_overall_checkpoint_artifact  # noqa: E402
from training_example import TrainingExample  # noqa: E402
from training_experimentation import compute_qwk  # noqa: E402

NUM_CLASSES = 5

ARTIFACTS_DIR = os.path.join(CAP_DIR, "artifacts", "overall_single_v5_1088")
DEFAULT_WEIGHTS_PATH = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
CAL_DATASET_PATH = os.path.join(CAP_DIR, "artifacts", "v5_short_quality_calibration_80", "dataset", "examples.jsonl")
CAL_ROW_META_PATH = os.path.join(CAP_DIR, "artifacts", "v5_short_quality_calibration_80", "dataset", "row_categories.json")
REPORT_OUT = os.path.join(ARTIFACTS_DIR, "v5_calibration_report.json")


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


def _load_cal_examples() -> tuple[TrainingExample, ...]:
    if not os.path.exists(CAL_DATASET_PATH):
        raise FileNotFoundError(f"{CAL_DATASET_PATH!r} not found.")
    examples = []
    with open(CAL_DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(TrainingExample.model_validate_json(line))
    return tuple(examples)


def _bucket(word_count: int) -> str:
    if word_count <= 35:
        return "short"
    if word_count <= 80:
        return "medium"
    return "long"


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


def run(weights_path: str = DEFAULT_WEIGHTS_PATH) -> int:
    if not os.path.exists(weights_path):
        _log(f"BLOCKER: {weights_path!r} not found. Run train_overall_v5.py train first (on Colab), "
             f"download the checkpoint back, or pass --weights pointing at it.")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = _load_cal_examples()
    _log(f"Loaded {len(examples)} v5 calibration examples (file untouched).")

    row_meta = {}
    if os.path.exists(CAL_ROW_META_PATH):
        with open(CAL_ROW_META_PATH, encoding="utf-8") as f:
            row_meta = {m["example_id"]: m for m in json.load(f)}

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256)
    tokenizer = build_tokenizer(backbone_config)
    model = load_overall_checkpoint_artifact(weights_path, backbone_config, map_location=device)
    model.eval()

    rows = []
    with torch.no_grad():
        for ex in examples:
            grounding_text = grounding_to_text(ex.inputs.specification.grounding)  # PRODUCTION function
            text_a, text_b = build_dimension_pair(  # PRODUCTION function
                ex.inputs.question_text, grounding_text, ex.inputs.expected_concepts, ex.inputs.answer_text,
            )
            encoding = tokenize_pair(tokenizer, text_a, text_b, backbone_config.max_length)  # PRODUCTION function
            batch = tokenizer.pad([encoding], return_tensors="pt")
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = model(ids, mask)
            pred = int(coral_predict(logits)[0].item())
            gold_tier = score_to_tier(ex.labels.overall_label.score)
            wc = len((ex.inputs.answer_text or "").split())

            eid = ex.metadata.example_id
            meta = row_meta.get(eid, {})
            rows.append({
                "example_id": eid,
                "category_num": meta.get("category_num"),
                "authored_length_bucket": meta.get("length_bucket"),
                "word_count": wc,
                "length_bucket": _bucket(wc),
                "question": ex.inputs.question_text,
                "answer": ex.inputs.answer_text,
                "true": gold_tier,
                "pred": pred,
                "abs_error": abs(gold_tier - pred),
            })

    y_true = [r["true"] for r in rows]
    y_pred = [r["pred"] for r in rows]
    overall = _overall_metrics(y_true, y_pred)
    _log(f"V5 CALIBRATION (n={overall['n']}): qwk={overall['qwk']} acc={overall['accuracy']} "
         f"mae={overall['mae']} within1={overall['within_1_accuracy']}")

    by_length_bucket = _breakdown(rows, lambda r: r["length_bucket"])
    by_category = _breakdown(rows, lambda r: r["category_num"])

    length_pred_corr = _pearson([float(r["word_count"]) for r in rows], [float(r["pred"]) for r in rows])
    length_error_corr = _pearson([float(r["word_count"]) for r in rows], [float(r["abs_error"]) for r in rows])

    short_t4_ids = {
        "v5cal_001", "v5cal_002", "v5cal_003", "v5cal_004", "v5cal_005", "v5cal_006", "v5cal_007", "v5cal_008",
        "v5cal_009", "v5cal_010", "v5cal_011", "v5cal_013", "v5cal_014", "v5cal_015",
    }
    tier3_ids = {"v5cal_076", "v5cal_079", "v5cal_080", "v5cal_081", "v5cal_082", "v5cal_083", "v5cal_084", "v5cal_085"}
    short_t4_rows = [r for r in rows if r["example_id"] in short_t4_ids]
    tier3_rows = [r for r in rows if r["example_id"] in tier3_ids]

    report = {
        "checkpoint_weights_path": weights_path,
        "overall_metrics": overall,
        "by_length_bucket": {"thresholds": "short<=35, medium 36-80, long>=81 words", "results": by_length_bucket},
        "by_authored_category": by_category,
        "length_shortcut_check": {
            "word_count_vs_predicted_overall_pearson": round(length_pred_corr, 4) if length_pred_corr is not None else None,
            "word_count_vs_absolute_error_pearson": round(length_error_corr, 4) if length_error_corr is not None else None,
            "interpretation": (
                "This is a MODEL BEHAVIOR measurement (predictions vs. word count), distinct from the "
                "0.0195 LABEL correlation reported at calibration-set construction time. A value close "
                "to 0 here means the trained model itself is not using length as a shortcut on this set. "
                "A high positive value would mean the model still predicts higher scores for longer "
                "answers regardless of the (length-decorrelated) ground truth -- i.e. the calibration "
                "examples did not fully correct the shortcut."
            ),
        },
        "short_tier4_predictions": short_t4_rows,
        "tier3_predictions": tier3_rows,
        "per_example_predictions": rows,
    }
    os.makedirs(os.path.dirname(REPORT_OUT), exist_ok=True)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _log(f"Wrote {REPORT_OUT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS_PATH)
    args = parser.parse_args()
    return run(args.weights)


if __name__ == "__main__":
    sys.exit(main())
