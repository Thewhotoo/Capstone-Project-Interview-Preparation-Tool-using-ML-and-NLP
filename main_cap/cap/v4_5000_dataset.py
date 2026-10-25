"""
V4 5000-Example Dataset — Harness (ingest / validate / dedup / split / report).

Builds the isolated `four_dim_overall_v4_5000` dataset for the single-overall-
score DeBERTa evaluator ENTIRELY from Claude-authored batch files — NO Gemini,
no network, no LLM API of any kind (see this dataset version's requirements
and the project memory). The existing Gemini generation/judge path
(`generation_client`, `rubric_judge`, `four_dim_dataset`) is NOT imported or
used here.

FLOW (resumable):
    author batch_*.jsonl (Claude)                     <- content + 4 labels
      -> ingest_records: per-record deterministic validation
           (schema, banned-phrase, malformed, hallucinated-tech vs grounding,
            four canonical 0-4 tiers, expected-concepts non-leaking)
      -> record_to_training_example (reuses the frozen TrainingExample schema;
           SYNTHETIC provenance, synthetic_ground_truth labels; overall_label
           derived by the EXISTING equal-weight-mean policy -> score_to_tier)
      -> assemble_dataset: + frozen 220, exact + semantic dedup, group-aware
           split (split_dataset_by_group), full acceptance/leakage/distribution
           reports, honest provenance accounting.

RESUME / CHECKPOINT: the dataset is the set of `batch_*.jsonl` files under the
batches dir. Adding more batch files and re-running `assemble_dataset` extends
the dataset — nothing is regenerated, already-authored batches are reused
as-is. `authored_target_remaining()` reports how many more valid examples are
needed to hit the target.

LABELS ARE CLAUDE'S OWN REASONING, honestly tracked as
synthetic_claude_authored / humanized_claude_authored provenance — never
claimed to be human-authored (only the frozen 220 are human_reviewed).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import timezone
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from dataset_filters import (
    exact_qa_duplicate_indices,
    find_banned_phrases,
    hallucinated_technologies,
    is_malformed_answer,
    normalize_for_dedup,
)
from evaluation_dimensions import CANONICAL_DIMENSIONS
from four_dim_experiment_v2_split import load_v2_pool
from model_dataset import score_to_tier
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    QualityTier,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
    TrainingExampleSyntheticMeta,
)
from training_experimentation import DatasetSplit, split_dataset_by_group

# ── constants ────────────────────────────────────────────────────────────────

DATASET_VERSION = "four_dim_overall_v4_5000"
_HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(_HERE, "artifacts", DATASET_VERSION)
BATCHES_DIR = os.path.join(ARTIFACTS_DIR, "batches")
DATASET_DIR = os.path.join(ARTIFACTS_DIR, "dataset")
REPORTS_DIR = os.path.join(ARTIFACTS_DIR, "reports")

TARGET_TOTAL = 5000
FROZEN_COUNT = 220
TARGET_NEW = TARGET_TOTAL - FROZEN_COUNT  # 4780

# Final split ratios (group-aware) over the WHOLE dataset -> ~3500/750/750.
FINAL_SPLIT_RATIOS: tuple[float, float, float] = (0.70, 0.15, 0.15)
FINAL_SPLIT_SEED = "four_dim_overall_v4_5000_split"

SEMANTIC_DEDUP_THRESHOLD = 0.92  # matches dataset_filters.near_duplicate_pairs' documented default

_CANONICAL_KEYS: tuple[str, ...] = tuple(d.value for d in CANONICAL_DIMENSIONS)
_FIXED_CREATED_AT = "2026-09-15T00:00:00+00:00"

# Honest provenance categories.
PROV_FROZEN = "frozen_hand_authored"
PROV_SYNTHETIC = "synthetic_claude_authored"
PROV_HUMANIZED = "humanized_claude_authored"


# ── authored-record schema (what a Claude batch file contains) ───────────────

class AuthoredGrounding(BaseModel):
    model_config = ConfigDict(frozen=True)
    title: str
    summary: str = ""
    technologies: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()


class AuthoredRecord(BaseModel):
    """One Claude-authored example. `dimensions` are Claude's own 0-4 tier
    judgments for the four canonical dimensions; `overall` is DERIVED, never
    supplied. `humanized` marks the humanized subset. `id` must be unique."""

    model_config = ConfigDict(frozen=True)

    id: str
    group_id: str
    candidate_profile_id: str = ""
    category: str
    reasoning_type: str
    grounding: AuthoredGrounding
    question: str
    expected_concepts: tuple[str, ...] = ()
    answer: str
    dimensions: dict[str, int]
    humanized: bool = False
    hard_case: Optional[str] = None
    style_note: str = ""
    # ── Optional diversity metadata (additive; the first 102 authored records
    # predate these and omit them — they stay fully valid and their converted
    # TrainingExample is byte-identical, since none of these fields are used by
    # record_to_training_example; they are read only by v4_5000_diversity for
    # steering/monitoring). Future batches SHOULD set them. ──
    question_form: str = ""
    intent: str = ""
    humanization_style: str = ""
    project_family: str = ""

    @field_validator("dimensions")
    @classmethod
    def _check_dims(cls, v: dict[str, int]) -> dict[str, int]:
        if set(v.keys()) != set(_CANONICAL_KEYS):
            raise ValueError(f"dimensions must be exactly {_CANONICAL_KEYS}, got {sorted(v.keys())}")
        for name, tier in v.items():
            if not isinstance(tier, int) or not (0 <= tier <= 4):
                raise ValueError(f"dimension {name} tier must be int 0..4, got {tier!r}")
        return v


# ── overall-target policy (EXISTING policy, reused, not reinvented) ──────────

def derive_overall_score(dimension_tiers: dict[str, int]) -> float:
    """Equal-weight mean of the four canonical dimension scores on the [0,1]
    scale — the SAME policy `four_dim_experiment_split._to_training_example`
    and `overall_dataset.py` use (mean of dim scores; each dim score = tier/4).
    Never a new weighting scheme."""
    scores = [dimension_tiers[k] / 4.0 for k in _CANONICAL_KEYS]
    return round(sum(scores) / len(scores), 4)


def derive_overall_tier(dimension_tiers: dict[str, int]) -> int:
    """The ordinal 0-4 training target: score_to_tier of the derived overall
    score — identical to `overall_dataset.overall_score_to_tier`."""
    return score_to_tier(derive_overall_score(dimension_tiers))


def _grade_from_score(score: float) -> str:
    if score >= 0.90:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


def _quality_tier_from_overall(tier: int) -> QualityTier:
    return (QualityTier.POOR, QualityTier.WEAK, QualityTier.ADEQUATE, QualityTier.GOOD, QualityTier.EXCELLENT)[tier]


# ── per-record validation ────────────────────────────────────────────────────

@dataclass(frozen=True)
class RecordVerdict:
    accepted: bool
    reasons: tuple[str, ...] = ()


def validate_record(rec: AuthoredRecord) -> RecordVerdict:
    """Deterministic per-record checks (NO LLM). Corpus-level dedup/leakage
    are the assembly step's job."""
    reasons: list[str] = []

    # category / reasoning_type must be valid enum values
    try:
        QuestionCategory(rec.category)
    except ValueError:
        reasons.append(f"invalid_category:{rec.category}")
    try:
        ReasoningType(rec.reasoning_type)
    except ValueError:
        reasons.append(f"invalid_reasoning_type:{rec.reasoning_type}")

    # answer quality: non-empty, not malformed, no self-describing quality phrases
    if is_malformed_answer(rec.answer):
        reasons.append("malformed_or_empty_answer")
    banned = find_banned_phrases(rec.answer)
    if banned:
        reasons.append(f"banned_quality_phrase_in_answer:{sorted(set(banned))}")

    # expected_concepts / question must not leak the score either
    leak_scan = " ".join(rec.expected_concepts) + " " + rec.question
    banned_ctx = find_banned_phrases(leak_scan)
    if banned_ctx:
        reasons.append(f"banned_quality_phrase_in_context:{sorted(set(banned_ctx))}")

    # grounding fidelity: known-vocab techs mentioned in the answer must be grounded
    halluc = hallucinated_technologies(rec.answer, rec.grounding.technologies)
    if halluc:
        reasons.append(f"hallucinated_technology:{halluc}")

    # question non-empty
    if not rec.question.strip():
        reasons.append("empty_question")

    return RecordVerdict(accepted=not reasons, reasons=tuple(reasons))


