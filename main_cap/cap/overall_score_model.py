"""
Overall Score Model — V3 Single-Overall-Score Architecture (isolated,
additive; supersedes NOTHING currently deployed — see module docstring of
`overall_single_evaluator.py` for the production-integration status).

ARCHITECTURE (as specified for this redesign):

    Input (QUESTION + RELEVANT CONTEXT + EXPECTED CONCEPTS as text_a,
    CANDIDATE ANSWER as text_b) -> DeBERTa-v3-base (CrossEncoderBackbone,
    UNCHANGED, reused from `model_backbone.py`) -> pooled representation
    -> ONE `CoralOrdinalHead` (UNCHANGED, reused from `model_heads.py`) ->
    overall_score, ordinal 0-4.

This is deliberately NOT `model_heads.MultiTaskModel` — that class always
builds one `CoralOrdinalHead` PER dimension (`DimensionOrdinalHeads`) plus a
concept head and a missing-reasoning head. This module is a genuinely
smaller model: a single shared CORAL head on top of the same backbone, no
per-dimension heads, no concept head, no missing-reasoning head. Reusing
`MultiTaskModel` and masking away everything but one dimension would still
carry three unused heads (extra parameters, extra state-dict entries, a
confusing "12-headed model gradually being run with only 1 used") — a
genuinely isolated, minimal class is the smaller and clearer change.

REUSE, NOT REIMPLEMENTATION: `CrossEncoderBackbone`/`BackboneConfig` (from
`model_backbone.py`) and `CoralOrdinalHead`/`coral_loss` (from
`model_heads.py`) are imported and used UNCHANGED by this module.
`coral_predict`/`coral_confidence` (also from `model_heads.py`, also
unmodified) are used downstream by `overall_single_evaluator.py` and
`run_overall_single_training.py`, which import them directly rather than
through this module — nothing here re-exports them. Nothing in either of
`model_backbone.py`/`model_heads.py` is modified by this file.

TRAINING LOOP: deliberately NOT `model_heads.train_model` (that function is
wired to `MultiTaskModel`'s multi-head `compute_batch_loss`, which expects
`dimension_targets`/`dimension_mask`/`presence_target`/`concept_*` batch
keys this model's much simpler batches don't have). `train_overall_model`
below is a minimal, single-head analogue of the same reference-trainer
shape (fixed epoch count, one AdamW optimizer, no mixed precision, no
distributed training, no LR schedule — same explicitly-scoped-down
discipline `model_heads.train_model`'s own docstring documents), using
PLAIN UNWEIGHTED CORAL loss only (no A1/A2 pos_weight machinery — this
redesign does not use loss weighting).
"""

from __future__ import annotations

from typing import Callable, Optional

import torch
from torch import nn
from torch.utils.data import DataLoader

from model_backbone import BackboneConfig, CrossEncoderBackbone
from model_heads import CoralOrdinalHead, coral_loss

NUM_ORDINAL_CLASSES: int = 5  # poor, weak, adequate, good, excellent — same 5-tier scale as everything else


