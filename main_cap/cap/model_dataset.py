"""
Model Dataset — Model-Implementation Layer (see model_backbone.py's
docstring for this layer's overall provenance/approval history).

Adapts `TrainingExample` into tokenized tensors for `model_heads.py`'s
`MultiTaskModel`. Selection of which examples go into train/val/test comes
EXCLUSIVELY from `training_experimentation.DatasetSplit` (unmodified,
already-built) — this module never re-derives a split, it only consumes one.

Ground truth for every head comes from `TrainingExample.labels` (the actual,
approved label schema) — never from `TrainingExample.synthetic`'s recipe
TARGETS, which are the Stage A generator's intent, not the ground truth of
record, and are absent entirely for a real-session example anyway.
"""

from __future__ import annotations

from typing import Optional

import torch
from torch.utils.data import DataLoader, Dataset

from evaluation_dimensions import all_keys as canonical_dimension_keys
from evaluation_result import ConceptObservationStatus
from model_backbone import BackboneConfig, build_dimension_pair, grounding_to_text, tokenize_pair
from model_heads import _MISSING_REASONING_CATEGORIES
from reasoning_dimension_relevance import ALL_DIMENSIONS, relevant_dimensions
from training_example import TrainingExample
from training_experimentation import DatasetSplit

# Four-dimension migration (additive): the canonical dimension names, as
# plain strings (matching `DimensionLabel.name`'s literal keys — see
# `four_dim_dataset._judge_dimension_labels`), not the `EvaluationDimension`
# enum objects themselves. `collate_fn`/`build_dataloaders` default to the
# LEGACY `ALL_DIMENSIONS` scheme unchanged (every existing call site keeps
# today's exact behavior); passing `dimension_names=CANONICAL_DIMENSION_KEYS`
# switches to the four-canonical-dimension scheme.
CANONICAL_DIMENSION_KEYS: tuple[str, ...] = canonical_dimension_keys()

_CONCEPT_STATUS_ORDER: tuple[ConceptObservationStatus, ...] = (
    ConceptObservationStatus.DEMONSTRATED, ConceptObservationStatus.SUPERFICIAL, ConceptObservationStatus.OMITTED,
)


def score_to_tier(score: float) -> int:
    """Bins a continuous [0,1] `DimensionLabel.score` into the same 5-tier
    scale `HeuristicEvaluator._grade` already uses (0.80/0.60/0.40/0.25
    cutpoints) — reused thresholds, not invented ones (approved decision:
    per-dimension ordinal via the existing cutpoint scheme). Duplicated
    locally rather than importing `heuristic_evaluator.py` (forbidden — see
    this layer's import-boundary test), same "deliberate independence
    between evaluator implementations" precedent already used elsewhere."""
    if score >= 0.80:
        return 4  # excellent
    if score >= 0.60:
        return 3  # good
    if score >= 0.40:
        return 2  # adequate
    if score >= 0.25:
        return 1  # weak
    return 0  # poor


class TrainingExampleDataset(Dataset):
    """One `torch.utils.data.Dataset` view over a `DatasetSplit` subset
    ("train"/"val"/"test") of `examples` — membership by
    `metadata.example_id`, mirroring `DatasetManifest`'s own "reference, not
    ownership" philosophy for which ids belong to which split."""

    def __init__(self, examples: tuple[TrainingExample, ...], split: DatasetSplit, subset: str):
        ids_by_subset = {"train": split.train_ids, "val": split.val_ids, "test": split.test_ids}
        if subset not in ids_by_subset:
            raise ValueError(f"subset must be one of {sorted(ids_by_subset)}, got {subset!r}")
        by_id = {e.metadata.example_id: e for e in examples}
        ids = ids_by_subset[subset]
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise ValueError(
                f"{len(missing)} example_id(s) in split.{subset}_ids were not found in `examples`: {missing[:5]}"
            )
        self._examples: tuple[TrainingExample, ...] = tuple(by_id[i] for i in ids)

    def __len__(self) -> int:
        return len(self._examples)

    def __getitem__(self, index: int) -> TrainingExample:
        return self._examples[index]


