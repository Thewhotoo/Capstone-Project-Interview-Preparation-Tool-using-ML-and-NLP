"""
Voice answers: POST /api/transcribe (speech_to_text.py).

test_data/voice_answer.webm is an 11 s spoken technical answer (made with
Windows text-to-speech, encoded as webm/opus like a browser recording). The
real-model tests load Whisper base.en; set CAP_SKIP_MODEL_TESTS=1 to skip them.
"""

import io
import os
import unittest
from unittest import mock

from _app_test_setup import app, signed_up_client

import speech_to_text

RECORDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data", "voice_answer.webm")


def post_audio(client, data, name="answer"):
    return client.post("/api/transcribe", data={"audio": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


class TestTranscribeRoute(unittest.TestCase):
    def setUp(self):
        self.client, _ = signed_up_client()

    def test_needs_login(self):
        response = post_audio(app.test_client(), b"x")
        self.assertEqual(response.status_code, 401)

    def test_missing_or_empty_recording(self):
        self.assertEqual(self.client.post("/api/transcribe").status_code, 400)
        self.assertEqual(post_audio(self.client, b"").status_code, 400)

    def test_unreadable_recording_is_a_clear_400(self):
        response = post_audio(self.client, b"this is not audio")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "The recording couldn't be read.")

    def test_returns_the_text(self):
        with mock.patch.object(speech_to_text, "transcribe", return_value="I used Redis") as fake:
            response = post_audio(self.client, b"audio bytes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"text": "I used Redis"})
        fake.assert_called_once_with(b"audio bytes")

    def test_unexpected_failure_is_a_500_with_a_message(self):
        with mock.patch.object(speech_to_text, "transcribe", side_effect=RuntimeError("boom")):
            response = post_audio(self.client, b"audio bytes")
        self.assertEqual(response.status_code, 500)
        self.assertIn("type your answer", response.get_json()["error"])

    def test_too_long_recording_is_refused(self):
        with mock.patch.object(speech_to_text, "MAX_SECONDS", 2):
            response = post_audio(self.client, open(RECORDING, "rb").read())
        self.assertEqual(response.status_code, 400)
        self.assertIn("too long", response.get_json()["error"])


class TestDecodeAudio(unittest.TestCase):
    def test_browser_recording_becomes_16khz_mono(self):
        samples = speech_to_text.decode_audio(open(RECORDING, "rb").read())
        self.assertAlmostEqual(len(samples) / speech_to_text.SAMPLE_RATE, 11.4, delta=0.3)
        self.assertEqual(samples.dtype.name, "float32")
        self.assertLessEqual(float(abs(samples).max()), 1.0)


@unittest.skipIf(os.environ.get("CAP_SKIP_MODEL_TESTS"), "model tests disabled")
class TestRealModel(unittest.TestCase):
    def test_transcribes_a_technical_answer(self):
        client, _ = signed_up_client()
        response = post_audio(client, open(RECORDING, "rb").read())
        self.assertEqual(response.status_code, 200)
        text = response.get_json()["text"]
        for words in ("task tracker", "Redis", "cache", "database", "Docker", "800 milliseconds"):
            self.assertIn(words, text)

    def test_silence_gives_no_text(self):
        import av
        buffer = io.BytesIO()
        with av.open(buffer, "w", format="wav") as out:   # 3 s of silence
            stream = out.add_stream("pcm_s16le", rate=16000)
            stream.layout = "mono"
            frame = av.AudioFrame.from_ndarray(__import__("numpy").zeros((1, 48000), dtype="int16"),
                                               format="s16", layout="mono")
            frame.sample_rate = 16000
            for packet in stream.encode(frame):
                out.mux(packet)
            for packet in stream.encode(None):
                out.mux(packet)
        self.assertEqual(speech_to_text.transcribe(buffer.getvalue()), "")


if __name__ == "__main__":
    unittest.main()
