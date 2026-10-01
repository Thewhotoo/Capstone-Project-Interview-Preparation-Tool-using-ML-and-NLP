"""Voice I/O for the interview app: speech-to-text, text-to-speech, tone + reading analysis."""
from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger(__name__)


def init_voice(app) -> None:
    from .routes import get_tts, voice_bp
    from .stt import get_transcriber

    app.register_blueprint(voice_bp)

    def _warm():
        with app.app_context():
            get_tts()
            stt = get_transcriber()
            if stt.available:
                try:
                    stt.load()
                except Exception as e:
                    log.warning("STT warm-up failed (will retry on first use): %s", e)

    if os.environ.get("CAP_MODEL_WARMUP", "1") != "0":
        threading.Thread(target=_warm, daemon=True, name="voice-warmup").start()
