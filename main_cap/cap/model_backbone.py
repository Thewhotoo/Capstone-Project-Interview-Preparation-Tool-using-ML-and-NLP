"""
Model Backbone — Model-Implementation Layer (deferred layer from the
Training & Experimentation milestone, approved this session; no RFC text
existed for this layer — design was proposed fresh from the codebase and
approved with clarifications before any code was written).

DeBERTa-v3 CROSS-ENCODER backbone + tokenizer pipeline, per the frozen ML
Architecture RFC's backbone recommendation (summarized in
SESSION_HANDOFF.md §3b item 2). "Cross-encoder" is the load-bearing
architectural choice: ONE shared encoder, invoked once per (text_a, text_b)
pair. Every downstream head (dimension scores, concept-observation) is a
separate forward pass through THIS SAME module with a different pairing —
never a separate per-side embedding computed once and reused (that would be
a bi-encoder).

CLS pooling is the default (DeBERTa's own convention, approved clarification
#2); mean-pooling is also implemented and selectable via `BackboneConfig`.
"""

from __future__ import annotations

from typing import Optional

import torch
from pydantic import BaseModel, ConfigDict, model_validator
from torch import nn


def _require_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


class BackboneConfig(BaseModel):
    """Opaque, caller-supplied backbone identity — `hf_model_id` defaults to
    the RFC's own named recommendation but is never hard-coded elsewhere."""

    model_config = ConfigDict(frozen=True)

    hf_model_id: str = "microsoft/deberta-v3-base"
    max_length: int = 256
    pooling: str = "cls"  # "cls" or "mean"

    @model_validator(mode="after")
    def _validate(self) -> "BackboneConfig":
        _require_non_empty(self.hf_model_id, "hf_model_id")
        if self.max_length < 1:
            raise ValueError("max_length must be >= 1")
        if self.pooling not in ("cls", "mean"):
            raise ValueError(f"pooling must be 'cls' or 'mean', got {self.pooling!r}")
        return self


def build_tokenizer(config: BackboneConfig):
    """Lazy import — `transformers` is a heavy dependency, imported only
    when actually needed (same lazy-load discipline `heuristic_evaluator.py`
    already uses for `sentence-transformers`)."""
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(config.hf_model_id)


def tokenize_pair(tokenizer, text_a: str, text_b: str, max_length: int):
    """Standard HF sentence-pair tokenization — '[CLS] text_a [SEP] text_b
    [SEP]', truncated to `max_length`. Padding is intentionally NOT applied
    here — it happens per-batch (dynamic padding, standard HF practice) in
    `model_dataset.collate_fn`."""
    return tokenizer(text_a, text_b, truncation=True, max_length=max_length)


# ═════════════════════════════════════════════════════════════════════════════
# Contextual dimension-model input (Step 2: feed context into the evaluator)
# ═════════════════════════════════════════════════════════════════════════════
# The dimension model is a CROSS-ENCODER over a (text_a, text_b) pair. Before
# this step text_a was the bare question; the grounding/expected-concepts that
# already exist on EvaluationRequest / TrainingExampleInputs were never shown
# to the model, so it could not judge relevance-completeness or
# grounding-ownership properly. These helpers build a DETERMINISTIC, labeled
# text_a from that context; the candidate ANSWER stays as text_b (segment B),
# so the model still sees exactly one [CLS] context [SEP] answer [SEP] pair —
# the cross-encoder shape and the CORAL heads are unchanged.
#
# Answer-as-segment-B is deliberate (not a fourth "ANSWER:" section inside
# text_a): it keeps the answer as the distinct thing being judged, matches the
# pre-existing segment-B-is-answer convention, and avoids duplicating the
# answer text (which would waste the max_length budget). Truncation is
# unchanged (`tokenize_pair(..., truncation=True, max_length=...)`), and HF's
# default longest-first strategy trims the (usually longer) context before the
# answer, so the answer is preserved under truncation.
#
# NOTE (checkpoint compatibility): the CURRENTLY deployed checkpoint was
# trained on (question, answer) only. This change makes the INPUT PIPELINE
# context-aware for the FUTURE four-dimension retrain; it does NOT make the
# existing checkpoint context-aware or more accurate — the existing weights
# have never seen the "QUESTION:/RELEVANT CONTEXT:/EXPECTED CONCEPTS:" framing.


def grounding_to_text(grounding) -> str:
    """Flattens a QuestionSpecification-style grounding (project / experience
    / certification) into a single plain-text context string. Duck-typed
    (attribute access via getattr) so it works for both the real
    `Grounding` object and any lightweight test stand-in, and never raises on
    a missing/empty field."""
    project = getattr(grounding, "project", None)
    if project is not None:
        parts = [getattr(project, "title", "") or "", getattr(project, "summary", "") or ""]
        parts += [str(t) for t in (getattr(project, "technologies", ()) or [])]
        parts += [str(c) for c in (getattr(project, "concepts", ()) or [])]
        return " ".join(p for p in parts if p).strip()
    experience = getattr(grounding, "experience", None)
    if experience is not None:
        parts = [
            getattr(experience, "role", "") or "",
            getattr(experience, "company", "") or "",
            getattr(experience, "summary", "") or "",
        ]
        return " ".join(p for p in parts if p).strip()
    certification = getattr(grounding, "certification", None)
    if certification is not None:
        return (getattr(certification, "name", "") or "").strip()
    return ""


