from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inference.input_validation import invalid_question_error, is_valid_question
from inference.rule_based import get_topic_labels


TOPIC_LABELS = ["OS", "DBMS", "CN", "OOP", "DSA", "General"]
SAVED_MODEL_DIR = ROOT_DIR / "model" / "saved_models" / "topic"


def predict_topic(text: str) -> dict[str, object]:
    if not is_valid_question(text):
        return invalid_question_error()

    # Use the trained model when available.
    if SAVED_MODEL_DIR.exists():
        from model.multitask_utils import predict_multi_label
        result = predict_multi_label(text, SAVED_MODEL_DIR)
        return {
            "labels": result["labels"],
            "scores": result["scores"],
            "source": "model",
        }

    # Fall back to rule-based heuristics.
    labels = get_topic_labels(text)
    scores = {topic_label: (0.9 if topic_label in labels else 0.1) for topic_label in TOPIC_LABELS}
    return {
        "labels": labels,
        "scores": scores,
        "source": "rule",
    }


if __name__ == "__main__":
    sample_text = "Explain binary tree and recursion"
    print(predict_topic(sample_text))
