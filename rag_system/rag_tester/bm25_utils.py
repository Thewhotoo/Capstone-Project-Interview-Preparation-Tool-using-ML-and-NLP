"""BM25 utilities for saving/loading and searching."""
import json
import pickle
from pathlib import Path
from rank_bm25 import BM25Okapi
import re

def tokenize(text):
    """Simple tokenizer: lowercase, remove punctuation, split."""
    text = re.sub(r'[^\w\s]', '', text.lower())
    return text.split()

def build_bm25(chunks):
    """Build BM25 index from list of chunk dicts."""
    tokenized_corpus = [tokenize(chunk["text"]) for chunk in chunks]
    return BM25Okapi(tokenized_corpus)

def save_bm25_meta(subject_dir, chunks):
    """Save BM25 index and tokenized corpus to subject folder."""
    bm25 = build_bm25(chunks)
    # Save the BM25 object (pickle) and the chunks for reference
    with open(subject_dir / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
    # Also save the tokenized corpus to rebuild if needed
    tokenized = [tokenize(chunk["text"]) for chunk in chunks]
    with open(subject_dir / "bm25_tokens.json", "w") as f:
        json.dump(tokenized, f)

def load_bm25_index(subject_dir):
    """Load BM25 index from subject folder."""
    pkl_path = subject_dir / "bm25.pkl"
    if not pkl_path.exists():
        return None
    with open(pkl_path, "rb") as f:
        return pickle.load(f)