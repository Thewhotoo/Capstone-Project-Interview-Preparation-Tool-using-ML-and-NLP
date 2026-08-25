"""Enhanced ingestor: multi-PDF subjects, OCR, slide-aware chunking with hybrid splitting."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import faiss
import fitz
import numpy as np
from sentence_transformers import SentenceTransformer

from bm25_utils import save_bm25_meta
from diagram_ingestor import ingest_diagrams_for_subject

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

# Chunking parameters
CHUNK_SIZE = 500          # target words per chunk (for long pages)
OVERLAP = 100             # overlap words for semantic chunking
MERGE_THRESHOLD_WORDS = 100   # merge chunks below this size

_model = None


def get_model():
    global _model
    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _ocr_page(page) -> str:
    """OCR fallback for scanned pages."""
    try:
        import pytesseract
        from PIL import Image
        import io

        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def extract_page_text(page) -> str:
    """Get text from page, with OCR fallback if needed."""
    text = page.get_text("text").strip()
    if len(text) < 20:
        ocr = _ocr_page(page)
        if len(ocr.strip()) >= 20:
            return ocr.strip()
    return text


def clean_slide_text(text: str) -> str:
    """
    Remove page markers, footers, and other noise from slide text.
    Keeps slide titles and content intact.
    """
    lines = text.split('\n')
    # Patterns to remove entirely (footer, page markers, etc.)
    noise_patterns = [
        r'^=+\s*Page\s+\d+\s*=+$',          # page marker
        r'^Team Networks.*$',               # footer
        r'^Department of Computer Science and Engineering.*$',
        r'^THANK YOU$',
        r'^COMPUTER NETWORKS$',             # sometimes repeated title; keep if it's the first line though
    ]
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        skip = False
        for pat in noise_patterns:
            if re.match(pat, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue
        # Remove trailing slide numbers like " - 1 -" etc.
        line = re.sub(r'\s*[-–]\s*\d+\s*[-–]\s*$', '', line)
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def is_heading(line: str) -> bool:
    """Heuristic to detect a slide heading."""
    line = line.strip()
    if not line or len(line) > 80:
        return False
    # All caps phrase
    if re.match(r'^[A-Z][A-Z\s]+$', line):
        return True
    # Phrase with colon, first word capital
    if ':' in line and not line.endswith(':'):
        heading = line.split(':')[0].strip()
        if len(heading.split()) >= 2 and len(heading) > 5 and heading[0].isupper():
            return True
    # Short phrase (2-4 words) with first letter capital, not ending in punctuation
    words = line.split()
    if 2 <= len(words) <= 4 and len(line) > 8:
        if line[0].isupper() and not line.endswith(('.', '?', '!')):
            if not line.lower().startswith(('the', 'a', 'an')):
                return True
    return False


def is_definition(line: str) -> bool:
    """Detect definition lines."""
    return re.match(r'^(Definition|Def|Def\.|Definition:)\s*', line.strip(), re.IGNORECASE) is not None


def is_example(line: str) -> bool:
    """Detect example lines."""
    return re.match(r'^(Example|Ex|Ex\.|Example:)\s*', line.strip(), re.IGNORECASE) is not None


def semantic_chunking(text: str, heading: str, chunk_size=CHUNK_SIZE, overlap=OVERLAP) -> list[str]:
    """
    Split long text into overlapping chunks, preserving paragraph boundaries.
    Prepend the heading to every chunk.
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_words = len(para.split())
        # If adding this paragraph would exceed chunk size and we already have content,
        # finalize current chunk and start a new one with overlap.
        if current and current_len + para_words > chunk_size:
            chunk_text = ' '.join(current)
            if heading:
                chunk_text = f"Heading: {heading}\n{chunk_text}"
            chunks.append(chunk_text)

            # Keep overlap: retain last few paragraphs that fit within overlap
            overlap_parts = []
            overlap_len = 0
            for p in reversed(current):
                p_len = len(p.split())
                if overlap_len + p_len <= overlap:
                    overlap_parts.insert(0, p)
                    overlap_len += p_len
                else:
                    break
            current = overlap_parts
            current_len = overlap_len

        current.append(para)
        current_len += para_words

    # Last chunk
    if current:
        chunk_text = ' '.join(current)
        if heading:
            chunk_text = f"Heading: {heading}\n{chunk_text}"
        chunks.append(chunk_text)

    return chunks


