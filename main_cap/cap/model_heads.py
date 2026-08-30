"""
Model Heads — Model-Implementation Layer (see model_backbone.py's docstring
for this layer's overall provenance/approval history).

Multi-task heads sitting on top of `CrossEncoderBackbone`'s pooled
embeddings, the CORAL ordinal-regression implementation (approved as the
specific technique), the two architecturally-different Missing-Reasoning
vs. Expected-Concepts designs (approved refinement), dimension masking
(reusing `reasoning_dimension_relevance.py`'s existing, frozen config table
— not a new taxonomy), and a minimal reference training loop (approved
clarification #1: no scheduler/mixed-precision/distributed training/
hyperparameter search — explicitly future work).

CONFIDENCE (approved clarification): no separate trained head. Derived
analytically from each CORAL head's own logit entropy — `coral_confidence`
— never a fabricated ground truth (there is no confidence label anywhere in
`TrainingExampleLabels`).

MISSING-REASONING CATEGORY SET: `_MISSING_REASONING_CATEGORIES` below is a
FIXED, closed-in-practice 11-item tuple (mirroring the same list
`generation_recipe._RELEVANT_REASONING_CATEGORIES` already treats as
practically fixed, reimplemented locally rather than importing that
Stage-A-only module — same "deliberate independence between subsystems"
precedent already used elsewhere in this codebase). NOTE: `MissingReasoningCategory`
itself (`evaluation_result.py`) is nominally an OPEN, registry-style
taxonomy — but a shared multi-label classification head, by construction,
requires a FIXED output dimension. If that open registry ever grows with a
genuinely new category, THIS model version simply won't predict it — a new
category requires a new trained model version, which is an inherent,
expected constraint of any trained classifier against an open vocabulary,
not a contradiction of the taxonomy's openness (the schema can always
represent a new value; a specific already-trained model just won't produce
one until retrained). Flagging this explicitly rather than glossing over it.
"""

from __future__ import annotations

from typing import Callable, Optional

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader

from evaluation_result import MissingReasoningCategory
from reasoning_dimension_relevance import ALL_DIMENSIONS

# The 11-category fixed-in-practice set this model version's shared
# multi-label head predicts over (see module docstring's note on the
# open/closed distinction).
_MISSING_REASONING_CATEGORIES: tuple[str, ...] = (
    MissingReasoningCategory.TRADEOFF, MissingReasoningCategory.ARCHITECTURE, MissingReasoningCategory.EXAMPLE,
    MissingReasoningCategory.TESTING, MissingReasoningCategory.DEBUGGING, MissingReasoningCategory.METRICS,
    MissingReasoningCategory.EDGE_CASE, MissingReasoningCategory.SCALABILITY, MissingReasoningCategory.DESIGN_DECISION,
    MissingReasoningCategory.OWNERSHIP, MissingReasoningCategory.COMMUNICATION,
)

_NUM_ORDINAL_CLASSES_DEFAULT = 5  # poor, weak, adequate, good, excellent


# ═════════════════════════════════════════════════════════════════════════════
# CORAL ordinal regression (approved as the specific technique)
# ═════════════════════════════════════════════════════════════════════════════


class CoralOrdinalHead(nn.Module):
    """
    Rank-consistent ordinal regression head (Cao et al., CORAL): a single
    shared linear projection plus `num_classes - 1` monotonically
    non-increasing bias terms, producing `P(tier > k)` logits for
    k=0..num_classes-2. Monotonicity is architecturally guaranteed (biases
    are `base - cumulative softplus offsets`, which is always
    non-increasing) rather than merely encouraged by the loss — this is
    what distinguishes CORAL from plain independent binary classifiers.
    """

    def __init__(self, in_features: int, num_classes: int = _NUM_ORDINAL_CLASSES_DEFAULT):
        super().__init__()
        if num_classes < 2:
            raise ValueError("num_classes must be >= 2")
        self.num_classes = num_classes
        self.num_thresholds = num_classes - 1
        self.shared = nn.Linear(in_features, 1, bias=False)
        self.bias_base = nn.Parameter(torch.zeros(1))
        if self.num_thresholds > 1:
            self.bias_deltas = nn.Parameter(torch.ones(self.num_thresholds - 1) * 0.5)
        else:
            self.register_parameter("bias_deltas", None)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logit = self.shared(x)  # (batch, 1)
        if self.bias_deltas is not None:
            offsets = torch.cat([
                torch.zeros(1, device=x.device, dtype=x.dtype),
                torch.cumsum(F.softplus(self.bias_deltas), dim=0),
            ])
        else:
            offsets = torch.zeros(1, device=x.device, dtype=x.dtype)
        biases = self.bias_base - offsets  # (num_thresholds,), non-increasing
        return logit + biases.unsqueeze(0)  # (batch, num_thresholds)


