from __future__ import annotations


VALID_QUESTION_PREFIXES = (
    "what",
    "explain",
    "compare",
    "how",
    "why",
    "difference",
    "describe",
    "define",
    "implement",
    "design",
    "write",
)


def is_valid_question(question: str) -> bool:
    lowered = question.strip().lower()
    if not lowered:
        return False
    return any(lowered.startswith(prefix) for prefix in VALID_QUESTION_PREFIXES)


def invalid_question_error() -> dict[str, str]:
    return {
        "error": "Invalid input. Please enter a complete question.",
    }
