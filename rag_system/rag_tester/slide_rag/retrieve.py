"""Section retrieval over the Stage 6 index.

  1. dense (FAISS) and keyword (BM25) search over child chunks
  2. both score lists min-max normalised over the candidate pool, mixed with
     weight `alpha` for dense
  3. child scores rolled up to their section (best child wins)
  4. top sections re-ranked with the MS MARCO cross-encoder
Each result carries the section's page range plus the single best-matching
slide page, so callers can cite either.
"""
from __future__ import annotations

import json
import pickle
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np

from .text_utils import bm25_tokenize

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base_v2"


@lru_cache(maxsize=None)
def _embedder(name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


class SubjectIndex:
    def __init__(self, subject: str, kb_dir: Path = KB_DIR):
        d = kb_dir / subject
        self.subject = subject
        self.manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        self.children = json.loads((d / "children.json").read_text(encoding="utf-8"))
        self.sections = {s["id"]: s for s in json.loads((d / "sections.json").read_text(encoding="utf-8"))}
        self.faiss = faiss.read_index(str(d / "index.faiss"))
        with open(d / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)

    def search(self, query: str, top_k: int = 5, alpha: float = 0.6, pool: int = 50,
               rerank: bool = True, rerank_depth: int = 20) -> list[dict]:
        model = _embedder(self.manifest["embedding_model"])
        q = model.encode([self.manifest.get("query_prefix", "") + query], convert_to_numpy=True,
                         normalize_embeddings=True).astype(np.float32)
        k = min(pool, len(self.children))
        dense_scores, dense_ids = self.faiss.search(q, k)
        dense = {int(i): float(s) for i, s in zip(dense_ids[0], dense_scores[0]) if i >= 0}

        bm = self.bm25.get_scores(bm25_tokenize(query))
        top_bm = np.argsort(-bm)[:k]
        sparse = {int(i): float(bm[i]) for i in top_bm if bm[i] > 0}

        def norm(d: dict) -> dict:
            if not d:
                return {}
            lo, hi = min(d.values()), max(d.values())
            return {i: (v - lo) / (hi - lo) if hi > lo else 1.0 for i, v in d.items()}

        nd, ns = norm(dense), norm(sparse)
        mixed = {i: alpha * nd.get(i, 0.0) + (1 - alpha) * ns.get(i, 0.0) for i in set(nd) | set(ns)}

        best: dict[int, tuple[float, int]] = {}      # section -> (score, best child)
        for cid, score in mixed.items():
            sid = self.children[cid]["section_id"]
            if sid not in best or score > best[sid][0]:
                best[sid] = (score, cid)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])

        if rerank and ranked:
            head = ranked[:rerank_depth]
            pairs = [(query, self._rerank_text(sid)) for sid, _ in head]
            ce = _reranker().predict(pairs)
            head = [(sid, (float(s), best[sid][1])) for (sid, _), s in zip(head, ce)]
            head.sort(key=lambda kv: -kv[1][0])
            ranked = head + ranked[rerank_depth:]

        out = []
        for sid, (score, cid) in ranked[:top_k]:
            sec = self.sections[sid]
            out.append({
                "section_id": sid, "title": sec["title"], "pdf": sec["pdf"],
                "pages": sec["pages"], "page_start": sec["page_start"], "page_end": sec["page_end"],
                "best_page": self.children[cid]["page"], "score": score, "text": sec["text"],
                "deck_title": sec["deck_title"], "topic": sec["topic"],
            })
        return out

    def _rerank_text(self, sid: int) -> str:
        sec = self.sections[sid]
        return f"{sec['title']}\n{sec['text']}"[:2000]


@lru_cache(maxsize=None)
def load(subject: str) -> SubjectIndex:
    return SubjectIndex(subject)


def retrieve(subject: str, query: str, top_k: int = 5, **kw) -> list[dict]:
    return load(subject).search(query, top_k=top_k, **kw)


def get_context_with_pages(subject: str, query: str, top_k: int = 3, max_words: int = 1200):
    """Drop-in shape of the old retrieval.get_context_with_pages: (context, pages, headings, [])."""
    hits = retrieve(subject, query, top_k=top_k)
    parts, pages, headings, budget = [], [], [], max_words
    for h in hits:
        cite = f"[{h['pdf']} p.{h['page_start']}-{h['page_end']}]" if h["page_end"] != h["page_start"] \
            else f"[{h['pdf']} p.{h['page_start']}]"
        block = " ".join(f"{cite} {h['title']}\n{h['text']}".split(" ")[:budget])
        parts.append(block)
        budget -= len(block.split())
        pages.extend(h["pages"])
        headings.append(h["title"])
        if budget <= 0:
            break
    return "\n\n".join(parts), pages, headings, []
