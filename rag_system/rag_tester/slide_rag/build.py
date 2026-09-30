"""Build the slide knowledge base for one or all subjects.

    python -m slide_rag.build                 # every folder in sources/
    python -m slide_rag.build --subject dbms
    python -m slide_rag.build --subject dbms --model BAAI/bge-small-en-v1.5 --out knowledge_base_v2_bge

Input:  sources/<subject>/*.pdf
Output: knowledge_base_v2/<subject>/ slides.json, sections.json, children.json,
        index.faiss, bm25.pkl, manifest.json, report.json, report.md

Stage 1 output is cached per PDF (keyed by file hash + extractor version),
so re-running after a grouping/index change skips PDF parsing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from .classify import classify_and_clean
from .extract import SlideRecord, extract_pdf
from .index import build_children, build_index
from .report import build_report
from .sections import build_sections

BASE = Path(__file__).resolve().parent.parent
SOURCES = BASE / "sources"
KB_V2 = BASE / "knowledge_base_v2"
CACHE = BASE / ".slide_cache"
EXTRACTOR_VERSION = "5"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VISION_MODEL = "Qwen/Qwen3-VL-2B-Instruct"     # whose cached Stage 3 output to merge (None = skip)
SUBJECT_LABELS = {"dbms": "DBMS", "dsa": "DSA", "ooad": "OOAD", "os": "Operating Systems",
                  "cn": "Computer Networks"}
# models that expect an instruction prefix on the query side
QUERY_PREFIX = {"BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: ",
                "BAAI/bge-base-en-v1.5": "Represent this sentence for searching relevant passages: "}


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _ocr_engine():
    """RapidOCR if installed (pip install rapidocr-onnxruntime); picture-only slides stay empty otherwise."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR()
    except Exception:
        print("  (no OCR engine -- picture-only slides are left for the vision stage)")
        return None


def _extract_cached(pdf: Path, subject: str) -> tuple[list[SlideRecord], set[str]]:
    CACHE.mkdir(exist_ok=True)
    key = CACHE / f"{subject}__{pdf.stem}__{_file_hash(pdf)}__v{EXTRACTOR_VERSION}.json"
    if key.exists():
        data = json.loads(key.read_text(encoding="utf-8"))
        return [SlideRecord(**s) for s in data["slides"]], set(data["boilerplate"])
    slides, boiler = extract_pdf(pdf, subject, ocr_engine=_ocr_engine())
    key.write_text(json.dumps({"slides": [s.to_dict() for s in slides], "boilerplate": sorted(boiler)},
                              ensure_ascii=False), encoding="utf-8")
    return slides, boiler


def _attach_vision(rec: SlideRecord, subject: str, pdf_hash: str, vision_model: str | None) -> None:
    """Merge a cached Stage 3 result into the slide (never runs the model itself)."""
    if not vision_model:
        return
    from .vision import cache_path, clean_output
    path = cache_path(subject, pdf_hash, rec.page, vision_model)
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    # re-clean from the raw model output, so cleaner fixes apply without re-running the model
    text = clean_output(data.get("raw", "")) if "raw" in data else data.get("text", "")
    if not text:
        return
    if data.get("picture_only") and not rec.title:
        # a picture-only slide's transcription starts with its title
        first = re.sub(r"^[#*\s\d.]+|[*]+$", "", text.split("\n", 1)[0]).strip()
        if 3 <= len(first) <= 100:
            rec.title = first
            text = text.split("\n", 1)[1].strip() if "\n" in text else ""
    rec.vision_text = text


def build_subject(subject: str, model_name: str = DEFAULT_MODEL, out_root: Path = KB_V2,
                  headers: bool = True, section_children: bool = True,
                  vision_model: str | None = VISION_MODEL) -> dict:
    from sentence_transformers import SentenceTransformer

    pdfs = sorted((SOURCES / subject).glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs in {SOURCES / subject}")
    t0 = time.time()
    slides: list[SlideRecord] = []
    boiler: set[str] = set()
    for pdf in pdfs:
        s, b = _extract_cached(pdf, subject)
        pdf_hash = _file_hash(pdf)
        for rec in s:
            # fresh classification every run (the cache holds Stage 1 only)
            rec.type, rec.dropped, rec.needs_vision, rec.deck, rec.deck_title = "", "", [], 0, ""
            _attach_vision(rec, subject, pdf_hash, vision_model)
        slides.extend(s)
        boiler |= b
    t1 = time.time()
    classify_and_clean(slides, boiler)
    # classification decides what needs vision; keep the flag on slides that already have it
    for rec in slides:
        if rec.vision_text and "vision_done" not in rec.needs_vision:
            rec.needs_vision.append("vision_done")

    model = SentenceTransformer(model_name)
    emb = model.encode([s.full_text() for s in slides], batch_size=64, convert_to_numpy=True,
                       normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
    sections = [s for s in build_sections(slides, emb, subject) if s.pages]
    for i, sec in enumerate(sections):
        sec.id = i
    label = SUBJECT_LABELS.get(subject, subject.upper())
    children = build_children(slides, sections, label, section_children=section_children, headers=headers)

    out = out_root / subject
    out.mkdir(parents=True, exist_ok=True)
    build_index(children, model, out)
    (out / "slides.json").write_text(json.dumps([s.to_dict() for s in slides], ensure_ascii=False), encoding="utf-8")
    quizzes = [{"page": s.page, "pdf": s.pdf, "deck_title": s.deck_title, "text": s.full_text()}
               for s in slides if s.type == "quiz"]
    (out / "quiz.json").write_text(json.dumps(quizzes, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "sections.json").write_text(json.dumps([s.to_dict() for s in sections], ensure_ascii=False), encoding="utf-8")
    manifest = {
        "subject": subject, "label": label, "pdfs": {p.name: _file_hash(p) for p in pdfs},
        "embedding_model": model_name, "query_prefix": QUERY_PREFIX.get(model_name, ""),
        "extractor_version": EXTRACTOR_VERSION, "contextual_headers": headers,
        "section_children": section_children, "vision_model": vision_model,
        "vision_slides": sum(1 for s in slides if s.vision_text), "slides": len(slides), "sections": len(sections),
        "children": len(children), "built_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rep = build_report(subject, slides, sections, boiler, out)
    print(f"✓ {subject}: {len(slides)} slides → {rep['content_slides']} content → {len(sections)} sections, "
          f"{len(children)} children  (extract {t1 - t0:.0f}s, rest {time.time() - t1:.0f}s)")
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default=str(KB_V2))
    ap.add_argument("--no-headers", action="store_true", help="ablation: embed chunks without breadcrumbs")
    ap.add_argument("--no-section-children", action="store_true")
    ap.add_argument("--no-vision", action="store_true", help="ablation: ignore Stage 3 vision output")
    args = ap.parse_args()
    subjects = [args.subject] if args.subject else sorted(p.name for p in SOURCES.iterdir()
                                                          if p.is_dir() and any(p.glob("*.pdf")))
    for subject in subjects:
        build_subject(subject, args.model, Path(args.out), headers=not args.no_headers,
                      section_children=not args.no_section_children,
                      vision_model=None if args.no_vision else VISION_MODEL)


if __name__ == "__main__":
    main()
