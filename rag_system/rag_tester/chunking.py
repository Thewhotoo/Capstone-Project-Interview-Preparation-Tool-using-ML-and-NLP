"""Section-aware PDF chunking: headings, definitions, examples, overlap."""
from __future__ import annotations

import re
from typing import Any

SECTION_MARKERS = re.compile(
    r"^(Definition|Problem|Solution|Example|Examples?|Note|Notes?|"
    r"Algorithm|Pseudocode|Steps?)\s*:?\s*",
    re.IGNORECASE | re.MULTILINE,
)
HEADING_LINE = re.compile(r"^[A-Z][A-Za-z0-9\s\-]{4,60}$")
MIN_CHUNK_WORDS = 40
MAX_CHUNK_WORDS = 450
OVERLAP_WORDS = 80
MERGE_SHORT_WORDS = 35


def _word_count(text: str) -> int:
    return len(text.split())


def split_into_sections(text: str) -> list[dict[str, Any]]:
    """Split page text into labeled sections preserving structure."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    sections: list[dict[str, Any]] = []
    current_label = "content"
    current_heading = ""
    buffer: list[str] = []

    def flush():
        nonlocal buffer, current_label, current_heading
        if not buffer:
            return
        body = " ".join(buffer).strip()
        if _word_count(body) >= 3:
            sections.append(
                {
                    "label": current_label,
                    "heading": current_heading,
                    "text": body,
                    "is_example": current_label.lower().startswith("example"),
                    "is_definition": current_label.lower() == "definition",
                }
            )
        buffer = []

    for line in lines:
        marker = SECTION_MARKERS.match(line)
        if marker:
            flush()
            current_label = marker.group(1).capitalize()
            rest = line[marker.end() :].strip()
            if rest:
                buffer.append(rest)
            continue
        if HEADING_LINE.match(line) and _word_count(line) <= 8:
            flush()
            current_heading = line
            current_label = "content"
            continue
        buffer.append(line)

    flush()
    return sections


def merge_short_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge tiny sections with the next block; keep examples with definitions."""
    if not sections:
        return sections
    merged: list[dict[str, Any]] = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        wc = _word_count(sec["text"])
        if wc < MERGE_SHORT_WORDS and i + 1 < len(sections):
            nxt = sections[i + 1]
            combined = {
                "label": sec["label"] if sec["label"] != "content" else nxt["label"],
                "heading": sec["heading"] or nxt["heading"],
                "text": sec["text"] + " " + nxt["text"],
                "is_example": sec["is_example"] or nxt["is_example"],
                "is_definition": sec["is_definition"] or nxt["is_definition"],
            }
            merged.append(combined)
            i += 2
        else:
            merged.append(sec)
            i += 1
    return merged


def pack_sections_into_chunks(
    sections: list[dict[str, Any]],
    page: int,
    pdf_name: str,
    headings: list[str],
    concepts: list[str],
    start_id: int,
) -> list[dict[str, Any]]:
    """Pack sections into word-bounded chunks with overlap."""
    chunks: list[dict[str, Any]] = []
    chunk_id = start_id
    carry_words: list[str] = []

    def make_chunk(text: str, meta: dict[str, Any], chunk_index: int):
        nonlocal chunk_id
        rich = []
        if meta.get("heading"):
            rich.append(f"Heading: {meta['heading']}")
        elif headings:
            rich.append("Heading: " + ", ".join(headings[:3]))
        if concepts:
            rich.append("Concepts: " + ", ".join(concepts[:8]))
        if meta.get("label") and meta["label"] != "content":
            rich.append(f"Section: {meta['label']}")
        rich.append(text)
        embedding_text = " | ".join(rich)
        chunks.append(
            {
                "id": chunk_id,
                "page": page,
                "pdf": pdf_name,
                "text": text,
                "embedding_text": embedding_text,
                "headings": headings or ([meta["heading"]] if meta.get("heading") else []),
                "concepts": concepts,
                "section_label": meta.get("label", "content"),
                "chunk_index": chunk_index,
                "has_definition": meta.get("is_definition", False),
                "has_example": meta.get("is_example", False),
            }
        )
        chunk_id += 1

    for sec in sections:
        words = sec["text"].split()
        if not words:
            continue
        idx = 0
        local_index = 0
        while idx < len(words):
            take = min(MAX_CHUNK_WORDS - len(carry_words), len(words) - idx)
            piece = carry_words + words[idx : idx + take]
            idx += take
            if _word_count(" ".join(piece)) >= MIN_CHUNK_WORDS or idx >= len(words):
                text = " ".join(piece).strip()
                make_chunk(text, sec, local_index)
                local_index += 1
                overlap = piece[-OVERLAP_WORDS:] if len(piece) > OVERLAP_WORDS else []
                carry_words = overlap
            else:
                carry_words = piece

    if carry_words and _word_count(" ".join(carry_words)) >= 10:
        make_chunk(
            " ".join(carry_words),
            {"label": "content", "heading": "", "is_definition": False, "is_example": False},
            999,
        )
    return chunks


def build_page_chunks(
    page_text: str,
    page_number: int,
    pdf_name: str,
    headings: list[str],
    concepts: list[str],
    start_id: int,
) -> list[dict[str, Any]]:
    sections = split_into_sections(page_text)
    sections = merge_short_sections(sections)
    if not sections:
        sections = [{"label": "content", "heading": "", "text": page_text, "is_example": False, "is_definition": False}]
    return pack_sections_into_chunks(sections, page_number, pdf_name, headings, concepts, start_id)
