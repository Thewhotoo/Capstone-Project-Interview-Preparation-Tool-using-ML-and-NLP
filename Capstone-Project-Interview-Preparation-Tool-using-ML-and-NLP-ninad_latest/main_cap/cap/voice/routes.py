"""Flask blueprint: /api/voice/{status,transcribe,tts,summary}. Login is enforced by app.py for /api/*."""
from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import uuid
import wave
from collections import OrderedDict
from pathlib import Path

import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request

from . import analyzer, reading
from .stt import get_transcriber
from .tts import TTS
from .prosody import SR

log = logging.getLogger(__name__)
voice_bp = Blueprint("voice", __name__)

MAX_BYTES, MAX_SECONDS, MIN_SECONDS = 10 * 1024 * 1024, 180, 0.6
_LOG: "OrderedDict[str, dict]" = OrderedDict()     # analysis id -> record (per process)
_BASELINE: dict[int, dict] = {}                    # user id -> running pitch baseline
_LOCK = threading.Lock()
_tts: TTS | None = None
_bank_refs: dict[str, list[str]] | None = None


def _uid() -> int:
    try:
        from flask_login import current_user
        return int(current_user.id)
    except Exception:
        return 0


def _instance() -> Path:
    p = Path(current_app.instance_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _references(question: str) -> list[str]:
    """Reference answer + key points of the technical-bank question being asked (the text a reader would have)."""
    global _bank_refs
    if _bank_refs is None:
        _bank_refs = {}
        try:
            from tech_interview.bank import load_bank
            for q in load_bank():
                _bank_refs[_norm(q.text)] = [q.reference_answer, *(k.point for k in q.key_points)]
        except Exception as e:
            log.info("No reference bank for reading detection: %s", e)
    return _bank_refs.get(_norm(question), [])


def decode_audio(raw: bytes) -> np.ndarray:
    """16-bit PCM WAV (what the browser client sends) -> mono float32 @16 kHz; other formats via PyAV."""
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw)) as w:
            if w.getsampwidth() == 2:
                x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
                x = x.reshape(-1, w.getnchannels()).mean(1)
                if w.getframerate() != SR:
                    from scipy.signal import resample_poly
                    from math import gcd
                    g = gcd(SR, w.getframerate())
                    x = resample_poly(x, SR // g, w.getframerate() // g).astype(np.float32)
                return x
    from faster_whisper.audio import decode_audio as _dec
    return _dec(io.BytesIO(raw), sampling_rate=SR)


def get_tts() -> TTS:
    global _tts
    if _tts is None:
        _tts = TTS(_instance() / "tts_cache")
    return _tts


@voice_bp.get("/api/voice/status")
def status():
    t = get_tts()
    return jsonify({"stt": get_transcriber().available, "stt_model": get_transcriber().name,
                    "tts": t.available, "tts_engine": t.engine_name})


@voice_bp.post("/api/voice/transcribe")
def transcribe():
    stt = get_transcriber()
    if not stt.available:
        return jsonify({"error": "Speech recognition is not installed (pip install faster-whisper)."}), 501
    f = request.files.get("audio")
    raw = f.read(MAX_BYTES + 1) if f else b""
    if not raw:
        return jsonify({"error": "No audio received."}), 400
    if len(raw) > MAX_BYTES:
        return jsonify({"error": "Recording too large."}), 413
    try:
        audio = decode_audio(raw)[: MAX_SECONDS * SR]
        ctx = json.loads(request.form.get("context") or "{}")
        if not isinstance(ctx, dict):
            ctx = {}
    except Exception as e:
        return jsonify({"error": f"Could not read the audio: {e}"}), 400
    if len(audio) < MIN_SECONDS * SR or float(np.abs(audio).max()) < 1e-3:
        return jsonify({"text": "", "empty": True})

    question = str(ctx.get("question") or "")[:600]
    tr = stt.transcribe(audio, hint=question)
    uid = _uid()
    result = analyzer.analyze(audio, tr, ctx, _references(question), _BASELINE.get(uid))

    p = result["prosody"]
    if p.get("pitch_median_hz"):       # running per-candidate baseline: later answers are compared to earlier ones
        b = _BASELINE.setdefault(uid, {"pitch_median_hz": p["pitch_median_hz"]})
        b["pitch_median_hz"] = 0.7 * b["pitch_median_hz"] + 0.3 * p["pitch_median_hz"]

    rid = uuid.uuid4().hex[:12]
    rec = {"id": rid, "user": uid, "ts": time.time(), "session": ctx.get("session_id"), "kind": ctx.get("kind"), **result}
    with _LOCK:
        _LOG[rid] = rec
        while len(_LOG) > 2000:
            _LOG.popitem(last=False)
    try:
        with open(_instance() / "voice_logs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: v for k, v in rec.items() if k != "text_stats"}) + "\n")
    except OSError:
        pass

    out = {"id": rid, "text": tr.text, "duration_s": p["duration_s"]}
    if request.args.get("debug") == "1":          # the live UI never shows verdicts; debug/testing only
        out.update(result)
    return jsonify(out)


@voice_bp.post("/api/voice/tts")
def tts():
    body = request.get_json(silent=True) or {}
    text, rate = body.get("text", ""), float(body.get("rate", 1.0))
    engine = get_tts()
    if not engine.available:
        return jsonify({"error": "No server-side TTS engine; use the browser voice."}), 501
    try:
        wav = engine.speak(text, min(1.5, max(0.6, rate)))
    except Exception as e:
        log.warning("TTS failed: %s", e)
        return jsonify({"error": "TTS failed."}), 501
    return Response(wav, mimetype="audio/wav", headers={"Cache-Control": "private, max-age=86400"})


@voice_bp.post("/api/voice/summary")
def summary():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    uid = _uid()
    with _LOCK:
        recs = [_LOG[i] for i in ids if i in _LOG and _LOG[i]["user"] == uid]
    return jsonify(reading.summarize(recs))
