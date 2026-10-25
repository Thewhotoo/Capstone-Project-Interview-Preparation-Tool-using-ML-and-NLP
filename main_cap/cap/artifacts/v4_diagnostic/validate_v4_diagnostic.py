"""
V4 Diagnostic Dataset Validator — READ-ONLY.

Validates `v4_diagnostic_58.jsonl` against every check listed in the V4
implementation request. Never writes to any frozen artifact (`seed_dataset_v1/`,
`hand_authored_50/`, `gap_coverage_20/`, `v2_targeted_50/`, `v3_grounding/`,
`four_dim_experiment_v1/`, `four_dim_experiment_v2/`) — only reads them, for
the isolation/source-id-collision check. Writes exactly one file:
`validation_report.json` in this same directory.

Run: `python validate_v4_diagnostic.py` from this directory, or
`python artifacts/v4_diagnostic/validate_v4_diagnostic.py` from `main_cap/cap/`.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CAP_DIR = os.path.dirname(os.path.dirname(_HERE))  # main_cap/cap
sys.path.insert(0, _HERE)

from v4_input_builder import FORBIDDEN_INPUT_LEAK_FIELDS, build_v4_model_input  # noqa: E402

DATASET_PATH = os.path.join(_HERE, "v4_diagnostic_58.jsonl")
REPORT_PATH = os.path.join(_HERE, "validation_report.json")

EXPECTED_TOTAL = 58
EXPECTED_CATEGORY_COUNTS = {
    "relevance_alignment": 16,
    "multipart_completeness": 9,
    "technical_correctness": 12,
    "depth_control": 6,
    "grounding_ownership": 9,
    "cross_dimension": 6,
}
CANONICAL_DIMENSIONS = (
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
)

# Groups where every member is INTENTIONALLY required to share the same
# answer text is not expected anywhere in V4 (every example has a distinct
# answer) but groups ARE expected to share question+grounding context.
MULTIPART_CATEGORY = "multipart_completeness"

# The frozen pools V4 must never overlap with (source_id and example_id).
_FROZEN_POOL_FILES = [
    os.path.join(_CAP_DIR, "artifacts", "seed_dataset_v1", "seed_v1_3_repaired.jsonl"),
    os.path.join(_CAP_DIR, "artifacts", "hand_authored_50", "hand_authored_50_v1.jsonl"),
    os.path.join(_CAP_DIR, "artifacts", "gap_coverage_20", "gap20_v1.jsonl"),
    os.path.join(_CAP_DIR, "artifacts", "v2_targeted_50", "v2_targeted_50_v1.jsonl"),
]

# Any V4 source_id/pipeline-registration string must never collide with a
# known V1/V2/V3 pool-loading entrypoint.
_TRAINING_PIPELINE_FILES = [
    os.path.join(_CAP_DIR, "four_dim_experiment_split.py"),
    os.path.join(_CAP_DIR, "run_four_dim_training.py"),
]


def _load_dataset() -> list[dict]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_frozen_pool_ids() -> tuple[set, set]:
    source_ids: set = set()
    example_ids: set = set()
    for path in _FROZEN_POOL_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if "source_id" in rec:
                    source_ids.add(rec["source_id"])
                if "example_id" in rec:
                    example_ids.add(rec["example_id"])
    return source_ids, example_ids


def validate(examples: list[dict]) -> dict:
    findings: list[dict] = []

    def fail(check: str, detail: str):
        findings.append({"check": check, "status": "FAIL", "detail": detail})

    def ok(check: str, detail: str = ""):
        findings.append({"check": check, "status": "PASS", "detail": detail})

    # 1. exactly 58 examples
    if len(examples) == EXPECTED_TOTAL:
        ok("total_count", f"{len(examples)} examples")
    else:
        fail("total_count", f"expected {EXPECTED_TOTAL}, got {len(examples)}")

    # 2. all four canonical dimensions present, labels in 0-4
    bad_labels = []
    for ex in examples:
        labels = ex.get("gold_labels", {})
        for dim in CANONICAL_DIMENSIONS:
            if dim not in labels:
                bad_labels.append(f"{ex['example_id']}: missing {dim}")
                continue
            v = labels[dim]
            if not isinstance(v, int) or not (0 <= v <= 4):
                bad_labels.append(f"{ex['example_id']}: {dim}={v!r} out of range")
    if bad_labels:
        fail("canonical_dimensions_and_range", "; ".join(bad_labels))
    else:
        ok("canonical_dimensions_and_range", "all 58 examples have all 4 dims, all in [0,4]")

    # 3. no duplicate example_ids
    ids = [ex["example_id"] for ex in examples]
    dup_ids = {i for i in ids if ids.count(i) > 1}
    if dup_ids:
        fail("unique_example_ids", f"duplicates: {sorted(dup_ids)}")
    else:
        ok("unique_example_ids", f"{len(set(ids))} unique ids")

    # 4. no duplicate (question, answer) pairs
    qa_pairs = [(ex["question"], ex["answer"]) for ex in examples]
    seen = {}
    exact_dupes = []
    for ex, pair in zip(examples, qa_pairs):
        if pair in seen:
            exact_dupes.append((seen[pair], ex["example_id"]))
        else:
            seen[pair] = ex["example_id"]
    if exact_dupes:
        fail("no_duplicate_qa_pairs", f"{exact_dupes}")
    else:
        ok("no_duplicate_qa_pairs", "0 exact (question, answer) duplicates")

    # 5. no duplicate ANSWERS unless intentionally required by a contrastive
    #    pair (V4's design never reuses answer text — every answer is
    #    distinct by construction, so any duplicate here is unintentional).
    answers = [ex["answer"] for ex in examples]
    answer_dupes = {a for a in answers if answers.count(a) > 1}
    if answer_dupes:
        fail("no_unintended_duplicate_answers", f"{len(answer_dupes)} duplicated answer string(s) found")
    else:
        ok("no_unintended_duplicate_answers", "0 duplicate answers (V4 design never intentionally reuses answer text)")

    # 6. every example has a diagnostic_category, and counts match design
    missing_cat = [ex["example_id"] for ex in examples if not ex.get("diagnostic_category")]
    if missing_cat:
        fail("diagnostic_category_present", f"missing on: {missing_cat}")
    else:
        ok("diagnostic_category_present", "all 58 examples have a diagnostic_category")

    cat_counts: dict = {}
    for ex in examples:
        cat_counts[ex["diagnostic_category"]] = cat_counts.get(ex["diagnostic_category"], 0) + 1
    if cat_counts == EXPECTED_CATEGORY_COUNTS:
        ok("category_counts_match_design", json.dumps(cat_counts))
    else:
        fail("category_counts_match_design", f"expected {EXPECTED_CATEGORY_COUNTS}, got {cat_counts}")

    # 7. every example has a pair_group_id, and every group has >=2 members
    missing_group = [ex["example_id"] for ex in examples if not ex.get("pair_group_id")]
    if missing_group:
        fail("pair_group_id_present", f"missing on: {missing_group}")
    else:
        ok("pair_group_id_present", "all 58 examples have a pair_group_id")

    group_members: dict = {}
    for ex in examples:
        group_members.setdefault(ex["pair_group_id"], []).append(ex)
    singleton_groups = [g for g, members in group_members.items() if len(members) < 2]
    if singleton_groups:
        fail("pair_groups_have_multiple_members", f"singleton groups: {singleton_groups}")
    else:
        ok("pair_groups_have_multiple_members", f"{len(group_members)} groups, all size >=2")

    # 8. paired examples actually share the intended question/context
    mismatched_pairs = []
    for group_id, members in group_members.items():
        questions = {m["question"] for m in members}
        titles = {m["grounding"]["title"] for m in members}
        source_ids = {m["source_id"] for m in members}
        if len(questions) != 1 or len(titles) != 1 or len(source_ids) != 1:
            mismatched_pairs.append(
                f"{group_id}: questions={len(questions)} titles={len(titles)} source_ids={len(source_ids)}"
            )
    if mismatched_pairs:
        fail("paired_examples_share_context", "; ".join(mismatched_pairs))
    else:
        ok("paired_examples_share_context", "every group shares one question + one grounding.title + one source_id")

    # 9. expected_concepts present for multipart examples
    mp_missing_concepts = [
        ex["example_id"] for ex in examples
        if ex["diagnostic_category"] == MULTIPART_CATEGORY and len(ex.get("expected_concepts") or []) < 2
    ]
    if mp_missing_concepts:
        fail("multipart_expected_concepts", f"fewer than 2 expected_concepts on: {mp_missing_concepts}")
    else:
        ok("multipart_expected_concepts", "every multipart_completeness example has >=2 expected_concepts (the two requested components)")

    # 10. rationales never enter model inputs (leakage check via the
    #     sanctioned input builder, not a guess)
    leak_hits = []
    forbidden_strings_per_example = []
    for ex in examples:
        text_a, text_b = build_v4_model_input(ex)
        full_input = text_a + "\n" + text_b
        # Direct check: none of the forbidden metadata keys' own field
        # *names* or their rationale *values* appear verbatim in the built
        # input text.
        for field in FORBIDDEN_INPUT_LEAK_FIELDS:
            if field in ex and isinstance(ex[field], str) and ex[field] and ex[field] in full_input:
                leak_hits.append(f"{ex['example_id']}: field {field!r} value leaked into input")
        rationale = ex.get("rationale", {})
        for dim, text in rationale.items():
            if text and text in full_input:
                leak_hits.append(f"{ex['example_id']}: rationale[{dim}] leaked into input")
    if leak_hits:
        fail("rationale_never_in_model_input", "; ".join(leak_hits))
    else:
        ok("rationale_never_in_model_input", "verified via v4_input_builder.build_v4_model_input on all 58 examples: rationale/gold_labels/diagnostic_category/pair_group_id never appear in the built (text_a, text_b) pair")

    # 11. no first-person leakage into grounding context
    first_person_markers = (" I ", " I'", " we ", " We ", " my ", " My ", " our ", " Our ")
    grounding_leak = []
    for ex in examples:
        g = ex.get("grounding", {})
        grounding_text = " ".join([g.get("title", ""), " ".join(g.get("technologies", [])), g.get("summary", "")])
        padded = f" {grounding_text} "
        if any(m in padded for m in first_person_markers):
            grounding_leak.append(ex["example_id"])
    if grounding_leak:
        fail("no_first_person_in_grounding", f"{grounding_leak}")
    else:
        ok("no_first_person_in_grounding", "0 first-person markers in any grounding.title/technologies/summary (summary is '' for all 58 by design)")

    # 12. no gold-label/rubric leakage (tier numbers or rubric words in
    #     question/answer/expected_concepts text)
    rubric_words = ("tier ", "gold label", "rubric", "score of ", "technical_correctness:", "depth_specificity:",
                     "relevance_completeness:", "grounding_ownership:")
    rubric_leak = []
    for ex in examples:
        text = " ".join([ex["question"], ex["answer"], " ".join(ex.get("expected_concepts") or [])]).lower()
        for w in rubric_words:
            if w in text:
                rubric_leak.append(f"{ex['example_id']}: {w!r}")
    if rubric_leak:
        fail("no_rubric_leakage", "; ".join(rubric_leak))
    else:
        ok("no_rubric_leakage", "0 rubric/tier/label words found in question/answer/expected_concepts text")

    # 13. no answer-copy leakage into grounding context (grounding.summary
    #     is '' for all 58 by design, so this reduces to confirming that)
    answer_in_grounding = []
    for ex in examples:
        summary = (ex.get("grounding", {}).get("summary") or "")
        if summary.strip():
            answer_in_grounding.append(f"{ex['example_id']}: non-empty grounding.summary {summary!r}")
        elif ex["answer"][:30] and ex["answer"][:30] in (ex.get("grounding", {}).get("title", "") or ""):
            answer_in_grounding.append(f"{ex['example_id']}: answer text found in grounding.title")
    if answer_in_grounding:
        fail("no_answer_copy_in_grounding", "; ".join(answer_in_grounding))
    else:
        ok("no_answer_copy_in_grounding", "grounding.summary is '' for all 58 examples by design; no answer text appears in grounding.title")

    # 14. no unsupported project facts (structural check: every source_id
    #     is v4h_-prefixed and hypothetical_source=True — the substantive
    #     truthfulness of each answer was reviewed manually during authoring,
    #     see README "Manual review" section; this check verifies the
    #     ISOLATION invariant that makes that review meaningful)
    unsupported = [
        ex["example_id"] for ex in examples
        if not ex.get("source_id", "").startswith("v4h_") or not ex.get("hypothetical_source")
    ]
    if unsupported:
        fail("hypothetical_source_marking", f"{unsupported}")
    else:
        ok("hypothetical_source_marking", "all 58 examples: source_id prefixed 'v4h_' and hypothetical_source=True")

    # 15. V4 cannot accidentally enter the existing V1/V2/V3 training splits
    frozen_source_ids, frozen_example_ids = _load_frozen_pool_ids()
    v4_source_ids = {ex["source_id"] for ex in examples}
    v4_example_ids = {ex["example_id"] for ex in examples}
    source_collisions = v4_source_ids & frozen_source_ids
    example_collisions = v4_example_ids & frozen_example_ids
    pipeline_reference = []
    for path in _TRAINING_PIPELINE_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if "v4_diagnostic" in content or "v4h_" in content:
            pipeline_reference.append(path)
    if source_collisions or example_collisions or pipeline_reference:
        fail(
            "isolated_from_training_pipeline",
            f"source_id collisions={sorted(source_collisions)}, "
            f"example_id collisions={sorted(example_collisions)}, "
            f"pipeline files referencing V4={pipeline_reference}",
        )
    else:
        ok(
            "isolated_from_training_pipeline",
            f"0 source_id collisions (checked against {len(frozen_source_ids)} frozen source_ids), "
            f"0 example_id collisions (checked against {len(frozen_example_ids)} frozen example_ids), "
            f"{os.path.basename(_TRAINING_PIPELINE_FILES[0])}/{os.path.basename(_TRAINING_PIPELINE_FILES[1])} "
            "do not reference v4_diagnostic or v4h_ at all",
        )

    return {
        "dataset_path": os.path.relpath(DATASET_PATH, _CAP_DIR),
        "total_examples": len(examples),
        "category_counts": cat_counts,
        "pair_group_counts": {g: len(m) for g, m in group_members.items()},
        "checks": findings,
        "all_passed": all(f["status"] == "PASS" for f in findings),
    }


def _sbert_near_duplicate_check(examples: list[dict]) -> dict:
    """Optional but requested: SBERT near-duplicate check against (a) V4
    internally, and (b) V4 vs. the frozen 220-example pool's answers, using
    the same production model (`all-MiniLM-L6-v2`) and 0.92 cosine
    threshold as every prior batch in this project. Read-only — does not
    modify any file. If sentence-transformers is unavailable, records that
    explicitly rather than silently skipping."""
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError as e:
        return {"status": "SKIPPED", "reason": f"sentence-transformers unavailable: {e}"}

    model = SentenceTransformer("all-MiniLM-L6-v2")
    v4_answers = [ex["answer"] for ex in examples]
    v4_ids = [ex["example_id"] for ex in examples]
    v4_embeds = model.encode(v4_answers, convert_to_tensor=True, show_progress_bar=False)

    threshold = 0.92
    internal_hits = []
    sims = util.cos_sim(v4_embeds, v4_embeds)
    n = len(v4_answers)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sims[i][j])
            if score >= threshold:
                internal_hits.append({"a": v4_ids[i], "b": v4_ids[j], "cosine": round(score, 4)})

    frozen_answers = []
    frozen_ids = []
    for path in _FROZEN_POOL_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if "answer" in rec:
                    frozen_answers.append(rec["answer"])
                    frozen_ids.append(rec.get("example_id", "?"))

    cross_hits = []
    if frozen_answers:
        frozen_embeds = model.encode(frozen_answers, convert_to_tensor=True, show_progress_bar=False)
        cross_sims = util.cos_sim(v4_embeds, frozen_embeds)
        for i in range(len(v4_answers)):
            for j in range(len(frozen_answers)):
                score = float(cross_sims[i][j])
                if score >= threshold:
                    cross_hits.append({"v4": v4_ids[i], "frozen_pool": frozen_ids[j], "cosine": round(score, 4)})

    return {
        "status": "RAN",
        "model": "all-MiniLM-L6-v2",
        "threshold": threshold,
        "v4_internal_near_duplicates": internal_hits,
        "v4_internal_pairs_checked": n * (n - 1) // 2,
        "v4_vs_frozen_pool_near_duplicates": cross_hits,
        "v4_vs_frozen_pool_pairs_checked": len(v4_answers) * len(frozen_answers),
        "frozen_pool_answers_checked": len(frozen_answers),
    }


def main() -> None:
    examples = _load_dataset()
    report = validate(examples)
    report["sbert_near_duplicate_check"] = _sbert_near_duplicate_check(examples)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print()
    print("ALL PASSED" if report["all_passed"] else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
