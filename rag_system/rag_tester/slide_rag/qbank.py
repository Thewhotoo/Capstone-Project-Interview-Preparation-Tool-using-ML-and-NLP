"""Phase 1 -- open-question bank for the technical interview (offline, local LLM via Ollama).

For every topic in topic_map.json, Qwen3-8B (Ollama, Q4_K_M) writes interview
questions from the topic's slide sections. Each question has:

  reference_answer   3-5 sentences
  key_points         3-5 specific points a good answer must cover, EACH with
                       quote            the slide sentence that supports it
                       followup         what to ask if the candidate left it out
                       followup_answer  the short expected answer to that follow-up
(No misconceptions: in the pilots they were the least reliable part -- often true
statements or paired with unrelated quotes -- and a wrong one teaches the wrong thing.)

How facts are checked:
  * in code: every key point's quote must actually appear in the slides' OWN text
    (fuzzy match; vision text excluded; a quote joining several bullets must match
    part by part), have >= 4 words, and be
    about the point (MiniLM cosine >= 0.35); other points are dropped, a question
    keeps >= 2
  * in code: trivia patterns (a specific return value, "the algorithm returns 0",
    named textbook rules) in the question, answer, key points or follow-ups
  * one judge call per question in Qwen3 thinking mode: on topic? tests understanding
    rather than trivia? which quotes don't actually support their point (dropped)?
    is the reference answer correct? (incorrect -> rejected)
  * questions of a topic must differ; no duplicates across the bank

Difficulty (defined in the prompt): easy = explain one concept; medium = how/why,
connecting 2-3 ideas; hard = scenario / why / what-if / trade-off, never trivia.
Each topic gets one easy-or-medium and one medium-or-hard slot, rotated through the
subject so it ends up balanced; the second question is written knowing the first
("cover a different aspect"). Low-priority topics ("| low" in the topic file) get
one question.

Every question slot is cached in .qbank_cache/ keyed by topic, context hash, slot,
runtime (model + quantization) and PROMPT_VERSION, so runs resume after
interruption. A slot that fails twice is logged and skipped, not retried.

    python -m slide_rag.qbank --pilot                 # 2 fixed topics per subject
    python -m slide_rag.qbank --subject os --limit 5
    python -m slide_rag.qbank --subject os            # the whole subject
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz

from .llm_client import OllamaClient

BASE = Path(__file__).resolve().parent.parent
KB_V2 = BASE / "knowledge_base_v2"
BANK_DIR = BASE / "question_bank"
CACHE = BASE / ".qbank_cache"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PROMPT_VERSION = "6"
MAX_CONTEXT_CHARS = 9000         # ~2,500 tokens of slides; well inside num_ctx=8192
QUOTE_MATCH = 88                 # rapidfuzz partial_ratio for a quote to count as "in the slides"
QUOTE_MIN_WORDS = 4              # terse bullets ("cookies: HTTP messages carry state") are real evidence;
                                 # bare fragments are caught by the thinking-mode judge's support check
POINT_QUOTE_SIM = 0.35           # coarse filter only; the thinking-mode judge checks real support
MIN_KEY_POINTS = 2
DISTINCT_SIM = 0.85
DUPLICATE_SIM = 0.90
FOLLOWUP_DUP_SIM = 0.92

COURSE = {"cn": "Computer Networks", "os": "Operating Systems", "dbms": "Database Management Systems",
          "dsa": "Data Structures and Algorithms", "ooad": "Object Oriented Analysis and Design"}
# one easy-or-medium + one medium-or-hard slot per topic; over 4 topics: 25% easy, 50% medium, 25% hard
# (warm-ups, the bulk of an interview, a few hard ones)
SLOT_CYCLE = [("easy", "medium"), ("medium", "hard"), ("easy", "medium"), ("medium", "hard")]

DIFFICULTY_TEXT = """Difficulty levels:
- easy: explain one concept or mechanism.
- medium: explain how or why something works, connecting 2-3 ideas.
- hard: a "why", a "what happens if", or a trade-off that requires reasoning about the concepts in the material.
Hard NEVER means a less common fact: do not ask about a specific return value, variable or function name from slide code, what "the algorithm" in some slide does, or a named rule from one textbook.
Never invent examples: no made-up tables, schemas, attribute sets, datasets, numbers or code. Reason only about concepts and examples that appear in the material."""

QUESTION_PROMPT = """You are a senior engineer writing ONE technical interview question for computer-science students.
Course: {course}
Topic: {topic}

