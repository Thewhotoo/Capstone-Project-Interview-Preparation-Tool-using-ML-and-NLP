"""Hybrid retrieval: FAISS + BM25, reranking, adjacent merge, page-aware context."""
from __future__ import annotations

import faiss
import json
from pathlib import Path
from typing import Any

# We assume bm25_utils provides save_bm25_meta and load_bm25_index.
# If not, implement a simple BM25 index using rank_bm25.
from bm25_utils import load_bm25_index

_model = None
_reranker = None
_loaded_kbs = {}  # cache (index, chunks, bm25)

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"


def _get_model():
    """Lazy load embedding model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_reranker():
    """Lazy load cross-encoder reranker (optional)."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            _reranker = False
    return _reranker if _reranker is not False else None


def load_knowledge_base(subject_name: str) -> tuple[faiss.Index | None, list[dict] | None, Any | None]:
    """
    Load FAISS index, chunks, and BM25 index for a subject.
    Caches them in memory for subsequent calls.
    """
    if subject_name in _loaded_kbs:
        return _loaded_kbs[subject_name]

    subject_dir = KNOWLEDGE_BASE_DIR / subject_name
    index_path = subject_dir / "index.faiss"
    chunks_path = subject_dir / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        _loaded_kbs[subject_name] = (None, None, None)
        return None, None, None

    index = faiss.read_index(str(index_path))
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    # Load BM25 index (built and saved by dynamic_ingestor)
    bm25 = load_bm25_index(subject_dir)

    _loaded_kbs[subject_name] = (index, chunks, bm25)
    return index, chunks, bm25


def _faiss_search(index: faiss.Index, chunks: list[dict], query: str, top_k: int) -> list[tuple[int, float, str]]:
    """Semantic search using FAISS."""
    if index is None or len(chunks) == 0:
        return []
    model = _get_model()
    qv = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(qv)
    k = min(top_k, len(chunks))
    distances, indices = index.search(qv, k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if 0 <= idx < len(chunks):
            results.append((int(idx), float(dist), "faiss"))
    return results


def _bm25_search(bm25: Any, query: str, top_k: int) -> list[tuple[int, float, str]]:
    """
    Keyword search using BM25.
    Handles both rank_bm25.BM25Okapi and bm25s styles.
    """
    if bm25 is None:
        return []

    # --- rank_bm25.BM25Okapi style ---
    if hasattr(bm25, "get_scores"):
        # Tokenize query the same way the corpus was tokenized (simple whitespace split)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        # Get top_k indices sorted by score descending
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(idx, float(scores[idx]), "bm25") for idx in top_indices]

    # --- bm25s style (library by xhlulu) ---
    if hasattr(bm25, "retrieve"):
        results = bm25.retrieve(query, k=top_k)
        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], (list, tuple)):
            return [(doc_id, float(score), "bm25") for doc_id, score in results]
        else:
            # Fallback: if results is a dict or unknown shape, try to convert
            try:
                return [(i, float(s), "bm25") for i, s in enumerate(results)]
            except Exception:
                pass

    # --- Fallback: try .search() if it exists (original assumption) ---
    if hasattr(bm25, "search"):
        return [(idx, float(score), "bm25") for idx, score in bm25.search(query, top_k)]

    # If all else fails, log and return empty
    print(f"Warning: BM25 object of type {type(bm25)} has no known search method.")
    return []


def _merge_hybrid(
    faiss_hits: list[tuple[int, float, str]],
    bm25_hits: list[tuple[int, float, str]],
    alpha: float = 0.6
) -> list[tuple[int, float]]:
    """
    Combine FAISS and BM25 scores using weighted sum with min-max normalization.
    α controls FAISS weight; BM25 weight = 1-α.
    Returns list of (chunk_id, combined_score) sorted descending.
    """
    scores: dict[int, float] = {}

    # Normalize BM25 scores to [0,1]
    max_b = max((s for _, s, _ in bm25_hits), default=1.0)
    max_b = max_b if max_b > 0 else 1.0

    for idx, sim, _ in faiss_hits:
        scores[idx] = scores.get(idx, 0) + alpha * sim

    for idx, sc, _ in bm25_hits:
        norm_sc = sc / max_b
        scores[idx] = scores.get(idx, 0) + (1 - alpha) * norm_sc

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _rerank(
    query: str,
    chunks: list[dict],
    candidates: list[tuple[int, float]],
    top_n: int = 5
) -> list[tuple[int, float]]:
    """
    Re-rank top candidates using a cross-encoder.
    candidates: list of (chunk_id, score) already sorted.
    Returns top_n re-ranked (chunk_id, cross-encoder_score).
    """
    reranker = _get_reranker()
    if reranker is None or not candidates:
        return candidates[:top_n]

    # Take top 15 for reranking to limit compute
    top_candidates = candidates[:15]
    pairs = [(query, chunks[idx]["text"][:512]) for idx, _ in top_candidates]
    scores = reranker.predict(pairs)
    # Sort by cross-encoder score descending
    ranked = sorted(zip(top_candidates, scores), key=lambda x: x[1], reverse=True)
    return [(idx, float(sc)) for (idx, _), sc in ranked[:top_n]]


