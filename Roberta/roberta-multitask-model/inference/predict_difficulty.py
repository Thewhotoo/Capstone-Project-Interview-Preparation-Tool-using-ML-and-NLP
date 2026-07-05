from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inference.input_validation import invalid_question_error, is_valid_question
from inference.rule_based import get_difficulty


DIFFICULTY_LABELS = ["easy", "medium", "hard"]
SAVED_MODEL_DIR = ROOT_DIR / "model" / "saved_models" / "difficulty"


def predict_difficulty(text: str) -> dict[str, object]:
    if not is_valid_question(text):
        return invalid_question_error()

    # Use the trained model when available.
    if SAVED_MODEL_DIR.exists():
        from model.multitask_utils import predict_single_label
        result = predict_single_label(text, SAVED_MODEL_DIR)
        return {
            "label": result["label"],
            "confidence": result["confidence"],
            "scores": result["scores"],
            "source": "model",
        }

    # Fall back to rule-based heuristics (confidence capped at 0.6 to signal fallback).
    label = get_difficulty(text)
    scores = {difficulty_label: (0.6 if difficulty_label == label else 0.2) for difficulty_label in DIFFICULTY_LABELS}
    return {
        "label": label,
        "confidence": 0.6,
        "scores": scores,
        "source": "rule",
    }


if __name__ == "__main__":
    sample_text = "Explain deadlock avoidance"
    print(predict_difficulty(sample_text))