Material for this topic (lines starting with [Figure] were read from diagrams and may be imprecise; never quote them):
<<<
{context}
>>>

{difficulty_text}

Write ONE {level} question about "{topic}" itself (ignore neighbouring topics in the material).
{other}
Rules:
- Use only facts supported by the material. Ask about understanding, not memorised lists. No pure numeric calculations.
- A good answer is 3-6 sentences, spoken aloud.
- Write as a real interviewer: never mention "the slides", "the lecture", "the material" or "the course".
- key_points: 3-5 SPECIFIC points a good answer must contain (not vague phrases). For each:
  - "quote": copy EXACTLY one sentence or bullet from the material that supports the point (not a [Figure] line)
  - "followup": the question to ask if the candidate left this point out; it hints at the point without stating it, and each follow-up is different
  - "followup_answer": the expected answer to that follow-up, 1-2 sentences
  The quote must itself state the point (a full sentence or bullet, not a heading or a fragment).
- reference_answer: 3-5 sentences, consistent with the key points and the quotes. Do not describe any mechanism the material does not describe."""

OTHER_QUESTION = """Another question on this topic already exists:
"{question}"
It covers: {points}
Your question must test a DIFFERENT aspect and must not overlap those points."""

JUDGE_PROMPT = """You are checking an interview question written from lecture material.
Topic: {topic} ({hints})
Question ({level}): {question}
Reference answer: {reference}
Key points, each with the quote from the material that is supposed to support it:
{points}

Answer:
1. on_topic: is the question mainly about the topic above (not a neighbouring topic)?
2. tests_understanding: does it test understanding or reasoning, rather than an obscure fact, a textbook-specific
   detail, or a detail of one particular piece of code (such as a specific return value)?
3. unsupported_points: the numbers of the key points whose quote does NOT actually state or directly imply the point
   (an unrelated or merely topical quote does not count as support).
4. reference_correct: is the reference answer factually correct computer science, and consistent with the quotes?"""

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "reference_answer": {"type": "string"},
        "key_points": {"type": "array", "minItems": 3, "maxItems": 5, "items": {
            "type": "object",
            "properties": {"point": {"type": "string"}, "quote": {"type": "string"},
                           "followup": {"type": "string"}, "followup_answer": {"type": "string"}},
            "required": ["point", "quote", "followup", "followup_answer"]}},
    },
    "required": ["question", "reference_answer", "key_points"],
}
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"on_topic": {"type": "boolean"}, "tests_understanding": {"type": "boolean"},
                   "unsupported_points": {"type": "array", "items": {"type": "integer"}},
                   "reference_correct": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["on_topic", "tests_understanding", "unsupported_points", "reference_correct", "reason"],
}

_META_RE = re.compile(r"\b(the|these|our)\s+(slides?|lecture|lectures|course|material|notes)\b", re.I)
# clear-cut trivia only (grey areas go to the judge): "fork() return" is a fair OS question,
# "why does the algorithm return 0" is a detail of one slide's code
_TRIVIA_RE = re.compile(
    r"\b(the )?(algorithm|code|function|program|implementation) (return|output|print)s?\s+(0|1|-1|true|false|null)\b"
    r"|\breturns?\s+(0|1|-1)\s+when\b|\bvariable (named|called)\b|\b\w+['’]s rule\b|\b\d+[- ]percent rule\b",
    re.I)


# ── inputs ───────────────────────────────────────────────────────────────────

def _load(subject: str) -> tuple[list[dict], dict[int, dict], dict[int, dict]]:
    d = KB_V2 / subject
    topics = json.loads((d / "topic_map.json").read_text(encoding="utf-8"))
    sections = {s["id"]: s for s in json.loads((d / "sections.json").read_text(encoding="utf-8"))}
    slides = {s["page"]: s for s in json.loads((d / "slides.json").read_text(encoding="utf-8"))}
    return topics, sections, slides


def _context(topic: dict, sections: dict[int, dict]) -> str:
    parts = [f"## {sections[sid]['title']}\n{sections[sid]['text']}" for sid in topic["sections"]]
    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def _slide_text(topic: dict, sections: dict[int, dict], slides: dict[int, dict]) -> str:
    """The slides' OWN text for the topic (vision text excluded), normalised for quote matching."""
    chunks = []
    for sid in topic["sections"]:
        for page in sections[sid]["pages"]:
            s = slides.get(page)
            if not s:
                continue
            chunks.append(s["title"])
            chunks += [it["text"] for it in s["items"]]
            chunks.append(s.get("code") or "")
            for t in s.get("tables") or []:
                chunks += [" ".join(c for c in row if c) for row in t]
    return _norm("\n".join(chunks))


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[•▪❖●➢➔○◦∙■□▶►✓✔·‣⁃➤\-–—*]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def assign_slots(topics: list[dict]) -> dict[str, tuple[str, ...]]:
    """Balanced across the subject: cycle (easy, medium) / (medium, hard) / (easy, hard) in topic order;
    low-priority topics get a single easy-or-medium question."""
    slots, i = {}, 0
    for t in topics:
        pair = SLOT_CYCLE[i % len(SLOT_CYCLE)]
        i += 1
        slots[t["id"]] = (pair[0],) if t.get("priority") == "low" else pair
    return slots


