"""
Speech-to-text for voice answers, done on this server with Whisper
(faster-whisper, CPU, int8), so voice answers work in every browser.

The browser's own speech recognition (Web Speech API) only works in Google
Chrome and Microsoft Edge, which send the audio to Google / Microsoft; Brave,
Firefox, Opera and others fail or don't have it. Instead, the page records the
answer (MediaRecorder: webm/opus, ogg or mp4) and posts it here when the
candidate clicks the mic off:

    POST /api/transcribe   multipart field "audio"   ->   {"text": "..."}

Model: `base.en` (CAP_WHISPER_MODEL to change), about 140 MB. Measured on this
project's CPU: 11 s of speech in 0.6 s, word-perfect on a technical answer
("Redis", "Docker", "800 milliseconds"); `small.en` was about 3x slower and
misheard "Redis". Silence is cut first (VAD), which also stops Whisper from
inventing words on a silent recording. Nothing is stored: the audio is decoded
in memory and dropped.
"""

from __future__ import annotations

import io
import logging
import os
import threading

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("CAP_WHISPER_MODEL", "base.en")
SAMPLE_RATE = 16000
# The page stops recording at 5 minutes; allow some slack for the container.
MAX_SECONDS = 330


def hub_repo_id(model_name: str = MODEL_NAME) -> str:
    """The Hugging Face repository faster-whisper downloads a model name from."""
    return model_name if "/" in model_name else f"Systran/faster-whisper-{model_name}"


class TranscriptionError(ValueError):
    """The recording can't be used. The message is safe to show to the user."""


class _LazyModel:
    _model = None
    _lock = threading.Lock()

    @classmethod
    def get(cls):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    from faster_whisper import WhisperModel
                    cls._model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
                    logger.info("Speech-to-text model loaded: %s", MODEL_NAME)
        return cls._model


def decode_audio(data: bytes):
    """Any format the browser records -> mono float32 samples at 16 kHz.

    Done here with PyAV rather than faster-whisper's own decoder, which passes
    an option that current PyAV versions no longer accept.
    """
    import av
    import numpy as np

    chunks = []
    try:
        with av.open(io.BytesIO(data)) as container:
            if not container.streams.audio:
                raise TranscriptionError("The recording has no sound.")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
    except TranscriptionError:
        raise
    except Exception as exc:     # PyAV raises its own errors for unreadable input
        raise TranscriptionError("The recording couldn't be read.") from exc
    if not chunks:
        raise TranscriptionError("The recording has no sound.")
    samples = np.concatenate(chunks).astype(np.float32) / 32768.0
    if len(samples) > MAX_SECONDS * SAMPLE_RATE:
        raise TranscriptionError("The recording is too long (5 minutes at most).")
    return samples


def transcribe(data: bytes) -> str:
    samples = decode_audio(data)
    segments, _info = _LazyModel.get().transcribe(
        samples, language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False)
    return " ".join(segment.text.strip() for segment in segments).strip()


speech_bp = Blueprint("speech", __name__)


@speech_bp.post("/api/transcribe")
def transcribe_route():
    upload = request.files.get("audio")
    data = upload.read() if upload else b""
    if not data:
        return jsonify({"error": "No recording was received."}), 400
    try:
        text = transcribe(data)
    except TranscriptionError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Speech-to-text failed")
        return jsonify({"error": "Couldn't turn the recording into text. Please type your answer."}), 500
    return jsonify({"text": text})
