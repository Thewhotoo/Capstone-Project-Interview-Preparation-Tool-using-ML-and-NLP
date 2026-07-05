import re
import json
import os

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)          # collapse whitespace
    text = re.sub(r'[^\x00-\x7F]+', ' ', text) # remove non-ASCII
    text = re.sub(r'http\S+', '', text)        # remove URLs
    return text.strip()

def truncate_text(text: str, max_words: int = 400) -> str:
    words = text.split()
    return " ".join(words[:max_words])