def build_dimension_input_text(
    question_text: str,
    grounding_text: str = "",
    expected_concepts: "tuple[str, ...] | list[str]" = (),
) -> str:
    """Builds the deterministic, labeled context string used as `text_a` for
    the dimension model. Always includes a QUESTION section; includes
    RELEVANT CONTEXT and EXPECTED CONCEPTS sections ONLY when non-empty, so an
    absent grounding or empty concept list simply omits that section rather
    than emitting a dangling label (safe handling of missing context). The
    candidate answer is NOT included here — it is passed separately as the
    pair's second segment (see module note above)."""
    sections = [f"QUESTION:\n{(question_text or '').strip()}"]
    grounding = (grounding_text or "").strip()
    if grounding:
        sections.append(f"RELEVANT CONTEXT:\n{grounding}")
    concepts = [str(c).strip() for c in (expected_concepts or ()) if c and str(c).strip()]
    if concepts:
        sections.append("EXPECTED CONCEPTS:\n" + ", ".join(concepts))
    return "\n\n".join(sections)


def build_dimension_pair(
    question_text: str,
    grounding_text: str,
    expected_concepts: "tuple[str, ...] | list[str]",
    answer_text: str,
) -> tuple[str, str]:
    """The full (text_a, text_b) pair the dimension model is tokenized on:
    the labeled context block, and the candidate answer. A single call site
    for both training (`model_dataset.collate_fn`) and inference
    (`model_evaluator.TrainedEvaluator.evaluate`) so the framing can never
    drift between them."""
    return (
        build_dimension_input_text(question_text, grounding_text, expected_concepts),
        answer_text or "",
    )


class CrossEncoderBackbone(nn.Module):
    """Wraps a HuggingFace `AutoModel` encoder. One forward pass = one
    (text_a, text_b) pair -> one pooled embedding vector. `encoder` may be
    injected directly (used by `build_tiny_random_backbone` for tests) —
    production code leaves it `None` and gets the real pretrained model."""

    def __init__(self, config: BackboneConfig, encoder: Optional[nn.Module] = None):
        super().__init__()
        self.config = config
        if encoder is not None:
            self.encoder = encoder
        else:
            from transformers import AutoModel
            # Force fp32 explicitly -- `from_pretrained` otherwise picks up
            # whatever dtype the checkpoint's own metadata declares (e.g.
            # fp16 for microsoft/deberta-v3-base), which would silently
            # mismatch model_heads.py's fp32 head layers (a real bug this
            # fixes: "expected m1 and m2 to have the same dtype"). Every
            # other part of this model (heads, training loop) assumes fp32
            # throughout -- this is a correctness fix, not a precision
            # policy choice.
            self.encoder = AutoModel.from_pretrained(config.hf_model_id, torch_dtype=torch.float32)
        self.hidden_size = self.encoder.config.hidden_size

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        hidden = outputs.last_hidden_state  # (batch, seq, hidden)
        if self.config.pooling == "cls":
            return hidden[:, 0, :]
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        summed = (hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        return summed / counts


def build_tiny_random_encoder(
    tokenizer,
    hf_model_id: str = "microsoft/deberta-v3-base",
    hidden_size: int = 16,
    num_hidden_layers: int = 1,
    num_attention_heads: int = 2,
    intermediate_size: int = 32,
) -> CrossEncoderBackbone:
    """
    TEST-ONLY helper (approved clarification #4): builds a randomly-
    initialized, tiny DeBERTa-v2 `CrossEncoderBackbone` — NOT pretrained
    weights (avoids the ~700MB production download in unit tests) — sized
    to match an ALREADY-BUILT `tokenizer`'s vocabulary (so token ids stay
    valid). Takes the tokenizer as a parameter rather than building one
    itself so a test suite can build the (comparatively slow, one-time)
    tokenizer ONCE and reuse it across many fast, independent tiny encoders
    — each test needing its own untrained weights (e.g. before/after a
    training step) doesn't need to re-download or re-instantiate the
    tokenizer. Never used in the production training/inference path;
    dedicated integration tests are the place for exercising real
    pretrained weights.
    """
    from transformers import AutoModel, DebertaV2Config

    tiny_hf_config = DebertaV2Config(
        vocab_size=tokenizer.vocab_size,
        hidden_size=hidden_size,
        num_hidden_layers=num_hidden_layers,
        num_attention_heads=num_attention_heads,
        intermediate_size=intermediate_size,
        pad_token_id=tokenizer.pad_token_id or 0,
    )
    encoder = AutoModel.from_config(tiny_hf_config)
    backbone_config = BackboneConfig(hf_model_id=hf_model_id)
    return CrossEncoderBackbone(backbone_config, encoder=encoder)


def build_tiny_random_backbone(
    hf_model_id: str = "microsoft/deberta-v3-base",
    hidden_size: int = 16,
    num_hidden_layers: int = 1,
    num_attention_heads: int = 2,
    intermediate_size: int = 32,
) -> tuple[CrossEncoderBackbone, object]:
    """Convenience wrapper: builds a fresh tokenizer AND a matching tiny
    encoder together. Prefer `build_tiny_random_encoder(tokenizer, ...)`
    directly when building many tiny backbones against one shared,
    already-built tokenizer (e.g. across a test suite) — see its docstring."""
    tokenizer = build_tokenizer(BackboneConfig(hf_model_id=hf_model_id))
    encoder = build_tiny_random_encoder(
        tokenizer, hf_model_id=hf_model_id, hidden_size=hidden_size,
        num_hidden_layers=num_hidden_layers, num_attention_heads=num_attention_heads,
        intermediate_size=intermediate_size,
    )
    return encoder, tokenizer
