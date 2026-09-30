"""Stage 3 -- recover what text extraction loses (diagrams, tables, formulas, picture slides).

Slides flagged in Stage 2 (`needs_vision`) are rendered to an image and read by
a local vision-language model on the GPU (Qwen3-VL-2B-Instruct by default, ~4.3 GB
in bf16, fits an 8 GB card). The model is given the slide's extracted text and
asked only for what the text is missing:

  diagram      -> 2-5 sentences on components and how they connect, using the
                  labels shown
  table        -> the table as Markdown
  formula      -> equations rewritten with ^ and _ restored
  picture-only -> transcription of the slide, then the figure

Decorative pictures are answered with NONE and dropped.

Trust: measured on CN, vision text improves retrieval (diagram questions: hit@1
0.45 -> 0.55, MRR 0.62 -> 0.73; gold hit@5 0.96 -> 1.00; probes unchanged), but a
spot-check found misreadings (e.g. a layer stack in the wrong order, numeric graph
weights). Treat `vision_text` as a retrieval aid, NOT as ground truth: question
generation must not rely on it without support from the slide's own text.

Every result is cached per slide in .vision_cache/<subject>/, keyed by PDF hash,
page, model and PROMPT_VERSION, so runs can be stopped and resumed and a
prompt change re-runs only what it affects. build.py merges the cache into the
slides (field `vision_text`, shown in the text as "[Figure] ...") before
sections and the index are built.

    python -m slide_rag.vision --subject cn                 # all flagged slides
    python -m slide_rag.vision --subject cn --pages 400,463  # try a few
    python -m slide_rag.vision --subject cn --limit 50
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import pymupdf

BASE = Path(__file__).resolve().parent.parent
SOURCES = BASE / "sources"
KB_V2 = BASE / "knowledge_base_v2"
CACHE = BASE / ".vision_cache"
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
PROMPT_VERSION = "2"
MAX_SIDE = 1280          # longest image side in pixels fed to the model
MAX_NEW_TOKENS = 350

SUBJECT_NAMES = {"cn": "Computer Networks", "os": "Operating Systems", "dbms": "Database Management Systems",
                 "dsa": "Data Structures and Algorithms", "ooad": "Object Oriented Analysis and Design"}

PROMPT = """You are reading one slide from a university {course} lecture.
The slide's text, as already extracted (it may be incomplete and misses anything inside pictures):
<<<
{text}
>>>

