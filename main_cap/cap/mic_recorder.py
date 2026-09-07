"""
Records a spoken answer from the microphone to a WAV file, for handoff to
InterviewAudioProcessor.process(). Records until the user presses Enter
(simple, reliable for a CLI turn-based flow — silence-detection auto-stop
is a nice-to-have but adds false-stop risk during natural thinking pauses,
which would directly undermine the pause-pattern cheating heuristic).

pip install sounddevice scipy
"""
from __future__ import annotations
import threading
import time
import tempfile

import sounddevice as sd
import scipy.io.wavfile as wavfile
import numpy as np


class MicRecorder:
    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._start_time: float | None = None
        self.time_to_first_sound: float | None = None
        self._speech_started = False

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())
        if not self._speech_started and self._start_time is not None:
            # crude voice-activity trigger: first frame with meaningful energy
            if np.abs(indata).mean() > 0.01:
                self.time_to_first_sound = time.time() - self._start_time
                self._speech_started = True

    def record_until_enter(self, prompt: str = "\n🎙️  Recording... press Enter when finished answering.") -> str:
        """Returns the path to a temp WAV file containing the recording."""
        self._frames = []
        self._speech_started = False
        self._start_time = time.time()
        self._recording = True

        stream = sd.InputStream(samplerate=self.samplerate, channels=1, callback=self._callback)
        stream.start()
        input(prompt)
        stream.stop()
        stream.close()
        self._recording = False

        if not self._frames:
            raise RuntimeError("No audio captured — check microphone permissions/device.")

        audio = np.concatenate(self._frames, axis=0)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        wavfile.write(tmp.name, self.samplerate, audio)
        return tmp.name