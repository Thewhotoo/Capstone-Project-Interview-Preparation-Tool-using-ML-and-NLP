"""
Checkpoint IO — Model-Implementation Layer (see model_backbone.py's
docstring for this layer's overall provenance/approval history).

Bridges torch state-dicts to `training_experimentation.Checkpoint`'s opaque
`artifact_uri` string. `training_experimentation.py` itself is never
modified and never imports torch — this is the one place a real filesystem
path gets real meaning; `Checkpoint` continues to treat it as an opaque
string, exactly as designed.
"""

from __future__ import annotations

from typing import Optional

import torch
from torch import nn

from model_backbone import BackboneConfig
from model_heads import MultiTaskModel


def save_checkpoint_artifact(model: MultiTaskModel, path: str) -> str:
    """Saves `model`'s state dict to `path` and returns `path` — the value
    to hand to `training_experimentation.assemble_checkpoint`'s
    `artifact_uri` argument."""
    torch.save(model.state_dict(), path)
    return path


def load_checkpoint_artifact(
    path: str,
    backbone_config: BackboneConfig,
    dimension_names: Optional[tuple[str, ...]] = None,
    missing_reasoning_categories: Optional[tuple[str, ...]] = None,
    num_ordinal_classes: int = 5,
    backbone: Optional[nn.Module] = None,
) -> MultiTaskModel:
    """Reconstructs a fresh `MultiTaskModel` (the architecture, not the
    weights) matching the given config/head shapes, then loads `path`'s
    saved state dict into it. The architecture must match whatever produced
    `path` — this function does not (and cannot) infer head shapes from the
    saved file alone. `backbone` lets a caller inject the SAME (e.g. tiny
    random-init test) backbone architecture the checkpoint was trained
    with — mirrors `train_model`'s own `backbone` override parameter;
    production callers leave it `None` and get the real pretrained model
    architecture matching `backbone_config.hf_model_id`."""
    from reasoning_dimension_relevance import ALL_DIMENSIONS
    from model_heads import _MISSING_REASONING_CATEGORIES

    model = MultiTaskModel(
        backbone_config,
        backbone=backbone,
        dimension_names=dimension_names or ALL_DIMENSIONS,
        missing_reasoning_categories=missing_reasoning_categories or _MISSING_REASONING_CATEGORIES,
        num_ordinal_classes=num_ordinal_classes,
    )
    state_dict = torch.load(path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model
