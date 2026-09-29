"""
Validation for v5_short_quality_calibration_80. Read-only against
four_dim_overall_v4_5000 and the V4 diagnostic set — never writes to either.
Reuses dataset_filters.py (exact/near-duplicate detection, malformed-answer
check, hallucinated-technology check) and dataset_acceptance.py's Pearson
helper rather than reimplementing them.
"""
from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict

from dataset_filters import (
    check_example,
    exact_qa_duplicate_indices,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
CAL_DIR = os.path.join(_HERE, "artifacts", "v5_short_quality_calibration_80")
CAL_EXAMPLES = os.path.join(CAL_DIR, "dataset", "examples.jsonl")
CAL_ROW_META = os.path.join(CAL_DIR, "dataset", "row_categories.json")

V4_5000_EXAMPLES = os.path.join(_HERE, "artifacts", "four_dim_overall_v4_5000", "dataset", "examples.jsonl")
V4_DIAG_PATH = os.path.join(_HERE, "artifacts", "v4_diagnostic", "v4_diagnostic_58.jsonl")

REPORT_PATH = os.path.join(CAL_DIR, "reports", "validation_report.json")


def _pearson(xs, ys):
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


def load_cal():
    recs = []
    with open(CAL_EXAMPLES, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    with open(CAL_ROW_META, encoding="utf-8") as f:
        meta = json.load(f)
    meta_by_id = {m["example_id"]: m for m in meta}
    return recs, meta_by_id


def load_v4_5000():
    recs = []
    with open(V4_5000_EXAMPLES, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    return recs


def load_v4_diag():
    recs = []
    with open(V4_DIAG_PATH, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    return recs


def main():
    cal, meta_by_id = load_cal()
    v4_5000 = load_v4_5000()
    v4_diag = load_v4_diag()

    report = {}

    # ── 1/2. counts + unique ids ─────────────────────────────────────────
    report["total_examples"] = len(cal)
    ids = [r["metadata"]["example_id"] for r in cal]
    report["unique_ids"] = len(set(ids)) == len(ids)
    report["duplicate_ids"] = [i for i, c in Counter(ids).items() if c > 1]

    # ── 3. exact duplicates within calibration set ───────────────────────
    pairs = [(r["inputs"]["question_text"], r["inputs"]["answer_text"]) for r in cal]
    exact_dup_idx = exact_qa_duplicate_indices(pairs)
    report["exact_duplicates_within_calibration"] = len(exact_dup_idx)
    report["exact_duplicate_indices"] = exact_dup_idx

    # ── 4. semantic (near) duplicates: within-set, vs 1003, vs V4 diag ────
    cal_answers = [r["inputs"]["answer_text"] for r in cal]

    v4_5000_answers = [r["inputs"]["answer_text"] for r in v4_5000]
    v4_5000_ids = [r["metadata"]["example_id"] for r in v4_5000]
    v4_diag_answers = [r["answer"] for r in v4_diag]
    v4_diag_ids = [r["example_id"] for r in v4_diag]

    from rewrite_verifier_client import _LazySemanticModel
    import numpy as np
    model = _LazySemanticModel.get()

    def batch_cross_near_dups(src_texts, src_ids, dst_texts, dst_ids, threshold=0.92):
        if model is None:
            return []  # SBERT unavailable in this environment; reported as skipped below
        src_emb = model.encode(src_texts, show_progress_bar=False)
        dst_emb = model.encode(dst_texts, show_progress_bar=False)
        src_norm = src_emb / np.linalg.norm(src_emb, axis=1, keepdims=True)
        dst_norm = dst_emb / np.linalg.norm(dst_emb, axis=1, keepdims=True)
        sims = src_norm @ dst_norm.T
        hits = []
        for i in range(sims.shape[0]):
            for j in range(sims.shape[1]):
                if sims[i, j] >= threshold:
                    hits.append({"cal_id": src_ids[i], "other_id": dst_ids[j], "score": round(float(sims[i, j]), 4)})
        return hits

    report["sbert_available"] = model is not None
    report["semantic_near_duplicates_vs_1003"] = batch_cross_near_dups(cal_answers, ids, v4_5000_answers, v4_5000_ids)
    report["semantic_near_duplicates_vs_v4_diagnostic"] = batch_cross_near_dups(cal_answers, ids, v4_diag_answers, v4_diag_ids)

    def within_set_near_dups(texts, id_list, threshold=0.92):
        if model is None:
            return []
        emb = model.encode(texts, show_progress_bar=False)
        norm = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        sims = norm @ norm.T
        hits = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if sims[i, j] >= threshold:
                    hits.append({"i": i, "j": j, "score": round(float(sims[i, j]), 4), "id_i": id_list[i], "id_j": id_list[j]})
        return hits

    report["semantic_near_duplicates_within_calibration"] = within_set_near_dups(cal_answers, ids)

    # ── 5/6. cross-split contamination / leakage: exact (question,answer) match ──
    v4_5000_pairs = {
        (r["inputs"]["question_text"].strip().lower(), r["inputs"]["answer_text"].strip().lower())
        for r in v4_5000
    }
    v4_diag_pairs = {
        (r["question"].strip().lower(), r["answer"].strip().lower())
        for r in v4_diag
    }
    exact_leak_1003 = [
        ids[i] for i, (q, a) in enumerate(pairs) if (q.strip().lower(), a.strip().lower()) in v4_5000_pairs
    ]
    exact_leak_diag = [
        ids[i] for i, (q, a) in enumerate(pairs) if (q.strip().lower(), a.strip().lower()) in v4_diag_pairs
    ]
    report["exact_leakage_vs_1003"] = exact_leak_1003
    report["exact_leakage_vs_v4_diagnostic"] = exact_leak_diag

    # ── 7. schema validity (re-parse via TrainingExample) ────────────────
    from training_example import TrainingExample
    schema_errors = []
    for r in cal:
        try:
            TrainingExample.model_validate(r)
        except Exception as e:
            schema_errors.append({"example_id": r["metadata"]["example_id"], "error": str(e)})
    report["schema_valid"] = len(schema_errors) == 0
    report["schema_errors"] = schema_errors

    # ── 8/9. label validity + overall consistency ────────────────────────
    label_errors = []
    for r in cal:
        dims = {d["name"]: d["score"] for d in r["labels"]["dimension_labels"]}
        expected_overall = round(sum(dims.values()) / len(dims), 4)
        actual_overall = r["labels"]["overall_label"]["score"]
        if abs(expected_overall - actual_overall) > 1e-6:
            label_errors.append({
                "example_id": r["metadata"]["example_id"],
                "expected_overall": expected_overall, "actual_overall": actual_overall,
            })
        for v in dims.values():
            if v not in (0.0, 0.25, 0.5, 0.75, 1.0):
                label_errors.append({"example_id": r["metadata"]["example_id"], "bad_score": v})
    report["overall_consistency_errors"] = label_errors
    report["overall_consistency_pass"] = len(label_errors) == 0

    # ── per-example filter checks (banned phrases, malformed, hallucinated tech) ──
    filter_flags = []
    for r in cal:
        tech = r["inputs"]["specification"]["grounding"]["project"]["technologies"]
        verdict = check_example(r["inputs"]["answer_text"], allowed_technologies=tech)
        if not verdict.accepted:
            filter_flags.append({"example_id": r["metadata"]["example_id"], "reasons": list(verdict.reasons)})
    report["filter_flags"] = filter_flags

    # ── 11. PII check (declared) ──────────────────────────────────────────
    pii_flagged = [r["metadata"]["example_id"] for r in cal if r["privacy"]["contains_pii"]]
    report["pii_flagged"] = pii_flagged

    # ── length stats + bucket/tier distribution + bias metrics ───────────
    def word_count(text):
        return len(text.split())

    lengths = [word_count(r["inputs"]["answer_text"]) for r in cal]
    overalls = [r["labels"]["overall_label"]["score"] for r in cal]

    def score_to_tier(score):
        if score >= 0.80:
            return 4
        if score >= 0.60:
            return 3
        if score >= 0.40:
            return 2
        if score >= 0.25:
            return 1
        return 0

    tiers = [score_to_tier(s) for s in overalls]

    def bucket(n):
        if n <= 35:
            return "short"
        if n <= 80:
            return "medium"
        return "long"

    buckets = [bucket(n) for n in lengths]
    report["length_stats"] = {
        "mean_words": round(statistics.mean(lengths), 2),
        "median_words": statistics.median(lengths),
        "min_words": min(lengths),
        "max_words": max(lengths),
    }
    report["length_bucket_counts"] = dict(Counter(buckets))
    report["tier_distribution"] = dict(sorted(Counter(tiers).items()))

    bucket_tier = defaultdict(lambda: defaultdict(int))
    for b, t in zip(buckets, tiers):
        bucket_tier[b][t] += 1
    report["length_bucket_by_tier"] = {b: dict(sorted(d.items())) for b, d in bucket_tier.items()}

    corr = _pearson([float(n) for n in lengths], [float(t) for t in tiers])
    report["length_tier_pearson_correlation"] = round(corr, 4) if corr is not None else None

    report["short_tier3_count"] = sum(1 for n, t in zip(lengths, tiers) if n <= 30 and t == 3)
    report["short_tier4_count"] = sum(1 for n, t in zip(lengths, tiers) if n <= 30 and t == 4)
    report["long_tier012_count"] = sum(1 for n, t in zip(lengths, tiers) if n >= 90 and t in (0, 1, 2))

    # ── composition counts (by authored category) ─────────────────────────
    cat_counts = Counter(meta_by_id[i]["category_num"] for i in ids)
    report["composition_counts"] = dict(sorted(cat_counts.items()))

    # ── domain/technology coverage ────────────────────────────────────────
    all_tech = Counter()
    for r in cal:
        for t in r["inputs"]["specification"]["grounding"]["project"]["technologies"]:
            all_tech[t] += 1
    report["technology_coverage"] = dict(sorted(all_tech.items(), key=lambda kv: -kv[1]))

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