# ── record -> TrainingExample (reuses the frozen schema) ─────────────────────

def record_to_training_example(rec: AuthoredRecord, batch_id: str) -> TrainingExample:
    """Convert one validated authored record into a standard TrainingExample.
    SYNTHETIC provenance + synthetic_ground_truth labels (Claude authored both
    the answer and the four labels — honestly synthetic, never human_reviewed).
    overall_label derived by the existing equal-weight-mean policy."""
    spec = QuestionSpecification(
        id=f"v4c_{rec.id}",
        category=QuestionCategory(rec.category),
        text_seed=rec.grounding.title,
        grounding=Grounding(project=ProjectGrounding(
            title=rec.grounding.title, summary=rec.grounding.summary,
            technologies=tuple(rec.grounding.technologies), concepts=tuple(rec.grounding.concepts),
        )),
        source_type=SourceType.PROJECT,
        source_id=rec.group_id,
        source_field="v4_5000_scaffold",
        reason="claude_authored_v4_5000",
    )

    dimension_labels = tuple(
        DimensionLabel(name=k, score=round(rec.dimensions[k] / 4.0, 4)) for k in _CANONICAL_KEYS
    )
    overall_score = derive_overall_score(rec.dimensions)
    overall_tier = derive_overall_tier(rec.dimensions)

    synthetic_meta = TrainingExampleSyntheticMeta(
        generation_prompt_id="claude_authored_v4_5000",
        prompt_version="v1",
        generator_model="claude-authored",  # honest: Claude, NOT Gemini
        generation_batch_id=batch_id,
        intended_quality_tier=_quality_tier_from_overall(overall_tier),
        diversity_seed=rec.group_id,
        style_seed=rec.id,
    )

    labels = TrainingExampleLabels(
        label_source="synthetic_ground_truth",
        dimension_labels=dimension_labels,
        contradiction_label=ContradictionLabel(contradiction_present=False),
        overall_label=OverallLabel(
            score=overall_score, grade=_grade_from_score(overall_score),
            rationale="Overall target derived by equal-weight mean of the four Claude-authored dimension labels.",
        ),
    )

    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=f"v4c_{rec.id}", created_at=_FIXED_CREATED_AT),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.SYNTHETIC, collection_batch_id=batch_id),
        inputs=TrainingExampleInputs(
            specification=spec, question_text=rec.question,
            reasoning_type=ReasoningType(rec.reasoning_type), answer_text=rec.answer,
            expected_concepts=tuple(rec.expected_concepts),
        ),
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        synthetic=synthetic_meta,
        labels=labels,
    )


