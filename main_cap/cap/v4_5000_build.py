"""
V4 5000-Example Dataset — Build Driver (assemble + validate + report).

Runnable orchestration over `v4_5000_dataset.py`'s harness. NO Gemini, no
network for generation/judging — it only assembles Claude-authored batches
that already exist on disk, merges the frozen 220, dedups, splits group-aware,
and writes every required report.

USAGE (resumable — add more batch_*.jsonl, re-run):
    python v4_5000_build.py status     # how many authored/accepted so far, gap to 5000
    python v4_5000_build.py assemble    # full assemble + all reports + artifacts
    python v4_5000_build.py assemble --no-semantic-dedup   # skip SBERT (fast, structural only)

TRAIN LATER (after the dataset is approved — NOT run here):
    the EXISTING architecture trains on this dataset by pointing
    run_overall_single_training.py at this pool/split (see the final report's
    "train command" section) — no model/architecture change.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

import glob

from dataset_filters import exact_qa_duplicate_indices
from four_dim_experiment_v2_split import load_v2_pool
from model_dataset import score_to_tier
from training_experimentation import split_dataset_by_group
from v4_5000_diversity import analyze as analyze_diversity
from v4_5000_dataset import (
    ARTIFACTS_DIR,
    BATCHES_DIR,
    DATASET_DIR,
    DATASET_VERSION,
    FINAL_SPLIT_RATIOS,
    FINAL_SPLIT_SEED,
    FROZEN_COUNT,
    PROV_FROZEN,
    REPORTS_DIR,
    SEMANTIC_DEDUP_THRESHOLD,
    TARGET_NEW,
    TARGET_TOTAL,
    IngestResult,
    load_all_batches,
    load_v4_identity,
    semantic_duplicate_pairs,
)
from evaluation_dimensions import CANONICAL_DIMENSIONS

_CANONICAL_KEYS = tuple(d.value for d in CANONICAL_DIMENSIONS)


def _overall_tier(example) -> int:
    return score_to_tier(example.labels.overall_label.score)


def read_raw_authored_records(batches_dir: str = BATCHES_DIR) -> list[dict]:
    """Raw authored batch dicts (as written), for the diversity monitor —
    separate from the TrainingExample ingest so diversity metadata fields
    (question_form/intent/humanization_style/project_family) are visible even
    though they are deliberately NOT threaded into the TrainingExample."""
    records: list[dict] = []
    if not os.path.isdir(batches_dir):
        return records
    for path in sorted(glob.glob(os.path.join(batches_dir, "batch_*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def _norm(s: str) -> str:
    return " ".join((s or "").split()).casefold()


@dataclass
class AssembledDataset:
    examples: list                       # list[TrainingExample], frozen first then authored
    provenance: dict                     # example_id -> category
    split: object                        # DatasetSplit
    reports: dict                        # name -> report dict
    exact_dropped: list                  # authored ids dropped as exact dups
    semantic_dropped: list               # authored ids dropped as semantic near-dups


def assemble(
    *, semantic_dedup: bool = True, embed_fn: Optional[Callable[[list[str]], object]] = None,
) -> AssembledDataset:
    # 1. frozen 220 (unchanged, included, provenance = frozen_hand_authored)
    frozen = list(load_v2_pool())
    frozen_ids = [e.metadata.example_id for e in frozen]

    # 2. Claude-authored accepted examples (resumable ingest of all batches)
    ingest: IngestResult = load_all_batches(BATCHES_DIR)
    authored = list(ingest.accepted)

    # 3. exact (question, answer) dedup — frozen first so frozen is always kept
    combined = frozen + authored
    pairs = [(_norm(e.inputs.question_text), _norm(e.inputs.answer_text)) for e in combined]
    dup_idx = set(exact_qa_duplicate_indices(pairs))
    exact_dropped_ids = [combined[i].metadata.example_id for i in sorted(dup_idx)]
    survivors = [e for i, e in enumerate(combined) if i not in dup_idx]

    # 4. semantic near-dup dedup (authored only ever dropped; frozen kept)
    semantic_dropped_ids: list[str] = []
    if semantic_dedup:
        answers = [e.inputs.answer_text for e in survivors]
        hits = semantic_duplicate_pairs(answers, threshold=SEMANTIC_DEDUP_THRESHOLD, embed_fn=embed_fn)
        frozen_id_set = set(frozen_ids)
        drop: set[int] = set()
        for i, j, _s in hits:
            # drop the later index unless it's frozen; never drop a frozen example
            later = j if survivors[j].metadata.example_id not in frozen_id_set else i
            if survivors[later].metadata.example_id in frozen_id_set:
                continue  # both frozen (shouldn't happen) — leave alone
            drop.add(later)
        semantic_dropped_ids = [survivors[i].metadata.example_id for i in sorted(drop)]
        survivors = [e for i, e in enumerate(survivors) if i not in drop]

    # 5. provenance map for survivors
    provenance = {eid: PROV_FROZEN for eid in frozen_ids}
    provenance.update(ingest.provenance)
    provenance = {e.metadata.example_id: provenance[e.metadata.example_id] for e in survivors}

    # 6. group-aware split over ALL survivors (keeps every source_id group whole)
    group_of = {e.metadata.example_id: e.inputs.specification.source_id for e in survivors}
    example_ids = tuple(group_of.keys())
    split = split_dataset_by_group(example_ids, group_of, FINAL_SPLIT_RATIOS, FINAL_SPLIT_SEED)

    reports = _build_reports(
        survivors, provenance, split, ingest, frozen, exact_dropped_ids, semantic_dropped_ids, semantic_dedup,
    )
    # Diversity monitor over RAW authored records (steering only; never rejects).
    raw_authored = read_raw_authored_records(BATCHES_DIR)
    div = analyze_diversity(raw_authored)
    reports["diversity"] = {
        "authored_count": div.authored_count,
        "frequencies": div.frequencies,
        "warnings": div.warnings,
    }
    return AssembledDataset(
        examples=survivors, provenance=provenance, split=split, reports=reports,
        exact_dropped=exact_dropped_ids, semantic_dropped=semantic_dropped_ids,
    )


# ── reports ──────────────────────────────────────────────────────────────────

def _split_of(split) -> dict:
    m = {}
    for s in split.train_ids:
        m[s] = "train"
    for s in split.val_ids:
        m[s] = "val"
    for s in split.test_ids:
        m[s] = "test"
    return m


def _tier_dist(examples) -> dict:
    c = Counter(_overall_tier(e) for e in examples)
    return {t: c.get(t, 0) for t in range(5)}


def _build_reports(survivors, provenance, split, ingest, frozen, exact_dropped, semantic_dropped, semantic_dedup) -> dict:
    reports: dict = {}
    by_id = {e.metadata.example_id: e for e in survivors}
    split_of = _split_of(split)

    # ---- validation ----
    reject_reason_hist: Counter = Counter()
    for _rid, reasons in ingest.rejected:
        for r in reasons:
            reject_reason_hist[r.split(":")[0]] += 1
    reports["validation"] = {
        "authored_records_accepted": len(ingest.accepted),
        "authored_records_rejected": len(ingest.rejected),
        "rejection_reason_histogram": dict(reject_reason_hist),
        "rejected_ids_sample": [rid for rid, _ in ingest.rejected[:20]],
    }

    # ---- dedup ----
    reports["dedup"] = {
        "exact_qa_duplicates_dropped": len(exact_dropped),
        "exact_dropped_ids_sample": exact_dropped[:20],
        "semantic_dedup_ran": semantic_dedup,
        "semantic_threshold": SEMANTIC_DEDUP_THRESHOLD,
        "semantic_near_duplicates_dropped": len(semantic_dropped),
        "semantic_dropped_ids_sample": semantic_dropped[:20],
    }

    # ---- counts / totals ----
    prov_counts = Counter(provenance.values())
    total = len(survivors)
    reports["counts"] = {
        "total": total,
        "target_total": TARGET_TOTAL,
        "gap_to_target": max(0, TARGET_TOTAL - total),
        "frozen": prov_counts.get(PROV_FROZEN, 0),
        "provenance": dict(prov_counts),
        "provenance_pct": {k: round(100 * v / total, 2) for k, v in prov_counts.items()} if total else {},
        "split_counts": {"train": len(split.train_ids), "val": len(split.val_ids), "test": len(split.test_ids)},
    }

    # ---- group diversity ----
    groups = Counter(e.inputs.specification.source_id for e in survivors)
    per_group = list(groups.values())
    reports["groups"] = {
        "unique_questions": len({_norm(e.inputs.question_text) for e in survivors}),
        "unique_contexts": len({_norm(e.inputs.specification.grounding.project.summary + " " + e.inputs.specification.grounding.project.title) for e in survivors if e.inputs.specification.grounding.project}),
        "unique_candidate_or_source_groups": len(groups),
        "examples_per_group_min": min(per_group) if per_group else 0,
        "examples_per_group_max": max(per_group) if per_group else 0,
        "examples_per_group_mean": round(sum(per_group) / len(per_group), 2) if per_group else 0,
    }

    # ---- label distributions ----
    def _perdim_dist(examples) -> dict:
        d = {k: {t: 0 for t in range(5)} for k in _CANONICAL_KEYS}
        for e in examples:
            for dl in e.labels.dimension_labels:
                if dl.name in d:
                    d[dl.name][round(dl.score * 4)] += 1
        return d

    humanized = [by_id[i] for i, c in provenance.items() if c == "humanized_claude_authored" and i in by_id]
    synthetic = [by_id[i] for i, c in provenance.items() if c == "synthetic_claude_authored" and i in by_id]
    frozen_present = [e for e in survivors if provenance.get(e.metadata.example_id) == PROV_FROZEN]
    reports["label_distribution"] = {
        "overall_tier_all": _tier_dist(survivors),
        "overall_tier_by_split": {
            "train": _tier_dist([e for e in survivors if split_of.get(e.metadata.example_id) == "train"]),
            "val": _tier_dist([e for e in survivors if split_of.get(e.metadata.example_id) == "val"]),
            "test": _tier_dist([e for e in survivors if split_of.get(e.metadata.example_id) == "test"]),
        },
        "overall_tier_frozen": _tier_dist(frozen_present),
        "overall_tier_synthetic": _tier_dist(synthetic),
        "overall_tier_humanized": _tier_dist(humanized),
        "per_dimension_tier_all": _perdim_dist(survivors),
    }

    # ---- humanized subset ----
    reports["humanized"] = {
        "count": len(humanized),
        "pct_of_total": round(100 * len(humanized) / total, 2) if total else 0,
        "score_distribution": _tier_dist(humanized),
        "spans_all_tiers": all(_tier_dist(humanized).get(t, 0) > 0 for t in range(5)) if humanized else False,
    }

    # ---- leakage ----
    def _cross_split_leak(key_fn, label) -> dict:
        spans: dict = {}
        for e in survivors:
            spl = split_of.get(e.metadata.example_id)
            if spl is None:
                continue
            spans.setdefault(key_fn(e), set()).add(spl)
        leaked = [k for k, spls in spans.items() if len(spls) > 1]
        return {"label": label, "leaked_count": len(leaked), "clean": len(leaked) == 0}

    v4 = load_v4_identity()
    survivor_ids = set(by_id.keys())
    survivor_sources = {e.inputs.specification.source_id for e in survivors}
    survivor_qa = {(_norm(e.inputs.question_text), _norm(e.inputs.answer_text)) for e in survivors}
    reports["leakage"] = {
        "cross_split_source_ids": _cross_split_leak(lambda e: e.inputs.specification.source_id, "source_ids"),
        "cross_split_questions": _cross_split_leak(lambda e: _norm(e.inputs.question_text), "questions"),
        "cross_split_answers": _cross_split_leak(lambda e: _norm(e.inputs.answer_text), "answers"),
        "cross_split_qa": _cross_split_leak(lambda e: (_norm(e.inputs.question_text), _norm(e.inputs.answer_text)), "question+answer"),
        "v4_found": v4["found"],
        "v4_example_id_overlap": sorted(survivor_ids & v4["example_ids"]),
        "v4_source_id_overlap": sorted(survivor_sources & v4["source_ids"]),
        "v4_qa_overlap_count": len(survivor_qa & v4["qa"]),
    }

    # ---- frozen-220 preservation ----
    frozen_ids_now = {e.metadata.example_id for e in frozen}
    present = frozen_ids_now & survivor_ids
    reports["frozen_preservation"] = {
        "frozen_expected": FROZEN_COUNT,
        "frozen_loaded": len(frozen),
        "frozen_present_in_final": len(present),
        "all_frozen_present": len(present) == len(frozen) == FROZEN_COUNT,
    }

    # ---- expected-concepts validity ----
    from dataset_filters import find_banned_phrases
    ec_leaks = sum(1 for e in survivors if find_banned_phrases(" ".join(e.inputs.expected_concepts)))
    reports["expected_concepts"] = {
        "examples_with_expected_concepts": sum(1 for e in survivors if e.inputs.expected_concepts),
        "expected_concepts_with_banned_quality_phrase": ec_leaks,
        "clean": ec_leaks == 0,
    }

    return reports


# ── samples for manual inspection ────────────────────────────────────────────

def build_samples_markdown(assembled: AssembledDataset, per_tier: int = 2) -> str:
    by_tier: dict[int, list] = {t: [] for t in range(5)}
    for e in assembled.examples:
        by_tier[_overall_tier(e)].append(e)
    lines = [f"# {DATASET_VERSION} — Representative Samples\n"]
    for t in range(5):
        lines.append(f"\n## Overall tier {t}\n")
        for e in by_tier[t][:per_tier]:
            lines.append(_sample_block(e, assembled.provenance.get(e.metadata.example_id, "?")))
    # humanized samples spanning tiers
    lines.append("\n## Humanized subset samples\n")
    hum = [e for e in assembled.examples if assembled.provenance.get(e.metadata.example_id) == "humanized_claude_authored"]
    shown_tiers = set()
    for e in hum:
        t = _overall_tier(e)
        if t in shown_tiers:
            continue
        shown_tiers.add(t)
        lines.append(_sample_block(e, "humanized_claude_authored"))
    return "\n".join(lines)


def _sample_block(e, provenance: str) -> str:
    dims = {dl.name: round(dl.score * 4) for dl in e.labels.dimension_labels}
    proj = e.inputs.specification.grounding.project
    return (
        f"**{e.metadata.example_id}** · provenance={provenance} · overall_tier={_overall_tier(e)} "
        f"(score={e.labels.overall_label.score})\n\n"
        f"- **Context:** {proj.title if proj else '?'} — {(proj.summary if proj else '')[:120]}\n"
        f"- **Tech:** {', '.join(proj.technologies) if proj else ''}\n"
        f"- **Q ({e.inputs.reasoning_type.value}):** {e.inputs.question_text}\n"
        f"- **Expected concepts:** {', '.join(e.inputs.expected_concepts)}\n"
        f"- **A:** {e.inputs.answer_text}\n"
        f"- **Dim tiers:** {dims}\n"
    )


# ── persistence ──────────────────────────────────────────────────────────────

def write_artifacts(assembled: AssembledDataset) -> dict:
    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    ex_path = os.path.join(DATASET_DIR, "examples.jsonl")
    with open(ex_path, "w", encoding="utf-8") as f:
        for e in assembled.examples:
            f.write(e.model_dump_json() + "\n")

    split_path = os.path.join(DATASET_DIR, "split.json")
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump({
            "train_ids": list(assembled.split.train_ids),
            "val_ids": list(assembled.split.val_ids),
            "test_ids": list(assembled.split.test_ids),
            "ratios": FINAL_SPLIT_RATIOS, "seed": FINAL_SPLIT_SEED,
        }, f, indent=2)

    prov_path = os.path.join(DATASET_DIR, "provenance.jsonl")
    with open(prov_path, "w", encoding="utf-8") as f:
        for eid, cat in assembled.provenance.items():
            f.write(json.dumps({"example_id": eid, "provenance": cat}) + "\n")

    for name, rep in assembled.reports.items():
        with open(os.path.join(REPORTS_DIR, f"{name}_report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)

    with open(os.path.join(REPORTS_DIR, "samples.md"), "w", encoding="utf-8") as f:
        f.write(build_samples_markdown(assembled))

    manifest = {
        "dataset_version": DATASET_VERSION,
        "total_examples": len(assembled.examples),
        "target_total": TARGET_TOTAL,
        "split_counts": assembled.reports["counts"]["split_counts"],
        "provenance": assembled.reports["counts"]["provenance"],
        "overall_target_policy": "equal-weight mean of four canonical dimension tiers -> score_to_tier (existing policy, unchanged)",
        "generation": "Claude-authored, no Gemini/LLM API",
        "semantic_dedup_threshold": SEMANTIC_DEDUP_THRESHOLD,
    }
    with open(os.path.join(DATASET_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {"examples": ex_path, "split": split_path, "provenance": prov_path, "manifest": os.path.join(DATASET_DIR, "manifest.json")}


# ── CLI ──────────────────────────────────────────────────────────────────────

def _status() -> int:
    ingest = load_all_batches(BATCHES_DIR)
    accepted = len(ingest.accepted)
    print(f"[{DATASET_VERSION}] authored accepted so far: {accepted} / target new {TARGET_NEW} "
          f"(total with frozen 220 would be {accepted + FROZEN_COUNT} / {TARGET_TOTAL})")
    print(f"rejected authored records: {len(ingest.rejected)}")
    print(f"remaining valid authored examples needed: {max(0, TARGET_NEW - accepted)}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] not in ("assemble", "status"):
        print("Usage: python v4_5000_build.py [assemble|status] [--no-semantic-dedup]", file=sys.stderr)
        return 2
    if args[0] == "status":
        return _status()
    semantic = "--no-semantic-dedup" not in args
    assembled = assemble(semantic_dedup=semantic)
    paths = write_artifacts(assembled)
    print(json.dumps({
        "total": len(assembled.examples),
        "split_counts": assembled.reports["counts"]["split_counts"],
        "provenance": assembled.reports["counts"]["provenance"],
        "leakage_clean": all(
            assembled.reports["leakage"][k]["clean"]
            for k in ("cross_split_source_ids", "cross_split_questions", "cross_split_answers", "cross_split_qa")
        ) and not assembled.reports["leakage"]["v4_example_id_overlap"]
          and not assembled.reports["leakage"]["v4_source_id_overlap"],
        "frozen_preserved": assembled.reports["frozen_preservation"]["all_frozen_present"],
        "artifacts": paths,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
