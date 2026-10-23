"""
Evaluator benchmark — how well each answer evaluator agrees with reference labels.

Item sources (all optional, combined, reported per source):
  * stress_set.json                 Claude-authored contrastive set (committable)
  * private/human_items.jsonl       real answers with HUMAN labels (gitignored;
                                    produced by collect_answers.py + label_answers.py)
  * --predictions-only file         extra judge scores to compare against, e.g. an
                                    LLM-as-judge baseline: {"<item_id>": score_0_to_1}

Metrics (labels are 0-4 tiers; evaluator scores are 0-1):
  pairwise   fraction of same-question answer pairs with different labels that the
             evaluator orders the same way (the most robust metric - no calibration needed)
  spearman   rank correlation with labels over all items
  qwk        quadratic-weighted kappa after binning score into 5 tiers (calibration)
  mae        mean |tier(score) - label|
  len_rho    Spearman(answer length, score) - should be close to len_rho of the LABELS;
             much higher means the evaluator is rewarding length

Usage (from main_cap/cap):
    py -3.13 benchmarks/evaluator/score_evaluator.py                  # all evaluators
    py -3.13 benchmarks/evaluator/score_evaluator.py --only evidence  # skip slow DeBERTa
    py -3.13 benchmarks/evaluator/score_evaluator.py --by-kind        # mean score per answer kind
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE.parents[1]
sys.path.insert(0, str(CAP))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest  # noqa: E402
from question_families import ReasoningType  # noqa: E402
from question_specification import (  # noqa: E402
    Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType,
)

STRESS_SET = HERE / "stress_set.json"
HOLDOUT_SET = HERE / "stress_set_holdout.json"
DEV_SET = HERE / "dev_set.json"   # the only set to tune on; the others are test sets
# Realistic answers on the real benchmark resumes' projects (private: real people's projects),
# labelled by two independent annotators: claude_a in the file, claude_b in LABELS_B.
RESUME_SET = HERE / "private" / "resume_set_v1.json"
RESUME_SET_LABELS_B = HERE / "private" / "resume_set_v1_labels_b.json"
HUMAN_ITEMS = HERE / "private" / "human_items.jsonl"


# ------------------------------------------------------------------ items

def load_stress_items() -> list[dict]:
    items = (_load_contrastive(DEV_SET, "dev(claude)") + _load_contrastive(STRESS_SET, "stress(claude)")
             + _load_contrastive(HOLDOUT_SET, "holdout(claude)"))
    resume_items = _load_contrastive(RESUME_SET, "resume-real(2 annotators)")
    if resume_items and RESUME_SET_LABELS_B.exists():
        labels_b = json.loads(RESUME_SET_LABELS_B.read_text(encoding="utf-8"))
        for it in resume_items:
            if it["item_id"] in labels_b:
                it["label_a"], it["label_b"] = it["label"], labels_b[it["item_id"]]
                it["label"] = (it["label_a"] + it["label_b"]) / 2
    return items + resume_items


def _load_contrastive(path: Path, source: str) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for q in data["items"]:
        g = data["groundings"][q["grounding"]]
        for i, a in enumerate(q["answers"]):
            items.append({
                "item_id": f"{q['id']}_{i}_{a['kind']}", "source": source, "question_id": q["id"],
                "grounding": g, "question": q["question"], "reasoning_type": q["reasoning_type"],
                "answer": a["answer"], "label": a["tier"], "kind": a["kind"],
            })
    return items


def load_human_items() -> list[dict]:
    """Rows written by label_answers.py; label = mean of annotators' tiers."""
    if not HUMAN_ITEMS.exists():
        return []
    items = []
    for line in HUMAN_ITEMS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        labels = row.get("labels") or []
        if not labels:
            continue
        row["label"] = sum(l["tier"] for l in labels) / len(labels)
        row.setdefault("source", "human")
        row.setdefault("kind", "real")
        items.append(row)
    return items


