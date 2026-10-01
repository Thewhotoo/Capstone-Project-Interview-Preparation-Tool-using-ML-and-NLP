"""Stage 6 -- two-level hybrid index with contextual chunk headers.

Children (what is searched):
  * one per content slide: the slide's own text
  * one per section: its title + opening text, for broad questions
Each child is embedded with a breadcrumb in front of it
("DBMS › Normalization › Second Normal Form: ..."), so terse bullets carry
their context (contextual chunk headers).

Parents (what is returned): the sections from Stage 4. A search matches
children, then returns their sections.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from .extract import SlideRecord
from .sections import Section
from .text_utils import bm25_tokenize

SECTION_CHILD_CHARS = 1200


def breadcrumb(subject_label: str, sec: Section) -> str:
    parts = [subject_label]
    if sec.deck_title:
        parts.append(sec.deck_title)
    if sec.topic and sec.topic.lower() not in (sec.title or "").lower():
        parts.append(sec.topic)
    if sec.title:
        parts.append(sec.title)
    return " › ".join(parts)


def build_children(slides: list[SlideRecord], sections: list[Section], subject_label: str,
                   section_children: bool = True, headers: bool = True) -> list[dict]:
    by_page = {s.page: s for s in slides}
    children: list[dict] = []
    for sec in sections:
        crumb = breadcrumb(subject_label, sec)
        for page in sec.pages:
            s = by_page[page]
            text = s.full_text()
            if s.type == "image_only" or len(text) < 15:
                continue
            children.append({
                "id": len(children), "section_id": sec.id, "kind": "slide", "page": page,
                "text": text,
                "embed_text": f"{crumb}: {text}" if headers else text,
            })
        if section_children and sec.text:
            opening = sec.text[:SECTION_CHILD_CHARS]
            children.append({
                "id": len(children), "section_id": sec.id, "kind": "section", "page": sec.page_start,
                "text": opening,
                "embed_text": f"{crumb}: {opening}" if headers else f"{sec.title}\n{opening}",
            })
    return children


def build_index(children: list[dict], model, out_dir: Path) -> None:
    texts = [c["embed_text"] for c in children]
    emb = model.encode(texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True,
                       normalize_embeddings=True).astype(np.float32)
    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    faiss.write_index(index, str(out_dir / "index.faiss"))
    bm25 = BM25Okapi([bm25_tokenize(t) for t in texts])
    with open(out_dir / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
    with open(out_dir / "children.json", "w", encoding="utf-8") as f:
        json.dump(children, f, ensure_ascii=False)