# ── checks (in code) ─────────────────────────────────────────────────────────

def quote_found(quote: str, slide_text: str) -> bool:
    """The quote (or, when it joins several bullets, every one of its parts) appears in the slide text."""
    q = _norm(quote)
    if len(q.split()) < QUOTE_MIN_WORDS:
        return False
    if fuzz.partial_ratio(q, slide_text) >= QUOTE_MATCH:
        return True
    # the model often joins consecutive bullets ("a – b", "a; b"): accept if every part is on the slides
    parts = [p.strip() for p in re.split(r"\s[-–—;|]\s|\s*[;|]\s*|(?<=[.!?])\s+", quote) if p.strip()]
    parts = [_norm(p) for p in parts if len(p.split()) >= 3]
    return len(parts) >= 2 and all(fuzz.partial_ratio(p, slide_text) >= QUOTE_MATCH for p in parts)


def check_question(q: dict, slide_text: str, embed) -> tuple[dict | None, list[str]]:
    """Verify quotes, trivia, meta phrasing. Returns (cleaned question or None, notes)."""
    notes = []
    stem = q.get("question", "").strip()
    if not stem:
        return None, ["empty question"]
    if _META_RE.search(stem):
        return None, [f"mentions slides/lecture: {stem[:60]}"]
    # trivia anywhere a candidate would be graded on it: question, answer, key points, follow-ups
    graded = [stem, q.get("reference_answer", "")] + [
        f"{kp.get('point', '')} {kp.get('followup', '')} {kp.get('followup_answer', '')}" for kp in q.get("key_points", [])]
    hit = next((t for t in graded if _TRIVIA_RE.search(t)), None)
    if hit:
        return None, [f"trivia pattern ({_TRIVIA_RE.search(hit).group(0)}): {stem[:60]}"]
    points = []
    for kp in q.get("key_points", []):
        point, quote = kp.get("point", "").strip(), kp.get("quote", "").strip()
        if not point:
            continue
        if not quote_found(quote, slide_text):
            notes.append(f"unverified quote -> dropped point: {point[:50]}")
            continue
        pv, qv = embed([point, quote])
        if float(pv @ qv) < POINT_QUOTE_SIM:
            notes.append(f"quote unrelated to point -> dropped: {point[:50]}")
            continue
        points.append({"point": point, "quote": quote, "followup": kp.get("followup", "").strip(),
                       "followup_answer": kp.get("followup_answer", "").strip()})
    if len(points) < MIN_KEY_POINTS:
        return None, notes + [f"only {len(points)} verified key points: {stem[:60]}"]
    # repeated follow-ups lose their text (the interview then uses a generic clarification)
    used = []
    for p in points:
        if p["followup"]:
            v = embed([p["followup"]])[0]
            if any(float(v @ u) >= FOLLOWUP_DUP_SIM for u in used):
                p["followup"], p["followup_answer"] = "", ""
            else:
                used.append(v)
    ref = " ".join(s for s in re.split(r"(?<=[.!?])\s+", q.get("reference_answer", "").strip())
                   if not _META_RE.search(s))
    return {"question": stem, "reference_answer": ref, "key_points": points}, notes


# ── generation ───────────────────────────────────────────────────────────────

def _cache_file(subject: str, topic: dict, context: str, slot: int, level: str, runtime: str) -> Path:
    h = hashlib.sha256(context.encode("utf-8")).hexdigest()[:12]
    return CACHE / subject / f"{topic['id']}__{h}__s{slot}-{level}__{runtime}__v{PROMPT_VERSION}.json"