Write ONLY the information that is inside the slide's figures, diagrams, charts, tables, equations or screenshots and is NOT already in the extracted text above.
- Diagram or chart: 2-4 plain sentences saying what is drawn: its parts, how they are connected or how data flows, using the labels exactly as shown.
- Table: reproduce it as a Markdown table.
- Equations: rewrite them in plain text, using ^ for powers and _ for subscripts.
- Screenshot of text or code: transcribe it.
Describe only what is visible. Do NOT define terms, explain fields or add background knowledge. Copy numbers exactly; if you cannot read them, say "values not legible" instead of guessing. Do not repeat the extracted text, and only write the parts that apply.
If the pictures are only decorative (logos, photos, clip art), answer exactly: NONE"""

PROMPT_PICTURE_ONLY = """This is one slide from a university {course} lecture. The whole slide is a picture.
1. Transcribe all readable text on the slide (title first), keeping bullet points and line breaks.
2. If there is a diagram, add 2-5 plain sentences describing its parts and how they are connected, using the labels shown.
3. If there is a table, reproduce it as a Markdown table. Write equations in plain text with ^ and _.
Only write what is visible on the slide."""


def _pdf_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _slide_text(s: dict) -> str:
    lines = [s["title"]] if s["title"] else []
    lines += [("  " * it["level"]) + ("- " if it["kind"] == "bullet" else "") + it["text"] for it in s["items"]]
    if s.get("code"):
        lines.append(s["code"])
    return "\n".join(lines)[:2500] or "(no text)"


def render(page: pymupdf.Page, max_side: int = MAX_SIDE):
    from PIL import Image
    zoom = max_side / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), annots=False)   # without personal ink/notes
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


class VisionModel:
    def __init__(self, model_id: str = MODEL_ID):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.model_id = model_id
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id, dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa").eval()
        self.torch = torch

    def ask(self, image, prompt: str) -> str:
        messages = [{"role": "user", "content": [{"type": "image", "image": image},
                                                 {"type": "text", "text": prompt}]}]
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        ).to(self.model.device)
        with self.torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                      repetition_penalty=1.05)
        text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return text.strip()


_PART = r"(diagram(?:\s+or\s+chart)?|chart|table|equations?|formulas?|screenshot[^:\n]*)"
_EMPTY_PART_RE = re.compile(rf"^\s*[-*]?\s*{_PART}\s*:\s*(none|n/a|not applicable)\.?\s*$", re.I | re.M)
_PART_LABEL_RE = re.compile(rf"^\s*[-*]?\s*{_PART}\s*:\s*", re.I | re.M)


def clean_output(text: str) -> str:
    text = text.replace("```markdown", "").replace("```", "")
    text = _EMPTY_PART_RE.sub("", text)                       # "- Equations: NONE"
    text = re.sub(r"^\s*none\.?\s*$", "", text, flags=re.I | re.M)   # stray NONE lines
    text = re.sub(r"^\s*there (is|are) no [^\n]{0,40} (in|on) the (image|slide)\.?\s*$", "", text, flags=re.I | re.M)
    text = _PART_LABEL_RE.sub("", text)                        # "- Diagram: ..." -> "..."
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 8:
        return ""
    return text


def cache_path(subject: str, pdf_hash: str, page: int, model_id: str) -> Path:
    tag = re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")
    return CACHE / subject / f"{pdf_hash}__p{page:04d}__{tag}__v{PROMPT_VERSION}.json"


def run(subject: str, pages: list[int] | None = None, limit: int | None = None, model_id: str = MODEL_ID,
        show: bool = False, reasons: set[str] | None = None) -> None:
    slides = json.loads((KB_V2 / subject / "slides.json").read_text(encoding="utf-8"))
    todo = [s for s in slides if not s["dropped"] and s["needs_vision"]
            and (not reasons or reasons & set(s["needs_vision"]))]
    if pages:
        todo = [s for s in slides if s["page"] in set(pages)]
    pdfs = {p.name: p for p in (SOURCES / subject).glob("*.pdf")}
    hashes = {name: _pdf_hash(p) for name, p in pdfs.items()}
    todo = [s for s in todo if pages or not cache_path(subject, hashes[s["pdf"]], s["page"], model_id).exists()]
    if limit:
        todo = todo[:limit]
    print(f"{subject}: {len(todo)} slides to read with {model_id}")
    if not todo:
        return
    vm = VisionModel(model_id)
    docs = {name: pymupdf.open(p) for name, p in pdfs.items()}
    course = SUBJECT_NAMES.get(subject, subject)
    t0 = time.time()
    for i, s in enumerate(todo, 1):
        text = _slide_text(s)
        picture_only = s["type"] == "image_only" or (s.get("ocr") and len(text) < 200)
        prompt = (PROMPT_PICTURE_ONLY if picture_only else PROMPT).format(course=course, text=text)
        t = time.time()
        raw = vm.ask(render(docs[s["pdf"]][s["page"] - 1]), prompt)
        result = {"subject": subject, "pdf": s["pdf"], "page": s["page"], "model": model_id,
                  "prompt_version": PROMPT_VERSION, "reasons": s["needs_vision"],
                  "picture_only": picture_only, "raw": raw, "text": clean_output(raw),
                  "seconds": round(time.time() - t, 1)}
        path = cache_path(subject, hashes[s["pdf"]], s["page"], model_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        if show:
            print(f"\n===== p{s['page']} {s['title'][:60]!r} {s['needs_vision']} ({result['seconds']}s)\n{result['text'] or '(NONE)'}")
        elif i % 25 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            print(f"  {i}/{len(todo)}  {rate:.1f}s/slide  ~{rate * (len(todo) - i) / 60:.0f} min left", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--pages", help="comma-separated pages to (re)read and print")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--reasons", help="only slides flagged for these reasons, e.g. image_heavy,image_only,table")
    args = ap.parse_args()
    pages = [int(p) for p in args.pages.split(",")] if args.pages else None
    reasons = set(args.reasons.split(",")) if args.reasons else None
    run(args.subject, pages, args.limit, args.model, show=bool(pages), reasons=reasons)


if __name__ == "__main__":
    main()
