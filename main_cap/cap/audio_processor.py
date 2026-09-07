import whisper
import librosa
import numpy as np
import tempfile
import os
import io
import re
from pydub import AudioSegment

# Whisper model size — bigger = far better with accents/grammar/noisy audio,
# at the cost of speed and RAM/VRAM. Override via env var without touching code:
#   set WHISPER_MODEL=small   (Windows)  /  export WHISPER_MODEL=small (Mac/Linux)
# Rough guide: base (~1GB, fastest, weakest on accents) < small (~2GB, noticeably
# better accent handling, still fast on CPU) < medium (~5GB, best accuracy,
# needs a GPU to be fast) < large-v3 (best possible, slow on CPU).
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")

# Threshold: 0.6 = Strict, 0.8 = Lenient. Tune this!
SUSPICION_THRESHOLD = 0.6

# Separate, stricter threshold for the SCRIPTED-ANSWER flag (semantic +
# acoustic combined). This is what triggers immediate session termination,
# so it's deliberately conservative — false positives here end an
# interview, which is a much bigger cost than a slightly-off suspicion score.
SCRIPTED_TERMINATION_THRESHOLD = 0.75

FILLER_WORDS = {"um", "uh", "umm", "uhh", "like", "you know", "so", "well", "actually", "basically"}