# ── batch ingestion (resumable) ──────────────────────────────────────────────

@dataclass
class IngestResult:
    accepted: list[TrainingExample] = field(default_factory=list)
    rejected: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)  # (record_id, reasons)
    provenance: dict[str, str] = field(default_factory=dict)   # example_id -> provenance category
    humanized_ids: set = field(default_factory=set)
    hard_case_by_id: dict[str, Optional[str]] = field(default_factory=dict)
    batch_of_id: dict[str, str] = field(default_factory=dict)


def ingest_records(records: list[AuthoredRecord], batch_id: str, into: Optional[IngestResult] = None) -> IngestResult:
    result = into or IngestResult()
    for rec in records:
        verdict = validate_record(rec)
        if not verdict.accepted:
            result.rejected.append((rec.id, verdict.reasons))
            continue
        ex = record_to_training_example(rec, batch_id)
        result.accepted.append(ex)
        eid = ex.metadata.example_id
        result.provenance[eid] = PROV_HUMANIZED if rec.humanized else PROV_SYNTHETIC
        if rec.humanized:
            result.humanized_ids.add(eid)
        result.hard_case_by_id[eid] = rec.hard_case
        result.batch_of_id[eid] = batch_id
    return result


def _read_batch_file(path: str) -> list[AuthoredRecord]:
    records: list[AuthoredRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(AuthoredRecord.model_validate_json(line))
    return records


def load_all_batches(batches_dir: str = BATCHES_DIR) -> IngestResult:
    """Ingest every `batch_*.jsonl` file (sorted) — the resume mechanism.
    Duplicate record ids across batches raise, so re-running is safe and never
    silently double-counts."""
    result = IngestResult()
    seen_ids: set = set()
    if not os.path.isdir(batches_dir):
        return result
    for name in sorted(os.listdir(batches_dir)):
        if not (name.startswith("batch_") and name.endswith(".jsonl")):
            continue
        path = os.path.join(batches_dir, name)
        batch_id = name[:-len(".jsonl")]
        records = _read_batch_file(path)
        for rec in records:
            if rec.id in seen_ids:
                raise ValueError(f"duplicate authored record id {rec.id!r} (found again in {name})")
            seen_ids.add(rec.id)
        ingest_records(records, batch_id, into=result)
    return result


# ── corpus-level dedup ───────────────────────────────────────────────────────

def _default_embed(texts: list[str]):
    """Batch-embed once with the same SBERT model the heuristic stack uses —
    lazy import so this module never loads it at import time, and tests inject
    their own embed_fn (never touching the network)."""
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embs = model.encode(texts, normalize_embeddings=True)
    return np.asarray(embs)


def semantic_duplicate_pairs(
    answers: list[str], threshold: float = SEMANTIC_DEDUP_THRESHOLD,
    embed_fn: Optional[Callable[[list[str]], object]] = None,
) -> list[tuple[int, int, float]]:
    """(i, j, cos) for answer pairs with cosine >= threshold. Embeds ONCE
    (not per pair) so it scales to the full corpus, unlike a naive per-pair
    SBERT call. `embed_fn` is injectable for tests."""
    if len(answers) < 2:
        return []
    import numpy as np
    embs = (embed_fn or _default_embed)(answers)
    embs = np.asarray(embs, dtype=float)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = embs / norms
    sims = unit @ unit.T
    hits: list[tuple[int, int, float]] = []
    n = len(answers)
    for i in range(n):
        for j in range(i + 1, n):
            s = float(sims[i, j])
            if s >= threshold:
                hits.append((i, j, round(s, 4)))
    return hits


# ── V4 disjointness ──────────────────────────────────────────────────────────

def load_v4_identity(v4_path: Optional[str] = None) -> dict:
    """Load the frozen V4 diagnostic benchmark's identifying fields (ids,
    source_ids, normalized question+answer) so assembly can PROVE the new
    dataset never overlaps it. Read-only; never modifies V4."""
    v4_path = v4_path or os.path.join(_HERE, "artifacts", "v4_diagnostic", "v4_diagnostic_58.jsonl")
    ids, sources, qa = set(), set(), set()
    if not os.path.exists(v4_path):
        return {"example_ids": ids, "source_ids": sources, "qa": qa, "found": False}
    with open(v4_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            ids.add(r.get("example_id", ""))
            sources.add(r.get("source_id", ""))
            qa.add((normalize_for_dedup(r.get("question", "")), normalize_for_dedup(r.get("answer", ""))))
    return {"example_ids": ids, "source_ids": sources, "qa": qa, "found": True}
