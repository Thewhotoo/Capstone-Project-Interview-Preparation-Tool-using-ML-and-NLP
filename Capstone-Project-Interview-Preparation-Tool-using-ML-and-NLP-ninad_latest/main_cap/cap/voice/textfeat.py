"""Text-side features of a spoken answer: disfluency, hedging, register, overlap."""
from __future__ import annotations

import re

_TOK = re.compile(r"[a-z0-9']+")
FILLER_RE = re.compile(r"\b(?:u+h+m*|u+m+|e+r+m*|a+h+m*|h+m+|mm+h*|you know|like(?=,))\b", re.I)
HEDGE_RE = re.compile(
    r"\b(?:i think|i guess|i believe|i suppose|maybe|perhaps|probably|sort of|kind of|"
    r"not (?:really |entirely )?sure|something like)\b", re.I)
RESTART_RE = re.compile(
    r"\b(?:i mean|sorry|let me (?:rephrase|start over|think)|what i meant|actually,? (?:no|wait)|"
    r"wait,? no|or rather)\b", re.I)
CONTRACTION_RE = re.compile(r"\b[a-z]+'(?:t|s|re|ve|ll|d|m)\b", re.I)
CONNECTIVE_RE = re.compile(
    r"\b(?:furthermore|moreover|additionally|in addition|consequently|therefore|thus|hence|"
    r"in conclusion|to summari[sz]e|in summary|firstly|secondly|thirdly|finally|"
    r"plays? a (?:crucial|vital|key) role|is defined as|refers to|it is (?:important|essential) to|"
    r"can be defined|is a fundamental)\b", re.I)
FIRST_PERSON = frozenset({"i", "my", "me", "we", "our", "i'm", "i've", "i'd", "i'll", "myself", "mine"})


def tokens(text: str) -> list[str]:
    return _TOK.findall((text or "").lower().replace("\u2019", "'"))


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s]


def _repetitions(t: list[str]) -> int:
    n = sum(1 for i in range(len(t) - 1) if t[i] == t[i + 1] and t[i] not in {"had", "that"})
    return n + sum(1 for i in range(len(t) - 3) if t[i:i + 2] == t[i + 2:i + 4])


def text_features(text: str) -> dict:
    text = (text or "").replace("\u2019", "'")
    toks = tokens(text)
    n = len(toks)
    sents = sentences(text)
    per100 = (lambda c: 100.0 * c / n) if n else (lambda c: 0.0)
    fillers = len(FILLER_RE.findall(text))
    reps = _repetitions(toks)
    restarts = len(RESTART_RE.findall(text))
    fp = sum(1 for t in toks if t in FIRST_PERSON)
    return {
        "words": n,
        "sentences": len(sents),
        "avg_sentence_len": n / len(sents) if sents else 0.0,
        "fillers": fillers,
        "repetitions": reps,
        "restarts": restarts,
        "disfluency_per100": per100(fillers + reps + restarts),
        "filler_per100": per100(fillers),
        "hedge_per100": per100(len(HEDGE_RE.findall(text))),
        "contractions": len(CONTRACTION_RE.findall(text)),
        "connective_per100": per100(len(CONNECTIVE_RE.findall(text))),
        "first_person_ratio": fp / n if n else 0.0,
    }


def _shingles(toks: list[str], n: int) -> set[tuple]:
    return set(zip(*[toks[i:] for i in range(n)])) if len(toks) >= n else set()


def ngram_containment(text: str, references: list[str], n: int = 4) -> float:
    """Fraction of the answer's n-grams that appear verbatim in any reference."""
    a = _shingles(tokens(text), n)
    if not a or not references:
        return 0.0
    ref: set[tuple] = set()
    for r in references:
        ref |= _shingles(tokens(r), n)
    return len(a & ref) / len(a)
