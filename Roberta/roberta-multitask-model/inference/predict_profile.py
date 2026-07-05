from __future__ import annotations

from inference.predict_difficulty import predict_difficulty
from inference.input_validation import invalid_question_error, is_valid_question
from inference.predict_intent import predict_intent


def predict_question_profile(text: str) -> dict[str, object]:
    if not is_valid_question(text):
        return invalid_question_error()

    intent_result = predict_intent(text)
    difficulty_result = predict_difficulty(text)
    confidence = (float(intent_result["confidence"]) + float(difficulty_result["confidence"])) / 2.0
    return {
        "intent": intent_result["label"],
        "difficulty": difficulty_result["label"],
        "confidence": confidence,
    }