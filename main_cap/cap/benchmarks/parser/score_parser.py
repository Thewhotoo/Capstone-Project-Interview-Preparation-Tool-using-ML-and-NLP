"""
Parser benchmark — field-level accuracy of a resume parser against hand-labelled gold.

Scores any parser that emits the public CandidateProfile shape
(candidate_name / contact_details / education / experience / projects /
skills / certifications). Two ways to get predictions:

  * live:   runs the deployed engine (`generate_candidate_profile_via_engine`)
  * file:   --predictions preds.json  ({"<gold file key>": <profile>, ...}) —
            used for baselines (e.g. an LLM's output on the same resumes)

Usage (from main_cap/cap, with the Python that has the engine deps):
    py -3.13 benchmarks/parser/score_parser.py
    py -3.13 benchmarks/parser/score_parser.py --predictions llm_preds.json --label llm
    py -3.13 benchmarks/parser/score_parser.py --save-predictions engine_preds.json

Resume files are resolved against $PARSER_BENCH_ROOT (default ~/Downloads).
Gold: gold_templates.json (fictional, committable) + private/gold_real.json
(real people, gitignored) when present.

Matching is deliberately independent of the engine's own normalisers so the
benchmark can't share the parser's blind spots.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
GOLD_FILES = [HERE / "gold_templates.json", HERE / "private" / "gold_real.json"]
ENTITY_MATCH_THRESHOLD = 85
CURRENT_YEAR = 2026

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_PRESENT = re.compile(r"\b(present|current|now|ongoing|till date|today)\b", re.I)


# ----------------------------------------------------------------- normalising

def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[–—‒−|]", " - ", text)
    text = re.sub(r"[^\w+#./& -]", " ", text)
    return " ".join(text.split())


def norm_skill(text: str) -> str:
    t = norm(text)
    t = re.sub(r"\.js$|\s+js$", "", t)
    t = re.sub(r"^(html|css)\d$", r"\1", t)
    t = {"ms powerbi": "powerbi", "power bi": "powerbi", "huggingface": "hugging face",
         "vscode": "vs code", "sse": "server-sent events"}.get(t, t)
    return t.strip()


def phone_digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")[-10:]


def parse_date_point(text: str) -> str:
    """'Jun 2025' -> '2025-06'; '2025' -> '2025'; 'Present' -> 'present'; '17-7-2024' -> '2024-07'."""
    text = (text or "").strip()
    if not text:
        return ""
    if _PRESENT.search(text):
        return "present"
    m = re.search(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})", text)  # d-m-yyyy
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})[./-](\d{4})", text)                        # mm.yyyy
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    year = re.search(r"(19|20)\d{2}", text)
    mon = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", text, re.I)
    if year and mon:
        return f"{year.group(0)}-{_MONTHS[mon.group(1).lower()[:3]]:02d}"
    return year.group(0) if year else ""


def split_duration(duration: str) -> tuple[str, str]:
    if re.search(r"\s+to\s+", duration or "", re.I):      # '17 - 7 - 2024 to 2 - 8 - 2024'
        a, b = re.split(r"\s+to\s+", duration, maxsplit=1, flags=re.I)
        return parse_date_point(a), parse_date_point(b)
    parts = re.split(r"\s+(?:-|to|–|—)\s+|\s*[–—]\s*|(?<=\d)\s*-\s*(?=[A-Za-z]|\d{4})", duration or "", maxsplit=1)
    if len(parts) == 2:
        return parse_date_point(parts[0]), parse_date_point(parts[1])
    point = parse_date_point(duration)
    return "", point


def date_equal(gold: str, pred: str) -> bool:
    """Compare at the gold's precision (a gold '2025' accepts any 2025 month)."""
    if not gold:
        return True
    if gold == "present" and re.fullmatch(r"\d{4}(-\d{2})?", pred or ""):
        return int(pred[:4]) >= CURRENT_YEAR     # an expected-graduation year for an ongoing degree
    return bool(pred) and pred[: len(gold)] == gold


# ------------------------------------------------------------------- matching

def greedy_match(gold: list, pred: list, key_g, key_p) -> list[tuple[int, int]]:
    scored = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(pred):
            s = fuzz.token_set_ratio(norm(key_g(g)), norm(key_p(p)))
            if s >= ENTITY_MATCH_THRESHOLD:
                scored.append((s, gi, pi))
    pairs, used_g, used_p = [], set(), set()
    for _s, gi, pi in sorted(scored, reverse=True):
        if gi not in used_g and pi not in used_p:
            pairs.append((gi, pi)); used_g.add(gi); used_p.add(pi)
    return pairs


class Counter:
    def __init__(self):
        self.tp = self.fp = self.fn = 0

    def add(self, tp, n_gold, n_pred):
        self.tp += tp; self.fn += n_gold - tp; self.fp += n_pred - tp

    def prf(self):
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else (1.0 if not self.fn else 0.0)
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return p, r, f


