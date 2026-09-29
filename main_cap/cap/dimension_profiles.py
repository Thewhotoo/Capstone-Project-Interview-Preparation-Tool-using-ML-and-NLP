"""
Four-Dimension Target Profiles — Step 3 dataset-generation infrastructure.

A `DimensionProfile` is a deterministic per-example GENERATION TARGET across
the canonical four dimensions (evaluation_dimensions.py), each an ordinal
tier 0-4:

    technical_correctness / depth_specificity / relevance_completeness / grounding_ownership

CRITICAL BOUNDARY: a profile is GENERATION METADATA only. It tells the
generator what KIND of answer to produce; it is NEVER the training label
(the independent rubric judge produces labels — see rubric_judge.py) and its
descriptive guidance text must never let the answer describe its own quality
(see `generation_guidance`, which is checked against the banned-phrase filter
by tests).

The 12 approved hard-case profiles (A-L) live here as DATA (`HARD_CASES`),
not as scattered logic. Coherent (non-hard-case) profiles are also supported
so a generated dataset is not just 12 repeated patterns.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from evaluation_dimensions import CANONICAL_DIMENSIONS, NUM_TIERS, EvaluationDimension

_MIN_TIER = 0
_MAX_TIER = NUM_TIERS - 1  # 4


@dataclass(frozen=True)
class DimensionProfile:
    """Target tiers (0-4) for the canonical four dimensions. Field order
    matches `evaluation_dimensions.CANONICAL_DIMENSIONS`."""

    technical_correctness: int
    depth_specificity: int
    relevance_completeness: int
    grounding_ownership: int

    def __post_init__(self) -> None:
        for dim in CANONICAL_DIMENSIONS:
            tier = getattr(self, dim.value)
            if not isinstance(tier, int) or not (_MIN_TIER <= tier <= _MAX_TIER):
                raise ValueError(f"{dim.value} tier must be an int in [{_MIN_TIER}, {_MAX_TIER}], got {tier!r}")

    # ── serialization ────────────────────────────────────────────────────
    def as_dict(self) -> dict[str, int]:
        return {dim.value: getattr(self, dim.value) for dim in CANONICAL_DIMENSIONS}

    def as_tuple(self) -> tuple[int, int, int, int]:
        return tuple(getattr(self, dim.value) for dim in CANONICAL_DIMENSIONS)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "DimensionProfile":
        missing = [d.value for d in CANONICAL_DIMENSIONS if d.value not in data]
        if missing:
            raise ValueError(f"profile dict missing dimensions: {missing}")
        return cls(**{d.value: int(data[d.value]) for d in CANONICAL_DIMENSIONS})

    @classmethod
    def from_tuple(cls, tiers: tuple[int, int, int, int]) -> "DimensionProfile":
        if len(tiers) != len(CANONICAL_DIMENSIONS):
            raise ValueError(f"expected {len(CANONICAL_DIMENSIONS)} tiers, got {len(tiers)}")
        return cls(**{d.value: int(t) for d, t in zip(CANONICAL_DIMENSIONS, tiers)})

    def tier_for(self, dimension: EvaluationDimension) -> int:
        return getattr(self, dimension.value)


# ── The 12 approved hard cases (data, keyed A-L) ─────────────────────────────
# Vectors are [technical_correctness, depth_specificity, relevance_completeness,
# grounding_ownership] — CANONICAL_DIMENSIONS order.
#
# REPAIR (seed_v1 forensic analysis, post profile-blind judging pass): J and K
# were revised because their originally-approved vectors coupled two
# dimensions the rubric's own `must_not_overlap_with` text declares
# independent (evaluation_dimensions.py). Independent judging on the 100
# hand-authored seed examples confirmed this systematically (all 4 instances
# of each letter), not as noise:
#   - J ("contradicts resume/project") had technical_correctness=2, but a
#     grounding/resume contradiction does not make the surrounding technical
#     claims false (e.g. seed_v1_037's SageMaker/Step-Functions claims are
#     independently accurate even though the answer wrongly denies using
#     Airflow) -- correctness must be judged on the claims themselves, and
#     the contradiction is grounding_ownership's job alone. 2 -> 4.
#   - K ("correct + weak specificity") had relevance_completeness=2, but the
#     rubric explicitly states shallow != incomplete ("A relevant, complete
#     answer can be shallow; this measures whether the question was
#     answered, not how deeply") -- all 4 K seed answers do answer the
#     literal question, just without depth. 2 -> 4. K's grounding_ownership
#     was also lowered 2 -> 1 to match what the authored answers actually
#     demonstrate (thin, generic "we" ownership) rather than an
#     unsubstantiated assumption.
# See docs/architecture/DeBERTa_Dataset_Rebuild_Status.md for the full
# forensic analysis and repair record.
_HARD_CASE_VECTORS: dict[str, tuple[int, int, int, int]] = {
    "A": (4, 1, 3, 2),  # correct + shallow
    "B": (4, 4, 4, 3),  # correct + deep
    "C": (1, 3, 3, 2),  # incorrect + fluent/confident
    "D": (3, 2, 1, 3),  # relevant but incomplete
    "E": (1, 3, 4, 2),  # complete but technically wrong
    "F": (3, 4, 0, 2),  # detailed but irrelevant
    "G": (4, 3, 3, 0),  # generic textbook to resume-specific question
    "H": (4, 4, 4, 4),  # grounded + genuine ownership
    "I": (2, 1, 3, 1),  # unsupported ownership claim
    "J": (4, 2, 3, 0),  # contradicts resume/project (repaired: correctness decoupled from the contradiction)
    "K": (4, 1, 4, 1),  # correct + weak specificity (repaired: shallow-but-on-topic keeps relevance high)
    "L": (4, 4, 3, 1),  # strong technical, no personal implementation
}

_HARD_CASE_LABELS: dict[str, str] = {
    "A": "correct + shallow",
    "B": "correct + deep",
    "C": "incorrect + fluent/confident",
    "D": "relevant but incomplete",
    "E": "complete but technically wrong",
    "F": "detailed but irrelevant",
    "G": "generic textbook to resume-specific question",
    "H": "grounded + genuine ownership",
    "I": "unsupported ownership claim",
    "J": "contradicts resume/project",
    "K": "correct + weak specificity",
    "L": "strong technical, no personal implementation",
}

HARD_CASES: dict[str, DimensionProfile] = {
    key: DimensionProfile.from_tuple(vec) for key, vec in _HARD_CASE_VECTORS.items()
}


def hard_case_label(case_id: str) -> str:
    return _HARD_CASE_LABELS[case_id]


# ── Coherent (non-hard-case) profiles ────────────────────────────────────────

def coherent_profile(base_tier: int, seed: str) -> DimensionProfile:
    """A profile whose four dimensions all sit within +/-1 of `base_tier`
    (deterministic jitter from `seed`), clamped to [0,4]. Provides natural,
    covarying examples so the dataset is not only the 12 divergent hard
    cases. Deterministic: same (base_tier, seed) always yields the same
    profile."""
    if not (_MIN_TIER <= base_tier <= _MAX_TIER):
        raise ValueError(f"base_tier must be in [{_MIN_TIER}, {_MAX_TIER}], got {base_tier}")
    tiers = []
    for dim in CANONICAL_DIMENSIONS:
        digest = zlib.crc32(f"{seed}::{dim.value}".encode("utf-8"))
        jitter = (digest % 3) - 1  # -1, 0, or +1
        tiers.append(max(_MIN_TIER, min(_MAX_TIER, base_tier + jitter)))
    return DimensionProfile.from_tuple(tuple(tiers))  # type: ignore[arg-type]


def sample_profile(seed: str, hard_case_ratio: float = 0.5) -> tuple[str, DimensionProfile]:
    """Deterministically choose EITHER one of the 12 hard cases OR a coherent
    profile, controlled by `hard_case_ratio`. Returns (profile_id, profile) —
    `profile_id` is the hard-case letter (e.g. "H") or a "coherent:<tier>"
    tag, recorded on the example for hard-case-coverage reporting.

    This is planning metadata only and is fully deterministic (crc32 seed),
    preserving the recipe/coverage layer's determinism discipline."""
    if not (0.0 <= hard_case_ratio <= 1.0):
        raise ValueError("hard_case_ratio must be in [0.0, 1.0]")
    roll = (zlib.crc32(f"{seed}::profile_kind".encode("utf-8")) % 1_000_000) / 1_000_000.0
    if roll < hard_case_ratio:
        keys = sorted(HARD_CASES.keys())
        idx = zlib.crc32(f"{seed}::hard_case".encode("utf-8")) % len(keys)
        key = keys[idx]
        return key, HARD_CASES[key]
    base_tier = zlib.crc32(f"{seed}::base_tier".encode("utf-8")) % NUM_TIERS
    return f"coherent:{base_tier}", coherent_profile(base_tier, seed)


