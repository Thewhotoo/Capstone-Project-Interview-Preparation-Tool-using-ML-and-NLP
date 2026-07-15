import fitz  # PyMuPDF
import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

# Load the same model used in engine.py
model = SentenceTransformer('all-MiniLM-L6-v2')

# Absolute path to knowledge_base directory (relative to this file)
_RAG_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_KB_DIR = os.path.join(_RAG_BASE_DIR, "knowledge_base")


def ingest_subject(pdf_path, subject_name):
    """
    Extract text from PDF, create embeddings, and build FAISS index.
    
    Args:
        pdf_path: Path to the PDF file
        subject_name: Name to save the index/chunks (e.g., 'cn_unit1')
    """
    # 1. Create the knowledge_base folder if it doesn't exist
    os.makedirs(_KB_DIR, exist_ok=True)

    # Check if PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    
    print(f"Extracting text from: {pdf_path}...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return False
    
    slide_texts = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text and len(text) > 20:
            slide_texts.append({"id": i, "page": i + 1, "text": text})

    if not slide_texts:
        print("No text extracted from PDF")
        return False

    print(f"Extracted {len(slide_texts)} pages with content")
    print(f"Encoding {len(slide_texts)} pages into vectors...")
    
    texts_only = [s['text'] for s in slide_texts]
    embeddings = model.encode(texts_only, show_progress_bar=True)

    # 2. Save the FAISS Index
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings).astype('float32'))
    index_path = os.path.join(_KB_DIR, f"{subject_name}.index")
    faiss.write_index(index, index_path)

    # 3. Save the Text Chunks
    chunks_path = os.path.join(_KB_DIR, f"{subject_name}_chunks.json")
    with open(chunks_path, "w", encoding='utf-8') as f:
        json.dump(slide_texts, f, indent=2, ensure_ascii=False)

    print(f"Success! Index saved: {index_path}, Chunks saved: {chunks_path}")
    
    return True

if __name__ == "__main__":
    # Point to your CN PDF and give it a subject name
    ingest_subject("samples/CN_UNIT1_MERGE.pdf", "cn_unit1")