def generate_slot(llm: OllamaClient, topic: dict, subject: str, context: str, slide_text: str, level: str,
                  first: dict | None, embed, bank_vecs: np.ndarray | None) -> dict:
    other = ""
    if first:
        other = OTHER_QUESTION.format(question=first["question"],
                                      points="; ".join(p["point"] for p in first["key_points"]))
    prompt = QUESTION_PROMPT.format(course=COURSE.get(subject, subject), topic=topic["name"], context=context,
                                    difficulty_text=DIFFICULTY_TEXT, level=level, other=other)
    attempts = []
    for attempt in range(2):
        t0 = time.time()
        try:
            raw, _ = llm.chat(prompt, schema=QUESTION_SCHEMA, temperature=0.2 if attempt == 0 else 0.7,
                              seed=7 + attempt, max_tokens=1500)
        except json.JSONDecodeError as e:
            attempts.append({"error": f"invalid JSON: {e}", "seconds": round(time.time() - t0, 1)})
            continue
        q, notes = check_question(raw, slide_text, embed)
        rec = {"raw": raw, "notes": notes, "seconds": round(time.time() - t0, 1)}
        if q is not None and first is not None:
            sim = float(embed([q["question"]])[0] @ embed([first["question"]])[0])
            if sim >= DISTINCT_SIM:
                rec["notes"].append(f"too close to the topic's first question ({sim:.2f})")
                q = None
        if q is not None and bank_vecs is not None and len(bank_vecs):
            if float((bank_vecs @ embed([q["question"]])[0]).max()) >= DUPLICATE_SIM:
                rec["notes"].append("duplicate of a question already in the bank")
                q = None
        if q is not None:
            numbered = "\n".join(f'{i}. {p["point"]}\n   quote: "{p["quote"]}"' for i, p in enumerate(q["key_points"], 1))
            try:
                verdict, thinking = llm.chat(JUDGE_PROMPT.format(
                    topic=topic["name"], hints=", ".join(topic["hints"][:5]), level=level, question=q["question"],
                    reference=q["reference_answer"], points=numbered), schema=JUDGE_SCHEMA, think=True,
                    max_tokens=400)
            except json.JSONDecodeError:
                verdict, thinking = {"on_topic": False, "tests_understanding": False, "unsupported_points": [],
                                     "reference_correct": False, "reason": "judge returned invalid output"}, ""
            rec["judge"] = {**verdict, "thinking": thinking[-1500:]}
            bad = {int(i) for i in verdict.get("unsupported_points", []) if str(i).isdigit()}
            if bad:
                rec["notes"].append(f"judge: key points {sorted(bad)} not supported by their quotes -> dropped")
                q["key_points"] = [p for i, p in enumerate(q["key_points"], 1) if i not in bad]
            if not (verdict.get("on_topic") and verdict.get("tests_understanding")):
                rec["notes"].append(f"judge rejected: {verdict.get('reason', '')[:120]}")
                q = None
            elif not verdict.get("reference_correct"):
                rec["notes"].append(f"judge: reference answer incorrect: {verdict.get('reason', '')[:120]}")
                q = None
            elif len(q["key_points"]) < MIN_KEY_POINTS:
                rec["notes"].append(f"only {len(q['key_points'])} key points left after the judge")
                q = None
        attempts.append(rec)
        if q is not None:
            q["difficulty"] = level
            return {"question": q, "attempts": attempts}
    return {"question": None, "attempts": attempts}


