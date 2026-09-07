"""
Natural-sounding TTS via edge-tts (Microsoft Edge's neural voices — free,
no API key, needs internet). Server-side version: returns audio BYTES for
a Flask route to send to the browser, rather than playing locally — a
Flask server has no business making sound on its own machine.

pip install edge-tts
"""
from __future__ import annotations
import asyncio
import tempfile
import os

import edge_tts

VOICE_PRESETS = {
    "female_us": "en-US-AriaNeural",
    "male_us": "en-US-GuyNeural",
    "female_uk": "en-GB-SoniaNeural",
    "male_uk": "en-GB-RyanNeural",
}

DEFAULT_VOICE = VOICE_PRESETS["female_us"]


class TTSEngine:
    def __init__(self, voice: str = DEFAULT_VOICE, rate: str = "+0%", volume: str = "+0%"):
        self.voice = VOICE_PRESETS.get(voice, voice)
        self.rate = rate
        self.volume = volume

    async def _synthesize_to_file(self, text: str, path: str) -> None:
        communicate = edge_tts.Communicate(text, voice=self.voice, rate=self.rate, volume=self.volume)
        await communicate.save(path)

    def synthesize_bytes(self, text: str) -> bytes:
        """
        Returns MP3 audio bytes for `text`. This is what a Flask route
        should call and send back in the HTTP response for the browser's
        <audio> element to play.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        try:
            asyncio.run(self._synthesize_to_file(text, tmp_path))
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)

    def save_to_file(self, text: str, path: str) -> None:
        """Render directly to a file on disk — useful for pre-caching common questions."""
        asyncio.run(self._synthesize_to_file(text, path))

    @staticmethod
    def list_voices(locale_prefix: str = "en") -> list[str]:
        async def _fetch():
            voices = await edge_tts.list_voices()
            return [v["ShortName"] for v in voices if v["ShortName"].startswith(locale_prefix)]
        return asyncio.run(_fetch())