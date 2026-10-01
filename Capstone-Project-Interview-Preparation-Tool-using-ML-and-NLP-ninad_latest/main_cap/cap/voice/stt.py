"""Speech-to-text via faster-whisper (local, word timestamps, VAD)."""
from __future__ import annotations

import logging
import os
import threading

import numpy as np

from .vtypes import Transcript, Word

log = logging.getLogger(__name__)

# Keeps Whisper verbatim (it otherwise deletes "um/uh", which disfluency analysis needs)
# and primes it with the interview vocabulary.
_STYLE_PROMPT = "Umm, let me think... so, uh, like, okay. "
_GLOSSARY = ("TCP, UDP, IP, HTTP, DNS, DBMS, SQL, NoSQL, ACID, normalization, B-tree, deadlock, semaphore, mutex, "
             "paging, polymorphism, encapsulation, OOAD, UML, Dijkstra, heap, hash table, Flask, REST API.")


class Transcriber:
    def __init__(self, model: str | None = None):
        self._name = model or os.environ.get("CAP_STT_MODEL", "")
        self._model = None
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()

    @property
    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self):
        with self._load_lock:
            if self._model is not None:
                return self._model
            from faster_whisper import WhisperModel
            try:
                import ctranslate2
                gpu = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                gpu = False
            name = self._name or ("small.en" if gpu else "base.en")
            kw = dict(device="cuda" if gpu else "cpu", compute_type="float16" if gpu else "int8")
            try:
                self._model = WhisperModel(name, local_files_only=True, **kw)
            except Exception:
                self._model = self._download_and_load(WhisperModel, name, kw)
            log.info("STT model '%s' loaded on %s", name, kw["device"])
            self._name = name
            return self._model

    @staticmethod
    def _download_and_load(cls, name, kw):
        """app.py may set HF_HUB_OFFLINE=1 once its own models are cached; allow this one download."""
        import huggingface_hub.constants as hc
        prev, prev_env = hc.HF_HUB_OFFLINE, os.environ.pop("HF_HUB_OFFLINE", None)
        hc.HF_HUB_OFFLINE = False
        try:
            return cls(name, **kw)
        finally:
            hc.HF_HUB_OFFLINE = prev
            if prev_env is not None:
                os.environ["HF_HUB_OFFLINE"] = prev_env

    @property
    def name(self) -> str:
        return self._name or "auto"

    def transcribe(self, audio: np.ndarray, hint: str = "") -> Transcript:
        model = self.load()
        prompt = f"{_STYLE_PROMPT}{_GLOSSARY} {hint[:160]}".strip()
        with self._run_lock:
            segs, info = model.transcribe(
                audio, language="en", beam_size=1, word_timestamps=True, condition_on_previous_text=False,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 300}, initial_prompt=prompt,
                temperature=0.0)
            words, parts = [], []
            for s in segs:
                parts.append(s.text.strip())
                words += [Word(w.word.strip(), float(w.start), float(w.end), float(w.probability))
                          for w in (s.words or []) if w.word.strip()]
        return Transcript(" ".join(parts).strip(), words, info.language, float(info.duration))


_default: Transcriber | None = None


def get_transcriber() -> Transcriber:
    global _default
    if _default is None:
        _default = Transcriber()
    return _default
