"""One call: audio + transcript (+ context) -> tone + reading-detection report."""
from __future__ import annotations

import numpy as np

from . import prosody, reading, textfeat
from .vtypes import Transcript


def analyze(audio: np.ndarray, tr: Transcript, ctx: dict | None = None,
            refs: list[str] | None = None, baseline: dict | None = None) -> dict:
    ctx = ctx or {}
    p = prosody.analyze(audio, tr.words, baseline)
    tf = textfeat.text_features(tr.text)
    return {
        "prosody": p,
        "tone": prosody.describe(p, tf),
        "reading": reading.assess(tr.text, p, tf, ctx, refs),
        "text_stats": {k: round(v, 2) if isinstance(v, float) else v for k, v in tf.items()},
    }
