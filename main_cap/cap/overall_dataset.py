"""
Overall Dataset — V3 Single-Overall-Score Architecture (isolated, additive).

Adapts `TrainingExample` into tokenized tensors for `overall_score_model.
OverallScoreModel`. Reuses `model_dataset.TrainingExampleDataset` UNCHANGED
(it is already generic over which subset of `DatasetSplit` an example
belongs to — nothing about it is tied to the four-dimension scheme), and
reuses `model_backbone.build_dimension_pair`/`tokenize_pair` so the
(context, answer) framing fed to this model is IDENTICAL to what every
other dimension/evaluator model in this codebase already uses (same
QUESTION/RELEVANT CONTEXT/EXPECTED CONCEPTS text_a, answer as text_b).

OVERALL TRAINING TARGET — POLICY (read before changing):

This redesign trains on a SINGLE overall 0-4 ordinal score, but the 220-
example dataset's ground truth is four canonical per-dimension labels
(`TrainingExample.labels.dimension_labels`), not an independently
human-annotated overall score. An "existing evaluation policy" for
deriving an overall value from those four dimensions ALREADY EXISTS in
this codebase: `four_dim_experiment_split.py`'s `_to_training_example`
already computes

    overall_score = sum(dims.values()) / (len(CANONICAL_DIMENSION_KEYS) * _MAX_TIER)

— i.e. the plain, EQUAL-WEIGHT MEAN of the four canonical dimensions' raw
tier scores — and stores it as every example's `labels.overall_label.score`
(both the 170-example core pool and the 220-example V2/V3 pool go through
this exact code path; `load_core_pool()`/`load_v2_pool()` both produce
examples whose `overall_label.score` is this same equal-weight mean).

Per this redesign's own instruction ("use the existing evaluation policy if
one already exists... do NOT invent arbitrary weights"), THIS module reuses
that exact, already-computed value — `example.labels.overall_label.score`
— as the overall training target, rather than re-deriving a new mean from
`dimension_labels` a second time (single source of truth: if the upstream
pool loader's policy ever changes, this module picks it up automatically,
with nothing to keep in sync).

IMPORTANT / EXPLICIT LIMITATION (read before treating this as ground
truth): `overall_label.score` is a PRODUCT-POLICY TARGET — a deterministic
equal-weight aggregation of four independently-labeled dimensions — NOT an
independently human-annotated "how good is this answer overall" judgment.
No annotator was ever asked to rate the answer holistically; the "overall"
number this model is trained to predict is defined entirely by this
aggregation formula. Any consumer of this model's overall_score should
understand it as "DeBERTa's own prediction of the equal-weight mean of the
four canonical dimensions," not as an independently-validated holistic
quality judgment.

The ordinal target (0-4) is produced by the SAME 5-tier binning
`model_dataset.score_to_tier` already uses for every per-dimension label
(0.80/0.60/0.40/0.25 cutpoints) — reused, not reinvented, so the overall
model's target scale is directly comparable to every per-dimension model's
target scale.
"""

from __future__ import annotations

from typing import Optional

import torch
from torch.utils.data import DataLoader

from model_backbone import BackboneConfig, build_dimension_pair, grounding_to_text, tokenize_pair
from model_dataset import TrainingExampleDataset, score_to_tier
from training_example import TrainingExample
from training_experimentation import DatasetSplit

# Re-exported so callers/tests have one place to import both dataset
# machinery pieces from (`overall_dataset.TrainingExampleDataset` ==
# `model_dataset.TrainingExampleDataset`, the identical class/object).
__all__ = [
    "TrainingExampleDataset",
    "overall_score_to_tier",
    "collate_fn",
    "build_overall_dataloaders",
]


def overall_score_to_tier(overall_score: float) -> int:
    """Bins `TrainingExample.labels.overall_label.score` (itself the
    existing equal-weight-mean-of-four-canonical-dimensions policy, see
    module docstring) into the same 5-tier ordinal scale every other model
    in this codebase targets. A thin, named wrapper around
    `model_dataset.score_to_tier` — not a re-derivation — so this module's
    call sites read as "the overall target," while staying byte-identical
    to the shared tiering rule."""
    return score_to_tier(overall_score)


def collate_fn(
    batch: list[TrainingExample],
    tokenizer,
    backbone_config: BackboneConfig,
) -> dict:
    """Tokenizes the (context, answer) pair per example, identical framing
    to `model_dataset.collate_fn`'s main pair (same `build_dimension_pair`
    call), plus the single derived overall ordinal target per example."""
    main_encodings = []
    for e in batch:
        context_text, answer_text = build_dimension_pair(
            e.inputs.question_text,
            grounding_to_text(e.inputs.specification.grounding),
            e.inputs.expected_concepts,
            e.inputs.answer_text,
        )
        main_encodings.append(tokenize_pair(tokenizer, context_text, answer_text, backbone_config.max_length))
    main_batch = tokenizer.pad(main_encodings, return_tensors="pt")

    overall_target = torch.tensor(
        [overall_score_to_tier(e.labels.overall_label.score) for e in batch], dtype=torch.long,
    )

    return {
        "example_ids": [e.metadata.example_id for e in batch],
        "main_input_ids": main_batch["input_ids"],
        "main_attention_mask": main_batch["attention_mask"],
        "overall_target": overall_target,
    }


def build_overall_dataloaders(
    examples: tuple[TrainingExample, ...],
    split: DatasetSplit,
    tokenizer,
    backbone_config: BackboneConfig,
    batch_size: int = 8,
    seed: Optional[int] = None,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Builds (train_loader, val_loader, test_loader) from an already-
    computed `DatasetSplit` — identical contract to
    `model_dataset.build_dataloaders` (never computes a split itself).
    `seed` controls ONLY the train loader's shuffle order (via an explicit
    `torch.Generator`), same reproducibility discipline as
    `model_dataset.build_dataloaders`'s own `seed` parameter."""

    def _collate(batch: list[TrainingExample]) -> dict:
        return collate_fn(batch, tokenizer, backbone_config)

    def _loader(subset: str, shuffle: bool) -> DataLoader:
        dataset = TrainingExampleDataset(examples, split, subset)
        generator = None
        if shuffle and seed is not None:
            generator = torch.Generator()
            generator.manual_seed(seed)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=_collate, generator=generator)

    return _loader("train", True), _loader("val", False), _loader("test", False)