def extract_headings(text: str) -> list[str]:
    """Extract potential headings from text (for enrichment)."""
    headings = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or len(line) > 80:
            continue
        if re.match(r'^[A-Z][A-Z\s]+$', line):
            headings.append(line.title())
        elif 2 <= len(line.split()) <= 6 and line[0].isupper() and not line.endswith(('.', '?', '!')):
            headings.append(line)
    seen, out = set(), []
    for h in headings:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out[:10]


def extract_concepts(text: str) -> list[str]:
    """Extract important concepts (bullet points or short phrases)."""
    concepts = []
    for line in text.split('\n'):
        line = line.strip()
        m = re.match(r'^[•\-*]\s*(.+)$', line)
        if m and 2 <= len(m.group(1).split()) <= 6:
            concepts.append(m.group(1).strip())
    return list(dict.fromkeys(concepts))[:10]


def discover_subject_pdfs() -> dict[str, list[Path]]:
    """
    Group PDFs:
      - samples/subject/*.pdf
      - samples/subject.pdf (single PDF, subject from stem)
    """
    groups: dict[str, list[Path]] = {}
    if not SAMPLES_DIR.exists():
        return groups
    # Subfolders
    for sub in sorted(SAMPLES_DIR.iterdir()):
        if sub.is_dir():
            pdfs = sorted(sub.glob("*.pdf"))
            if pdfs:
                groups[sub.name.lower()] = pdfs
    # Top-level PDFs
    for pdf in sorted(SAMPLES_DIR.glob("*.pdf")):
        stem = pdf.stem.lower()
        subject = stem.split("_")[0] if "_" in stem else stem
        groups.setdefault(subject, []).append(pdf)
    # Deduplicate
    for k in groups:
        groups[k] = sorted(set(groups[k]))
    return groups


def subject_hash(pdfs: list[Path]) -> str:
    h = hashlib.sha256()
    for pdf in sorted(pdfs, key=lambda p: p.name):
        with open(pdf, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
    return h.hexdigest()


def needs_rebuild(subject_dir: Path, pdf_hash: str) -> bool:
    meta_file = subject_dir / "metadata.json"
    if not (meta_file.exists() and (subject_dir / "chunks.json").exists() and (subject_dir / "index.faiss").exists()):
        return True
    if not (subject_dir / "diagram_chunks.json").exists():
        # text index is up to date but diagrams haven't been ingested yet
        # (e.g. diagram pipeline was added after this subject was first built)
        return True
    try:
        with open(meta_file) as f:
            return json.load(f).get("pdf_hash") != pdf_hash
    except Exception:
        return True


def extract_chunks_from_pdfs(pdfs: list[Path]) -> list[dict]:
    """
    Process each PDF page with slide‑aware hybrid chunking.
    Returns a list of chunk dicts with keys: id, page, text, embedding_text, headings, concepts.
    """
    all_chunks = []
    chunk_id = 0

    for pdf_path in pdfs:
        print(f"Extracting {pdf_path.name}...")
        doc = fitz.open(pdf_path)
        page_chunks = []   # temporary list for this PDF (for merging)

        for page_number in range(1, len(doc) + 1):
            page = doc[page_number - 1]
            raw = extract_page_text(page)
            if len(raw) < 20:
                continue

            cleaned = clean_slide_text(raw)
            if not cleaned:
                continue

            # Detect heading for this slide
            lines = [ln.strip() for ln in cleaned.split('\n') if ln.strip()]
            heading = None
            for line in lines:
                if is_heading(line):
                    heading = line
                    break
            if not heading:
                heading = f"Slide {page_number}"

            # Extract additional headings and concepts for enrichment
            extra_headings = extract_headings(raw)
            concepts = extract_concepts(raw)

            # Combine all headings (primary + extra)
            all_headings = [heading] + [h for h in extra_headings if h != heading]
            all_headings = list(dict.fromkeys(all_headings))  # unique, preserve order

            word_count = len(cleaned.split())

            if word_count > CHUNK_SIZE:
                # Long page: split semantically with overlap
                sub_chunks = semantic_chunking(cleaned, heading, CHUNK_SIZE, OVERLAP)
                for sub_text in sub_chunks:
                    # Build embedding text with heading and concepts
                    embed_parts = []
                    if all_headings:
                        embed_parts.append("Heading: " + ", ".join(all_headings))
                    if concepts:
                        embed_parts.append("Concepts: " + ", ".join(concepts))
                    embed_parts.append(sub_text)
                    embedding_text = " | ".join(embed_parts)

                    page_chunks.append({
                        "id": chunk_id,
                        "page": page_number,
                        "text": sub_text,
                        "embedding_text": embedding_text,
                        "headings": all_headings,
                        "concepts": concepts,
                    })
                    chunk_id += 1
            else:
                # Short/medium page: keep as a single chunk
                embed_parts = []
                if all_headings:
                    embed_parts.append("Heading: " + ", ".join(all_headings))
                if concepts:
                    embed_parts.append("Concepts: " + ", ".join(concepts))
                embed_parts.append(cleaned)
                embedding_text = " | ".join(embed_parts)

                page_chunks.append({
                    "id": chunk_id,
                    "page": page_number,
                    "text": cleaned,
                    "embedding_text": embedding_text,
                    "headings": all_headings,
                    "concepts": concepts,
                })
                chunk_id += 1

        doc.close()

        # After processing all pages of this PDF, merge very short consecutive chunks
        if len(page_chunks) > 1:
            merged = []
            i = 0
            while i < len(page_chunks):
                current = page_chunks[i]
                current_words = len(current['text'].split())
                if current_words < MERGE_THRESHOLD_WORDS and i + 1 < len(page_chunks):
                    next_chunk = page_chunks[i+1]
                    combined_text = current['text'] + "\n\n" + next_chunk['text']
                    combined_embedding = current['embedding_text'] + " | " + next_chunk['embedding_text']
                    combined_headings = list(dict.fromkeys(current['headings'] + next_chunk['headings']))
                    combined_concepts = list(dict.fromkeys(current['concepts'] + next_chunk['concepts']))
                    merged.append({
                        "id": len(merged),  # will reassign later
                        "page": current['page'],
                        "text": combined_text,
                        "embedding_text": combined_embedding,
                        "headings": combined_headings,
                        "concepts": combined_concepts,
                    })
                    i += 2
                else:
                    # keep current as is
                    current['id'] = len(merged)
                    merged.append(current)
                    i += 1
            page_chunks = merged

        # Add to global list and reassign final IDs
        for idx, chunk in enumerate(page_chunks):
            chunk['id'] = len(all_chunks) + idx
        all_chunks.extend(page_chunks)

    # Final reassign IDs (just in case)
    for idx, chunk in enumerate(all_chunks):
        chunk['id'] = idx

    return all_chunks


def build_embeddings(chunks):
    print("Generating embeddings...")
    model = get_model()
    texts = [c.get("embedding_text", c["text"]) for c in chunks]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)
    faiss.normalize_L2(embeddings)
    return embeddings.astype(np.float32)


