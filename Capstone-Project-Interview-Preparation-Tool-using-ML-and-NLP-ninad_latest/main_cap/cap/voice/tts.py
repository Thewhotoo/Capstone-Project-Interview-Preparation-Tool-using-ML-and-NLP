"""Text-to-speech: Piper (neural, offline) -> pyttsx3 (offline system voices). Disk-cached WAVs.

Env: CAP_PIPER_MODEL=/path/voice.onnx   CAP_TTS_RATE=170 (pyttsx3 wpm)   CAP_TTS=0 disables.
If no engine is available the API answers 501 and the browser falls back to speechSynthesis.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import queue
import re
import threading
import wave
from concurrent.futures import Future
from pathlib import Path

log = logging.getLogger(__name__)

_SPOKEN = {"SQL": "sequel", "NoSQL": "no sequel", "TCP/IP": "T C P I P", "I/O": "I O", "RAM": "ram", "ACID": "acid",
           "LIFO": "life-oh", "FIFO": "fife-oh", "GUI": "gooey", "JSON": "jason", "OOP": "O O P", "CPU": "C P U",
           "OS": "O S", "CN": "C N", "DSA": "D S A", "DBMS": "D B M S", "OOAD": "O O A D", "API": "A P I"}
_ACRONYM = re.compile(r"\b[A-Z]{2,6}(?:/[A-Z]{2,6})?\b")


def prepare_text(text: str) -> str:
    """Strip markup and make acronyms pronounceable."""
    t = re.sub(r"<[^>]+>|[*_`#>]", " ", text or "")
    t = re.sub(r"\bQ(\d+)\s*/\s*\d+\s*:?", r"Question \1.", t)
    t = _ACRONYM.sub(lambda m: _SPOKEN.get(m.group(0), " ".join(m.group(0).replace("/", " "))), t)
    return re.sub(r"\s+", " ", t).strip()[:1200]


class _PiperEngine:
    name = "piper"

    def __init__(self, model_path: str):
        from piper import PiperVoice
        self.voice = PiperVoice.load(model_path)

    def synth(self, text: str, path: str, rate: float) -> None:
        with wave.open(path, "wb") as wf:
            if hasattr(self.voice, "synthesize_wav"):
                self.voice.synthesize_wav(text, wf)
            else:
                self.voice.synthesize(text, wf)


class _Pyttsx3Engine:
    name = "pyttsx3"

    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", int(os.environ.get("CAP_TTS_RATE", "170")))

    def synth(self, text: str, path: str, rate: float) -> None:
        self.engine.setProperty("rate", int(int(os.environ.get("CAP_TTS_RATE", "170")) * rate))
        self.engine.save_to_file(text, path)
        self.engine.runAndWait()


class TTS:
    """One worker thread owns the engine (SAPI/COM and espeak are not thread-safe)."""

    def __init__(self, cache_dir: str | os.PathLike):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._q: queue.Queue = queue.Queue()
        self._engine = None
        self._ready = threading.Event()
        self.engine_name = "none"
        if os.environ.get("CAP_TTS", "1") != "0":
            threading.Thread(target=self._worker, daemon=True, name="tts").start()
            self._ready.wait(timeout=20)

    @property
    def available(self) -> bool:
        return self._engine is not None

    def _init_engine(self):
        model = os.environ.get("CAP_PIPER_MODEL")
        for factory in ([lambda: _PiperEngine(model)] if model else []) + [_Pyttsx3Engine]:
            try:
                return factory()
            except Exception as e:  # missing package / driver
                log.info("TTS engine unavailable: %s", e)
        return None

    def _worker(self):
        self._engine = self._init_engine()
        self.engine_name = self._engine.name if self._engine else "none"
        self._ready.set()
        while self._engine:
            text, path, rate, fut = self._q.get()
            try:
                self._engine.synth(text, path, rate)
                fut.set_result(None)
            except Exception as e:
                fut.set_exception(e)

    def speak(self, text: str, rate: float = 1.0) -> bytes:
        text = prepare_text(text)
        if not text or not self.available:
            raise RuntimeError("tts unavailable")
        key = hashlib.sha1(f"{self.engine_name}|{rate:.2f}|{text}".encode()).hexdigest()
        path = self.cache / f"{key}.wav"
        if not path.exists():
            tmp = str(path) + ".tmp.wav"
            fut: Future = Future()
            self._q.put((text, tmp, rate, fut))
            fut.result(timeout=60)
            os.replace(tmp, path)
        return path.read_bytes()


def wav_duration(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()