def _merge_adjacent(chunks: list[dict], selected_indices: list[int]) -> list[int]:
    """
    Add adjacent chunks on the same page to provide more complete context.
    Uses chunk_index (if available) to detect sequential order.
    """
    if not selected_indices:
        return []

    by_page: dict[int, list[int]] = {}
    for idx in selected_indices:
        page = chunks[idx].get("page", 0)
        by_page.setdefault(page, []).append(idx)

    merged_set = set(selected_indices)
    for page, idxs in by_page.items():
        # Sort by chunk_index if present, else by id
        idxs.sort(key=lambda i: chunks[i].get("chunk_index", i))
        for i in range(len(idxs) - 1):
            a, b = idxs[i], idxs[i+1]
            # If consecutive in the same page, keep both
            a_idx = chunks[a].get("chunk_index", a)
            b_idx = chunks[b].get("chunk_index", b)
            if abs(a_idx - b_idx) <= 1:
                merged_set.add(b)
    return sorted(merged_set)


def _chunk_to_result(chunk: dict, score: float, idx: int) -> dict:
    """Convert a chunk dict and score to a result dict."""
    return {
        "chunk_id": idx,
        "page": chunk.get("page", 0),
        "pdf": chunk.get("pdf", ""),
        "text": chunk["text"],
        "headings": chunk.get("headings", []),
        "concepts": chunk.get("concepts", []),
        "section_label": chunk.get("section_label", ""),
        "similarity": score,
        "relevance_score": score,
    }


def retrieve_relevant_content(
    subject_name: str,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.25,
    use_hybrid: bool = True,
    use_rerank: bool = True,
    merge_adjacent: bool = True,
    page_filter: int | None = None,
) -> list[dict]:
    """
    Main retrieval function.

    Args:
        subject_name: Subject folder name (e.g., "cn")
        query: User query string
        top_k: Number of final chunks to return
        similarity_threshold: Minimum combined score (0-1) to include
        use_hybrid: If True, combine FAISS and BM25; else FAISS only
        use_rerank: If True, apply cross-encoder reranking
        merge_adjacent: If True, include neighbouring chunks from same page
        page_filter: Optional page number to restrict results

    Returns:
        List of result dicts with keys: chunk_id, page, text, headings, concepts, similarity.
    """
    index, chunks, bm25 = load_knowledge_base(subject_name)
    if index is None or not chunks:
        print(f"Knowledge base not found for '{subject_name}'")
        return []

    # Increase candidate pool for hybrid/reranking
    candidate_k = top_k * 4

    # 1. FAISS search
    faiss_hits = _faiss_search(index, chunks, query, candidate_k)

    # 2. BM25 search (if hybrid)
    if use_hybrid and bm25 is not None:
        bm25_hits = _bm25_search(bm25, query, candidate_k)
    else:
        bm25_hits = []

    # 3. Merge scores
    if use_hybrid and bm25_hits:
        merged = _merge_hybrid(faiss_hits, bm25_hits)
    else:
        merged = [(idx, sc) for idx, sc, _ in faiss_hits]

    # Apply page filter if specified
    if page_filter is not None:
        merged = [(i, s) for i, s in merged if chunks[i].get("page", 0) == page_filter]

    # Apply similarity threshold
    merged = [(i, s) for i, s in merged if s >= similarity_threshold]

    # 4. Rerank (optional)
    if use_rerank and merged:
        merged = _rerank(query, chunks, merged, top_n=top_k * 2)

    # 5. Select top candidates
    selected_indices = [i for i, _ in merged[:top_k * 2]]

    # 6. Merge adjacent chunks (optional)
    if merge_adjacent:
        selected_indices = _merge_adjacent(chunks, selected_indices)[:top_k * 2]

    # Build final results (top_k)
    results = []
    score_map = dict(merged)
    for idx in selected_indices[:top_k]:
        sc = score_map.get(idx, 0.0)
        results.append(_chunk_to_result(chunks[idx], sc, idx))

    # Sort by relevance score descending
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results


def get_best_context(subject_name: str, query: str, **kwargs) -> str:
    """Return the text of the single best chunk."""
    hits = retrieve_relevant_content(subject_name, query, top_k=1, **kwargs)
    return hits[0]["text"] if hits else ""


def load_test_cases(subject_name: str, topic: str) -> list:
    """Load pre‑defined test cases for a topic (from tests.json)."""
    test_path = KNOWLEDGE_BASE_DIR / subject_name / "tests.json"
    if test_path.exists():
        import json
        with open(test_path, "r") as f:
            data = json.load(f)
            return data.get(topic, {}).get("test_cases", [])
    return []


def get_context_with_pages(
    subject_name: str,
    query: str,
    top_k: int = 3,
    max_tokens: int = 1200,
    **kwargs
) -> tuple[str, list[int], list[str], list[str]]:
    """
    Retrieve top chunks, concatenate into a single context string with page citations.
    Returns (context_text, pages, headings, concepts).
    """
    hits = retrieve_relevant_content(subject_name, query, top_k=top_k, **kwargs)
    if not hits:
        return "", [], [], []

    parts, pages, headings, concepts = [], [], [], []
    word_budget = max_tokens
    for h in hits:
        cite = f"[p.{h['page']}]"
        block = f"{cite} {h['text']}"
        wc = len(block.split())
        if wc > word_budget:
            block = " ".join(block.split()[:word_budget])
        parts.append(block)
        word_budget -= len(block.split())
        pages.append(h["page"])
        headings.extend(h.get("headings", []))
        concepts.extend(h.get("concepts", []))
        if word_budget <= 0:
            break

    # Deduplicate headings and concepts while preserving order
    unique_headings = list(dict.fromkeys(headings))
    unique_concepts = list(dict.fromkeys(concepts))

    return "\n\n".join(parts), pages, unique_headings, unique_concepts