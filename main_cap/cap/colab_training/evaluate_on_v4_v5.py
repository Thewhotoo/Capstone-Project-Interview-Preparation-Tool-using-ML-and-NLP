"""
Evaluation B — V4 DIAGNOSTIC benchmark evaluation for the v5_1088 checkpoint
(1003 baseline + 85 v5_short_quality_calibration_80 examples appended to
train only) -- READ-ONLY, INFERENCE-ONLY (COLAB-INTENDED, GPU recommended,
CPU works).

Identical to evaluate_on_v4.py (the v4_1003 baseline's V4-diagnostic
evaluator) except for the checkpoint/output directory. Same gold-overall
derivation policy (equal-weight mean of the four gold_labels dimension
tiers, then score_to_tier -- not independently annotated, not invented
here), same production input-construction functions
(grounding_to_text/build_dimension_pair/tokenize_pair), same read-only
discipline against `v4_diagnostic_58.jsonl`.

Per the task instructions this experiment was built for: V4 is a targeted
58-example behavioral stress-test, NOT a second held-out test set -- its
numbers are compared against the 1003 baseline's own V4 run, never averaged
into the primary 151-example test QWK.

Does NOT modify `v4_diagnostic_58.jsonl` or any other V4 artifact. Writes
exactly one new file: `<artifacts_dir>/v4_overall_predictions.json` plus
`<artifacts_dir>/v4_overall_report.json`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from types import SimpleNamespace

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
CAP_DIR = os.path.dirname(_HERE)
sys.path.insert(0, CAP_DIR)

from evaluation_dimensions import CANONICAL_DIMENSIONS  # noqa: E402
from model_backbone import BackboneConfig, build_dimension_pair, build_tokenizer, grounding_to_text, tokenize_pair  # noqa: E402
from model_dataset import score_to_tier  # noqa: E402
from model_heads import coral_predict  # noqa: E402
from overall_score_model import load_overall_checkpoint_artifact  # noqa: E402
from training_experimentation import compute_qwk  # noqa: E402

_CANONICAL_KEYS = tuple(d.value for d in CANONICAL_DIMENSIONS)
NUM_CLASSES = 5

ARTIFACTS_DIR = os.path.join(CAP_DIR, "artifacts", "overall_single_v5_1088")
DEFAULT_WEIGHTS_PATH = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
V4_DATASET_PATH = os.path.join(CAP_DIR, "artifacts", "v4_diagnostic", "v4_diagnostic_58.jsonl")
PREDICTIONS_OUT = os.path.join(ARTIFACTS_DIR, "v4_overall_predictions.json")
REPORT_OUT = os.path.join(ARTIFACTS_DIR, "v4_overall_report.json")

BASELINE_1003_V4_COMPARISON_NOTE = (
    "Compare against the 1003 baseline's own v4_overall_report.json "
    "(artifacts/overall_single_v4_1003/v4_overall_report.json) -- V4 QWK 0.6298, "
    "accuracy 0.50, MAE 0.7069, within-1 0.8103 (per the frozen baseline record). "
    "V4 is a diagnostic stress-test, not a second held-out test set."
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _load_v4_examples(path: str = V4_DATASET_PATH) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path!r} not found. artifacts/ is .gitignore'd and NOT pulled in by `git clone` -- "
            "upload v4_diagnostic_58.jsonl into this exact path before running this script."
        )
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _grounding_object(example: dict):
    """Same minimal duck-typed stand-in `run_v3_inference_on_v4.py` uses,
    matching exactly what `model_backbone.grounding_to_text` reads."""
    g = example["grounding"]
    project = SimpleNamespace(
        title=g.get("title", ""), summary=g.get("summary", ""),
        technologies=tuple(g.get("technologies", ())), concepts=(),
    )
    return SimpleNamespace(project=project, experience=None, certification=None)


def _derive_gold_overall_tier(gold_labels: dict) -> int:
    """Existing, non-invented policy: equal-weight mean of the four
    canonical dimension tiers -> score_to_tier. Identical to
    `v4_5000_dataset.derive_overall_tier` / `overall_dataset.
    overall_score_to_tier`, re-derived here (not imported) only because
    `v4_5000_dataset.derive_overall_tier` takes an `AuthoredRecord`-shaped
    dict with the same key names -- the formula itself is not reinvented."""
    scores = [gold_labels[k] / 4.0 for k in _CANONICAL_KEYS]
    overall_score = sum(scores) / len(scores)
    return score_to_tier(overall_score)


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


def run(weights_path: str = DEFAULT_WEIGHTS_PATH) -> int:
    if not os.path.exists(weights_path):
        _log(f"BLOCKER: {weights_path!r} not found. Run train_overall.py train first, "
             f"or pass --weights pointing at a downloaded checkpoint.")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = _load_v4_examples()
    _log(f"Loaded {len(examples)} V4 diagnostic examples (isolation_note fields preserved, file untouched).")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256)
    tokenizer = build_tokenizer(backbone_config)
    model = load_overall_checkpoint_artifact(weights_path, backbone_config, map_location=device)
    model.eval()

    predictions = []
    y_true, y_pred = [], []
    with torch.no_grad():
        for ex in examples:
            grounding_obj = _grounding_object(ex)
            grounding_text = grounding_to_text(grounding_obj)  # PRODUCTION function, unmodified
            text_a, text_b = build_dimension_pair(  # PRODUCTION function, unmodified
                ex["question"], grounding_text, tuple(ex.get("expected_concepts") or ()), ex["answer"],
            )
            encoding = tokenize_pair(tokenizer, text_a, text_b, backbone_config.max_length)  # PRODUCTION function
            batch = tokenizer.pad([encoding], return_tensors="pt")
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = model(ids, mask)
            pred = int(coral_predict(logits)[0].item())
            gold_tier = _derive_gold_overall_tier(ex["gold_labels"])

            y_true.append(gold_tier)
            y_pred.append(pred)
            predictions.append({
                "example_id": ex["example_id"],
                "diagnostic_category": ex["diagnostic_category"],
                "pair_group_id": ex["pair_group_id"],
                "question": ex["question"],
                "answer": ex["answer"],
                "gold_dimension_labels": ex["gold_labels"],
                "derived_gold_overall_tier": gold_tier,
                "predicted_overall_tier": pred,
            })

    with open(PREDICTIONS_OUT, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    _log(f"Wrote {len(predictions)} predictions to {PREDICTIONS_OUT}")

    metrics = _overall_metrics(y_true, y_pred)
    _log(f"V4 diagnostic (n={metrics['n']}): qwk={metrics['qwk']} acc={metrics['accuracy']} "
         f"mae={metrics['mae']} within1={metrics['within_1_accuracy']}")

    # Per-diagnostic-category breakdown (relevance_alignment, technical_correctness,
    # depth_control, grounding_ownership, multipart_completeness, cross_dimension, ...)
    by_category: dict[str, list[dict]] = {}
    for p in predictions:
        by_category.setdefault(p["diagnostic_category"], []).append(p)
    category_metrics = {}
    for cat, rows in by_category.items():
        yt = [r["derived_gold_overall_tier"] for r in rows]
        yp = [r["predicted_overall_tier"] for r in rows]
        if len(rows) < 2:
            category_metrics[cat] = {"n": len(rows), "note": "too few examples for a stable QWK"}
        else:
            category_metrics[cat] = _overall_metrics(yt, yp)

    report = {
        "architecture": "single_coral_head_overall_score (OverallScoreModel)",
        "checkpoint_weights_path": weights_path,
        "baseline_1003_v4_comparison": BASELINE_1003_V4_COMPARISON_NOTE,
        "gold_overall_derivation": (
            "equal-weight mean of the four gold_labels dimension tiers, then score_to_tier "
            "-- same existing policy the training dataset uses, not independently annotated"
        ),
        "overall_metrics": metrics,
        "by_diagnostic_category": category_metrics,
        "note": (
            "V4 is a 58-example HYPOTHETICAL diagnostic stress-test (hypothetical_source=true on "
            "every record), not a held-out sample of the training distribution -- treat these numbers "
            "as targeted behavioral probes (does the model correctly penalize off-topic depth, fluent-"
            "but-wrong claims, unsupported ownership, etc.), not as a second test-set QWK to average "
            "with the real test QWK."
        ),
    }
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
