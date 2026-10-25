"""
V3-on-V4 analysis — READ-ONLY. Consumes `v4_diagnostic_58.jsonl` (gold
labels + rationale, metadata only) and `v3_predictions_on_v4.json`
(predictions already produced by `run_v3_inference_on_v4.py`). Performs no
inference itself and trains nothing. Writes exactly one new file:
`v3_on_v4_report.json`.
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
V4_DATASET_PATH = os.path.join(_HERE, "v4_diagnostic_58.jsonl")
PREDICTIONS_PATH = os.path.join(_HERE, "v3_predictions_on_v4.json")
REPORT_PATH = os.path.join(_HERE, "v3_on_v4_report.json")

DIMS = ("technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership")

# Which dimension each category's contrast is primarily about.
CATEGORY_TARGET_DIM = {
    "relevance_alignment": "relevance_completeness",
    "multipart_completeness": "relevance_completeness",
    "technical_correctness": "technical_correctness",
    "depth_control": "depth_specificity",
    "grounding_ownership": "grounding_ownership",
}
# cross_dimension groups each target a different single dimension.
XD_TARGET_DIM = {"XD-1": "grounding_ownership", "XD-2": "relevance_completeness"}
XD_HELD_CONSTANT = {
    "XD-1": ["technical_correctness", "depth_specificity", "relevance_completeness"],
    "XD-2": ["technical_correctness", "grounding_ownership"],  # depth explicitly disclosed as not fully held (see README)
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
        "n": n,
        "accuracy": round(exact, 4),
        "mae": round(mae, 4),
        "within_1_accuracy": round(within1, 4),
        "qwk": round(qwk(y_true, y_pred), 4),
        "mean_true": round(mean_true, 4),
        "mean_pred": round(mean_pred, 4),
        "bias": round(mean_pred - mean_true, 4),  # positive = systematic over-prediction
    }


def main():
    with open(V4_DATASET_PATH, encoding="utf-8") as f:
        gold_examples = {json.loads(l)["example_id"]: json.loads(l) for l in f if l.strip()}
    with open(PREDICTIONS_PATH, encoding="utf-8") as f:
        preds = json.load(f)
    assert len(preds) == 58, f"expected 58 predictions, got {len(preds)}"

    # ---------------- PHASE 3: aggregate + per-category metrics ----------------
    aggregate = {dim: dim_metrics(preds, dim) for dim in DIMS}

    by_category = {}
    for row in preds:
        by_category.setdefault(row["diagnostic_category"], []).append(row)
    category_metrics = {}
    for cat, rows in by_category.items():
        category_metrics[cat] = {
            "n_examples": len(rows),
            "per_dimension": {dim: dim_metrics(rows, dim) for dim in DIMS},
        }

    # ---------------- PHASE 4: pairwise diagnostic ----------------
    by_group = {}
    for row in preds:
        by_group.setdefault(row["pair_group_id"], []).append(row)

    pair_results = []
    for group_id, rows in sorted(by_group.items()):
        cat = rows[0]["diagnostic_category"]
        target_dim = XD_TARGET_DIM.get(group_id) if cat == "cross_dimension" else CATEGORY_TARGET_DIM[cat]
        gold_vals = {r["example_id"]: r[f"{target_dim}_true"] for r in rows}
        pred_vals = {r["example_id"]: r[f"{target_dim}_pred"] for r in rows}

        ids = [r["example_id"] for r in rows]
        concordant = discordant = tied_pairs = 0
        pair_detail = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                gdiff = gold_vals[a] - gold_vals[b]
                pdiff = pred_vals[a] - pred_vals[b]
                if gdiff == 0:
                    continue  # not a meaningful contrast on this dimension
                if pdiff == 0:
                    tied_pairs += 1
                    verdict = "tied"
                elif (gdiff > 0) == (pdiff > 0):
                    concordant += 1
                    verdict = "concordant"
                else:
                    discordant += 1
                    verdict = "discordant"
                pair_detail.append({
                    "a": a, "b": b, "gold_diff": gdiff, "pred_diff": pdiff, "verdict": verdict,
                })

        if discordant > 0:
            status = "INCORRECTLY_ORDERED"
        elif concordant > 0 and tied_pairs == 0:
            status = "CORRECTLY_SEPARATED"
        elif concordant > 0 and tied_pairs > 0:
            status = "PARTIALLY_SEPARATED"
        else:
            status = "TIED"

        entry = {
            "pair_group_id": group_id,
            "category": cat,
            "n_examples": len(rows),
            "intended_dimension": target_dim,
            "gold_ordering": sorted(ids, key=lambda i: gold_vals[i]),
            "gold_values": {i: gold_vals[i] for i in ids},
            "predicted_ordering": sorted(ids, key=lambda i: pred_vals[i]),
            "predicted_values": {i: pred_vals[i] for i in ids},
            "status": status,
            "concordant_pairs": concordant,
            "discordant_pairs": discordant,
            "tied_pairs": tied_pairs,
            "pair_detail": pair_detail,
        }

        # cross_dimension groups also get an explicit "held constant" check
        if cat == "cross_dimension":
            held = XD_HELD_CONSTANT[group_id]
            drift = {}
            for dim in held:
                vals = [r[f"{dim}_pred"] for r in rows]
                drift[dim] = {"pred_values": vals, "range": max(vals) - min(vals)}
            entry["held_constant_check"] = drift

        pair_results.append(entry)

    n_groups = len(pair_results)
    n_correct = sum(1 for p in pair_results if p["status"] == "CORRECTLY_SEPARATED")
    n_partial = sum(1 for p in pair_results if p["status"] == "PARTIALLY_SEPARATED")
    n_tied = sum(1 for p in pair_results if p["status"] == "TIED")
    n_wrong = sum(1 for p in pair_results if p["status"] == "INCORRECTLY_ORDERED")
    pair_summary = {
        "total_groups": n_groups,
        "correctly_separated": n_correct,
        "partially_separated": n_partial,
        "tied": n_tied,
        "incorrectly_ordered": n_wrong,
        "separation_rate": round(n_correct / n_groups, 4),
        "separation_rate_including_partial": round((n_correct + n_partial) / n_groups, 4),
    }

    # ---------------- PHASE 5: critical failure checks ----------------
    def pred(eid, dim):
        return next(r[f"{dim}_pred"] for r in preds if r["example_id"] == eid)

    def true(eid, dim):
        return next(r[f"{dim}_true"] for r in preds if r["example_id"] == eid)

    checks = {}

    # 1. detailed-but-irrelevant -> relevance 4
    detailed_irrelevant = [r for r in preds if r["diagnostic_category"] in ("relevance_alignment",)
                            and r["example_id"].endswith("_a") and r["relevance_completeness_true"] <= 1]
    checks["1_detailed_irrelevant_scored_high_relevance"] = {
        "n_candidates": len(detailed_irrelevant),
        "n_scored_relevance_4": sum(1 for r in detailed_irrelevant if r["relevance_completeness_pred"] == 4),
        "n_scored_relevance_3plus": sum(1 for r in detailed_irrelevant if r["relevance_completeness_pred"] >= 3),
        "examples": [
            {"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
             "relevance_pred": r["relevance_completeness_pred"]}
            for r in detailed_irrelevant
        ],
    }

    # 2. concise-but-relevant -> low relevance (should NOT happen if model works)
    concise_relevant = [r for r in preds if r["diagnostic_category"] in ("relevance_alignment",)
                         and r["example_id"].endswith("_b") and r["relevance_completeness_true"] >= 3]
    checks["2_concise_relevant_scored_low"] = {
        "n_candidates": len(concise_relevant),
        "n_scored_relevance_le2": sum(1 for r in concise_relevant if r["relevance_completeness_pred"] <= 2),
        "examples": [
            {"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
             "relevance_pred": r["relevance_completeness_pred"]}
            for r in concise_relevant
        ],
    }

    # 3. fluent misconception -> technical_correctness 4
    misconceptions = [r for r in preds if r["diagnostic_category"] == "technical_correctness"
                       and r["technical_correctness_true"] <= 1]
    checks["3_fluent_misconception_scored_high_TC"] = {
        "n_candidates": len(misconceptions),
        "n_scored_TC_4": sum(1 for r in misconceptions if r["technical_correctness_pred"] == 4),
        "n_scored_TC_3plus": sum(1 for r in misconceptions if r["technical_correctness_pred"] >= 3),
        "examples": [
            {"example_id": r["example_id"], "TC_true": r["technical_correctness_true"],
             "TC_pred": r["technical_correctness_pred"]}
            for r in misconceptions
        ],
    }

    # 4. correct-but-shallow -> depth 4
    shallow_correct = [r for r in preds if r["diagnostic_category"] == "depth_control"
                        and r["depth_specificity_true"] <= 1]
    checks["4_correct_but_shallow_scored_high_depth"] = {
        "n_candidates": len(shallow_correct),
        "n_scored_depth_4": sum(1 for r in shallow_correct if r["depth_specificity_pred"] == 4),
        "n_scored_depth_3plus": sum(1 for r in shallow_correct if r["depth_specificity_pred"] >= 3),
        "examples": [
            {"example_id": r["example_id"], "depth_true": r["depth_specificity_true"],
             "depth_pred": r["depth_specificity_pred"]}
            for r in shallow_correct
        ],
    }

    # 5. unsupported ownership -> grounding 3/4
    unsupported_ownership = [r for r in preds if r["diagnostic_category"] == "grounding_ownership"
                              and gold_examples[r["example_id"]]["gold_labels"]["grounding_ownership"] <= 1
                              and gold_examples[r["example_id"]]["example_id"].endswith("_d")]
    checks["5_unsupported_ownership_scored_high_grounding"] = {
        "n_candidates": len(unsupported_ownership),
        "n_scored_grounding_3plus": sum(1 for r in unsupported_ownership if r["grounding_ownership_pred"] >= 3),
        "examples": [
            {"example_id": r["example_id"], "grounding_true": r["grounding_ownership_true"],
             "grounding_pred": r["grounding_ownership_pred"]}
            for r in unsupported_ownership
        ],
    }

    # 6. genuine ownership -> grounding 0/1 (should NOT happen if model works)
    genuine_ownership = [r for r in preds if r["diagnostic_category"] == "grounding_ownership"
                          and r["grounding_ownership_true"] == 4]
    checks["6_genuine_ownership_scored_low_grounding"] = {
        "n_candidates": len(genuine_ownership),
        "n_scored_grounding_le1": sum(1 for r in genuine_ownership if r["grounding_ownership_pred"] <= 1),
        "examples": [
            {"example_id": r["example_id"], "grounding_true": r["grounding_ownership_true"],
             "grounding_pred": r["grounding_ownership_pred"]}
            for r in genuine_ownership
        ],
    }

    # 7. partial multipart answer -> relevance 4
    partial_multipart = [r for r in preds if r["diagnostic_category"] == "multipart_completeness"
                          and r["relevance_completeness_true"] <= 2]
    checks["7_partial_multipart_scored_relevance_4"] = {
        "n_candidates": len(partial_multipart),
        "n_scored_relevance_4": sum(1 for r in partial_multipart if r["relevance_completeness_pred"] == 4),
        "n_scored_relevance_3plus": sum(1 for r in partial_multipart if r["relevance_completeness_pred"] >= 3),
        "examples": [
            {"example_id": r["example_id"], "relevance_true": r["relevance_completeness_true"],
             "relevance_pred": r["relevance_completeness_pred"]}
            for r in partial_multipart
        ],
    }

    # 8. off-topic but technically correct -> relevance 4
    offtopic_correct = [r for r in preds if r["diagnostic_category"] == "relevance_alignment"
                         and r["example_id"].endswith("_a")
                         and r["technical_correctness_true"] >= 3
                         and r["relevance_completeness_true"] <= 1]
    checks["8_offtopic_but_correct_scored_relevance_4"] = {
        "n_candidates": len(offtopic_correct),
        "n_scored_relevance_4": sum(1 for r in offtopic_correct if r["relevance_completeness_pred"] == 4),
        "examples": [
            {"example_id": r["example_id"], "TC_true": r["technical_correctness_true"],
             "relevance_true": r["relevance_completeness_true"],
             "relevance_pred": r["relevance_completeness_pred"]}
            for r in offtopic_correct
        ],
    }

    # ---------------- PHASE 6: cross-dimension behavior ----------------
    xd_analysis = {}
    for group_id in ("XD-1", "XD-2"):
        rows = by_group[group_id]
        held = XD_HELD_CONSTANT[group_id]
        target = XD_TARGET_DIM[group_id]
        target_pred_range = max(r[f"{target}_pred"] for r in rows) - min(r[f"{target}_pred"] for r in rows)
        held_ranges = {dim: max(r[f"{dim}_pred"] for r in rows) - min(r[f"{dim}_pred"] for r in rows) for dim in held}
        xd_analysis[group_id] = {
            "target_dimension": target,
            "target_dimension_pred_range": target_pred_range,
            "held_constant_dims": held,
            "held_constant_pred_ranges": held_ranges,
            "unwanted_movement": {dim: rng for dim, rng in held_ranges.items() if rng > 0},
        }

    # also: broader co-movement check across ALL relevance_alignment pairs --
    # when relevance drops sharply (gold), do TC/depth/grounding predictions
    # also drop even though gold says they should NOT?
    comovement_flags = []
    for group_id, rows in by_group.items():
        if len(rows) != 2:
            continue
        a, b = rows
        rel_gold_diff = a["relevance_completeness_true"] - b["relevance_completeness_true"]
        if abs(rel_gold_diff) < 2:
            continue
        for dim in ("technical_correctness", "depth_specificity", "grounding_ownership"):
            gold_diff = abs(a[f"{dim}_true"] - b[f"{dim}_true"])
            pred_diff = abs(a[f"{dim}_pred"] - b[f"{dim}_pred"])
            if gold_diff <= 1 and pred_diff >= 2:
                comovement_flags.append({
                    "pair_group_id": group_id, "dimension_that_moved_unexpectedly": dim,
                    "gold_diff": gold_diff, "pred_diff": pred_diff,
                    "a": a["example_id"], "b": b["example_id"],
                })

    report = {
        "n_examples_evaluated": len(preds),
        "aggregate_metrics": aggregate,
        "category_metrics": category_metrics,
        "pair_summary": pair_summary,
        "pair_results": pair_results,
        "critical_failure_checks": checks,
        "cross_dimension_analysis": xd_analysis,
        "comovement_flags_general": comovement_flags,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote report to {REPORT_PATH}")
    print(json.dumps({"aggregate_metrics": aggregate, "pair_summary": pair_summary}, indent=2))


if __name__ == "__main__":
    main()
