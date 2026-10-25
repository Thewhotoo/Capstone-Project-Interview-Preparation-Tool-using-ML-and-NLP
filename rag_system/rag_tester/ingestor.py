import os
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
import fitz
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

# Chunking parameters
CHUNK_SIZE = 500          # target words per chunk
OVERLAP = 100             # overlap words (not used in section‑based chunking, kept for compatibility)
MIN_SECTION_WORDS = 100   # merge sections below this size

_model = None

def get_model():
    global _model
    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def discover_pdfs():
    return sorted(SAMPLES_DIR.glob("*.pdf"))

def get_subject_name(pdf_path):
    return pdf_path.stem.lower()

def get_pdf_hash(pdf_path):
    sha256 = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def get_subject_directory(subject):
    subject_dir = KNOWLEDGE_BASE_DIR / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    return subject_dir

def needs_rebuild(subject_dir, pdf_hash):
    metadata_file = subject_dir / "metadata.json"
    if not metadata_file.exists():
        return True
    chunks_file = subject_dir / "chunks.json"
    index_file = subject_dir / "index.faiss"
    if not chunks_file.exists():
        return True
    if not index_file.exists():
        return True
    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        return metadata.get("pdf_hash") != pdf_hash
    except Exception:
        return True

def clean_slide_text(text):
    """
    Clean slide text during ingestion.
    Removes slide numbers, page markers, and other noise,
    but keeps definition/example labels and headings.
    """
    lines = text.split('\n')
    # Patterns that indicate entire lines to drop (noise)
    noise_patterns = [
        r'^Object Oriented Analysis and Design.*$',
        r'^Name:.*$',
        r'^Problem:.*$',
        r'^Solution:.*$',
        r'^contd\.{0,2}$',
        r'^Page \d+$',
        r'^Chapter \d+$',
        r'^Slide \d+$',
        r'^[•\-*]\s*$',                  # empty bullet
        r'^[•\-*]\s*(Definition|Problem|Solution|Name):?$',  # keep only if followed by content
    ]
    # But we want to keep lines that start with "Definition:" or "Example:" etc.
    # So we modify: we only drop lines that exactly match noise patterns and have no content.
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        skip = False
        for pattern in noise_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                # If the line is just the label (e.g., "Definition:"), we keep it if it has content?
                # Actually, we want to keep the label along with its content.
                # We'll keep lines that are just labels, because they will be attached to content.
                # However, we remove lines that are just "Definition:" without following content.
                # But that's hard to know now, so we keep all lines except pure noise.
                # We'll skip only if the line matches exactly and is very short.
                if len(line.split()) <= 2:
                    skip = True
                    break
        if skip:
            continue
        # Remove bullet symbols and common prefixes
        line = re.sub(r'^[•\-*]\s*', '', line)
        # Keep "Definition:", "Example:" etc. as is (we will use them for detection later)
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

def is_heading(line):
    """Heuristic to detect a heading line."""
    line = line.strip()
    if not line:
        return False
    # Long lines are unlikely headings
    if len(line) > 80:
        return False
    # All caps phrase
    if re.match(r'^[A-Z][A-Z\s]+$', line):
        return True
    # Phrase with colon, first word capital, and not too long
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

def is_definition(line):
    """Detect definition lines."""
    line = line.strip()
    return re.match(r'^(Definition|Def|Def\.|Definition:)\s*', line, re.IGNORECASE) is not None

def is_example(line):
    """Detect example lines."""
    line = line.strip()
    return re.match(r'^(Example|Ex|Ex\.|Example:)\s*', line, re.IGNORECASE) is not None

def parse_paragraphs(text, page_num):
    """
    Split text into paragraphs and classify each.
    Returns list of dicts: {type, content, page}.
    """
    paragraphs = re.split(r'\n\s*\n', text.strip())
    parsed = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Determine type
        lines = para.split('\n')
        # If paragraph consists of a single line, classify it
        if len(lines) == 1:
            line = lines[0].strip()
            if is_heading(line):
                parsed.append({'type': 'heading', 'content': line, 'page': page_num})
            elif is_definition(line):
                parsed.append({'type': 'definition', 'content': line, 'page': page_num})
            elif is_example(line):
                parsed.append({'type': 'example', 'content': line, 'page': page_num})
            else:
                parsed.append({'type': 'normal', 'content': line, 'page': page_num})
        else:
            # Multi-line paragraph: we don't classify the whole as heading/definition/example
            # We'll keep as normal, but we can check if first line is a label
            first = lines[0].strip()
            if is_definition(first) or is_example(first):
                # Treat the whole paragraph as definition/example
                kind = 'definition' if is_definition(first) else 'example'
                parsed.append({'type': kind, 'content': para, 'page': page_num})
            else:
                parsed.append({'type': 'normal', 'content': para, 'page': page_num})
    return parsed

