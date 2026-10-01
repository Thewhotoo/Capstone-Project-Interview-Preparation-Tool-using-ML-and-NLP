"""Pre-synthesise every question-bank prompt so interviews start instantly.

    cd main_cap/cap && python -m voice.prewarm
"""
from flask import Flask

from tech_interview.bank import load_bank
from .routes import get_tts


def main():
    app = Flask(__name__)
    with app.app_context():
        tts = get_tts()
        if not tts.available:
            raise SystemExit("No TTS engine available (pip install pyttsx3, or set CAP_PIPER_MODEL).")
        qs = load_bank()
        for i, q in enumerate(qs, 1):
            tts.speak(q.text)
            print(f"\r{i}/{len(qs)}", end="", flush=True)
        print("\ndone")


if __name__ == "__main__":
    main()