def build_request(item: dict) -> EvaluationRequest:
    g = item["grounding"]
    project = ProjectGrounding(title=g["title"], summary=g.get("summary", ""),
                               technologies=tuple(g.get("technologies", ())), concepts=tuple(g.get("concepts", ())))
    spec = QuestionSpecification(
        id=item["question_id"], category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=g["title"],
        grounding=Grounding(project=project), source_type=SourceType.PROJECT, source_id=g["title"],
        source_field="interview_seeds", reason="benchmark",
    )
    return EvaluationRequest(
        request_id=f"bench_{item['item_id']}", requested_at="2026-10-23T00:00:00+00:00",
        specification=spec, question_text=item["question"], reasoning_type=ReasoningType(item["reasoning_type"]),
        answer_text=item["answer"],
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
    )


# ------------------------------------------------------------- evaluators

def load_evaluators(only: set[str] | None, factcheck: bool = False) -> dict:
    from heuristic_evaluator import HeuristicEvaluator
    from resume_evidence_evaluator import ResumeEvidenceEvaluator
    evs = {}
    if not only or "heuristic" in only:
        evs["heuristic"] = HeuristicEvaluator()
    if not only or "v5" in only:
        evs["v5_1088"] = _load_v5_averaged()
    if not only or "evidence" in only:
        evs["evidence v1"] = ResumeEvidenceEvaluator(scoring="v1")
        evs["evidence v2"] = ResumeEvidenceEvaluator(scoring="v2")
        if factcheck:
            from fact_checker import OllamaFactChecker
            evs["evidence v2 + factcheck"] = ResumeEvidenceEvaluator(scoring="v2", fact_checker=OllamaFactChecker())
    return evs


def _load_v5_averaged():
    """Same construction deployment_evaluator.py uses, without touching the registry."""
    from averaged_evaluator import AveragedEvaluator
    from experiment_dataset_io import load_json
    from heuristic_evaluator import HeuristicEvaluator
    from model_backbone import BackboneConfig, build_tokenizer
    from overall_score_model import load_overall_checkpoint_artifact
    from overall_single_evaluator import OverallSingleEvaluator
    from training_experimentation import Checkpoint

    d = CAP / "deployed_model_overall_single_v5_1088"
    checkpoint = load_json(Checkpoint, str(d / "best_checkpoint.json"))
    cfg = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256)
    model = load_overall_checkpoint_artifact(str(d / "best_checkpoint_weights.pt"), cfg)
    return AveragedEvaluator(HeuristicEvaluator(), OverallSingleEvaluator(checkpoint, model, build_tokenizer(cfg), cfg))


# ---------------------------------------------------------------- metrics

def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    return ranks


def spearman(a, b) -> float:
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def to_tier(score: float) -> int:
    return max(0, min(4, int(score * 5)))