class OverallScoreModel(nn.Module):
    """DeBERTa-v3-base backbone + ONE `CoralOrdinalHead` -> a single ordinal
    0-4 overall score. `backbone` may be injected (tiny random-init, for
    tests) exactly like `model_heads.MultiTaskModel`'s own `backbone`
    override parameter — production code leaves it `None` and gets the real
    pretrained model."""

    def __init__(
        self,
        backbone_config: BackboneConfig,
        backbone: Optional[nn.Module] = None,
        num_ordinal_classes: int = NUM_ORDINAL_CLASSES,
    ):
        super().__init__()
        self.backbone = backbone if backbone is not None else CrossEncoderBackbone(backbone_config)
        self.num_ordinal_classes = num_ordinal_classes
        self.head = CoralOrdinalHead(self.backbone.hidden_size, num_ordinal_classes)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Returns CORAL threshold logits, shape (batch, num_ordinal_classes - 1)."""
        pooled = self.backbone(input_ids, attention_mask)
        return self.head(pooled)


def compute_overall_batch_loss(model: OverallScoreModel, batch: dict, device: str = "cpu") -> torch.Tensor:
    """Plain, UNWEIGHTED CORAL loss over the single overall target — no
    `pos_weight`, no A1/A2 loss-weighting machinery (this redesign's own
    spec: "Use unweighted CORAL loss. No A1/A2 weighting.")."""
    input_ids = batch["main_input_ids"].to(device)
    attention_mask = batch["main_attention_mask"].to(device)
    targets = batch["overall_target"].to(device)
    logits = model(input_ids, attention_mask)
    return coral_loss(logits, targets, model.num_ordinal_classes)


def train_overall_model(
    train_loader: DataLoader,
    val_loader: Optional[DataLoader],
    backbone_config: BackboneConfig,
    num_epochs: int = 1,
    learning_rate: float = 2e-5,
    device: str = "cpu",
    backbone: Optional[nn.Module] = None,
    random_seed: Optional[int] = None,
    on_epoch_end: Optional[Callable[[int, OverallScoreModel, Optional[float], Optional[float]], None]] = None,
    weight_decay: float = 0.01,
) -> OverallScoreModel:
    """Minimal reference trainer for `OverallScoreModel` — single-head
    analogue of `model_heads.train_model` (see module docstring for why
    that function isn't reused directly). Fixed epoch count, plain AdamW,
    no scheduler (matches this redesign's spec: "no scheduler"), unweighted
    CORAL loss only.

    REPRODUCIBILITY: identical discipline to `model_heads.train_model` --
    if `random_seed` is given, `torch.manual_seed(random_seed)` is called
    BEFORE the model is constructed, so freshly-initialized head weights and
    dropout masks are reproducible. `train_loader`'s own shuffle order is a
    separate concern, controlled by the caller's `DataLoader`/`Generator`
    (see `overall_dataset.build_overall_dataloaders`'s `seed` parameter).
    """
    if random_seed is not None:
        torch.manual_seed(random_seed)

    model = OverallScoreModel(backbone_config, backbone=backbone)
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    if on_epoch_end is not None:
        model.eval()
        on_epoch_end(0, model, None, None)

    for epoch_index in range(1, num_epochs + 1):
        model.train()
        train_loss_total = 0.0
        train_batch_count = 0
        for batch in train_loader:
            optimizer.zero_grad()
            loss = compute_overall_batch_loss(model, batch, device)
            loss.backward()
            optimizer.step()
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
                    loss = compute_overall_batch_loss(model, batch, device)
                    val_loss_total += loss.item()
                    val_batch_count += 1
            avg_val_loss = (val_loss_total / val_batch_count) if val_batch_count else None

        if on_epoch_end is not None:
            model.eval()
            on_epoch_end(epoch_index, model, avg_train_loss, avg_val_loss)

    model.eval()
    return model


# ═════════════════════════════════════════════════════════════════════════════
# Checkpoint IO — isolated from model_checkpoint_io.py (that module's
# load/save functions are typed to `model_heads.MultiTaskModel`'s
# architecture; reusing them for a differently-shaped model would be a type
# mismatch dressed up as reuse). Same simple `torch.save(state_dict)` /
# reconstruct-then-`load_state_dict` pattern, applied to `OverallScoreModel`.
# ═════════════════════════════════════════════════════════════════════════════


def save_overall_checkpoint_artifact(model: OverallScoreModel, path: str) -> str:
    """Saves `model`'s state dict to `path` and returns `path`."""
    torch.save(model.state_dict(), path)
    return path


def load_overall_checkpoint_artifact(
    path: str,
    backbone_config: BackboneConfig,
    num_ordinal_classes: int = NUM_ORDINAL_CLASSES,
    backbone: Optional[nn.Module] = None,
    map_location: str = "cpu",
) -> OverallScoreModel:
    """Reconstructs a fresh `OverallScoreModel` (architecture only) matching
    the given config, then loads `path`'s saved state dict into it. Mirrors
    `model_checkpoint_io.load_checkpoint_artifact`'s own contract (the
    architecture must match whatever produced `path` — this function does
    not and cannot infer head shape from the saved file alone)."""
    model = OverallScoreModel(backbone_config, backbone=backbone, num_ordinal_classes=num_ordinal_classes)
    state_dict = torch.load(path, map_location=map_location)
    model.load_state_dict(state_dict)
    model.to(map_location)
    model.eval()
    return model