def build_sections(paragraphs):
    """
    Group paragraphs into sections based on headings.
    Returns list of sections: {heading, paragraphs (list of dicts), pages (set)}.
    """
    sections = []
    current_section = {'heading': None, 'paragraphs': [], 'pages': set()}
    for para in paragraphs:
        if para['type'] == 'heading':
            # Start a new section with this heading
            if current_section['paragraphs']:
                sections.append(current_section)
            current_section = {'heading': para['content'], 'paragraphs': [], 'pages': set()}
        else:
            current_section['paragraphs'].append(para)
            current_section['pages'].add(para['page'])
    if current_section['paragraphs']:
        sections.append(current_section)
    return sections

def merge_short_sections(sections, min_words=MIN_SECTION_WORDS):
    """
    Merge a section into the previous one if its total word count < min_words.
    """
    if not sections:
        return sections
    merged = []
    for sec in sections:
        # Count words in all paragraph contents
        total_words = sum(len(p['content'].split()) for p in sec['paragraphs'])
        if total_words < min_words and merged:
            # Merge with previous section
            prev = merged[-1]
            prev['paragraphs'].extend(sec['paragraphs'])
            prev['pages'].update(sec['pages'])
            # Keep the heading of the previous section (or if previous had no heading, use this one? Not needed)
        else:
            merged.append(sec)
    return merged

def create_chunks_from_section(section, chunk_size=CHUNK_SIZE):
    """
    Create chunks from a section, preserving atomic paragraphs (definition/example).
    Returns list of chunks, each with: text, headings (list), pages (list), concepts, etc.
    """
    heading = section['heading']
    paragraphs = section['paragraphs']
    pages = sorted(section['pages'])
    if not paragraphs:
        return []

    # Combine all paragraph contents into a single text for overall concept extraction
    full_text = ' '.join(p['content'] for p in paragraphs)
    headings_list = [heading] if heading else []
    concepts = extract_concepts(full_text)  # use existing function

    # We'll split by paragraphs, but keep atomic types together.
    # We'll accumulate paragraphs until adding next would exceed chunk_size.
    # But we also want to avoid splitting a definition/example paragraph.
    chunks = []
    current_chunk_paragraphs = []
    current_word_count = 0

    for para in paragraphs:
        para_words = len(para['content'].split())
        # If adding this paragraph would exceed chunk_size and we already have something,
        # finalize current chunk and start a new one.
        if current_chunk_paragraphs and current_word_count + para_words > chunk_size:
            # If the current paragraph is atomic (definition/example), we might want to start a new chunk with it,
            # but we also need to decide if we should split earlier.
            # To keep atomic, we start a new chunk with this paragraph.
            # But if the current chunk is too small, we could merge? We'll handle merging later.
            chunk_text = ' '.join(p['content'] for p in current_chunk_paragraphs)
            chunk_pages = sorted({p['page'] for p in current_chunk_paragraphs})
            # Add heading to text if present
            if heading:
                chunk_text = f"Heading: {heading}\n{chunk_text}"
            chunks.append({
                'text': chunk_text,
                'headings': headings_list,
                'pages': chunk_pages,
                'concepts': concepts,  # same for all chunks from this section
                'embedding_text': chunk_text  # we'll enrich later
            })
            # Start new chunk with current paragraph
            current_chunk_paragraphs = [para]
            current_word_count = para_words
        else:
            current_chunk_paragraphs.append(para)
            current_word_count += para_words

    # Add remaining
    if current_chunk_paragraphs:
        chunk_text = ' '.join(p['content'] for p in current_chunk_paragraphs)
        chunk_pages = sorted({p['page'] for p in current_chunk_paragraphs})
        if heading:
            chunk_text = f"Heading: {heading}\n{chunk_text}"
        chunks.append({
            'text': chunk_text,
            'headings': headings_list,
            'pages': chunk_pages,
            'concepts': concepts,
            'embedding_text': chunk_text
        })

    return chunks

