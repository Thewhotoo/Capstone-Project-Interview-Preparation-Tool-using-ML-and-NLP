"""
A2-on-V4 analysis — READ-ONLY. Consumes `../v4_diagnostic_58.jsonl` (gold
labels + rationale metadata only), `a2_predictions_on_v4.json` (just
produced), and the existing, untouched `../v3_predictions_on_v4.json` (A0)
and `../a1_inference/a1_predictions_on_v4.json` (A1) to build the A2 report
AND the direct A0-vs-A1-vs-A2 comparison. Performs no inference itself,
trains nothing, and does not modify any A0/V3/A1 artifact. Writes exactly
one new file: `a2_on_v4_report.json`.
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_V4_DIR = os.path.dirname(_HERE)
V4_DATASET_PATH = os.path.join(_V4_DIR, "v4_diagnostic_58.jsonl")
A2_PREDICTIONS_PATH = os.path.join(_HERE, "a2_predictions_on_v4.json")
A0_PREDICTIONS_PATH = os.path.join(_V4_DIR, "v3_predictions_on_v4.json")  # existing, untouched
A1_PREDICTIONS_PATH = os.path.join(_V4_DIR, "a1_inference", "a1_predictions_on_v4.json")  # existing, untouched
REPORT_PATH = os.path.join(_HERE, "a2_on_v4_report.json")

DIMS = ("technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership")

CATEGORY_TARGET_DIM = {
    "relevance_alignment": "relevance_completeness",
    "multipart_completeness": "relevance_completeness",
    "technical_correctness": "technical_correctness",
    "depth_control": "depth_specificity",
    "grounding_ownership": "grounding_ownership",
}
XD_TARGET_DIM = {"XD-1": "grounding_ownership", "XD-2": "relevance_completeness"}
XD_HELD_CONSTANT = {
    "XD-1": ["technical_correctness", "depth_specificity", "relevance_completeness"],
    "XD-2": ["technical_correctness", "grounding_ownership"],
}


def qwk(y_true, y_pred, n=5):
    if not y_true:
        return None
    O = [[0] * n for _ in range(n)]
    for t, p in zip(y_true, y_pred):
        O[t][p] += 1
    hist_t = [0] * n
    hist_p = [0] * n
    for t in y_true:
        hist_t[t] += 1
    for p in y_pred:
        hist_p[p] += 1
    N = len(y_true)
    E = [[hist_t[i] * hist_p[j] / N for j in range(n)] for i in range(n)]
    W = [[((i - j) ** 2) / ((n - 1) ** 2) for j in range(n)] for i in range(n)]
    num = sum(W[i][j] * O[i][j] for i in range(n) for j in range(n))
    den = sum(W[i][j] * E[i][j] for i in range(n) for j in range(n))
    return 1.0 if den == 0 else 1 - num / den


def dim_metrics(rows, dim):
    y_true = [r[f"{dim}_true"] for r in rows]
    y_pred = [r[f"{dim}_pred"] for r in rows]
    n = len(rows)
    if n == 0:
        return None
    exact = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n
    mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n
    within1 = sum(1 for t, p in zip(y_true, y_pred) if abs(t - p) <= 1) / n
    mean_true = sum(y_true) / n
    mean_pred = sum(y_pred) / n
    return {
        "n": n, "accuracy": round(exact, 4), "mae": round(mae, 4),
        "within_1_accuracy": round(within1, 4), "qwk": round(qwk(y_true, y_pred), 4),
        "mean_true": round(mean_true, 4), "mean_pred": round(mean_pred, 4),
        "bias": round(mean_pred - mean_true, 4),
    }


def pair_analysis(preds):
    by_group = {}
    for row in preds:
        by_group.setdefault(row["pair_group_id"], []).append(row)

    results = []
    for group_id, rows in sorted(by_group.items()):
        cat = rows[0]["diagnostic_category"]
        target_dim = XD_TARGET_DIM.get(group_id) if cat == "cross_dimension" else CATEGORY_TARGET_DIM[cat]
        gold_vals = {r["example_id"]: r[f"{target_dim}_true"] for r in rows}
        pred_vals = {r["example_id"]: r[f"{target_dim}_pred"] for r in rows}
        ids = [r["example_id"] for r in rows]
        concordant = discordant = tied_pairs = 0
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                gdiff = gold_vals[a] - gold_vals[b]
                pdiff = pred_vals[a] - pred_vals[b]
                if gdiff == 0:
                    continue
                if pdiff == 0:
                    tied_pairs += 1
                elif (gdiff > 0) == (pdiff > 0):
                    concordant += 1
                else:
                    discordant += 1
        if discordant > 0:
            status = "INCORRECTLY_ORDERED"
        elif concordant > 0 and tied_pairs == 0:
            status = "CORRECTLY_SEPARATED"
        elif concordant > 0 and tied_pairs > 0:
            status = "PARTIALLY_SEPARATED"
        else:
            status = "TIED"
        results.append({
            "pair_group_id": group_id, "category": cat, "n_examples": len(rows),
            "intended_dimension": target_dim,
            "gold_values": {i: gold_vals[i] for i in ids},
            "predicted_values": {i: pred_vals[i] for i in ids},
            "status": status, "concordant_pairs": concordant,
            "discordant_pairs": discordant, "tied_pairs": tied_pairs,
        })
    return results


def summarize_pairs(pair_results, category_filter=None):
    rows = [p for p in pair_results if category_filter is None or p["category"] == category_filter]
    n = len(rows)
    correct = sum(1 for p in rows if p["status"] == "CORRECTLY_SEPARATED")
    partial = sum(1 for p in rows if p["status"] == "PARTIALLY_SEPARATED")
    tied = sum(1 for p in rows if p["status"] == "TIED")
    wrong = sum(1 for p in rows if p["status"] == "INCORRECTLY_ORDERED")
    return {
        "total_groups": n, "correctly_separated": correct, "partially_separated": partial,
        "tied": tied, "incorrectly_ordered": wrong,
        "separation_rate": round(correct / n, 4) if n else None,
        "separation_rate_including_partial": round((correct + partial) / n, 4) if n else None,
    }


def main():
    with open(V4_DATASET_PATH, encoding="utf-8") as f:
        gold_examples = {json.loads(l)["example_id"]: json.loads(l) for l in f if l.strip()}
    with open(A2_PREDICTIONS_PATH, encoding="utf-8") as f:
        a2_preds = json.load(f)
    with open(A0_PREDICTIONS_PATH, encoding="utf-8") as f:
        a0_preds = json.load(f)
    with open(A1_PREDICTIONS_PATH, encoding="utf-8") as f:
        a1_preds = json.load(f)
    assert len(a2_preds) == 58
    assert len(a0_preds) == 58
    assert len(a1_preds) == 58

    # ---- aggregate + per-category metrics (A2) ----
    a2_aggregate = {dim: dim_metrics(a2_preds, dim) for dim in DIMS}
    a0_aggregate = {dim: dim_metrics(a0_preds, dim) for dim in DIMS}
    a1_aggregate = {dim: dim_metrics(a1_preds, dim) for dim in DIMS}

    by_category_a2 = {}
    for row in a2_preds:
        by_category_a2.setdefault(row["diagnostic_category"], []).append(row)
    a2_category_metrics = {
        cat: {"n_examples": len(rows), "per_dimension": {dim: dim_metrics(rows, dim) for dim in DIMS}}
        for cat, rows in by_category_a2.items()
    }

    # ---- pairwise diagnostic (A2) ----
    a2_pair_results = pair_analysis(a2_preds)
    a0_pair_results = pair_analysis(a0_preds)
    a1_pair_results = pair_analysis(a1_preds)
    a0_pair_by_id = {p["pair_group_id"]: p for p in a0_pair_results}
    a1_pair_by_id = {p["pair_group_id"]: p for p in a1_pair_results}

    a2_pair_summary_overall = summarize_pairs(a2_pair_results)
    a0_pair_summary_overall = summarize_pairs(a0_pair_results)
    a1_pair_summary_overall = summarize_pairs(a1_pair_results)
    a2_pair_summary_rel = summarize_pairs(a2_pair_results, "relevance_alignment")
    a0_pair_summary_rel = summarize_pairs(a0_pair_results, "relevance_alignment")
    a1_pair_summary_rel = summarize_pairs(a1_pair_results, "relevance_alignment")

    # group-by-group A0 vs A1 vs A2 comparison
    group_comparison = []
    for p in a2_pair_results:
        a0p = a0_pair_by_id[p["pair_group_id"]]
        a1p = a1_pair_by_id[p["pair_group_id"]]
        group_comparison.append({
            "pair_group_id": p["pair_group_id"], "category": p["category"],
            "n_examples": p["n_examples"], "intended_dimension": p["intended_dimension"],
            "gold_values": p["gold_values"],
            "a0_predicted_values": a0p["predicted_values"], "a0_status": a0p["status"],
            "a1_predicted_values": a1p["predicted_values"], "a1_status": a1p["status"],
            "a2_predicted_values": p["predicted_values"], "a2_status": p["status"],
            "status_changed_a1_to_a2": a1p["status"] != p["status"],
        })

    # per-category summaries for all three, for the comparison table
    category_summary_table = {}
    for cat in ("relevance_alignment", "multipart_completeness", "technical_correctness",
                "depth_control", "grounding_ownership", "cross_dimension"):
        target_dim = CATEGORY_TARGET_DIM.get(cat)
        a0_rows = [r for r in a0_preds if r["diagnostic_category"] == cat]
        a1_rows = [r for r in a1_preds if r["diagnostic_category"] == cat]
        a2_rows = [r for r in a2_preds if r["diagnostic_category"] == cat]
        a0_dim_m = dim_metrics(a0_rows, target_dim) if target_dim else None
        a1_dim_m = dim_metrics(a1_rows, target_dim) if target_dim else None
        a2_dim_m = dim_metrics(a2_rows, target_dim) if target_dim else None
        category_summary_table[cat] = {
            "primary_dimension": target_dim,
            "a0_qwk": a0_dim_m["qwk"] if a0_dim_m else None,
            "a1_qwk": a1_dim_m["qwk"] if a1_dim_m else None,
            "a2_qwk": a2_dim_m["qwk"] if a2_dim_m else None,
            "a0_pair_summary": summarize_pairs(a0_pair_results, cat),
            "a1_pair_summary": summarize_pairs(a1_pair_results, cat),
            "a2_pair_summary": summarize_pairs(a2_pair_results, cat),
        }

    # ---- critical failure checks (A2), mirroring analyze_v3_on_v4.py / analyze_a1_on_v4.py ----
    checks = {}
    detailed_irrelevant = [r for r in a2_preds if r["diagnostic_category"] == "relevance_alignment"
                            and r["example_id"].endswith("_a") and r["relevance_completeness_true"] <= 1]
    checks["1_detailed_irrelevant_scored_high_relevance"] = {
        "n_candidates": len(detailed_irrelevant),
        "n_scored_relevance_4": sum(1 for r in detailed_irrelevant if r["relevance_completeness_pred"] == 4),
        "n_scored_relevance_3plus": sum(1 for r in detailed_irrelevant if r["relevance_completeness_pred"] >= 3),
        "examples": [{"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
                      "relevance_pred": r["relevance_completeness_pred"]} for r in detailed_irrelevant],
    }
    concise_relevant = [r for r in a2_preds if r["diagnostic_category"] == "relevance_alignment"
                         and r["example_id"].endswith("_b") and r["relevance_completeness_true"] >= 3]
    checks["2_concise_relevant_scored_low"] = {
        "n_candidates": len(concise_relevant),
        "n_scored_relevance_le2": sum(1 for r in concise_relevant if r["relevance_completeness_pred"] <= 2),
        "examples": [{"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
                      "relevance_pred": r["relevance_completeness_pred"]} for r in concise_relevant],
    }
    misconceptions = [r for r in a2_preds if r["diagnostic_category"] == "technical_correctness"
                       and r["technical_correctness_true"] <= 1]
    checks["3_fluent_misconception_scored_high_TC"] = {
        "n_candidates": len(misconceptions),
        "n_scored_TC_4": sum(1 for r in misconceptions if r["technical_correctness_pred"] == 4),
        "n_scored_TC_3plus": sum(1 for r in misconceptions if r["technical_correctness_pred"] >= 3),
        "examples": [{"example_id": r["example_id"], "TC_true": r["technical_correctness_true"],
                      "TC_pred": r["technical_correctness_pred"]} for r in misconceptions],
    }
    partial_multipart = [r for r in a2_preds if r["diagnostic_category"] == "multipart_completeness"
                          and r["relevance_completeness_true"] <= 2]
    checks["7_partial_multipart_scored_relevance_4"] = {
        "n_candidates": len(partial_multipart),
        "n_scored_relevance_4": sum(1 for r in partial_multipart if r["relevance_completeness_pred"] == 4),
        "examples": [{"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
                      "relevance_pred": r["relevance_completeness_pred"]} for r in partial_multipart],
    }

    report = {
        "n_examples_evaluated": len(a2_preds),
        "a2_aggregate_metrics": a2_aggregate,
        "a0_aggregate_metrics_for_reference": a0_aggregate,
        "a1_aggregate_metrics_for_reference": a1_aggregate,
        "a2_category_metrics": a2_category_metrics,
        "a2_pair_summary_overall": a2_pair_summary_overall,
        "a0_pair_summary_overall_for_reference": a0_pair_summary_overall,
        "a1_pair_summary_overall_for_reference": a1_pair_summary_overall,
        "relevance_alignment_pair_summary": {"a0": a0_pair_summary_rel, "a1": a1_pair_summary_rel, "a2": a2_pair_summary_rel},
        "category_a0_vs_a1_vs_a2_table": category_summary_table,
        "group_by_group_a0_vs_a1_vs_a2": group_comparison,
        "a2_critical_failure_checks": checks,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote report to {REPORT_PATH}")
    print(json.dumps({
        "a2_aggregate_metrics": a2_aggregate,
        "a2_pair_summary_overall": a2_pair_summary_overall,
        "relevance_alignment_pair_summary": {"a0": a0_pair_summary_rel, "a1": a1_pair_summary_rel, "a2": a2_pair_summary_rel},
    }, indent=2))


if __name__ == "__main__":
    main()