def run_subject(subject: str, llm: OllamaClient | None, embed, limit: int | None = None,
                only: set[str] | None = None) -> list[dict]:
    topics, sections, slides = _load(subject)
    slots = assign_slots(topics)
    todo = [t for t in topics if t["sections"] and (not only or t["id"] in only)]
    bank_file = BANK_DIR / f"{subject}.json"
    bank = json.loads(bank_file.read_text(encoding="utf-8")) if bank_file.exists() else []
    bank = [q for q in bank if not only or q["topic_id"] not in only]
    done = {q["topic_id"] for q in bank}
    pending = [t for t in todo if t["id"] not in done]
    if limit:
        pending = pending[:limit]
    runtime = llm.runtime_tag if llm else "cache-only"
    print(f"{subject}: {len(pending)} topics to generate ({len(done)} already in the bank) with {runtime}", flush=True)
    t_start = time.time()
    for i, t in enumerate(pending, 1):
        context = _context(t, sections)
        slide_text = _slide_text(t, sections, slides)
        made, first = [], None
        for s, level in enumerate(slots[t["id"]]):
            cache = _cache_file(subject, t, context, s, level, runtime)
            if cache.exists():
                result = json.loads(cache.read_text(encoding="utf-8"))
            elif llm is None:
                continue
            else:
                bank_vecs = embed([q["question"] for q in bank]) if bank else None
                result = generate_slot(llm, t, subject, context, slide_text, level, first, embed, bank_vecs)
                result.update({"topic": t, "runtime": runtime, "prompt_version": PROMPT_VERSION})
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
            q = result["question"]
            if q is None:
                continue
            first = first or q
            made.append(q)
            bank.append({
                "id": f"{t['id']}.{level}{s + 1}", "subject": subject, "topic_id": t["id"], "topic": t["name"],
                "unit": t["unit"], "priority": t.get("priority", "high"), "topic_coverage": t["coverage"],
                "question": q["question"], "difficulty": level, "reference_answer": q["reference_answer"],
                "key_points": q["key_points"],
                "source_pages": t["pages"], "source_sections": t["sections"],
                "runtime": runtime, "prompt_version": PROMPT_VERSION,
                # hard questions reason beyond single slide sentences, which the checks can't fully verify
                "review": "needs_review" if level == "hard" else "unreviewed",
            })
        BANK_DIR.mkdir(exist_ok=True)
        bank_file.write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8")
        rate = (time.time() - t_start) / i
        speed = f", {llm.tokens_per_second():.0f} tok/s" if llm else ""
        print(f"  {i}/{len(pending)} {t['name'][:40]:40} -> {len(made)}/{len(slots[t['id']])} questions "
              f"(~{rate * (len(pending) - i) / 60:.0f} min left{speed})", flush=True)
    _report(subject, bank, topics)
    return bank


def _report(subject: str, bank: list[dict], topics: list[dict]) -> None:
    by_topic = {}
    for q in bank:
        by_topic.setdefault(q["topic_id"], []).append(q)
    no_q = [t["name"] for t in topics if t["id"] not in by_topic and t["sections"]]
    md = [f"# Question bank: {subject}", "",
          f"- Questions: {len(bank)} across {len(by_topic)} topics",
          f"- Topics without questions yet: {len(no_q)}",
          "- Difficulty: " + ", ".join(f"{d} {sum(q['difficulty'] == d for q in bank)}" for d in ("easy", "medium", "hard")),
          ""]
    for q in bank:
        md += [f"### [{q['topic']}] {q['question']}",
               f"*{q['difficulty']} · priority {q.get('priority', 'high')} · slides {q['source_pages'][:6]}"
               + (" · ⚠ NEEDS REVIEW" if q.get("review") == "needs_review" else "") + "*", "",
               f"**Reference:** {q['reference_answer']}", "", "**Key points** (slide quote → follow-up → expected answer):"]
        for p in q["key_points"]:
            md.append(f"- **{p['point']}**  \n  quote: \"{p['quote']}\"  \n  follow-up: _{p['followup'] or '(generic clarification)'}_"
                      + (f"  \n  expected: {p['followup_answer']}" if p['followup_answer'] else ""))
        md.append("")
    (BANK_DIR / f"{subject}_report.md").write_text("\n".join(md), encoding="utf-8")


def make_embedder():
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(EMBED_MODEL, device="cpu")    # keep the GPU for Ollama
    return lambda texts: st.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True,
                                   show_progress_bar=False)


PILOT_SEED = 42


def pilot_topics(subject: str) -> set[str]:
    topics = [t for t in _load(subject)[0] if t["sections"]]
    return {t["id"] for t in random.Random(PILOT_SEED).sample(topics, 2)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--pilot", action="store_true", help="the same 2 topics per subject as earlier pilots")
    ap.add_argument("--no-generate", action="store_true", help="only rebuild the bank from the cache")
    ap.add_argument("--model", default="qwen3:8b")
    args = ap.parse_args()
    subjects = [args.subject] if args.subject else ["cn", "dbms", "dsa", "ooad", "os"]
    embed = make_embedder()
    llm = None if args.no_generate else OllamaClient(args.model)
    t0 = time.time()
    for s in subjects:
        run_subject(s, llm, embed, limit=args.limit, only=pilot_topics(s) if args.pilot else None)
    if llm:
        st = llm.stats
        print(f"done in {(time.time() - t0) / 60:.1f} min: {st['calls']} calls, {st['output_tokens']} output tokens, "
              f"{llm.tokens_per_second():.1f} tok/s")


if __name__ == "__main__":
    main()
