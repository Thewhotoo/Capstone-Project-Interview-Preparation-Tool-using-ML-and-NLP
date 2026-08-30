"""
Experiment Dataset IO — minimal, additive persistence for experiment
artifacts. No new schema anywhere in this file: everything here is built
entirely on the ALREADY-EXISTING Pydantic JSON serialization
(`model_dump_json`/`model_validate_json`) of whatever frozen model is being
persisted — `TrainingExample`, `DatasetManifest`, `Checkpoint`,
`BenchmarkResult`, `PromotionDecision`, or any other frozen `BaseModel` this
project already has.

Two shapes are provided:
  - `save_examples_jsonl`/`load_examples_jsonl` — JSONL (one example per
    line) specifically for a large batch of `TrainingExample`s, so a big
    dataset can be written/read incrementally without holding a giant
    single JSON document in memory.
  - `save_json`/`load_json` — a single JSON document for any OTHER frozen
    Pydantic artifact (a `DatasetManifest`, a `Checkpoint`'s metadata, a
    `BenchmarkResult`, a `PromotionDecision`, ...) — generic, not tied to
    one model type, since the serialization mechanism is identical for all
    of them.

Purpose: at the scale the dataset-scaling milestone targets (thousands of
examples), never persisting a generated dataset means every experiment
re-generates from scratch — free and instant with `FakeGenerationClient`,
but would burn irreplaceable Gemini quota repeatedly once real generation is
used at this scale. This closes that gap (SESSION_HANDOFF.md §6 item 8).

Portability (session 10): with a local Windows development machine and
Google Colab as the primary training/benchmarking environment, EVERY
artifact an experiment produces or consumes — the dataset, its manifest,
the checkpoint's metadata, benchmark results, promotion decisions — needs
to survive being written on one machine and read on the other. Plain JSON
built on each model's own existing serialization is the simplest, most
portable choice available: no new format, no new dependency, and it
round-trips through the SAME frozen validators either model already
enforces at construction time.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from training_example import TrainingExample

_ModelT = TypeVar("_ModelT", bound=BaseModel)


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


def save_json(model: BaseModel, path: str) -> str:
    """Writes any single frozen Pydantic artifact (`DatasetManifest`,
    `Checkpoint`, `BenchmarkResult`, `PromotionDecision`, ...) to `path` as
    one JSON document, via that model's own `model_dump_json()`. Returns
    `path` for convenient chaining."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(model.model_dump_json())
    return path


def load_json(model_cls: type[_ModelT], path: str) -> _ModelT:
    """Reads a JSON document written by `save_json` back into an instance
    of `model_cls`, re-validated through that model's own frozen validators
    (`model_validate_json`) — never trusted blindly. `model_cls` must match
    whatever type was actually saved; this function does not (and cannot)
    infer the type from the file alone."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return model_cls.model_validate_json(content)
