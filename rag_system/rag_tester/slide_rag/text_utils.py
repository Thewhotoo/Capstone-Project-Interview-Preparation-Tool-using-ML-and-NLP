"""Tokenisation shared by index building and querying.

The old retrieval tokenised the corpus with punctuation stripped but the
query with a bare .split(), so "deadlock?" never matched "deadlock". Using
one function on both sides fixes that.
"""
import re

_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "in", "on", "at", "to", "for",
    "and", "or", "it", "its", "this", "that", "these", "those", "with", "as", "by", "from", "what",
    "which", "how", "why", "when", "does", "do", "can", "you", "i", "we", "explain", "describe",
}


def bm25_tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:[+#][a-z0-9+#]*)?", text.lower()) if t not in _STOP]
