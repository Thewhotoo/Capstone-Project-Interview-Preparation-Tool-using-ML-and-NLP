"""
Experiment Dataset IO — minimal, additive persistence for a batch of
`TrainingExample`s. No new schema: built entirely on `TrainingExample`'s
own existing Pydantic JSON serialization (`model_dump_json`/
`model_validate_json`). JSONL (one example per line) so a large dataset can
be written/read incrementally without holding a giant single JSON document.

Purpose: at the scale this milestone targets (thousands of examples), never
persisting a generated dataset means every experiment re-generates from
scratch — free and instant with `FakeGenerationClient`, but would burn
irreplaceable Gemini quota repeatedly once real generation is used at this
scale. This closes that gap (SESSION_HANDOFF.md §6 item 8), now genuinely
load-bearing rather than speculative.
"""

from __future__ import annotations

from training_example import TrainingExample


def save_examples_jsonl(examples: tuple[TrainingExample, ...], path: str) -> str:
    """Writes `examples` to `path`, one JSON object per line. Returns `path`
    for convenient chaining. Raises if `examples` is empty -- an empty
    dataset file is never a meaningful artifact to persist."""
    if not examples:
        raise ValueError("examples must not be empty")
    with open(path, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(example.model_dump_json())
            f.write("\n")
    return path


def load_examples_jsonl(path: str) -> tuple[TrainingExample, ...]:
    """Reads a JSONL file written by `save_examples_jsonl` back into a tuple
    of `TrainingExample`s, re-validated through the same frozen schema
    (`model_validate_json`) -- never trusted blindly."""
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(TrainingExample.model_validate_json(line))
    if not examples:
        raise ValueError(f"{path!r} contained no examples")
    return tuple(examples)
