"""Tests for voice/: prosody, reading detection, routes (STT/TTS stubbed)."""
import io
import json
import wave

import numpy as np
import pytest
from flask import Flask

from voice import analyzer, prosody, reading, textfeat
from voice.vtypes import Transcript, Word

SR = 16000


def tone(dur, f0_fn, amp=0.3):
    t = np.arange(int(dur * SR)) / SR
    f = f0_fn(t)
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = sum(np.sin(k * phase) / k for k in (1, 2, 3, 4))
    return (amp * y / 2).astype(np.float32)


def words_for(text, wps, pauses_after=()):
    out, t = [], 0.3
    for i, w in enumerate(text.split()):
        out.append(Word(w, t, t + 1 / wps * 0.9))
        t += 1 / wps + (pauses_after[i] if i < len(pauses_after) else 0)
    return out


def test_pitch_tracker_accuracy():
    y = tone(2.0, lambda t: np.full_like(t, 150.0))
    f0, _, _ = prosody.pitch_track(y)
    v = f0[~np.isnan(f0)]
    assert len(v) > 100 and abs(np.median(v) - 150) < 3


def test_monotone_vs_expressive():
    mono = prosody.analyze(tone(4, lambda t: np.full_like(t, 140.0)))
    expr = prosody.analyze(tone(4, lambda t: 140 * 2 ** ((6 * np.sin(2 * np.pi * 0.7 * t)) / 12)))
    assert mono["pitch_std_st"] < 0.7
    assert expr["pitch_std_st"] > 3.0
    tf = textfeat.text_features("hello")
    assert prosody.describe(mono, tf)["pitch_variation"] == "monotone"
    assert prosody.describe(expr, tf)["pitch_variation"] == "expressive"


def test_pause_alignment_and_rate():
    text = "First, we parse. Then, we index. After that, we rank. Finally, we report."
    toks = text.split()
    w = words_for(text, 3.0, [0.5 if x.endswith((",", ".")) else 0 for x in toks])
    p = prosody.analyze(tone(w[-1].end + 0.3, lambda t: np.full_like(t, 120.0)), w)
    assert p["pause_count"] >= 6 and p["boundary_pause_alignment"] == 1.0 and p["long_midclause_pauses"] == 0
    assert 60 < p["wpm"] < 200 and p["articulation_wpm"] > p["wpm"]


def test_text_features():
    tf = textfeat.text_features("Um, so I think, uh, we we used Redis. You know, it's fast.")
    assert tf["fillers"] >= 3 and tf["repetitions"] >= 1 and tf["contractions"] == 1
    assert textfeat.ngram_containment("the quick brown fox jumps over", ["the quick brown fox jumps high"]) > 0.4
    assert textfeat.ngram_containment("totally different words here now", ["nothing in common at all"]) == 0


READ = ("Furthermore, a transaction is defined as a logical unit of work that must be executed atomically. "
        "Consequently, the database guarantees consistency, isolation and durability. "
        "Moreover, deadlock refers to a state in which two processes wait for each other indefinitely. "
        "Therefore, the operating system must detect and resolve such cycles.")
SPOKEN = ("Um, so I built the, uh, the cache layer, and I think we used Redis? "
          "Honestly it was kind of tricky, I mean, we had a few, like, timeouts. "
          "So I, uh, added retries and it's way faster now, sorry, I mean about three times faster.")


def _run(text, wps, gaps, pitch_fn, ctx=None, refs=None):
    w = words_for(text, wps, gaps)
    dur = w[-1].end + 0.3
    return analyzer.analyze(tone(dur, pitch_fn), Transcript(text, w, duration=dur), ctx, refs)


def test_reading_detected_vs_spontaneous():
    n = len(READ.split())
    gaps = [0.45 if READ.split()[i].endswith((",", ".")) else 0 for i in range(n)]
    r = _run(READ, 2.6, gaps, lambda t: np.full_like(t, 130.0), {"gaze_away_ratio": 0.5}, [READ])["reading"]
    assert r["label"] == "likely_reading" and r["reasons"]

    rng = np.random.default_rng(1)
    toks = SPOKEN.split()
    gaps2 = [float(rng.choice([0, 0, 0.9, 0.3])) for _ in toks]
    # uneven speed: alternate fast / slow words
    w = []
    t = 0.4
    for i, tok in enumerate(toks):
        d = float(rng.choice([0.15, 0.6]))
        w.append(Word(tok, t, t + d))
        t += d + gaps2[i]
    dur = t + 0.3
    res = analyzer.analyze(tone(dur, lambda x: 130 * 2 ** (4 * np.sin(2 * np.pi * 0.5 * x) / 12)),
                           Transcript(SPOKEN, w, duration=dur), {})
    assert res["reading"]["label"] == "natural_speech"


def test_insufficient_data():
    r = _run("short answer here", 2.0, [], lambda t: np.full_like(t, 120.0))["reading"]
    assert r["label"] == "insufficient_data" and r["score"] is None


def test_summarize():
    rec = _run(READ, 2.6, [0.4] * 40, lambda t: np.full_like(t, 130.0), {}, [READ])
    s = reading.summarize([rec, rec])
    assert s["answers"] == 2 and len(s["per_answer"]) == 2


# ── routes ──
def _wav(y):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return b.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from voice import routes, stt
    app = Flask(__name__, instance_path=str(tmp_path))
    app.register_blueprint(routes.voice_bp)

    class FakeSTT:
        available, name = True, "fake"
        def transcribe(self, audio, hint=""):
            w = words_for(READ, 2.6, [0.4] * 40)
            return Transcript(READ, w, duration=len(audio) / SR)
    monkeypatch.setattr(routes, "get_transcriber", lambda: FakeSTT())

    class FakeTTS:
        available, engine_name = True, "fake"
        def speak(self, text, rate=1.0): return _wav(tone(0.3, lambda t: np.full_like(t, 200.0)))
    monkeypatch.setattr(routes, "get_tts", lambda: FakeTTS())
    monkeypatch.setattr(routes, "_references", lambda q: [READ])
    return app.test_client()


def test_routes_roundtrip(client):
    assert client.get("/api/voice/status").get_json()["tts"] is True
    audio = _wav(tone(12, lambda t: np.full_like(t, 130.0)))
    r = client.post("/api/voice/transcribe?debug=1", data={"audio": (io.BytesIO(audio), "a.wav"),
                    "context": json.dumps({"kind": "technical", "question": "What is a transaction?"})})
    d = r.get_json()
    assert r.status_code == 200 and d["text"].startswith("Furthermore") and d["reading"]["label"] != "natural_speech"
    assert "reading" not in client.post("/api/voice/transcribe", data={"audio": (io.BytesIO(audio), "a.wav")}).get_json()
    s = client.post("/api/voice/summary", json={"ids": [d["id"]]}).get_json()
    assert s["answers"] == 1
    assert client.post("/api/voice/tts", json={"text": "Hello"}).mimetype == "audio/wav"
    assert client.post("/api/voice/transcribe", data={}).status_code == 400


def test_tts_prepare_text():
    from voice.tts import prepare_text
    assert "D B M S" in prepare_text("Explain DBMS <b>ACID</b> Q3/8: now") and "Question 3." in prepare_text("Q3/8: now")
