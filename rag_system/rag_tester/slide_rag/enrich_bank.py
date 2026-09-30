"""Enrich the question bank so a light grader can recognise how students really talk.

    python -m slide_rag.enrich_bank                  all subjects, active questions
    python -m slide_rag.enrich_bank --subject cn --limit 5
    python -m slide_rag.enrich_bank --ids cn.tcp_vs_udp.easy1 os.deadlock_avoidance.easy1
    python -m slide_rag.enrich_bank --no-generate    re-apply cached results only

Why: the interview grader (main_cap/cap/tech_interview/grader.py) runs on any
laptop, so it can't use an LLM at interview time. It checks answers against
each key point with an NLI model, which misses short, informal answers
("3 way handshake" for "TCP requires a connection setup", "nope", "banker's
algorithm"). This one-off offline pass (local Qwen3-8B via Ollama, like
qbank.py) writes, per active question:

  key_points[i].variants          ~6 informal ways a student might SAY the point
  key_points[i].followup_replies  ~5 short correct replies to its follow-up
  core_point                      the question's main idea (asked for blind), when the key points
                                  miss it (e.g. "safe state" without "a safe
                                  sequence exists"); flagged needs_review

The grader then matches answers against the point AND its variants.
Checks: variants must be 2-25 words, on topic (MiniLM cosine to their point
>= VARIANT_MIN_SIM), no slide/lecture mentions, no duplicates. Results are
cached per question in .enrich_cache/ (keyed by question content, model and
PROMPT_VERSION), so an interrupted run resumes. Review: question_bank/enrich_report.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .llm_client import OllamaClient, PromptTooLong

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "question_bank"
CACHE_DIR = ROOT / ".enrich_cache"
SUBJECTS = ("cn", "dbms", "dsa", "ooad", "os")
PROMPT_VERSION = "4"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VARIANT_MIN_SIM = 0.35
CORE_MIN_SIM = 0.30          # a proposed core point must relate to the question / reference

PROMPT = """You are helping build an automatic grader for SPOKEN technical-interview answers from undergraduate computer-science students.

Subject: {subject}
Question: {question}
Reference answer: {reference}

Key points the grader checks (numbered):
{points}

Do two things.

1. For EACH key point, write 6 different ways a student might SAY that point out loud in an interview.
   - informal and spoken: lowercase is fine, short (4-20 words), no bullet points
   - vary them: a full sentence, a terse version with just the key terms, a version using a common
     synonym or the mechanism's name (e.g. "3 way handshake before sending data" for "TCP requires a
     connection setup", or "syn, syn-ack, ack"), a version as a consequence ("so udp can lose packets")
   - each must mean the same thing as the key point and be technically correct
   - do NOT add facts, numbers, examples or claims that the key point does not imply
   - do NOT reverse the logic or make it stronger: "a safe state has no deadlock" must not become
     "no deadlock means a safe state"
   - write each as a FULL sentence that names its subject ("udp can lose packets"), not a fragment

2. For EACH key point's follow-up question, write 5 short CORRECT replies a student might give,
   ranging from 1-3 words ("nope", "banker's algorithm", "it halves") to one sentence.
   Each must be a correct answer to that follow-up question.

Return JSON with exactly {n} items in key_points, in the same order."""

SCHEMA = {
    "type": "object",
    "properties": {
        "key_points": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "variants": {"type": "array", "items": {"type": "string"}},
                "followup_replies": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["variants", "followup_replies"],
        }},
    },
    "required": ["key_points"],
}

# The main idea is asked for BLIND (question only): shown the reference answer,
# the model just paraphrased it, flaws included. Whether the existing key
# points already state it is then checked with NLI, not by asking the model.
CORE_PROMPT = """Answer this {subject} interview question in ONE short, precise, textbook-correct sentence
(at most 20 words) that states the single main idea an interviewer most wants to hear.
State the DEFINING condition or mechanism, not a consequence or benefit of it. For example, for
"What is a safe state?" write "a state in which some ordering of all processes lets each get its resources
and finish", NOT "a state that avoids deadlock".
No examples, no complexity figures, no preamble, no second clause about something else.
Then write 5 different ways a student might SAY that same main idea out loud: informal, short (5-25 words),
same meaning and just as specific (keep the defining condition), technically correct, nothing added.
Write the main idea and every variant as a FULL sentence that names its subject ("a safe state is when ...",
"tcp sets up a connection ..."), never a fragment like "a state where ...".

