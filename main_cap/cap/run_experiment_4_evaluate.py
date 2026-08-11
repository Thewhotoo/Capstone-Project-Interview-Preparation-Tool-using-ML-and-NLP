"""
Experiment 4 — Head-to-head evaluation (MEASUREMENT ONLY, no training, no
dataset changes, no weight changes). Compares, on the SAME held-out test
set (`v_experiment_4_combined`'s `split.test_ids`, 362 examples, never
touched by any training/augmentation step):

  A. OLD DeBERTa   (deberta_v3_base_experiment_2_tuned_epoch5, backed up
                     from the previously-deployed checkpoint before this
                     session overwrote deployed_model/)
  B. NEW DeBERTa   (deberta_v3_base_experiment_4_epoch4, just trained on
                     Colab, now in deployed_model/)
  C. HeuristicEvaluator (unchanged, the existing deterministic scorer)
  D. HybridEvaluator (existing, unmodified per-dimension agreement-banded
                     blend of HeuristicEvaluator + the NEW TrainedEvaluator
                     -- see hybrid_evaluator.py; not reinvented here)

Reuses existing code exclusively: `compute_qwk`, `run_benchmark`'s own
request-building pattern, `score_to_tier` (the same 5-tier cutpoints used
at training time), `TrainedEvaluator`, `HeuristicEvaluator`,
`HybridEvaluator`. No new scoring logic, no new subsystem.

Output: prints a full report to stdout AND writes a structured JSON summary
to `artifacts/experiment_4_evaluation/report.json` for later reference.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from collections import defaultdict

from dataset_manifest import DatasetManifest
from evaluation_request import EvaluationRequest, ConversationContextSnapshot
from experiment_dataset_io import load_examples_jsonl, load_json
from heuristic_evaluator import HeuristicEvaluator
from hybrid_evaluator import HybridEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact
from model_evaluator import TrainedEvaluator
from reasoning_dimension_relevance import ALL_DIMENSIONS
from training_example import TrainingExample
from training_experimentation import (
    Checkpoint,
    DatasetSplit,
    compute_qwk,
    grade_to_ordinal,
)

CAP_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(CAP_DIR, "artifacts", "experiment_4_combined")
DATASET_PATH = os.path.join(DATASET_DIR, "dataset.jsonl")
SPLIT_PATH = os.path.join(DATASET_DIR, "split.json")

OLD_CHECKPOINT_DIR = None  # set via main() argv / discovered by caller
NEW_CHECKPOINT_DIR = os.path.join(CAP_DIR, "deployed_model")

OUT_DIR = os.path.join(CAP_DIR, "artifacts", "experiment_4_evaluation")

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})
_NUM_ORDINAL_CLASSES = 5


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _build_evaluation_request(example: TrainingExample) -> EvaluationRequest:
    inputs = example.inputs
    return EvaluationRequest(
        request_id=f"eval4_{example.metadata.example_id}",
        requested_at="2026-08-09T00:00:00+00:00",
        specification=inputs.specification,
        question_text=inputs.question_text,
        reasoning_type=inputs.reasoning_type,
        answer_text=inputs.answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=inputs.expected_concepts,
    )


def _score_to_tier(score: float) -> int:
    if score >= 0.80:
        return 4
    if score >= 0.60:
        return 3
    if score >= 0.40:
        return 2
    if score >= 0.25:
        return 1
    return 0


def _load_trained_evaluator(checkpoint_dir: str, tokenizer, backbone_config: BackboneConfig) -> TrainedEvaluator:
    checkpoint = load_json(Checkpoint, os.path.join(checkpoint_dir, "best_checkpoint.json"))
    model = load_checkpoint_artifact(os.path.join(checkpoint_dir, "best_checkpoint_weights.pt"), backbone_config)
    return TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def run(old_checkpoint_dir: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    examples = load_examples_jsonl(DATASET_PATH)
    split = load_json(DatasetSplit, SPLIT_PATH)
    by_id = {e.metadata.example_id: e for e in examples}
    test_examples = tuple(by_id[i] for i in split.test_ids)
    _log(f"Loaded {len(test_examples)} held-out TEST examples (split.test_ids from {SPLIT_PATH!r}).")
    assert len(test_examples) == 362, f"expected 362 test examples, got {len(test_examples)}"

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=128)
    tokenizer = build_tokenizer(backbone_config)

    _log("Loading OLD DeBERTa checkpoint (experiment_2_tuned, backed up)...")
    old_trained = _load_trained_evaluator(old_checkpoint_dir, tokenizer, backbone_config)
    _log(f"  OLD: {old_trained.name}")

    _log("Loading NEW DeBERTa checkpoint (experiment_4, deployed)...")
    new_trained = _load_trained_evaluator(NEW_CHECKPOINT_DIR, tokenizer, backbone_config)
    _log(f"  NEW: {new_trained.name}")

    heuristic = HeuristicEvaluator()
    hybrid = HybridEvaluator(HeuristicEvaluator(), new_trained)

    evaluators = {
        "old_deberta": old_trained,
        "new_deberta": new_trained,
        "heuristic": heuristic,
        "hybrid": hybrid,
    }

    # Per-example, per-evaluator results collected here.
    results: dict[str, list] = {k: [] for k in evaluators}
    requests = []
    gt_grades = []
    gt_overall_scores = []

    t0 = time.time()
    for i, ex in enumerate(test_examples):
        req = _build_evaluation_request(ex)
        requests.append(req)
        gt_grades.append(ex.labels.overall_label.grade)
        gt_overall_scores.append(ex.labels.overall_label.score)
        for name, ev in evaluators.items():
            results[name].append(ev.evaluate(req))
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            _log(f"  ...{i + 1}/{len(test_examples)} examples evaluated by all 4 evaluators ({elapsed:.1f}s elapsed)")
    _log(f"All evaluations complete in {time.time() - t0:.1f}s.")

    report: dict = {"example_count": len(test_examples), "evaluators": {}}

    # ── 1 & 7: overall QWK (core-grade subset only, matching run_benchmark's own methodology) ──
    core_idx = [i for i, g in enumerate(gt_grades) if g in _CORE_GRADES]
    y_true_overall = tuple(grade_to_ordinal(gt_grades[i]) for i in core_idx)
    _log(f"Core-grade (non off_topic/contradictory) test examples used for overall QWK: {len(core_idx)}/{len(test_examples)}")

    for name in evaluators:
        y_pred = tuple(grade_to_ordinal(results[name][i].grade) for i in core_idx)
        qwk = compute_qwk(y_true_overall, y_pred, _NUM_ORDINAL_CLASSES)
        report["evaluators"].setdefault(name, {})["overall_qwk"] = qwk
        report["evaluators"][name]["overall_qwk_n"] = len(core_idx)

    # ── 2 & 3: per-dimension QWK / MAE / RMSE ──
    for name in evaluators:
        per_dim = {}
        for dim in ALL_DIMENSIONS:
            gt_scores = []
            pred_scores = []
            for ex, res in zip(test_examples, results[name]):
                gt_label = next((d for d in ex.labels.dimension_labels if d.name == dim), None)
                pred_dim = res.dimension(dim)
                if gt_label is None or pred_dim is None:
                    continue
                gt_scores.append(gt_label.score)
                pred_scores.append(pred_dim.raw_score)
            if len(gt_scores) < 2:
                continue
            gt_tiers = tuple(_score_to_tier(s) for s in gt_scores)
            pred_tiers = tuple(_score_to_tier(s) for s in pred_scores)
            try:
                qwk = compute_qwk(gt_tiers, pred_tiers, _NUM_ORDINAL_CLASSES)
            except ValueError:
                qwk = None
            mae = sum(abs(g - p) for g, p in zip(gt_scores, pred_scores)) / len(gt_scores)
            rmse = math.sqrt(sum((g - p) ** 2 for g, p in zip(gt_scores, pred_scores)) / len(gt_scores))
            per_dim[dim] = {"n": len(gt_scores), "qwk": qwk, "mae": round(mae, 4), "rmse": round(rmse, 4)}
        report["evaluators"][name]["per_dimension"] = per_dim

    # ── 6: correlation between predicted overall_score and ground-truth overall score ──
    for name in evaluators:
        pred_overall = [r.overall_score for r in results[name]]
        corr = _pearson(gt_overall_scores, pred_overall)
        report["evaluators"][name]["overall_score_pearson_r"] = None if math.isnan(corr) else round(corr, 4)

    # ── 4: missing-reasoning performance (binary presence per category, micro-averaged) ──
    for name in evaluators:
        tp = fp = fn = tn = 0
        for ex, res in zip(test_examples, results[name]):
            gt_present = {m.category for m in ex.labels.missing_reasoning_labels if m.present}
            pred_present = {m.category for m in res.missing_reasoning}
            all_categories = gt_present | pred_present
            # Also count true negatives across the full known category vocabulary
            # minus what's already counted, for a complete confusion matrix.
            for cat in gt_present | pred_present:
                if cat in gt_present and cat in pred_present:
                    tp += 1
                elif cat in pred_present and cat not in gt_present:
                    fp += 1
                elif cat in gt_present and cat not in pred_present:
                    fn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall) > 0) else None
        report["evaluators"][name]["missing_reasoning"] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }

    # ── 5: concept-level performance (3-state exact match accuracy) ──
    for name in evaluators:
        correct = 0
        total = 0
        confusion = defaultdict(int)
        for ex, res in zip(test_examples, results[name]):
            gt_by_concept = {c.concept: c.status.value if hasattr(c.status, "value") else c.status for c in ex.labels.concept_labels}
            pred_by_concept = {c.concept: c.status.value if hasattr(c.status, "value") else c.status for c in res.concept_coverage}
            for concept, gt_status in gt_by_concept.items():
                pred_status = pred_by_concept.get(concept)
                if pred_status is None:
                    continue
                total += 1
                if pred_status == gt_status:
                    correct += 1
                confusion[f"{gt_status}->{pred_status}"] += 1
        report["evaluators"][name]["concept_coverage"] = {
            "n": total, "accuracy": round(correct / total, 4) if total else None,
            "confusion": dict(confusion),
        }

    # ── Scoring-behavior sanity checks (new_deberta and heuristic, for comparison) ──
    for name in ("old_deberta", "new_deberta", "heuristic", "hybrid"):
        by_grade = defaultdict(list)
        dim_spread = []
        for ex, res in zip(test_examples, results[name]):
            by_grade[ex.labels.overall_label.grade].append(res.overall_score)
            dim_scores = [d.raw_score for d in res.dimensions]
            if len(dim_scores) >= 2:
                dim_spread.append(max(dim_scores) - min(dim_scores))
        behavior = {}
        for grade in ("poor", "weak", "adequate", "good", "excellent"):
            vals = by_grade.get(grade, [])
            if vals:
                behavior[grade] = {
                    "n": len(vals), "mean_predicted_overall": round(statistics.mean(vals), 4),
                    "min": round(min(vals), 4), "max": round(max(vals), 4),
                }
        behavior["mean_within_example_dimension_spread"] = round(statistics.mean(dim_spread), 4) if dim_spread else None
        report["evaluators"][name]["scoring_behavior"] = behavior

    # ── 8 & 9: dramatic new_deberta-vs-heuristic outliers (relative to ground truth) ──
    outliers = []
    for i, ex in enumerate(test_examples):
        gt = ex.labels.overall_label.score
        new_err = abs(results["new_deberta"][i].overall_score - gt)
        heur_err = abs(results["heuristic"][i].overall_score - gt)
        outliers.append({
            "example_id": ex.metadata.example_id,
            "gt_grade": ex.labels.overall_label.grade,
            "gt_score": gt,
            "new_deberta_score": results["new_deberta"][i].overall_score,
            "heuristic_score": results["heuristic"][i].overall_score,
            "new_deberta_error": round(new_err, 4),
            "heuristic_error": round(heur_err, 4),
            "delta_new_minus_heuristic_error": round(new_err - heur_err, 4),
        })
    outliers_sorted = sorted(outliers, key=lambda o: o["delta_new_minus_heuristic_error"])
    report["new_deberta_dramatically_better_than_heuristic"] = outliers_sorted[:8]
    report["new_deberta_dramatically_worse_than_heuristic"] = outliers_sorted[-8:][::-1]

    with open(os.path.join(OUT_DIR, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _log(f"Full report written to {os.path.join(OUT_DIR, 'report.json')!r}")

    # ── Print summary ──
    print("\n" + "=" * 90)
    print("OVERALL QWK (core-grade test subset)")
    print("=" * 90)
    for name in evaluators:
        e = report["evaluators"][name]
        print(f"  {name:14s} QWK={e['overall_qwk']:.4f}  (n={e['overall_qwk_n']})  pearson_r={e['overall_score_pearson_r']}")

    print("\n" + "=" * 90)
    print("PER-DIMENSION QWK / MAE / RMSE")
    print("=" * 90)
    for dim in ALL_DIMENSIONS:
        row = f"  {dim:20s}"
        for name in evaluators:
            d = report["evaluators"][name]["per_dimension"].get(dim)
            if d is None:
                row += f" | {name}: n/a"
            else:
                qwk_str = f"{d['qwk']:.3f}" if d["qwk"] is not None else "n/a"
                row += f" | {name}: qwk={qwk_str} mae={d['mae']:.3f} (n={d['n']})"
        print(row)

    print("\n" + "=" * 90)
    print("MISSING-REASONING (micro P/R/F1)")
    print("=" * 90)
    for name in evaluators:
        m = report["evaluators"][name]["missing_reasoning"]
        print(f"  {name:14s} P={m['precision']} R={m['recall']} F1={m['f1']} (tp={m['tp']} fp={m['fp']} fn={m['fn']})")

    print("\n" + "=" * 90)
    print("CONCEPT COVERAGE (3-state exact accuracy)")
    print("=" * 90)
    for name in evaluators:
        c = report["evaluators"][name]["concept_coverage"]
        print(f"  {name:14s} accuracy={c['accuracy']} (n={c['n']})")

    print("\n" + "=" * 90)
    print("SCORING BEHAVIOR BY GROUND-TRUTH GRADE")
    print("=" * 90)
    for name in ("old_deberta", "new_deberta", "heuristic", "hybrid"):
        print(f"  --- {name} ---")
        b = report["evaluators"][name]["scoring_behavior"]
        for grade in ("poor", "weak", "adequate", "good", "excellent"):
            if grade in b:
                g = b[grade]
                print(f"    {grade:10s} n={g['n']:3d} mean_pred_overall={g['mean_predicted_overall']:.3f} range=[{g['min']:.3f}, {g['max']:.3f}]")
        print(f"    mean within-example dimension spread: {b['mean_within_example_dimension_spread']}")

    print("\n" + "=" * 90)
    print("NEW DEBERTA DRAMATICALLY BETTER THAN HEURISTIC (top 5)")
    print("=" * 90)
    for o in report["new_deberta_dramatically_better_than_heuristic"][:5]:
        print(f"  {o['example_id']}: gt={o['gt_grade']}({o['gt_score']:.2f}) new={o['new_deberta_score']:.2f}(err={o['new_deberta_error']:.3f}) heur={o['heuristic_score']:.2f}(err={o['heuristic_error']:.3f})")

    print("\n" + "=" * 90)
    print("NEW DEBERTA DRAMATICALLY WORSE THAN HEURISTIC (top 5)")
    print("=" * 90)
    for o in report["new_deberta_dramatically_worse_than_heuristic"][:5]:
        print(f"  {o['example_id']}: gt={o['gt_grade']}({o['gt_score']:.2f}) new={o['new_deberta_score']:.2f}(err={o['new_deberta_error']:.3f}) heur={o['heuristic_score']:.2f}(err={o['heuristic_error']:.3f})")

    print("\nDONE.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python run_experiment_4_evaluate.py <old_checkpoint_dir>", file=sys.stderr)
        sys.exit(2)
    run(sys.argv[1])