def extract_chunks(pdf_path):
    """
    Extract text, build sections, create chunks preserving headings, definitions, examples.
    """
    print(f"Extracting text from {pdf_path.name}...")
    doc = fitz.open(pdf_path)
    all_paragraphs = []

    for page_number in range(1, len(doc) + 1):
        page = doc[page_number - 1]
        text = page.get_text("text")
        if not text.strip():
            continue
        # Clean noise
        cleaned = clean_slide_text(text)
        # Parse into paragraphs with classification
        parsed = parse_paragraphs(cleaned, page_number)
        all_paragraphs.extend(parsed)

    doc.close()

    # Build sections from parsed paragraphs
    sections = build_sections(all_paragraphs)
    # Merge short sections
    sections = merge_short_sections(sections)

    # Create chunks from each section
    all_chunks = []
    for sec in sections:
        chunks = create_chunks_from_section(sec)
        all_chunks.extend(chunks)

    # Enrich embedding_text with headings and concepts (already included in text)
    # We'll also add concepts explicitly to embedding_text for better retrieval
    for chunk in all_chunks:
        if chunk['headings']:
            heading_text = "Heading: " + ", ".join(chunk['headings'])
            chunk['embedding_text'] = f"{heading_text} | {chunk['text']}"
        else:
            chunk['embedding_text'] = chunk['text']
        # Optionally add concepts
        if chunk['concepts']:
            concepts_text = "Concepts: " + ", ".join(chunk['concepts'])
            chunk['embedding_text'] = f"{chunk['embedding_text']} | {concepts_text}"

    # Assign IDs and page numbers
    for idx, chunk in enumerate(all_chunks):
        chunk['id'] = idx
        chunk['page'] = chunk['pages'][0]  # primary page (first)
        # Keep pages list for reference
        chunk['pages'] = chunk['pages']  # already there

    return all_chunks

# The following functions remain unchanged:
# build_embeddings, build_faiss_index, save_index, save_chunks, save_metadata, process_pdf, ingest_all

def build_embeddings(chunks):
    print("Generating embeddings...")
    model = get_model()
    texts = [chunk["embedding_text"] for chunk in chunks]
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    faiss.normalize_L2(embeddings)
    return embeddings.astype(np.float32)

def build_faiss_index(embeddings):
    print("Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    return index

def save_index(subject_dir, index):
    index_file = subject_dir / "index.faiss"
    faiss.write_index(index, str(index_file))
    return index_file

def save_chunks(subject_dir, chunks):
    chunks_file = subject_dir / "chunks.json"
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    return chunks_file

def save_metadata(subject_dir, subject, pdf_path, pdf_hash, chunks):
    total_headings = sum(len(chunk.get("headings", [])) for chunk in chunks)
    total_concepts = sum(len(chunk.get("concepts", [])) for chunk in chunks)
    pages = set()
    for chunk in chunks:
        pages.update(chunk.get("pages", []))
    metadata = {
        "subject": subject,
        "pdf": pdf_path.name,
        "pdf_hash": pdf_hash,
        "pages": len(pages),
        "chunks": len(chunks),
        "total_headings": total_headings,
        "total_concepts": total_concepts,
        "embedding_model": "all-MiniLM-L6-v2",
        "chunking_strategy": "section_based_heading_definition_example",
        "embedding_type": "normalized_cosine",
        "created_at": datetime.now().isoformat()
    }
    metadata_file = subject_dir / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    return metadata_file

def process_pdf(pdf_path):
    subject = get_subject_name(pdf_path)
    subject_dir = get_subject_directory(subject)
    pdf_hash = get_pdf_hash(pdf_path)
    
    if not needs_rebuild(subject_dir, pdf_hash):
        print(f"✓ {subject} already up to date.")
        print()
        return
    
    print(f"Rebuilding {subject}...")
    chunks = extract_chunks(pdf_path)
    embeddings = build_embeddings(chunks)
    index = build_faiss_index(embeddings)
    index_file = save_index(subject_dir, index)
    print(f"Embeddings Shape : {embeddings.shape}")
    print()
    chunks_file = save_chunks(subject_dir, chunks)
    metadata_file = save_metadata(subject_dir, subject, pdf_path, pdf_hash, chunks)
    
    print()
    print("=" * 60)
    print(f"Subject      : {subject}")
    print(f"PDF          : {pdf_path.name}")
    print(f"Hash         : {pdf_hash[:16]}...")
    pages = set()
    for chunk in chunks:
        pages.update(chunk.get("pages", []))
    print(f"Pages        : {len(pages)}")
    print(f"Chunks       : {len(chunks)}")
    print(f"Chunks File  : {chunks_file.name}")
    print(f"Index File   : {index_file.name}")
    print(f"Metadata     : {metadata_file.name}")
    total_headings = sum(len(chunk.get("headings", [])) for chunk in chunks)
    total_concepts = sum(len(chunk.get("concepts", [])) for chunk in chunks)
    print(f"Total Headings: {total_headings}")
    print(f"Total Concepts: {total_concepts}")
    print("=" * 60)
    print()

def ingest_all():
    pdfs = discover_pdfs()
    print(f"\nFound {len(pdfs)} PDF(s).\n")
    for pdf in pdfs:
        process_pdf(pdf)

if __name__ == "__main__":
    ingest_all()