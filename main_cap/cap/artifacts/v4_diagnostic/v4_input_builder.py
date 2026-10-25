"""
V4 model-input builder — the ONE sanctioned way to turn a V4 diagnostic
record into the (text_a, text_b) pair the real model would see, for use by
`validate_v4_diagnostic.py`'s leakage checks and any future read-only
inference script.

Deliberately mirrors `model_backbone.build_dimension_input_text` /
`build_dimension_pair`'s shape (QUESTION / RELEVANT CONTEXT / EXPECTED
CONCEPTS sections, answer as the separate second segment) WITHOUT importing
production code, so V4 stays fully decoupled from the training/inference
pipeline while still being checked against the exact fields a real run would
expose. Reads only `question`, `grounding.title`, `grounding.technologies`,
`grounding.summary`, `expected_concepts`, `answer` — never `rationale`,
`gold_labels`, `diagnostic_category`, `pair_group_id`, or any other
metadata field.
"""
from __future__ import annotations


def build_v4_model_input(example: dict) -> tuple[str, str]:
    """Returns (text_a, text_b) exactly like the production
    `build_dimension_pair` would, using ONLY sanctioned model-input fields."""
    sections = [f"QUESTION:\n{(example.get('question') or '').strip()}"]

    grounding = example.get("grounding") or {}
    title = (grounding.get("title") or "").strip()
    technologies = [str(t).strip() for t in (grounding.get("technologies") or ()) if str(t).strip()]
    summary = (grounding.get("summary") or "").strip()
    context_parts = [p for p in ([title] + technologies + [summary]) if p]
    if context_parts:
        sections.append("RELEVANT CONTEXT:\n" + " ".join(context_parts))

    concepts = [str(c).strip() for c in (example.get("expected_concepts") or ()) if str(c).strip()]
    if concepts:
        sections.append("EXPECTED CONCEPTS:\n" + ", ".join(concepts))

    text_a = "\n\n".join(sections)
    text_b = example.get("answer") or ""
    return text_a, text_b


# Fields that must NEVER appear in `build_v4_model_input`'s output — used by
# the leakage check in `validate_v4_diagnostic.py`.
FORBIDDEN_INPUT_LEAK_FIELDS: tuple[str, ...] = (
    "rationale", "gold_labels", "diagnostic_category", "pair_group_id",
    "hypothetical_source", "isolation_note", "example_id",
)
