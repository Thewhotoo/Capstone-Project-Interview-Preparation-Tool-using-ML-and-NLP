"""
TTS-only Flask blueprint. Deliberately has ZERO dependency on
audio_processor.py (Whisper/librosa) so a missing/broken package there
(numpy, transformers, faiss, sentence_transformers are all currently
missing per the app's own startup log) can never take TTS down with it.

Register in app.py with:
    from tts_routes import tts_bp
    app.register_blueprint(tts_bp)
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify, Response
import logging

logger = logging.getLogger(__name__)
tts_bp = Blueprint("tts", __name__, url_prefix="/audio")

_tts = None  # lazy-loaded so a missing `edge-tts` package doesn't crash app startup


def _get_tts():
    global _tts
    if _tts is None:
        from tts_engine import TTSEngine
        _tts = TTSEngine()
    return _tts


@tts_bp.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        engine = _get_tts()
        audio_bytes = engine.synthesize_bytes(text)
        return Response(audio_bytes, mimetype="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