class InterviewAudioProcessor:
    def __init__(self, model_size: str | None = None):
        """
        model_size: "tiny" | "base" | "small" | "medium" | "large".
        Larger models handle accents/disfluencies/noise noticeably better
        at the cost of memory and inference speed. Defaults to the
        WHISPER_MODEL env var (falls back to "small") if not passed explicitly.
        """
        size = model_size or WHISPER_MODEL_SIZE
        print(f"[Audio] Loading Whisper model ({size})...")
        self.stt_model = whisper.load_model(size)
        print("[Audio] Whisper loaded.")
        self._embed_model = None  # lazy-loaded, reuses evaluate.py's model choice

    def _get_embed_model(self):
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embed_model

    def process(self, audio_file_path, reference_context: str = None, time_to_first_sound: float = None):
        """
        Takes a file path (could be WebM, OGG, MP3, WAV).
        Converts to proper WAV using pydub, then analyzes.

        reference_context: the RAG-retrieved context/reference answer for
            this question, if available. Enables semantic scripted-answer
            detection (near-verbatim match to text the candidate wasn't
            shown is a much stronger signal than acoustics alone).
        time_to_first_sound: seconds between question display and first
            detected speech, if the caller tracked it (see mic_recorder.py).
            Near-zero latency on an open-ended question is itself a signal —
            genuine thinking usually takes at least a beat.
        """
        try:
            # --- STEP 1: Convert ANY browser/mic audio to clean WAV using pydub ---
            audio_segment = AudioSegment.from_file(audio_file_path)
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format="wav", parameters=["-ac", "1", "-ar", "16000"])
            wav_io.seek(0)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
                tmp_wav.write(wav_io.read())
                tmp_wav_path = tmp_wav.name

            # --- STEP 2: Run Whisper STT ---
            # initial_prompt biases recognition toward technical vocabulary,
            # which meaningfully reduces mistranscription of jargon (TCP,
            # polymorphism, etc.) independent of the speaker's accent.
            result = self.stt_model.transcribe(
                tmp_wav_path,
                word_timestamps=True,
                initial_prompt="Technical interview about computer science, networking, data structures, and object-oriented design.",
                fp16=False,  # avoids a spurious warning/slowdown on CPU-only machines
            )
            transcript = result["text"].strip()
            segments = result["segments"]

            # --- STEP 3: Extract Acoustic Features ---
            y, sr = librosa.load(tmp_wav_path, sr=16000)
            duration = len(y) / sr
            os.unlink(tmp_wav_path)

            if duration < 1.0:
                return self._empty_result(transcript)

            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = pitches[magnitudes > np.median(magnitudes)]
            pitch_std = float(np.std(pitch_values)) if len(pitch_values) > 0 else 0

            energy = librosa.feature.rms(y=y)
            energy_std = float(np.std(energy))

            word_count = len(transcript.split())
            speaking_rate = word_count / duration if duration > 0 else 0

            word_pauses = []
            for seg in segments:
                for word_info in seg.get("words", []):
                    word_pauses.append({"start": word_info["start"], "end": word_info["end"]})

            pause_durations = []
            for i in range(1, len(word_pauses)):
                gap = word_pauses[i]["start"] - word_pauses[i - 1]["end"]
                if gap > 0.1:
                    pause_durations.append(gap)

            pause_std = float(np.std(pause_durations)) if pause_durations else 0
            pause_mean = float(np.mean(pause_durations)) if pause_durations else 0

            # --- STEP 4: Acoustic cheating heuristic (original, unchanged) ---
            acoustic_score = 0.0
            if pitch_std < 25:
                acoustic_score += 0.25
            if energy_std < 0.04:
                acoustic_score += 0.20
            if speaking_rate > 3.8:
                acoustic_score += 0.20
            if pause_mean > 0.15 and pause_std < 0.08:
                acoustic_score += 0.35
            acoustic_score = min(acoustic_score, 1.0)

            # --- STEP 5: Filler-word ratio (natural speech has some; reading doesn't) ---
            words_lower = transcript.lower().split()
            filler_count = sum(1 for w in words_lower if w.strip(".,!?") in FILLER_WORDS)
            filler_ratio = filler_count / max(1, word_count)
            # long, filler-free answers are a mild signal on their own
            no_filler_flag = word_count > 30 and filler_count == 0

            # --- STEP 6: Semantic similarity to reference (the strong signal) ---
            semantic_similarity = None
            if reference_context:
                model = self._get_embed_model()
                from sentence_transformers import util
                t_emb = model.encode(transcript, convert_to_tensor=True)
                r_emb = model.encode(reference_context, convert_to_tensor=True)
                semantic_similarity = max(0.0, min(1.0, util.cos_sim(t_emb, r_emb).item()))

            # --- STEP 7: Response-latency signal ---
            near_instant_response = time_to_first_sound is not None and time_to_first_sound < 0.4 and word_count > 15

            # --- STEP 8: Combine into a scripted-answer score ---
            # Weighted so that semantic match to unseen reference text dominates —
            # it's the hardest signal to produce by accident.
            scripted_score = 0.0
            scripted_score += acoustic_score * 0.35
            if no_filler_flag:
                scripted_score += 0.15
            if semantic_similarity is not None:
                if semantic_similarity > 0.90:
                    scripted_score += 0.45
                elif semantic_similarity > 0.80:
                    scripted_score += 0.20
            if near_instant_response:
                scripted_score += 0.15
            scripted_score = min(scripted_score, 1.0)

            is_scripted = scripted_score >= SCRIPTED_TERMINATION_THRESHOLD
            is_cheating = acoustic_score >= SUSPICION_THRESHOLD  # preserved original meaning

            return {
                "transcript": transcript,
                "is_cheating": is_cheating,
                "suspicion_score": round(acoustic_score, 3),
                "is_scripted": is_scripted,
                "scripted_score": round(scripted_score, 3),
                "metrics": {
                    "pitch_std": round(pitch_std, 2),
                    "energy_std": round(energy_std, 4),
                    "speaking_rate": round(speaking_rate, 2),
                    "pause_std": round(pause_std, 3),
                    "duration_sec": round(duration, 2),
                    "filler_ratio": round(filler_ratio, 3),
                    "semantic_similarity_to_reference": round(semantic_similarity, 3) if semantic_similarity is not None else None,
                    "time_to_first_sound": round(time_to_first_sound, 3) if time_to_first_sound is not None else None,
                },
            }

        except Exception as e:
            print(f"[Audio Error] {e}")
            return {
                "transcript": "",
                "is_cheating": False,
                "suspicion_score": 0.0,
                "is_scripted": False,
                "scripted_score": 0.0,
                "metrics": {},
                "error": str(e),
            }

    @staticmethod
    def _empty_result(transcript: str) -> dict:
        return {
            "transcript": transcript,
            "is_cheating": False,
            "suspicion_score": 0.0,
            "is_scripted": False,
            "scripted_score": 0.0,
            "metrics": {},
        }
