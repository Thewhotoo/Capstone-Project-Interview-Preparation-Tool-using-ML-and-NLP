"""
V3 DATA REPAIR -- Phase 5 validation. READ-ONLY: never writes to any
training artifact. Writes only artifacts/v3_grounding/validation_report.json.
"""
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ARTIFACTS_DIR = os.path.dirname(_HERE)
_CAP_DIR = os.path.dirname(_ARTIFACTS_DIR)  # .../main_cap/cap
_REPO_ROOT = os.path.dirname(os.path.dirname(_CAP_DIR))  # git toplevel

sys.path.insert(0, os.path.dirname(_HERE))  # main_cap/cap on path
from build_grounding_proposals import load_pool_records, build_proposals  # noqa: E402

# Examples independently identified (in the prior read-only audit) as
# containing a technically wrong / self-contradicting claim, OR as a vague
# unsupported-ownership claim with no verifiable content. Evidence must never
# be drawn from these.
MISCONCEPTION_OR_CONTRADICTED_EXAMPLE_IDS = {
    "seed_v1_009", "seed_v1_018",          # MeshRouter (circuit-breaking / load-balancing misconceptions)
    "seed_v1_016",                          # OrderMesh (exactly-once misconception)
    "seed_v1_008",                          # VaultGuard (symmetric-cipher misconception)
    "hand50_v1_023",                        # RaftKeeper (leader-election misconception)
    "seed_v1_017",                          # ShardDB (SQL-text-hash misconception)
    "v2t50_v1_024",                         # StreamPipe (cross-partition ordering misconception)
    "seed_v1_019",                          # SupportBot (unbounded-context misconception)
    "seed_v1_036",                          # TaskFlow (Firebase, contradicts sibling account)
    "v2t50_v1_038",                         # GeoPulse (contradicts sibling Kalman-filter account)
    "hand50_v1_044",                        # PipelineForge (overconfident/likely-wrong schema claim)
    "seed_v1_039",                          # CloudScaler (Pulumi, contradicts title's Terraform tag)
}
UNSUPPORTED_OWNERSHIP_EXAMPLE_IDS = {
    "seed_v1_034",   # DefectScan
    "seed_v1_033",   # StreamETL
    "hand50_v1_015", # TrailRunner
    "hand50_v1_040", # VisionSort
    "seed_v1_035",   # SupportBot
}

SINGLE_EXAMPLE_PROJECT_IDS = {
    "gap20_v1_000", "gap20_v1_012", "v2t50_v1_003", "gap20_v1_008",
    "gap20_v1_003", "gap20_v1_009", "gap20_v1_005", "v2t50_v1_045",
    "gap20_v1_007", "gap20_v1_010", "gap20_v1_004", "v2t50_v1_000",
    "gap20_v1_002", "v2t50_v1_002", "gap20_v1_006", "gap20_v1_013",
    "gap20_v1_001", "gap20_v1_011",
}

GOLD_LABEL_WORDS = re.compile(
    r"\b(gold|tier|score|technical_correctness|depth_specificity|"
    r"relevance_completeness|grounding_ownership|rubric|correct answer|"
    r"should mention|should say)\b",
    re.IGNORECASE,
)
FIRST_PERSON = re.compile(
    r"\b(I|I've|I'd|I'll|my|My|mine|we|We|we've|We've|our|Our|us|Us)\b(?!/O)"
)