def qwk(a: list[int], b: list[int], k: int = 5) -> float:
    o = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        o[x][y] += 1
    n = len(a)
    ha = [sum(r) for r in o]
    hb = [sum(o[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * o[i][j]
            den += w * ha[i] * hb[j] / n
    return 1 - num / den if den else float("nan")


def pairwise(items, scores) -> tuple[int, int]:
    by_q = defaultdict(list)
    for it, s in zip(items, scores):
        by_q[it["question_id"]].append((it["label"], s))
    agree = total = 0
    for rows in by_q.values():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                (li, si), (lj, sj) = rows[i], rows[j]
                if li == lj:
                    continue
                total += 1
                agree += (si - sj) * (li - lj) > 0
    return agree, total


def report(items, scores_by_ev: dict, by_kind: bool) -> str:
    if len(items) < 5:
        return f"only {len(items)} labelled items - label more before reading any metric"
    labels = [it["label"] for it in items]
    both = [it for it in items if "label_b" in it]
    if both:
        a, b = [it["label_a"] for it in both], [it["label_b"] for it in both]
        exact = sum(x == y for x, y in zip(a, b)) / len(both)
        within1 = sum(abs(x - y) <= 1 for x, y in zip(a, b)) / len(both)
        agree = (f"annotator A vs B: n={len(both)} spearman {spearman(a, b):+.2f} qwk {qwk(a, b):.2f} "
                 f"exact {exact:.0%} within-1 {within1:.0%}   (label = mean of A and B)\n")
    else:
        agree = ""
    lengths = [len(it["answer"].split()) for it in items]
    out = [agree + f"n={len(items)}  questions={len({it['question_id'] for it in items})}  "
           f"label-vs-length rho={spearman(lengths, labels):+.2f}", "",
           "| evaluator | pairwise | spearman | qwk | mae (tiers) | len_rho |", "|---|---|---|---|---|---|"]
    for name, scores in scores_by_ev.items():
        a, t = pairwise(items, scores)
        tiers = [to_tier(s) for s in scores]
        mae = sum(abs(x - y) for x, y in zip(tiers, labels)) / len(items)
        pw = f"{a}/{t} = {a / t:.0%}" if t else "n/a"
        out.append(f"| {name} | {pw} | {spearman(scores, labels):+.2f} | "
                   f"{qwk(tiers, [round(l) for l in labels]):.2f} | {mae:.2f} | {spearman(lengths, scores):+.2f} |")
    if by_kind:
        kinds = sorted({it["kind"] for it in items}, key=lambda k: -sum(it["label"] for it in items if it["kind"] == k))
        out += ["", "Mean score (0-100) by answer kind:", "",
                "| kind | label | " + " | ".join(scores_by_ev) + " |", "|---|---|" + "---|" * len(scores_by_ev)]
        for k in kinds:
            idx = [i for i, it in enumerate(items) if it["kind"] == k]
            lab = sum(labels[i] for i in idx) / len(idx)
            cells = [f"{100 * sum(s[i] for i in idx) / len(idx):.0f}" for s in scores_by_ev.values()]
            out.append(f"| {k} | {lab:.1f} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma list of: heuristic,v5,evidence")
    ap.add_argument("--judge", action="append", default=[],
                    help="extra precomputed scores, NAME=path.json mapping item_id -> 0..1 (e.g. an LLM judge)")
    ap.add_argument("--by-kind", action="store_true")
    ap.add_argument("--factcheck", action="store_true", help="also run v2 with the local Ollama fact checker")
    ap.add_argument("--questions", help="comma list of question ids to keep (e.g. a dev/held-out split)")
    ap.add_argument("--dump", help="write per-item scores to this JSON")
    args = ap.parse_args()

    items = load_stress_items() + load_human_items()
    if args.questions:
        keep = set(args.questions.split(","))
        items = [it for it in items if it["question_id"] in keep]
    evaluators = load_evaluators(set(args.only.split(",")) if args.only else None, args.factcheck)
    scores_by_ev = {}
    for name, ev in evaluators.items():
        scores_by_ev[name] = [ev.evaluate(build_request(it)).overall_score for it in items]
    for spec in args.judge:
        name, path = spec.split("=", 1)
        judged = json.loads(Path(path).read_text(encoding="utf-8"))
        scores_by_ev[name] = [float(judged.get(it["item_id"], float("nan"))) for it in items]

    for source in sorted({it["source"] for it in items}):
        idx = [i for i, it in enumerate(items) if it["source"] == source]
        sub = [items[i] for i in idx]
        print(f"\n## {source}\n")
        print(report(sub, {n: [s[i] for i in idx] for n, s in scores_by_ev.items()}, args.by_kind))

    if args.dump:
        Path(args.dump).write_text(json.dumps(
            [{**{k: it[k] for k in ("item_id", "kind", "label")}, **{n: round(s[i], 3) for n, s in scores_by_ev.items()}}
             for i, it in enumerate(items)], indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