class Acc:
    def __init__(self):
        self.ok = self.n = 0

    def add(self, ok: bool):
        self.n += 1; self.ok += int(ok)

    def value(self):
        return self.ok / self.n if self.n else float("nan")


def set_match(gold: list[str], pred: list[str], fn=norm_skill, threshold=92) -> int:
    g = [fn(x) for x in gold if fn(x)]
    p = [fn(x) for x in pred if fn(x)]
    used, tp = set(), 0
    for gi in g:
        best = max(((fuzz.ratio(gi, pj), j) for j, pj in enumerate(p) if j not in used), default=(0, -1))
        if best[0] >= threshold:
            used.add(best[1]); tp += 1
    return tp


# -------------------------------------------------------------------- scoring

FIELDS_PRF = ["education", "experience", "projects", "certifications", "skills", "project_tech"]
FIELDS_ACC = ["name", "email", "phone", "exp_role", "exp_dates", "edu_end"]


def _as_list(x):
    return x if isinstance(x, list) else []


def _cert_text(c):
    return c if isinstance(c, str) else (c.get("name") or c.get("title") or "") if isinstance(c, dict) else str(c)


def score_one(gold: dict, pred: dict, prf: dict, acc: dict, errors: list):
    pred = pred or {}
    contact = pred.get("contact_details") or {}
    f = gold["file"]

    ok = fuzz.token_sort_ratio(norm(gold["name"]), norm(pred.get("candidate_name", ""))) >= 90
    acc["name"].add(ok); ok or errors.append(f"{f}: name {pred.get('candidate_name')!r} != {gold['name']!r}")
    ok = norm(gold["email"]) == norm(contact.get("email", ""))
    acc["email"].add(ok); ok or errors.append(f"{f}: email {contact.get('email')!r} != {gold['email']!r}")
    if gold.get("phone"):
        ok = phone_digits(gold["phone"]) == phone_digits(contact.get("phone", ""))
        acc["phone"].add(ok); ok or errors.append(f"{f}: phone {contact.get('phone')!r} != {gold['phone']!r}")

    # education — matched on institution + degree text
    # school-level entries are suppressed by design when a degree exists (education_parser.py),
    # so only degree-level education is scored
    g_edu = [e for e in gold["education"] if not e.get("secondary")]
    p_edu = _as_list(pred.get("education"))
    key_g = lambda e: f"{e['institution']} {e['degree']}"
    key_p = lambda e: f"{e.get('institution', '')} {e.get('degree', '')} {e.get('major', '')}"
    pairs = greedy_match(g_edu, p_edu, key_g, key_p)
    prf["education"].add(len(pairs), len(g_edu), len(p_edu))
    for gi, pi in pairs:
        if g_edu[gi].get("end"):
            ok = date_equal(g_edu[gi]["end"][:4] if g_edu[gi]["end"] != "present" else "present",
                            parse_date_point(str(p_edu[pi].get("graduation_year", ""))))
            acc["edu_end"].add(ok)
    _log_unmatched(errors, f, "education", g_edu, pairs, key_g)

    # experience — matched on company
    g_exp, p_exp = gold["experience"], _as_list(pred.get("experience"))
    pairs = greedy_match(g_exp, p_exp, lambda e: e["company"], lambda e: e.get("company", ""))
    prf["experience"].add(len(pairs), len(g_exp), len(p_exp))
    for gi, pi in pairs:
        ge, pe = g_exp[gi], p_exp[pi]
        ok = (not ge["role"] and not pe.get("role")) or (
            bool(ge["role"]) and fuzz.token_set_ratio(norm(ge["role"]), norm(pe.get("role", ""))) >= 85)
        acc["exp_role"].add(ok)
        ok or errors.append(f"{f}: role at {ge['company']!r}: {pe.get('role')!r} != {ge['role']!r}")
        s, e = split_duration(pe.get("duration", ""))
        ok = date_equal(ge["start"], s) and date_equal(ge["end"], e)
        acc["exp_dates"].add(ok)
        ok or errors.append(f"{f}: dates at {ge['company']!r}: {pe.get('duration')!r} -> ({s},{e}) != ({ge['start']},{ge['end']})")
    _log_unmatched(errors, f, "experience", g_exp, pairs, lambda e: e["company"])
    _log_spurious(errors, f, "experience", p_exp, pairs, lambda e: e.get("company", ""))

    # projects — matched on title; then technologies inside matched projects
    g_pr, p_pr = gold["projects"], _as_list(pred.get("projects"))
    pairs = greedy_match(g_pr, p_pr, lambda p: p["title"], lambda p: p.get("title", ""))
    prf["projects"].add(len(pairs), len(g_pr), len(p_pr))
    for gi, pi in pairs:
        gt, pt = g_pr[gi]["technologies"], _as_list(p_pr[pi].get("technologies"))
        tp = set_match(gt, pt)
        prf["project_tech"].add(tp, len(gt), len(pt))
    _log_unmatched(errors, f, "project", g_pr, pairs, lambda p: p["title"])
    _log_spurious(errors, f, "project", p_pr, pairs, lambda p: p.get("title", ""))

    # skills (flat set) and certifications
    gs, ps = gold["skills"], [s if isinstance(s, str) else str(s) for s in _as_list(pred.get("skills"))]
    prf["skills"].add(set_match(gs, ps), len(gs), len(ps))
    gc, pc = gold["certifications"], [_cert_text(c) for c in _as_list(pred.get("certifications"))]
    pairs = greedy_match(gc, pc, lambda c: c, lambda c: c)
    prf["certifications"].add(len(pairs), len(gc), len(pc))
    _log_unmatched(errors, f, "certification", gc, pairs, lambda c: c)