Question: {question}"""
CORE_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"},
                                               "variants": {"type": "array", "items": {"type": "string"}}},
               "required": ["answer", "variants"]}
CORE_VERSION = "5"
NLI_MODEL = "cross-encoder/nli-deberta-v3-base"
CORE_COVERED_ENTAIL = 0.5    # reference answer or a key point entails the blind main idea -> nothing missing
VARIANT_MAX_CONTRADICTION = 0.5          # paraphrase vs its key point, either direction
VARIANT_MAX_IMPLIED_BY_QUESTION = 0.5    # the question alone implies it -> too generic to count
# Same patterns as the grader's yes/no rule (main_cap/cap/tech_interview/grader.py).
_POLAR_QUESTION_RE = re.compile(r"^\s*(does|do|did|is|are|was|were|can|could|will|would|should|has|have|must)\b", re.I)
_YES_RE = re.compile(r"^\s*(yes|yeah|yep|yup|ya|sure|correct|right|it does|it can|it is|true)\b", re.I)
_NO_RE = re.compile(r"^\s*(no|nope|nah|not really|never|it doesn'?t|it does not|it can'?t|it cannot|it isn'?t|false)\b", re.I)

SUBJECT_NAMES = {"cn": "Computer Networks", "dbms": "Database Management Systems",
                 "dsa": "Data Structures and Algorithms", "ooad": "Object-Oriented Analysis and Design",
                 "os": "Operating Systems"}
_BANNED = re.compile(r"\b(slides?|lecture|the key point|as mentioned)\b", re.I)


def _content_hash(q: dict) -> str:
    payload = json.dumps([q["question"], q["reference_answer"],
                          [[k["point"], k.get("followup", ""), k.get("followup_answer", "")] for k in q["key_points"]]])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _prompt(q: dict, subject: str) -> str:
    lines = []
    for i, k in enumerate(q["key_points"], 1):
        lines.append(f"{i}. {k['point']}")
        if k.get("followup"):
            lines.append(f"   follow-up question: {k['followup']}")
            lines.append(f"   expected reply: {k.get('followup_answer', '')}")
    return PROMPT.format(subject=SUBJECT_NAMES[subject], question=q["question"], reference=q["reference_answer"],
                         points="\n".join(lines), n=len(q["key_points"]))


def _clean(items, min_words: int, max_words: int) -> list[str]:
    out, seen = [], set()
    for t in items or []:
        t = re.sub(r"\s+", " ", str(t)).strip().strip('"').strip()
        n = len(t.split())
        if not (min_words <= n <= max_words) or _BANNED.search(t) or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out


class Enricher:
    def __init__(self, generate: bool = True, model: str | None = None, strict: bool = False):
        self.strict = strict
        self.llm = OllamaClient(model) if (generate and model) else OllamaClient() if generate else None
        from sentence_transformers import SentenceTransformer
        self.st = SentenceTransformer(EMBED_MODEL, device="cpu")    # keep the GPU for Ollama
        self.nli = None                                             # loaded on first use, also on CPU
        self.stats = {"generated": 0, "cached": 0, "failed": 0, "skipped": 0,
                      "variants_kept": 0, "variants_dropped": 0, "variants_contradicting": 0,
                      "variants_generic": 0, "variants_not_same": 0, "replies_wrong_polarity": 0,
                      "core_points": 0, "core_gaps": 0}

    def _sim(self, a: list[str], b: str):
        v = self.st.encode(a + [b], normalize_embeddings=True, show_progress_bar=False)
        return v[:-1] @ v[-1]

    def _cache_path(self, q: dict, subject: str) -> Path | None:
        tag = self.llm.runtime_tag if self.llm else None
        d = CACHE_DIR / subject
        if tag:
            return d / f"{q['id']}__{_content_hash(q)}__{tag}__v{PROMPT_VERSION}.json"
        hits = sorted(d.glob(f"{q['id']}__{_content_hash(q)}__*__v{PROMPT_VERSION}.json")) if d.exists() else []
        return hits[-1] if hits else None

    def raw(self, q: dict, subject: str) -> dict | None:
        path = self._cache_path(q, subject)
        if path and path.exists():
            self.stats["cached"] += 1
            return json.loads(path.read_text(encoding="utf-8"))
        if self.llm is None:
            self.stats["skipped"] += 1
            return None
        n = len(q["key_points"])
        for attempt in range(2):
            try:
                result, _ = self.llm.chat(_prompt(q, subject), schema=SCHEMA, think=False, max_tokens=1800,
                                          temperature=0.4, seed=7 + attempt)
            except (PromptTooLong, json.JSONDecodeError) as exc:
                print(f"    {q['id']}: {exc}", file=sys.stderr)
                continue
            if len(result.get("key_points", [])) == n:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
                self.stats["generated"] += 1
                return result
        self.stats["failed"] += 1
        return None

    def core_answer(self, q: dict, subject: str) -> dict:
        """The question's main idea (+ informal variants), written without seeing
        the reference answer (cached). {} when unavailable."""
        tag = self.llm.runtime_tag if self.llm else "*"
        d = CACHE_DIR / subject
        pattern = f"{q['id']}__{_content_hash(q)}__{tag}__core_v{CORE_VERSION}.json"
        if self.llm is None:
            hits = sorted(d.glob(pattern)) if d.exists() else []
            return json.loads(hits[-1].read_text(encoding="utf-8")) if hits else {}
        path = d / pattern
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            result, _ = self.llm.chat(CORE_PROMPT.format(subject=SUBJECT_NAMES[subject], question=q["question"]),
                                      schema=CORE_SCHEMA, think=False, max_tokens=500, temperature=0.2)
        except (PromptTooLong, json.JSONDecodeError) as exc:
            print(f"    {q['id']} core: {exc}", file=sys.stderr)
            return {}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    def _probs(self, pairs: list[tuple[str, str]]):
        """(entailment, contradiction) probabilities for (premise, hypothesis) pairs."""
        if self.nli is None:
            from sentence_transformers import CrossEncoder
            import numpy as np
            self.nli = CrossEncoder(NLI_MODEL, device="cpu")
            labels = {v.lower(): int(k) for k, v in self.nli.model.config.id2label.items()}
            self._entail_idx, self._contra_idx, self._np = labels["entailment"], labels["contradiction"], np
        np = self._np
        logits = np.asarray(self.nli.predict(pairs, show_progress_bar=False))
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        p = e / e.sum(axis=1, keepdims=True)
        return p[:, self._entail_idx], p[:, self._contra_idx]

    def _entails(self, premises: list[str], hypothesis: str) -> float:
        return float(self._probs([(p, hypothesis) for p in premises])[0].max())

    def _check_variants(self, original: str, variants: list[str], question: str) -> list[str]:
        """Drop paraphrases that are wrong or empty, keep ones the NLI model merely can't link:
          contradicts   the original contradicts it or it contradicts the original (reversed logic)
          generic       the question alone already implies it ("safe state avoids deadlock")
          not_same      (--strict-variants only) not entailed in BOTH directions -- this also
                        drops the useful ones ("tcp uses a 3 way handshake"), hence optional
        """
        if not variants:
            return []
        n = len(variants)
        e, c = self._probs([(original, v) for v in variants] + [(v, original) for v in variants]
                           + [(question, v) for v in variants])
        kept = []
        for i, v in enumerate(variants):
            if max(c[i], c[n + i]) >= VARIANT_MAX_CONTRADICTION:
                self.stats["variants_contradicting"] += 1
            elif e[2 * n + i] >= VARIANT_MAX_IMPLIED_BY_QUESTION:
                self.stats["variants_generic"] += 1
            elif self.strict and min(e[i], e[n + i]) < 0.5:
                self.stats["variants_not_same"] += 1
            else:
                kept.append(v)
        return kept

    def _check_replies(self, followup: str, expected: str, replies: list[str]) -> list[str]:
        """A yes/no follow-up's replies must have the expected answer's polarity."""
        if not _POLAR_QUESTION_RE.match(followup or ""):
            return replies
        want = "yes" if _YES_RE.match(expected) else "no" if _NO_RE.match(expected) else None
        if want is None:
            return replies
        kept = []
        for r in replies:
            got = "yes" if _YES_RE.match(r) else "no" if _NO_RE.match(r) else None
            if got is not None and got != want:
                self.stats["replies_wrong_polarity"] += 1
            else:
                kept.append(r)
        return kept

    def apply(self, q: dict, result: dict, core_result: dict | None = None) -> dict:
        """Validated fields for this question (also written into q)."""
        for k, gen in zip(q["key_points"], result["key_points"]):
            variants = _clean(gen.get("variants"), 2, 25)
            if variants:
                sims = self._sim(variants, k["point"])
                kept = self._check_variants(k["point"], [v for v, s in zip(variants, sims) if s >= VARIANT_MIN_SIM],
                                            q["question"])
            else:
                kept = []
            self.stats["variants_kept"] += len(kept)
            self.stats["variants_dropped"] += len(gen.get("variants") or []) - len(kept)
            k["variants"] = kept
            k["followup_replies"] = (self._check_replies(k["followup"], k.get("followup_answer", ""),
                                                         _clean(gen.get("followup_replies"), 1, 30))
                                     if k.get("followup") else [])
        core = str((core_result or {}).get("answer", "")).strip()
        q.pop("core_point", None)
        if core and 5 <= len(core.split()) <= 30 and not _BANNED.search(core):
            related = max(self._sim([core], q["question"])[0], self._sim([core], q["reference_answer"])[0])
            if related >= CORE_MIN_SIM:
                # stated_by_bank < CORE_COVERED_ENTAIL: the bank's own answer doesn't say it -- a
                # likely gap in the key points, listed first in the report for review
                stated = self._entails([q["reference_answer"], " ".join(k["point"] for k in q["key_points"])]
                                       + [k["point"] for k in q["key_points"]], core)
                variants = _clean(core_result.get("variants"), 3, 30)
                if variants:
                    variants = self._check_variants(
                        core, [v for v, s in zip(variants, self._sim(variants, core)) if s >= VARIANT_MIN_SIM],
                        q["question"])
                q["core_point"] = {"point": core, "variants": variants, "review": "unreviewed",
                                   "stated_by_bank": round(stated, 3)}
                self.stats["core_points"] += 1
                self.stats["core_gaps"] = self.stats.get("core_gaps", 0) + (stated < CORE_COVERED_ENTAIL)
        return q


def _report(bank: dict[str, list[dict]], stats: dict, seconds: float) -> str:
    lines = ["# Question bank enrichment (slide_rag/enrich_bank.py)", "",
             f"Prompt v{PROMPT_VERSION}. {json.dumps(stats)}. {seconds / 60:.1f} min.", "",
             "## Main ideas the bank's own answer does NOT state (likely gaps; check these first)", "",
             "The main idea (core_point) is an extra route to credit in the grader, never a penalty.", ""]
    for subject, qs in bank.items():
        for q in qs:
            core = q.get("core_point")
            if core and core.get("stated_by_bank", 1) < CORE_COVERED_ENTAIL:
                lines += [f"- **{q['id']}**: {q['question']}", f"  - main idea: {core['point']}"]
    lines += ["", "## Sample variants (first enriched question per subject)", ""]
    for subject, qs in bank.items():
        q = next((q for q in qs if any(k.get("variants") for k in q["key_points"])), None)
        if not q:
            continue
        lines.append(f"### {q['id']}: {q['question']}")
        for k in q["key_points"]:
            lines.append(f"- {k['point']}")
            lines += [f"  - says: {v}" for v in k.get("variants", [])]
            if k.get("followup"):
                lines.append(f"  - follow-up: {k['followup']}")
                lines += [f"    - reply: {r}" for r in k.get("followup_replies", [])]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", choices=SUBJECTS, action="append")
    ap.add_argument("--ids", nargs="*", default=None, help="only these question ids")
    ap.add_argument("--limit", type=int, default=None, help="at most N questions per subject")
    ap.add_argument("--all", action="store_true", help="also inactive (held-back) questions")
    ap.add_argument("--no-generate", action="store_true", help="only apply cached results")
    ap.add_argument("--model", default=None)
    ap.add_argument("--strict-variants", action="store_true",
                    help="keep only paraphrases the NLI model confirms in both directions")
    args = ap.parse_args()

    enricher = Enricher(generate=not args.no_generate, model=args.model, strict=args.strict_variants)
    t0 = time.time()
    banks = {}
    for subject in args.subject or SUBJECTS:
        path = BANK_DIR / f"{subject}.json"
        qs = json.loads(path.read_text(encoding="utf-8"))
        todo = [q for q in qs if (args.all or q.get("active")) and (args.ids is None or q["id"] in args.ids)]
        if args.limit:
            todo = todo[:args.limit]
        for i, q in enumerate(todo, 1):
            result = enricher.raw(q, subject)
            if result is not None:
                enricher.apply(q, result, enricher.core_answer(q, subject))
            if enricher.llm and i % 5 == 0:
                done = enricher.stats["generated"]
                rate = (time.time() - t0) / max(1, done)
                print(f"  {subject}: {i}/{len(todo)}  ({enricher.llm.tokens_per_second():.0f} tok/s, "
                      f"~{rate:.0f}s per question)", flush=True)
        path.write_text(json.dumps(qs, indent=1, ensure_ascii=False), encoding="utf-8")
        banks[subject] = qs
        print(f"{subject}: {len(todo)} questions processed", flush=True)
    (BANK_DIR / "enrich_report.md").write_text(_report(banks, enricher.stats, time.time() - t0), encoding="utf-8")
    print("done:", enricher.stats, f"{(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