def coral_targets(y: torch.Tensor, num_classes: int) -> torch.Tensor:
    """`y`: (batch,) int ordinal labels in [0, num_classes-1] -> (batch,
    num_classes-1) binary targets, `t_k = 1[y > k]`."""
    thresholds = torch.arange(num_classes - 1, device=y.device).unsqueeze(0)
    return (y.unsqueeze(1) > thresholds).float()


def coral_loss(logits: torch.Tensor, y: torch.Tensor, num_classes: int) -> torch.Tensor:
    """Rank-consistent binary cross-entropy across all thresholds, averaged
    over the batch and thresholds."""
    targets = coral_targets(y, num_classes)
    return F.binary_cross_entropy_with_logits(logits, targets)


def coral_predict(logits: torch.Tensor) -> torch.Tensor:
    """Predicted ordinal class = number of thresholds exceeded (P > 0.5)."""
    probs = torch.sigmoid(logits)
    return (probs > 0.5).sum(dim=1)


def coral_confidence(logits: torch.Tensor) -> torch.Tensor:
    """
    Analytical confidence (approved: no separate trained head) — 1 minus the
    mean binary entropy (in bits, so already in [0,1]) across the
    thresholds' sigmoid probabilities. A confident (near-0-or-1 at every
    threshold) prediction scores near 1.0; a maximally uncertain one (every
    threshold at 0.5) scores near 0.0.
    """
    probs = torch.sigmoid(logits).clamp(1e-6, 1 - 1e-6)
    entropy = -(probs * torch.log2(probs) + (1 - probs) * torch.log2(1 - probs))
    return 1.0 - entropy.mean(dim=1)


# ═════════════════════════════════════════════════════════════════════════════
# Per-dimension ordinal heads (masking reuses reasoning_dimension_relevance.py)
# ═════════════════════════════════════════════════════════════════════════════


class DimensionOrdinalHeads(nn.Module):
    """One `CoralOrdinalHead` per dimension in `dimension_names` — ALL 12 are
    always computed (a real trained model always declares full coverage,
    per `TrainedEvaluator.declared_dimensions`); masking irrelevant
    dimensions for a given `ReasoningType` happens at LOSS time
    (`compute_batch_loss`) and at read time (`TrainedEvaluator.evaluate`
    only reports relevant ones), never by omitting a head."""

    def __init__(self, in_features: int, dimension_names: tuple[str, ...] = ALL_DIMENSIONS,
                 num_classes: int = _NUM_ORDINAL_CLASSES_DEFAULT):
        super().__init__()
        self.dimension_names = dimension_names
        self.num_classes = num_classes
        self.heads = nn.ModuleDict({
            name: CoralOrdinalHead(in_features, num_classes) for name in dimension_names
        })

    def forward(self, pooled: torch.Tensor) -> dict[str, torch.Tensor]:
        return {name: head(pooled) for name, head in self.heads.items()}


# ═════════════════════════════════════════════════════════════════════════════
# Expected Concepts — separate cross-encoder pass per concept (approved, retained)
# ═════════════════════════════════════════════════════════════════════════════