def process_subject(subject: str, pdfs: list[Path]):
    subject_dir = KNOWLEDGE_BASE_DIR / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    pdf_hash = subject_hash(pdfs)
    if not needs_rebuild(subject_dir, pdf_hash):
        print(f"✓ {subject} up to date ({len(pdfs)} PDF(s)).")
        return

    print(f"Rebuilding {subject} from {len(pdfs)} PDF(s)...")
    chunks = extract_chunks_from_pdfs(pdfs)
    embeddings = build_embeddings(chunks)

    # Save FAISS index
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(subject_dir / "index.faiss"))

    # Save chunks
    with open(subject_dir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    # Save BM25 metadata (for hybrid retrieval)
    save_bm25_meta(subject_dir, chunks)

    # Extract, classify, and structure diagrams (runs automatically —
    # fails soft per-diagram, so a missing/unwired VLM never blocks text ingestion)
    print(f"Extracting diagrams for {subject}...")
    diagram_chunks = ingest_diagrams_for_subject([str(p) for p in pdfs], subject_dir)
    print(f"✓ {subject}: {len(diagram_chunks)} diagram(s) extracted and structured")

    # Save metadata
    metadata = {
        "subject": subject,
        "pdfs": [p.name for p in pdfs],
        "pdf_hash": pdf_hash,
        "pages": len({c["page"] for c in chunks}),
        "chunks": len(chunks),
        "diagram_chunks": len(diagram_chunks),
        "chunking_strategy": "slide_aware_hybrid_merge",
        "embedding_model": "all-MiniLM-L6-v2",
        "ocr_enabled": True,
        "created_at": datetime.now().isoformat(),
    }
    with open(subject_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ {subject}: {len(chunks)} chunks from {metadata['pages']} pages")


def ingest_all():
    groups = discover_subject_pdfs()
    if not groups:
        print("No PDFs found in samples/ or samples/<subject>/")
        return
    print(f"Found {len(groups)} subject(s).\n")
    for subject, pdfs in groups.items():
        process_subject(subject, pdfs)


if __name__ == "__main__":
    ingest_all()