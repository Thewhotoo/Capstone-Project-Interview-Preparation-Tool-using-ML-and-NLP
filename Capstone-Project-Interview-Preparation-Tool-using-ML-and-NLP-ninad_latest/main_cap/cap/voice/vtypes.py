"""Shared value types for the voice package."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    prob: float = 1.0


@dataclass
class Transcript:
    text: str
    words: list[Word] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0