def _log_unmatched(errors, f, what, gold_list, pairs, key):
    matched = {gi for gi, _ in pairs}
    for gi, g in enumerate(gold_list):
        if gi not in matched:
            errors.append(f"{f}: MISSED {what} {key(g)!r}")


def _log_spurious(errors, f, what, pred_list, pairs, key):
    matched = {pi for _, pi in pairs}
    for pi, p in enumerate(pred_list):
        if pi not in matched:
            errors.append(f"{f}: SPURIOUS {what} {key(p)!r}")


def evaluate(gold_items: list[dict], preds: dict) -> dict:
    prf = {k: Counter() for k in FIELDS_PRF}
    acc = {k: Acc() for k in FIELDS_ACC}
    errors: list[str] = []
    for g in gold_items:
        score_one(g, preds.get(g["file"]), prf, acc, errors)
    result = {"n_resumes": len(gold_items), "errors": errors}
    for k, c in prf.items():
        p, r, f = c.prf()
        result[k] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}
    for k, a in acc.items():
        result[k] = {"accuracy": round(a.value(), 3), "n": a.n}
    return result


# ------------------------------------------------------------------- plumbing

def load_gold() -> list[dict]:
    items = []
    for path in GOLD_FILES:
        if path.exists():
            for it in json.loads(path.read_text(encoding="utf-8"))["items"]:
                it["_split"] = "real" if "private" in path.parts else "template"
                items.append(it)
    return items


def run_engine(gold_items: list[dict], root: Path) -> dict:
    sys.path.insert(0, str(HERE.parents[1]))
    from candidate_profile_generator import generate_candidate_profile_via_engine
    preds = {}
    for g in gold_items:
        try:
            preds[g["file"]] = generate_candidate_profile_via_engine(str(root / g["file"]))
        except Exception as exc:  # a crash scores as an empty profile, and is reported
            print(f"[engine] {g['file']}: {type(exc).__name__}: {exc}", file=sys.stderr)
            preds[g["file"]] = {}
    return preds


def format_report(label: str, by_split: dict) -> str:
    lines = [f"# Parser benchmark — {label}", ""]
    header = "| field | " + " | ".join(by_split) + " |"
    lines += [header, "|" + "---|" * (len(by_split) + 1)]
    for k in FIELDS_ACC:
        cells = [f"{r[k]['accuracy']:.2f} (n={r[k]['n']})" if r[k]["n"] else "-" for r in by_split.values()]
        lines.append(f"| {k} (acc) | " + " | ".join(cells) + " |")
    for k in FIELDS_PRF:
        cells = [f"P {r[k]['precision']:.2f} / R {r[k]['recall']:.2f} / F1 {r[k]['f1']:.2f}" for r in by_split.values()]
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    lines += ["", f"resumes: " + ", ".join(f"{s}={r['n_resumes']}" for s, r in by_split.items()), ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", help="score a saved {file: profile} JSON instead of running the engine")
    ap.add_argument("--save-predictions", help="write the engine's predictions to this JSON")
    ap.add_argument("--label", default=None)
    ap.add_argument("--errors", action="store_true", help="print every per-field error")
    args = ap.parse_args()

    gold = load_gold()
    if not gold:
        sys.exit("no gold files found")
    root = Path(os.environ.get("PARSER_BENCH_ROOT", Path.home() / "Downloads"))
    if args.predictions:
        preds = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
        label = args.label or Path(args.predictions).stem
    else:
        preds = run_engine(gold, root)
        label = args.label or "resume_engine (live)"
        if args.save_predictions:
            Path(args.save_predictions).write_text(json.dumps(preds, indent=1, default=str), encoding="utf-8")

    splits = {"all": gold}
    for s in ("real", "template"):
        subset = [g for g in gold if g["_split"] == s]
        if subset:
            splits[s] = subset
    by_split = {s: evaluate(items, preds) for s, items in splits.items()}
    print(format_report(label, by_split))
    if args.errors:
        print("## Errors\n")
        for e in by_split["all"]["errors"]:
            print("-", e)


if __name__ == "__main__":
    main()