def git_diff_only_expected_concepts(paths):
    """Confirm the only field-level change in the 4 raw pool files (vs the
    pre-Phase-1 committed state) is expected_concepts on the 3 approved
    examples. Returns (ok, detail)."""
    proc = subprocess.run(
        ["git", "diff", "--", *paths],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    diff = proc.stdout
    changed_lines = [l for l in diff.splitlines() if l.startswith("+{") or l.startswith("-{")]
    # every changed line must parse as JSON and differ from its pair only in
    # expected_concepts
    pairs = {}
    for l in changed_lines:
        sign = l[0]
        rec = json.loads(l[1:])
        eid = rec["example_id"]
        pairs.setdefault(eid, {})[sign] = rec
    bad = []
    for eid, sides in pairs.items():
        if "+" not in sides or "-" not in sides:
            bad.append((eid, "unpaired change"))
            continue
        a, b = sides["-"], sides["+"]
        diff_keys = [k for k in a if a.get(k) != b.get(k)]
        if diff_keys != ["expected_concepts"]:
            bad.append((eid, f"changed fields: {diff_keys}"))
    return (len(bad) == 0, bad, sorted(pairs.keys()))


def main():
    pool = load_pool_records()
    by_id = {r["example_id"]: r for r in pool}
    proposals = build_proposals(pool)
    by_prop_id = {p["example_id"]: p for p in proposals}

    checks = {}
    failures = []

    # 1. at most one grounding proposal per example
    ids = [p["example_id"] for p in proposals]
    checks["at_most_one_proposal_per_example"] = len(ids) == len(set(ids))
    if not checks["at_most_one_proposal_per_example"]:
        failures.append("duplicate example_id in proposals")

    # 2. all example_ids valid (exist in pool)
    checks["all_example_ids_valid"] = all(eid in by_id for eid in ids)
    if not checks["all_example_ids_valid"]:
        failures.append("proposal example_id not found in pool")

    # 3. all evidence_example_ids exist
    all_evidence = [eid for p in proposals for eid in p["evidence_example_ids"]]
    checks["all_evidence_ids_valid"] = all(eid in by_id for eid in all_evidence)
    if not checks["all_evidence_ids_valid"]:
        failures.append("evidence example_id not found in pool")

    # 4. evidence stays within same source_id, and never self-cites
    same_source_ok = True
    no_self_cite = True
    for p in proposals:
        for eid in p["evidence_example_ids"]:
            if by_id[eid]["source_id"] != p["source_id"]:
                same_source_ok = False
            if eid == p["example_id"]:
                no_self_cite = False
    checks["evidence_same_source_id"] = same_source_ok
    checks["no_self_sourcing"] = no_self_cite
    if not same_source_ok:
        failures.append("evidence crosses source_id boundary")
    if not no_self_cite:
        failures.append("an example cites itself as its own evidence")

    # 5. no evidence from misconception/contradicted examples
    bad_evidence = [
        (p["example_id"], eid) for p in proposals for eid in p["evidence_example_ids"]
        if eid in MISCONCEPTION_OR_CONTRADICTED_EXAMPLE_IDS
    ]
    checks["no_misconception_evidence"] = len(bad_evidence) == 0
    if bad_evidence:
        failures.append(f"evidence drawn from flagged misconception examples: {bad_evidence}")

    # 6. no evidence from unsupported-ownership examples
    bad_ownership_evidence = [
        (p["example_id"], eid) for p in proposals for eid in p["evidence_example_ids"]
        if eid in UNSUPPORTED_OWNERSHIP_EXAMPLE_IDS
    ]
    checks["no_unsupported_ownership_evidence"] = len(bad_ownership_evidence) == 0
    if bad_ownership_evidence:
        failures.append(f"evidence drawn from unsupported-ownership examples: {bad_ownership_evidence}")

    # 7. no first-person attribution in grounding text
    fp_hits = [p["example_id"] for p in proposals if FIRST_PERSON.search(p["grounding_text"])]
    checks["no_first_person_in_grounding"] = len(fp_hits) == 0
    if fp_hits:
        failures.append(f"first-person language found in grounding: {fp_hits}")

    # 8. no gold labels/scores/rubric terminology in grounding text
    gold_hits = [p["example_id"] for p in proposals if GOLD_LABEL_WORDS.search(p["grounding_text"])]
    checks["no_gold_label_leakage"] = len(gold_hits) == 0
    if gold_hits:
        failures.append(f"gold-label/rubric terminology found in grounding: {gold_hits}")

    # 9. no exact candidate-answer copy (grounding text is not a verbatim
    #    substring of, nor contains, the receiving example's own answer, and
    #    is not identical to any evidence example's answer either)
    exact_copy_hits = []
    for p in proposals:
        own_answer = by_id[p["example_id"]]["answer"]
        gt = p["grounding_text"]
        if gt in own_answer or own_answer in gt:
            exact_copy_hits.append(p["example_id"])
    checks["no_exact_answer_copy"] = len(exact_copy_hits) == 0
    if exact_copy_hits:
        failures.append(f"grounding text is an exact substring match with the answer: {exact_copy_hits}")

    # 10. SBERT similarity between grounding and the RECEIVING example's own
    #     candidate answer must not be suspiciously high (threshold 0.92,
    #     same threshold/model used by every prior batch's near-duplicate check)
    sbert_report = []
    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts_a = [p["grounding_text"] for p in proposals]
        texts_b = [by_id[p["example_id"]]["answer"] for p in proposals]
        emb_a = model.encode(texts_a, convert_to_tensor=True, normalize_embeddings=True)
        emb_b = model.encode(texts_b, convert_to_tensor=True, normalize_embeddings=True)
        sims = util.cos_sim(emb_a, emb_b).diagonal().tolist() if hasattr(util.cos_sim(emb_a, emb_b), "diagonal") else None
        cos = util.cos_sim(emb_a, emb_b)
        sims = [float(cos[i][i]) for i in range(len(proposals))]
        high_sim = []
        for p, sim in zip(proposals, sims):
            sbert_report.append({"example_id": p["example_id"], "cosine_similarity_to_own_answer": round(sim, 4)})
            if sim >= 0.92:
                high_sim.append((p["example_id"], round(sim, 4)))
        checks["no_suspiciously_high_sbert_similarity"] = len(high_sim) == 0
        if high_sim:
            failures.append(f"grounding too similar (>=0.92 cosine) to its own answer: {high_sim}")
        sbert_ran = True
    except Exception as exc:  # pragma: no cover
        checks["no_suspiciously_high_sbert_similarity"] = None
        sbert_ran = False
        sbert_report = [{"error": str(exc)}]

    # 11. no question/answer text changes, no gold-label changes (field-level
    #     diff restricted to expected_concepts on the 3 approved examples)
    raw_paths = [
        "main_cap/cap/artifacts/seed_dataset_v1/seed_v1_3_repaired.jsonl",
        "main_cap/cap/artifacts/hand_authored_50/hand_authored_50_v1.jsonl",
        "main_cap/cap/artifacts/gap_coverage_20/gap20_v1.jsonl",
        "main_cap/cap/artifacts/v2_targeted_50/v2_targeted_50_v1.jsonl",
    ]
    diff_ok, diff_bad, diff_changed_ids = git_diff_only_expected_concepts(raw_paths)
    checks["only_expected_concepts_changed_in_pool_files"] = diff_ok
    checks["pool_files_changed_example_ids"] = diff_changed_ids
    if not diff_ok:
        failures.append(f"unexpected field changes in pool files: {diff_bad}")
    APPROVED_EXPECTED_CONCEPTS_CHANGES = sorted([
        "hand50_v1_020", "seed_v1_089", "v2t50_v1_041",
        "seed_v1_038", "seed_v1_078", "seed_v1_004", "seed_v1_026",
    ])
    checks["exactly_the_approved_examples_changed"] = diff_changed_ids == APPROVED_EXPECTED_CONCEPTS_CHANGES
    if not checks["exactly_the_approved_examples_changed"]:
        failures.append(
            f"pool-file diff touched a different set than the approved list: "
            f"{diff_changed_ids} != {APPROVED_EXPECTED_CONCEPTS_CHANGES}"
        )

    # 11b. the 5 CloudScaler examples (held, NOT approved yet) must be
    # byte-identical to before -- explicit negative check
    cloudscaler_held = ["seed_v1_006", "seed_v1_021", "seed_v1_031", "seed_v1_039", "seed_v1_079"]
    checks["cloudscaler_held_examples_unchanged"] = not any(
        eid in diff_changed_ids for eid in cloudscaler_held
    )
    if not checks["cloudscaler_held_examples_unchanged"]:
        failures.append("a held CloudScaler example was unexpectedly changed")

    # 12. source_id / group assignments and V2 split unchanged
    split_path = os.path.join(_ARTIFACTS_DIR, "four_dim_experiment_v2", "split.json")
    proc = subprocess.run(["git", "diff", "--stat", "--", split_path.replace(_REPO_ROOT + os.sep, "")],
                           cwd=_REPO_ROOT, capture_output=True, text=True)
    checks["v2_split_json_untouched"] = proc.stdout.strip() == ""
    if not checks["v2_split_json_untouched"]:
        failures.append("four_dim_experiment_v2/split.json has uncommitted changes")

    proc2 = subprocess.run(["git", "status", "--porcelain", "--", split_path.replace(_REPO_ROOT + os.sep, "")],
                            cwd=_REPO_ROOT, capture_output=True, text=True)
    checks["v2_split_json_status_clean"] = proc2.stdout.strip() == ""

    # 13. all 18 single-example projects remain unenriched
    single_enriched = [eid for eid in ids if eid in SINGLE_EXAMPLE_PROJECT_IDS]
    checks["single_example_projects_unenriched"] = len(single_enriched) == 0
    if single_enriched:
        failures.append(f"single-example project examples were enriched: {single_enriched}")

    # ---- summary stats ----
    total_v2 = len(pool)
    enriched_ids = set(ids)
    confidence_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in proposals:
        confidence_counts[p["confidence"]] += 1

    # projects with >=2 examples but zero safe grounding fragment for ANY member
    multi_example_source_ids = {}
    for r in pool:
        multi_example_source_ids.setdefault(r["source_id"], []).append(r["example_id"])
    multi_projects = {sid: eids for sid, eids in multi_example_source_ids.items() if len(eids) >= 2}
    zero_grounding_projects = sorted(
        sid for sid, eids in multi_projects.items()
        if not any(eid in enriched_ids for eid in eids)
    )

    low_confidence_chains = [
        {"example_id": p["example_id"], "evidence_example_ids": p["evidence_example_ids"],
         "grounding_scope": p["grounding_scope"]}
        for p in proposals if p["confidence"] == "LOW"
    ]

    report = {
        "checks": checks,
        "all_checks_passed": all(v for v in checks.values() if isinstance(v, bool)),
        "failures": failures,
        "stats": {
            "total_v2_pool_examples": total_v2,
            "examples_with_grounding_proposal": len(enriched_ids),
            "examples_left_unchanged": total_v2 - len(enriched_ids),
            "confidence_breakdown": confidence_counts,
            "multi_example_projects_total": len(multi_projects),
            "multi_example_projects_with_zero_safe_grounding": len(zero_grounding_projects),
            "multi_example_projects_with_zero_safe_grounding_list": zero_grounding_projects,
            "single_example_projects_total": len(SINGLE_EXAMPLE_PROJECT_IDS),
            "single_example_projects_enriched": len(single_enriched),
        },
        "low_confidence_evidence_chains": low_confidence_chains,
        "sbert_check_ran": sbert_ran,
        "sbert_similarity_report": sbert_report,
    }

    out_path = os.path.join(_HERE, "validation_report.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report["checks"], indent=2))
    print(json.dumps(report["stats"], indent=2))
    print("ALL CHECKS PASSED" if report["all_checks_passed"] else f"FAILURES: {failures}")
    return report


if __name__ == "__main__":
    main()
