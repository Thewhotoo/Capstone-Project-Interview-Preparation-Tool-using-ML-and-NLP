import re
import json

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_text(text: str) -> str:
    """Collapse all whitespace (including newlines) into single spaces.
    Used for SBERT input where structure doesn't matter."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'http\S+', '', text)
    return text.strip()

def clean_text_structured(text: str) -> str:
    """Normalise whitespace but preserve newlines.
    Used for feature extraction where section structure matters."""
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'http\S+', '', text)
    # Fix word-boundary collapse from pdfplumber: insert space after comma
    # when sandwiched between letters (e.g. "Bangalore,Karnataka" → "Bangalore, Karnataka")
    text = re.sub(r'([a-zA-Z]),([a-zA-Z])', r'\1, \2', text)
    # Fix missing space before opening brackets (e.g. "ForGood.ai[..." → "ForGood.ai [...")
    text = re.sub(r'(\w)(\[)', r'\1 \2', text)
    # Fix letter↔digit concatenation from pdfplumber
    # "January2025" → "January 2025", "ClassXII" → "Class XII", "20212025" → "2021 2025"
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    # Collapse runs of spaces/tabs on each line, but keep the newlines
    lines = text.split('\n')
    lines = [re.sub(r'[^\S\n]+', ' ', line).strip() for line in lines]
    return '\n'.join(line for line in lines if line)

def truncate_text(text: str, max_words: int = 800) -> str:
    words = text.split()
    return " ".join(words[:max_words])