# ── Neutral generation guidance (metadata -> prompt text) ────────────────────
# Per-dimension, per-tier INSTRUCTIONS to the generator. These describe the
# CONTENT to produce (accurate vs. flawed claims, concrete vs. generic, on-
# vs. off-topic, first-person-project vs. textbook), NEVER the answer's own
# quality. They must contain none of the banned self-describing phrases
# (dataset_filters.BANNED_QUALITY_PATTERNS) — verified by test.
_GUIDANCE: dict[EvaluationDimension, dict[int, str]] = {
    EvaluationDimension.TECHNICAL_CORRECTNESS: {
        0: "Include one or more clearly mistaken technical claims, stated plainly as if true.",
        1: "Let several technical statements be inaccurate or misuse terminology.",
        2: "Mix accurate points with at least one clear technical error.",
        3: "Keep the technical claims accurate, allowing only minor imprecision.",
        4: "Make every technical claim accurate and sound, including any nuance.",
    },
    EvaluationDimension.DEPTH_SPECIFICITY: {
        0: "Stay at the level of buzzwords and generalities; give no mechanism.",
        1: "Name things but do not explain how they work; stay vague.",
        2: "Give a partial mechanism and a couple of concrete details.",
        3: "Explain concretely how it works, naming specific components and decisions.",
        4: "Go deep: specific mechanisms, concrete numbers, and reasoning about alternatives or edge cases.",
    },
    EvaluationDimension.RELEVANCE_COMPLETENESS: {
        0: "Respond about a different aspect than what the question asks; drift off-topic.",
        1: "Touch the general subject but do not address what the question actually asks.",
        2: "Address part of the question while leaving major parts or expected concepts uncovered.",
        3: "Address the question and cover most of its parts, with only minor gaps.",
        4: "Directly and fully address every part of the question and the expected concepts.",
    },
    EvaluationDimension.GROUNDING_OWNERSHIP: {
        0: "Give a generic textbook response not tied to this project, or one that conflicts with the stated context.",
        1: "Speak mostly in generalities or collective terms, with little tie to your own role.",
        2: "Reference the project but keep first-hand detail and personal role thin.",
        3: "Speak in first person about your involvement in this specific project.",
        4: "Speak clearly in first person about your own specific decisions and contribution on this project.",
    },
}


def generation_guidance(profile: DimensionProfile) -> str:
    """Renders a `DimensionProfile` into a deterministic, labeled block of
    per-dimension generation instructions for the prompt's user text. The
    output describes the content to produce, never the answer's quality, and
    is safe to append after the promptbook's own controllers."""
    lines = ["Shape the answer's CONTENT to these per-aspect targets (do not mention these targets in the answer):"]
    for dim in CANONICAL_DIMENSIONS:
        tier = profile.tier_for(dim)
        lines.append(f"- {dim.value}: {_GUIDANCE[dim][tier]}")
    return "\n".join(lines)