def collate_fn(
    batch: list[TrainingExample],
    tokenizer,
    backbone_config: BackboneConfig,
    missing_reasoning_categories: tuple[str, ...] = _MISSING_REASONING_CATEGORIES,
    dimension_names: tuple[str, ...] = ALL_DIMENSIONS,
) -> dict:
    """
    Tokenizes the main (question, answer) pair per example (dynamic
    padding across the batch) plus every (answer, concept) pair flattened
    across the whole batch (approved: "simplest correct implementation" for
    variable-length concept batching — flatten with an index-back-to-example
    mapping rather than pad to a per-batch max-concepts count).

    DIMENSION SCHEME (additive, four-dimension migration): `dimension_names`
    defaults to the LEGACY `ALL_DIMENSIONS` (12-dimension) set, so every
    existing call site is completely unaffected. Passing
    `dimension_names=CANONICAL_DIMENSION_KEYS` switches `dimension_targets`/
    `dimension_mask` to the four canonical dimensions
    (technical_correctness, depth_specificity, relevance_completeness,
    grounding_ownership), in that exact order. The two schemes need
    different masking rules and are never mixed within one call:
      - LEGACY: a dimension is masked in only when it is BOTH labeled AND
        `reasoning_dimension_relevance.relevant_dimensions(...)`-relevant
        for the example's reasoning_type (today's exact behavior).
      - CANONICAL FOUR: every one of the four dimensions applies to every
        question intent by design (`evaluation_dimensions.py`'s own
        `applies_to: "all question intents"` on each rubric) — there is no
        legacy relevance table entry for these names (calling
        `relevant_dimensions()` on them would silently return an
        always-empty set, zeroing every canonical loss term), so masking is
        presence-only: in whenever the example actually carries a labeled
        score for that dimension.
    """
    use_legacy_relevance = set(dimension_names) == set(ALL_DIMENSIONS)
    # Step 2: the main (dimension) pair is now (context, answer) where context
    # = QUESTION + RELEVANT CONTEXT (grounding) + EXPECTED CONCEPTS, built by
    # the SAME `build_dimension_pair` helper the live evaluator uses so the
    # training-time and inference-time framing are identical. The grounding /
    # expected_concepts already live on every TrainingExample's inputs.
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

    n = len(batch)
    dimension_targets = torch.zeros((n, len(dimension_names)), dtype=torch.long)
    dimension_mask = torch.zeros((n, len(dimension_names)), dtype=torch.float)
    for i, example in enumerate(batch):
        labels_by_name = {d.name: d.score for d in example.labels.dimension_labels}
        relevant = relevant_dimensions(example.inputs.reasoning_type) if use_legacy_relevance else None
        for j, name in enumerate(dimension_names):
            if name in labels_by_name:
                dimension_targets[i, j] = score_to_tier(labels_by_name[name])
                if use_legacy_relevance:
                    if name in relevant:
                        dimension_mask[i, j] = 1.0
                else:
                    dimension_mask[i, j] = 1.0

    presence_target = torch.zeros((n, len(missing_reasoning_categories)), dtype=torch.float)
    severity_target = torch.zeros((n, len(missing_reasoning_categories)), dtype=torch.float)
    for i, example in enumerate(batch):
        present_categories = {ml.category: ml.severity for ml in example.labels.missing_reasoning_labels}
        for j, category in enumerate(missing_reasoning_categories):
            if category in present_categories:
                presence_target[i, j] = 1.0
                severity_target[i, j] = present_categories[category]

    concept_pairs: list[tuple[str, str]] = []
    concept_targets: list[int] = []
    concept_example_index: list[int] = []
    for i, example in enumerate(batch):
        for concept_label in example.labels.concept_labels:
            concept_pairs.append((example.inputs.answer_text, concept_label.concept))
            concept_targets.append(_CONCEPT_STATUS_ORDER.index(concept_label.status))
            concept_example_index.append(i)

    if concept_pairs:
        concept_encodings = [
            tokenize_pair(tokenizer, answer, concept, backbone_config.max_length) for answer, concept in concept_pairs
        ]
        concept_batch = tokenizer.pad(concept_encodings, return_tensors="pt")
        concept_input_ids = concept_batch["input_ids"]
        concept_attention_mask = concept_batch["attention_mask"]
    else:
        concept_input_ids = None
        concept_attention_mask = None

    return {
        "example_ids": [e.metadata.example_id for e in batch],
        "main_input_ids": main_batch["input_ids"],
        "main_attention_mask": main_batch["attention_mask"],
        "dimension_targets": dimension_targets,
        "dimension_mask": dimension_mask,
        "presence_target": presence_target,
        "severity_target": severity_target,
        "concept_input_ids": concept_input_ids,
        "concept_attention_mask": concept_attention_mask,
        "concept_targets": torch.tensor(concept_targets, dtype=torch.long),
        "concept_example_index": torch.tensor(concept_example_index, dtype=torch.long),
    }


def build_dataloaders(
    examples: tuple[TrainingExample, ...],
    split: DatasetSplit,
    tokenizer,
    backbone_config: BackboneConfig,
    batch_size: int = 8,
    missing_reasoning_categories: tuple[str, ...] = _MISSING_REASONING_CATEGORIES,
    seed: Optional[int] = None,
    dimension_names: tuple[str, ...] = ALL_DIMENSIONS,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Builds (train_loader, val_loader, test_loader) from an
    already-computed `DatasetSplit` — this module never calls
    `training_experimentation.split_dataset` itself; the caller does, and
    passes the result in, keeping split-computation single-sourced.

    REPRODUCIBILITY (Experiment 0, research-validity milestone): if `seed`
    is given, the TRAIN loader's shuffle order is controlled by an explicit
    `torch.Generator().manual_seed(seed)` rather than PyTorch's implicit
    global RNG state — this is deliberately independent of, and
    complementary to, `model_heads.train_model`'s own `random_seed`
    parameter (which covers weight initialization and dropout), so
    reproducibility does not depend on the exact order in which global
    state happens to be consumed across both modules. `val`/`test` loaders
    never shuffle, so `seed` has no effect on them. `seed=None` (the
    default) preserves the previous, unseeded behavior exactly.
    """

    def _collate(batch: list[TrainingExample]) -> dict:
        return collate_fn(batch, tokenizer, backbone_config, missing_reasoning_categories, dimension_names)

    def _loader(subset: str, shuffle: bool) -> DataLoader:
        dataset = TrainingExampleDataset(examples, split, subset)
        generator = None
        if shuffle and seed is not None:
            generator = torch.Generator()
            generator.manual_seed(seed)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=_collate, generator=generator)

    return _loader("train", True), _loader("val", False), _loader("test", False)
