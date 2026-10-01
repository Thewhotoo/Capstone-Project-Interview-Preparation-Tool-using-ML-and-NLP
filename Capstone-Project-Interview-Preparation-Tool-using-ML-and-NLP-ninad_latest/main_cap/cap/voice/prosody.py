"""Prosody / tonality features from 16 kHz mono audio (+ optional word timings).

Pure numpy/scipy: FFT autocorrelation pitch tracker, energy, pause structure,
local speech-rate variability, terminal pitch slopes, and a coaching-oriented
tone description.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import medfilt

from .vtypes import Word

SR = 16_000
FRAME, HOP, NFFT = 1024, 256, 2048
F0_MIN, F0_MAX = 70.0, 400.0
PAUSE_MIN_S = 0.25
_BOUNDARY = (".", "?", "!", ",", ";", ":", "\u2026")
_SENT_END = (".", "?", "!")


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(min(hi, max(lo, x)))


def _r(x, nd: int = 3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def pitch_track(y: np.ndarray):
    """Return (f0_hz with NaN for unvoiced, frame_db, active_mask)."""
    y = np.asarray(y, dtype=np.float32)
    if len(y) < FRAME:
        y = np.pad(y, (0, FRAME - len(y)))
    fr = np.lib.stride_tricks.sliding_window_view(y, FRAME)[::HOP]
    n = len(fr)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    floor, peak = np.percentile(db, 10), np.percentile(db, 95)
    active = db > max(min(floor + 12.0, peak - 20.0), -60.0)   # peak-20 dB when there is no real silence

    win = np.hanning(FRAME).astype(np.float32)
    spec = np.fft.rfft(fr * win, NFFT, axis=1)
    ac = np.fft.irfft(spec.real ** 2 + spec.imag ** 2, NFFT, axis=1)[:, :FRAME]
    wspec = np.fft.rfft(win, NFFT)
    wac = np.fft.irfft(np.abs(wspec) ** 2, NFFT)[:FRAME]
    ac = ac / (ac[:, :1] + 1e-9) / (wac / wac[0] + 1e-9)[None, :]

    lo, hi = int(SR / F0_MAX), int(SR / F0_MIN)
    c = ac[:, lo - 1:hi + 2]
    mid = c[:, 1:-1]
    is_peak = (mid > c[:, :-2]) & (mid >= c[:, 2:])
    m = np.where(is_peak, mid, -1.0).max(1)
    cand = is_peak & (mid >= 0.9 * m[:, None])       # first strong peak -> avoids octave errors
    has, idx = cand.any(1), cand.argmax(1)
    rows = np.arange(n)
    a, b, d = c[rows, idx], c[rows, idx + 1], c[rows, idx + 2]
    delta = 0.5 * (a - d) / (a - 2 * b + d - 1e-9)
    lag = lo - 1 + idx + 1 + np.clip(delta, -1, 1)
    f0 = SR / lag
    f0[~(active & has & (b > 0.5))] = np.nan
    return f0, db, active


def _semitones(f0: np.ndarray) -> np.ndarray:
    v = f0[~np.isnan(f0)]
    if len(v) < 8:
        return np.full_like(f0, np.nan)
    st = 12 * np.log2(f0 / np.median(v))
    ok = ~np.isnan(st)
    sm = medfilt(st[ok], 5)
    bad = np.abs(st[ok] - sm) > 3.0          # octave jumps / tracking glitches
    tmp = st[ok]
    tmp[bad] = np.nan
    st[ok] = tmp
    return st


def _frame_t(i) -> np.ndarray:
    return (np.asarray(i) * HOP + FRAME / 2) / SR


def _pauses(words: list[Word]) -> list[tuple[float, bool]]:
    out = []
    for a, b in zip(words, words[1:]):
        gap = b.start - a.end
        if gap >= PAUSE_MIN_S:
            out.append((gap, a.text.strip().endswith(_BOUNDARY)))
    return out


def _local_rates(words: list[Word], win: int = 6) -> list[float]:
    rates = []
    for i in range(len(words) - win + 1):
        seg = words[i:i + win]
        dur = seg[-1].end - seg[0].start
        dur -= sum(max(0.0, b.start - a.end) for a, b in zip(seg, seg[1:]) if b.start - a.end >= PAUSE_MIN_S)
        if dur > 0.3:
            rates.append(win / dur)
    return rates


def _terminal_slopes(st: np.ndarray, words: list[Word]) -> list[float]:
    t = _frame_t(np.arange(len(st)))
    out = []
    for w in words:
        if not w.text.strip().endswith(_SENT_END) or w.text.strip().endswith("?"):
            continue
        m = (t >= w.end - 0.5) & (t <= w.end) & ~np.isnan(st)
        if m.sum() >= 8:
            out.append(float(np.polyfit(t[m], st[m], 1)[0]))
    return out


def analyze(y: np.ndarray, words: list[Word] | None = None, baseline: dict | None = None) -> dict:
    y = np.asarray(y, dtype=np.float32)
    dur = len(y) / SR
    f0, db, active = pitch_track(y)
    st = _semitones(f0)
    v = st[~np.isnan(st)]
    feats: dict = {"duration_s": _r(dur, 2), "speech_ratio": _r(active.mean())}

    if len(v) >= 10:
        feats.update(
            pitch_median_hz=_r(np.nanmedian(f0), 1),
            pitch_std_st=_r(v.std()),
            pitch_range_st=_r(np.percentile(v, 90) - np.percentile(v, 10)),
            voiced_ratio=_r(len(v) / max(1, active.sum())),
        )
    else:
        feats.update(pitch_median_hz=None, pitch_std_st=None, pitch_range_st=None, voiced_ratio=0.0)
    feats["energy_std_db"] = _r(db[active].std()) if active.sum() > 10 else None

    words = [w for w in (words or []) if w.end > w.start]
    if len(words) >= 3:
        pauses = _pauses(words)
        gaps = [g for g, _ in pauses]
        speech_time = (words[-1].end - words[0].start) - sum(gaps)
        rates = _local_rates(words)
        mins = max(dur, 1e-3) / 60
        mid = [g for g, at_b in pauses if not at_b]
        slopes = _terminal_slopes(st, words)
        feats.update(
            onset_s=_r(words[0].start, 2),
            wpm=_r(len(words) / mins, 1),
            articulation_wpm=_r(60 * len(words) / max(speech_time, 0.5), 1),
            rate_cv=_r(np.std(rates) / np.mean(rates)) if len(rates) >= 5 else None,
            pause_count=len(pauses),
            pauses_per_min=_r(len(pauses) / mins, 1),
            pause_ratio=_r(sum(gaps) / max(dur, 1e-3)),
            boundary_pause_alignment=_r(sum(1 for _, b in pauses if b) / len(pauses)) if len(pauses) >= 4 else None,
            long_midclause_pauses=sum(1 for g in mid if g >= 0.7),
            long_midclause_per_min=_r(sum(1 for g in mid if g >= 0.7) / mins, 2),
            uptalk_ratio=_r(sum(1 for s in slopes if s > 4.0) / len(slopes)) if len(slopes) >= 2 else None,
            asr_confidence=_r(np.mean([w.prob for w in words])),
        )
    else:
        feats.update(onset_s=None, wpm=None, articulation_wpm=None, rate_cv=None, pause_count=None,
                     pauses_per_min=None, pause_ratio=None, boundary_pause_alignment=None,
                     long_midclause_pauses=0, long_midclause_per_min=0.0, uptalk_ratio=None,
                     asr_confidence=None)

    if baseline and feats.get("pitch_median_hz") and baseline.get("pitch_median_hz"):
        feats["pitch_vs_baseline_st"] = _r(12 * np.log2(feats["pitch_median_hz"] / baseline["pitch_median_hz"]), 2)
    return feats


def describe(p: dict, tf: dict) -> dict:
    """Coaching-oriented tone summary from prosody (p) and text features (tf)."""
    art = p.get("articulation_wpm")
    pace = None if art is None else ("slow" if art < 110 else "fast" if art > 185 else "steady")
    std = p.get("pitch_std_st")
    variation = None if std is None else ("monotone" if std < 1.5 else "moderate" if std < 3.0 else "expressive")
    e = p.get("energy_std_db")
    energy = None if e is None else ("flat" if e < 4.0 else "dynamic")

    hes = _clip(p.get("long_midclause_per_min", 0) / 4)
    fill = _clip(tf.get("filler_per100", 0) / 6)
    hedge = _clip(tf.get("hedge_per100", 0) / 4)
    up = p.get("uptalk_ratio") or 0.0
    pace_pen = _clip((abs((art or 150) - 150) - 40) / 60)
    confidence = _clip(1 - (0.30 * hes + 0.25 * fill + 0.15 * hedge + 0.15 * up + 0.15 * pace_pen))

    tips = []
    if pace == "fast":
        tips.append("Pace is fast: pause briefly between ideas.")
    if pace == "slow":
        tips.append("Pace is slow: tighten your delivery.")
    if variation == "monotone":
        tips.append("Pitch is flat: stress the key terms.")
    if fill >= 0.5:
        tips.append("Frequent fillers: use a silent pause instead.")
    if hes >= 0.5:
        tips.append("Mid-sentence hesitations: structure the answer before speaking.")
    if up >= 0.5:
        tips.append("Statements end on a rising pitch; finish with a falling tone to sound certain.")
    return {
        "pace": pace, "pitch_variation": variation, "energy": energy,
        "confidence": _r(confidence, 2),
        "confidence_label": "high" if confidence >= 0.75 else "moderate" if confidence >= 0.5 else "low",
        "tips": tips,
    }