class ConceptObservationHead(nn.Module):
    """3-class head (DEMONSTRATED/SUPERFICIAL/OMITTED) off a per-(answer,
    concept) cross-encoder pass — Expected Concepts are dynamic/open
    (`expected_concepts_registry.py`'s growable lookup table), so each
    concept gets its own true cross-encoder invocation, unlike Missing
    Reasoning's fixed multi-label head below."""

    def __init__(self, in_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, 3)

    def forward(self, pooled: torch.Tensor) -> torch.Tensor:
        return self.linear(pooled)


# ═════════════════════════════════════════════════════════════════════════════
# Missing Reasoning — single shared multi-label head (approved refinement)
# ═════════════════════════════════════════════════════════════════════════════


class MissingReasoningHead(nn.Module):
    """Single shared multi-label classification head off the MAIN (question,
    answer) pooled representation — NOT a per-category cross-encoder pass
    (approved architectural refinement: missing-reasoning categories are a
    small, fixed-in-practice set, unlike Expected Concepts). Two output
    projections: `presence` (multi-label binary per category) and
    `severity` (regression per category, meaningful only where present)."""

    def __init__(self, in_features: int, num_categories: int = len(_MISSING_REASONING_CATEGORIES)):
        super().__init__()
        self.presence = nn.Linear(in_features, num_categories)
        self.severity = nn.Linear(in_features, num_categories)

    def forward(self, pooled: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.presence(pooled), torch.sigmoid(self.severity(pooled))


def missing_reasoning_loss(
    presence_logits: torch.Tensor, severity_pred: torch.Tensor,
    presence_target: torch.Tensor, severity_target: torch.Tensor,
) -> torch.Tensor:
    """Presence: multi-label BCE across all categories. Severity: masked
    smooth-L1, computed ONLY where `presence_target == 1` — this mirrors
    `ReasoningCategoryTarget`'s own existing frozen invariant ("severity must
    be 0.0 when present=False"), not a new rule invented here."""
    presence_loss = F.binary_cross_entropy_with_logits(presence_logits, presence_target)
    severity_loss_per = F.smooth_l1_loss(severity_pred, severity_target, reduction="none") * presence_target
    denom = presence_target.sum().clamp(min=1.0)
    severity_loss = severity_loss_per.sum() / denom
    return presence_loss + severity_loss


# ═════════════════════════════════════════════════════════════════════════════
# MultiTaskModel — backbone + all heads
# ═════════════════════════════════════════════════════════════════════════════


class MultiTaskModel(nn.Module):
    def __init__(
        self,
        backbone_config,
        backbone: Optional[nn.Module] = None,
        dimension_names: tuple[str, ...] = ALL_DIMENSIONS,
        missing_reasoning_categories: tuple[str, ...] = _MISSING_REASONING_CATEGORIES,
        num_ordinal_classes: int = _NUM_ORDINAL_CLASSES_DEFAULT,
    ):
        super().__init__()
        from model_backbone import CrossEncoderBackbone

        self.backbone = backbone if backbone is not None else CrossEncoderBackbone(backbone_config)
        hidden = self.backbone.hidden_size
        self.dimension_names = dimension_names
        self.missing_reasoning_categories = missing_reasoning_categories
        self.num_ordinal_classes = num_ordinal_classes
        self.dimension_heads = DimensionOrdinalHeads(hidden, dimension_names, num_ordinal_classes)
        self.concept_head = ConceptObservationHead(hidden)
        self.missing_reasoning_head = MissingReasoningHead(hidden, len(missing_reasoning_categories))

    def forward_dimensions(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> dict:
        pooled = self.backbone(input_ids, attention_mask)
        dimension_logits = self.dimension_heads(pooled)
        presence_logits, severity_pred = self.missing_reasoning_head(pooled)
        return {
            "pooled": pooled, "dimension_logits": dimension_logits,
            "presence_logits": presence_logits, "severity_pred": severity_pred,
        }

    def forward_concept(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        pooled = self.backbone(input_ids, attention_mask)
        return self.concept_head(pooled)


# ═════════════════════════════════════════════════════════════════════════════
# Batch loss + minimal reference trainer (approved clarification #1)
# ═════════════════════════════════════════════════════════════════════════════


def compute_batch_loss(model: MultiTaskModel, batch: dict, device: str = "cpu") -> torch.Tensor:
    """Sums per-dimension CORAL loss (masked to relevant+labeled dimensions
    only), missing-reasoning loss, and concept-observation loss (skipped for
    a batch with no concept pairs at all)."""
    main_ids = batch["main_input_ids"].to(device)
    main_mask = batch["main_attention_mask"].to(device)
    outputs = model.forward_dimensions(main_ids, main_mask)

    total_loss = torch.zeros((), device=device)
    dim_targets = batch["dimension_targets"].to(device)
    dim_mask = batch["dimension_mask"].to(device)
    for j, name in enumerate(model.dimension_names):
        valid = dim_mask[:, j] > 0
        if valid.any():
            logits = outputs["dimension_logits"][name][valid]
            targets = dim_targets[valid, j].clamp(min=0)
            total_loss = total_loss + coral_loss(logits, targets, model.num_ordinal_classes)

    total_loss = total_loss + missing_reasoning_loss(
        outputs["presence_logits"], outputs["severity_pred"],
        batch["presence_target"].to(device), batch["severity_target"].to(device),
    )

    if batch["concept_input_ids"] is not None:
        concept_ids = batch["concept_input_ids"].to(device)
        concept_mask = batch["concept_attention_mask"].to(device)
        concept_logits = model.forward_concept(concept_ids, concept_mask)
        concept_targets = batch["concept_targets"].to(device)
        total_loss = total_loss + F.cross_entropy(concept_logits, concept_targets)

    return total_loss


def _linear_warmup_decay_lambda(step: int, num_warmup_steps: int, num_training_steps: int) -> float:
    """Multiplicative LR factor: linear ramp 0 -> 1 over the first
    `num_warmup_steps` steps, then linear decay 1 -> 0 over the remaining
    steps to `num_training_steps`. Standard transformer fine-tuning shape
    (matches `transformers.get_linear_schedule_with_warmup`'s formula) --
    reimplemented directly on `torch.optim.lr_scheduler.LambdaLR` rather
    than importing that helper, to keep this a single, dependency-free
    function."""
    if step < num_warmup_steps:
        return step / max(1, num_warmup_steps)
    return max(0.0, (num_training_steps - step) / max(1, num_training_steps - num_warmup_steps))


def train_model(
    train_loader: DataLoader,
    val_loader: Optional[DataLoader],
    backbone_config,
    num_epochs: int = 1,
    learning_rate: float = 2e-5,
    num_ordinal_classes: int = _NUM_ORDINAL_CLASSES_DEFAULT,
    missing_reasoning_categories: tuple[str, ...] = _MISSING_REASONING_CATEGORIES,
    device: str = "cpu",
    backbone: Optional[nn.Module] = None,
    random_seed: Optional[int] = None,
    on_epoch_end: Optional[Callable[[int, MultiTaskModel, Optional[float], Optional[float]], None]] = None,
    weight_decay: float = 0.01,
    num_warmup_steps: int = 0,
    use_lr_decay: bool = False,
) -> MultiTaskModel:
    """
    Minimal, reference end-to-end trainer (approved clarification #1) —
    produces a real, loadable `MultiTaskModel`. Deliberately minimal: fixed
    epoch count, a single AdamW optimizer, no mixed precision, no
    distributed training, no hyperparameter search, no early stopping. All
    of that remains explicitly future work for a production training
    harness, not this milestone.

    OPTIONAL LR SCHEDULE (session 11, additive, backward-compatible): by
    default (`use_lr_decay=False`, `num_warmup_steps=0`) there is still NO
    scheduler at all -- the optimizer uses a constant `learning_rate`,
    identical to every previous call site. Passing `use_lr_decay=True`
    switches on a linear warmup (`num_warmup_steps` steps) followed by
    linear decay to zero over the rest of training (`_linear_warmup_decay_lambda`),
    stepped once per optimizer step. `weight_decay` defaults to `0.01` --
    `torch.optim.AdamW`'s own default, so omitting it (as every existing
    caller does) is bit-for-bit identical to before this parameter existed;
    it is now explicit rather than implicit.

    REPRODUCIBILITY (Experiment 0, research-validity milestone): if
    `random_seed` is given, `torch.manual_seed(random_seed)` is called
    FIRST, before the model is constructed and before any training happens
    — this is what makes freshly-initialized head-layer weights (the
    backbone's own pretrained weights are already deterministic, loaded
    from a checkpoint, not randomly initialized) and dropout masks during
    training reproducible. `train_loader`'s own shuffle order is a
    SEPARATE, complementary concern — see `model_dataset.build_dataloaders`'s
    `seed` parameter, which controls that independently via an explicit
    `torch.Generator` rather than relying on this global-state seeding
    alone. `random_seed=None` (the default) preserves the previous,
    unseeded behavior exactly — this is an additive, backward-compatible
    parameter, not a behavior change for existing callers.

    PORTABILITY / best-effort GPU determinism (session 10, Colab vs. local
    execution): when `random_seed` is given and `device` is a CUDA device,
    `torch.backends.cudnn.deterministic`/`benchmark` are set for best-effort
    reproducibility — PyTorch does NOT guarantee bit-identical results
    across different GPU models/driver versions the way `torch.manual_seed`
    alone guarantees on CPU. Honest limitation, not something this function
    can fully close.

    PER-EPOCH CHECKPOINTING (Experiment 1, session 10): if `on_epoch_end` is
    given, it is called once BEFORE training starts — `on_epoch_end(0,
    model, None, None)`, the untrained model — and once after each of the
    `num_epochs` epochs completes — `on_epoch_end(epoch_index, model,
    avg_train_loss, avg_val_loss)` for `epoch_index` in `1..num_epochs`
    (`avg_val_loss` is `None` if `val_loader` is `None`). This lets a caller
    capture/benchmark/persist the model's state at every point along an
    epoch curve from a SINGLE training run instead of restarting training
    from scratch per epoch count. `train_model` itself never persists or
    benchmarks anything — the callback decides what, if anything, to do
    with the model/losses it receives. `on_epoch_end=None` (the default)
    preserves the previous behavior exactly.
    """
    if random_seed is not None:
        torch.manual_seed(random_seed)
        if str(device).startswith("cuda") and torch.cuda.is_available():
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

    model = MultiTaskModel(
        backbone_config, backbone=backbone, missing_reasoning_categories=missing_reasoning_categories,
        num_ordinal_classes=num_ordinal_classes,
    )
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    scheduler = None
    if use_lr_decay:
        total_steps = num_epochs * len(train_loader)
        scheduler = torch.optim.lr_scheduler.LambdaLR(
            optimizer,
            lr_lambda=lambda step: _linear_warmup_decay_lambda(step, num_warmup_steps, total_steps),
        )

    if on_epoch_end is not None:
        model.eval()
        on_epoch_end(0, model, None, None)

    for epoch_index in range(1, num_epochs + 1):
        model.train()
        train_loss_total = 0.0
        train_batch_count = 0
        for batch in train_loader:
            optimizer.zero_grad()
            loss = compute_batch_loss(model, batch, device)
            loss.backward()
            optimizer.step()
            if scheduler is not None:
                scheduler.step()
            train_loss_total += loss.item()
            train_batch_count += 1
        avg_train_loss = (train_loss_total / train_batch_count) if train_batch_count else None

        avg_val_loss = None
        if val_loader is not None:
            model.eval()
            val_loss_total = 0.0
            val_batch_count = 0
            with torch.no_grad():
                for batch in val_loader:
                    loss = compute_batch_loss(model, batch, device)
                    val_loss_total += loss.item()
                    val_batch_count += 1
            avg_val_loss = (val_loss_total / val_batch_count) if val_batch_count else None

        if on_epoch_end is not None:
            model.eval()
            on_epoch_end(epoch_index, model, avg_train_loss, avg_val_loss)

    model.eval()
    return model
