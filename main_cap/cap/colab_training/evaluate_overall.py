"""
Post-training evaluation + qualitative breakdown analysis for the v4_1003
single-overall checkpoint (COLAB-INTENDED, GPU recommended but not required
-- CPU inference works, just slower).

READ-ONLY / INFERENCE-ONLY. Loads the best checkpoint `train_overall.py`
already selected (by validation QWK -- this script never re-selects a
checkpoint) and:

  1. Re-reports VALIDATION metrics (for reference; already computed during
     training and saved in `test_metrics.json`'s `val_metrics`).
  2. Reports FINAL TEST metrics -- clearly labeled and separate from
     validation. The test set is evaluated exactly once by this script
     (or once by `train_overall.py`; running this script again just
     re-runs inference on the same frozen test set, it does not select a
     different checkpoint or leak test information back into training).
  3. Breaks test-set (and, separately, whole-dataset) performance down by:
     humanized vs non-humanized, short vs long answers (median split),
     hard-case categories A-L (with B and H called out specifically per
     the dataset audit's flagged deviation), and grounding-heavy examples
     (grounding_ownership dimension label tier >= 3, read directly from
     each `TrainingExample.labels.dimension_labels` -- no new heuristic).

Every breakdown is computed from real per-example predictions; none of it
is estimated or asserted without the underlying per-example table also
being written to disk (`evaluate_overall_report.json`'s `"per_example"`
key) so the breakdown claims are independently checkable.

Does not train. Does not modify the checkpoint, the dataset, or any batch
file. Writes exactly one new file: `<artifacts_dir>/evaluate_overall_report.json`.
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

from dataset_loader import load_batch_metadata, load_examples, load_split, verify_dataset_integrity  # noqa: E402
from model_backbone import BackboneConfig, build_tokenizer  # noqa: E402
from overall_dataset import build_overall_dataloaders  # noqa: E402
from overall_score_model import load_overall_checkpoint_artifact  # noqa: E402
from training_experimentation import compute_qwk  # noqa: E402

NUM_CLASSES = 5
_CANONICAL_DIM_ORDER = ("technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership")

ARTIFACTS_DIR = os.path.join(CAP_DIR, "artifacts", "overall_single_v4_1003")
DEFAULT_WEIGHTS_PATH = os.path.join(ARTIFACTS_DIR, "best_checkpoint_weights.pt")
DEFAULT_CHECKPOINT_JSON = os.path.join(ARTIFACTS_DIR, "best_checkpoint.json")


def _log(msg: str) -> None:
    print(msg, flush=True)


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


def _breakdown(rows: list[dict], key_fn, label: str) -> dict:
    groups: dict = defaultdict(list)
    for r in rows:
        groups[key_fn(r)].append(r)
    out = {}
    for k, grp in groups.items():
        if len(grp) < 2:
            out[str(k)] = {"n": len(grp), "note": "too few examples for a stable QWK"}
            continue
        y_true = [g["true"] for g in grp]
        y_pred = [g["pred"] for g in grp]
        out[str(k)] = _overall_metrics(y_true, y_pred)
    return out


def run(weights_path: str = DEFAULT_WEIGHTS_PATH, checkpoint_json: str = DEFAULT_CHECKPOINT_JSON) -> int:
    if not os.path.exists(weights_path):
        _log(f"BLOCKER: {weights_path!r} not found. Run train_overall.py train first, "
             f"or pass --weights pointing at a downloaded checkpoint.")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"Using device: {device}")

    examples = load_examples()
    split = load_split()
    verify_dataset_integrity(examples, split)
    meta = load_batch_metadata()

    checkpoint_meta = {}
    if os.path.exists(checkpoint_json):
        with open(checkpoint_json, encoding="utf-8") as f:
            checkpoint_meta = json.load(f)
    max_length = 256
    try:
        max_length = int(checkpoint_meta["experiment_config"]["parameters"]["max_length"])
    except Exception:
        pass

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=max_length)
    tokenizer = build_tokenizer(backbone_config)
    _, val_loader, test_loader = build_overall_dataloaders(
        examples, split, tokenizer, backbone_config, batch_size=8, seed=None,
    )

    model = load_overall_checkpoint_artifact(weights_path, backbone_config, map_location=device)

    # ── VALIDATION (reference only -- this is what selected the checkpoint) ──
    val_rows = _collect_predictions_with_ids(model, val_loader, device)
    val_metrics = _overall_metrics([r["true"] for r in val_rows], [r["pred"] for r in val_rows])
    _log(f"VALIDATION: qwk={val_metrics['qwk']} acc={val_metrics['accuracy']} mae={val_metrics['mae']} "
         f"within1={val_metrics['within_1_accuracy']} n={val_metrics['n']}")

    # ── FINAL TEST (evaluated once; never used for model/epoch selection) ──
    test_rows = _collect_predictions_with_ids(model, test_loader, device)
    test_metrics = _overall_metrics([r["true"] for r in test_rows], [r["pred"] for r in test_rows])
    _log(f"FINAL TEST: qwk={test_metrics['qwk']} acc={test_metrics['accuracy']} mae={test_metrics['mae']} "
         f"within1={test_metrics['within_1_accuracy']} n={test_metrics['n']}")

    # ── enrich test rows with metadata for breakdown analysis ──
    by_id_example = {e.metadata.example_id: e for e in examples}
    for r in test_rows:
        ex = by_id_example[r["example_id"]]
        m = meta.get(r["example_id"])
        r["humanized"] = bool(m["humanized"]) if m else False
        r["hard_case"] = (m or {}).get("hard_case")
        r["project_family"] = (m or {}).get("project_family", "")
        r["word_count"] = len((ex.inputs.answer_text or "").split())
        dims = {d.name: round(d.score * 4) for d in ex.labels.dimension_labels}
        r["grounding_ownership_tier"] = dims.get("grounding_ownership")
        r["is_frozen"] = m is None

    median_wc = statistics.median(r["word_count"] for r in test_rows)

    humanized_breakdown = _breakdown(test_rows, lambda r: "humanized" if r["humanized"] else "non_humanized", "humanized")
    length_breakdown = _breakdown(
        test_rows, lambda r: "short (<=median)" if r["word_count"] <= median_wc else "long (>median)", "length",
    )
    hard_case_breakdown = _breakdown(test_rows, lambda r: r["hard_case"] or "none/coherent", "hard_case")
    grounding_heavy_breakdown = _breakdown(
        test_rows,
        lambda r: "grounding_heavy (tier>=3)" if (r["grounding_ownership_tier"] or 0) >= 3 else "grounding_light (tier<3)",
        "grounding_heavy",
    )
    project_family_breakdown = _breakdown(test_rows, lambda r: r["project_family"] or "n/a", "project_family")

    b_rows = [r for r in test_rows if r["hard_case"] == "B"]
    h_rows = [r for r in test_rows if r["hard_case"] == "H"]
    b_h_note = (
        f"B examples in TEST split: n={len(b_rows)}. H examples in TEST split: n={len(h_rows)}. "
        "If either n is small (hard-case letters are spread across train/val/test by the existing "
        "group-aware split, not stratified per-letter), any QWK computed on it will be noisy -- "
        "read the raw per-example true/pred pairs below rather than trusting a QWK number alone."
    )
    _log(b_h_note)

    report = {
        "checkpoint": {"weights_path": weights_path, "checkpoint_json": checkpoint_json, "meta": checkpoint_meta},
        "validation_results": val_metrics,
        "final_test_results": test_metrics,
        "breakdowns": {
            "humanized_vs_non_humanized": humanized_breakdown,
            "short_vs_long_answers": {"median_word_count_in_test": median_wc, "results": length_breakdown},
            "hard_case_A_to_L": hard_case_breakdown,
            "grounding_heavy_vs_light": grounding_heavy_breakdown,
            "project_family": project_family_breakdown,
        },
        "b_examples": {"n": len(b_rows), "rows": b_rows},
        "h_examples": {"n": len(h_rows), "rows": h_rows},
        "b_h_note": b_h_note,
        "per_example_test_predictions": test_rows,
    }

    out_path = os.path.join(os.path.dirname(weights_path), "evaluate_overall_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _log(f"Wrote {out_path}")
    _log("NOTE: this script does not evaluate against the V4 diagnostic benchmark -- "
         "run evaluate_on_v4.py separately for that (different dataset, different report).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS_PATH)
    parser.add_argument("--checkpoint-json", default=DEFAULT_CHECKPOINT_JSON)
    args = parser.parse_args()
    return run(args.weights, args.checkpoint_json)


if __name__ == "__main__":
    sys.exit(main())
