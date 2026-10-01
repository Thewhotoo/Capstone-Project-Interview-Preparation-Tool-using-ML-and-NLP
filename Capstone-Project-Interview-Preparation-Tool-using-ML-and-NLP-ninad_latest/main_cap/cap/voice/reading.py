"""Reading-from-script detection.

Fuses audio evidence (steady rate, punctuation-aligned pauses, no hesitation,
flat delivery, long-silence-then-fluency), text evidence (written register,
verbatim overlap with reference material, missing first-person ownership) and
optional gaze evidence into a 0..1 score. Each signal is (evidence 0..1,
weight); missing signals are skipped, not treated as neutral.

This is a heuristic indicator, not proof: rehearsed/memorised answers and
non-native speakers can trigger it. Thresholds are starting points; tune
SIGNAL_WEIGHTS / LABEL_* on recorded samples.
"""
from __future__ import annotations

import math

from .textfeat import ngram_containment

MIN_WORDS, MIN_SECONDS = 15, 6.0
LABEL_LIKELY, LABEL_POSSIBLE = 0.75, 0.50
SIGNAL_WEIGHTS = {
    "steady_rate": 1.0, "no_disfluency": 1.0, "punctuated_pauses": 1.2, "no_hesitation": 0.8,
    "flat_pitch": 0.6, "flat_energy": 0.3, "gaze_off_screen": 0.8, "latency_then_fluent": 0.5,
    "reference_overlap": 2.0, "written_register": 0.8, "no_ownership": 0.5,
}


def _c(x: float) -> float:
    return min(1.0, max(0.0, x))


def _signals(tf: dict, p: dict, ctx: dict, refs: list[str], text: str) -> dict[str, tuple[float, str]]:
    n, s = tf["words"], {}
    if p.get("rate_cv") is not None:
        s["steady_rate"] = (_c((0.30 - p["rate_cv"]) / 0.18), f"speaking speed barely varies (CV {p['rate_cv']:.2f})")
    if n >= 40:
        s["no_disfluency"] = (_c(1 - tf["disfluency_per100"] / 3), f"almost no fillers, repeats or restarts ({tf['disfluency_per100']:.1f}/100 words)")
    if p.get("boundary_pause_alignment") is not None:
        s["punctuated_pauses"] = (_c((p["boundary_pause_alignment"] - 0.6) / 0.35),
                                  f"{p['boundary_pause_alignment']:.0%} of pauses fall exactly on punctuation")
    if p.get("pause_count") is not None:
        s["no_hesitation"] = (_c(1 - p["long_midclause_per_min"] / 3), "no mid-sentence hesitations")
    if p.get("pitch_std_st") is not None:
        s["flat_pitch"] = (_c((3.0 - p["pitch_std_st"]) / 1.8), f"flat, read-aloud pitch ({p['pitch_std_st']:.1f} st)")
    if p.get("energy_std_db") is not None:
        s["flat_energy"] = (_c((8.0 - p["energy_std_db"]) / 4.0), "uniform loudness")
    g = ctx.get("gaze_away_ratio")
    if isinstance(g, (int, float)):
        s["gaze_off_screen"] = (_c(g / 0.4), f"looked away from the screen {g:.0%} of the answer")
    lat = (ctx.get("response_latency_s") or 0) + (p.get("onset_s") or 0)
    if lat and n >= 40:
        s["latency_then_fluent"] = (_c((lat - 4) / 8) * _c(1 - tf["disfluency_per100"] / 2),
                                    f"{lat:.0f}s of silence, then unbroken fluent speech")
    if refs:
        c = ngram_containment(text, refs)
        s["reference_overlap"] = (_c((c - 0.10) / 0.25), f"{c:.0%} of the answer's 4-word phrases appear verbatim in the source material")
    if n >= 40:
        reg = [_c((tf["avg_sentence_len"] - 16) / 14), _c(tf["connective_per100"] / 2),
               1.0 if (tf["contractions"] == 0 and n >= 60) else 0.0]
        s["written_register"] = (sum(reg) / 3, "written rather than spoken phrasing (long sentences, formal connectives, no contractions)")
    if ctx.get("kind") == "resume" and n >= 50:
        s["no_ownership"] = (1.0 if tf["first_person_ratio"] < 0.01 else 0.0, "a project answer with almost no 'I' / 'we' ownership")
    return s


def assess(text: str, p: dict, tf: dict, ctx: dict | None = None, refs: list[str] | None = None) -> dict:
    ctx, refs = ctx or {}, refs or []
    if tf["words"] < MIN_WORDS or (p.get("duration_s") or 0) < MIN_SECONDS:
        return {"label": "insufficient_data", "score": None, "confidence": 0.0, "reasons": [], "signals": {}}
    sig = _signals(tf, p, ctx, refs, text)
    wsum = sum(SIGNAL_WEIGHTS[k] for k in sig)
    raw = sum(SIGNAL_WEIGHTS[k] * v for k, (v, _) in sig.items()) / wsum
    score = 1 / (1 + math.exp(-8 * (raw - 0.55)))
    label = "likely_reading" if score >= LABEL_LIKELY else "possible_reading" if score >= LABEL_POSSIBLE else "natural_speech"
    reasons = [msg for k, (v, msg) in sorted(sig.items(), key=lambda kv: -SIGNAL_WEIGHTS[kv[0]] * kv[1][0])
               if v >= 0.7][:4] if label != "natural_speech" else []
    coverage = wsum / sum(SIGNAL_WEIGHTS.values())
    return {
        "label": label, "score": round(score, 3), "raw": round(raw, 3),
        "confidence": round(min(1.0, tf["words"] / 80) * coverage, 2),
        "reasons": reasons,
        "signals": {k: round(v, 2) for k, (v, _) in sig.items()},
    }


def summarize(records: list[dict]) -> dict:
    """Aggregate per-answer analyses (from routes) into a session-level view."""
    scored = [r for r in records if r["reading"]["score"] is not None]
    flagged = [r for r in scored if r["reading"]["label"] != "natural_speech"]

    def avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "answers": len(records), "assessed": len(scored), "flagged": len(flagged),
        "likely_reading": sum(1 for r in scored if r["reading"]["label"] == "likely_reading"),
        "mean_reading_score": avg([r["reading"]["score"] for r in scored]),
        "mean_confidence": avg([r["tone"]["confidence"] for r in records]),
        "mean_wpm": avg([r["prosody"].get("wpm") for r in records]),
        "pitch_variation": _mode([r["tone"]["pitch_variation"] for r in records]),
        "pace": _mode([r["tone"]["pace"] for r in records]),
        "tips": sorted({t for r in records for t in r["tone"]["tips"]})[:4],
        "per_answer": [{"n": i + 1, "label": r["reading"]["label"], "score": r["reading"]["score"],
                        "reasons": r["reading"]["reasons"], "confidence": r["tone"]["confidence_label"]}
                       for i, r in enumerate(records)],
    }


def _mode(vals):
    vals = [v for v in vals if v]
    return max(set(vals), key=vals.count) if vals else None
