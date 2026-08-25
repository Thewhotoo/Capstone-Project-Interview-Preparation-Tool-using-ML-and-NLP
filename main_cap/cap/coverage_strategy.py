"""
Coverage Strategy — Stage A Synthetic Dataset Generation Pipeline (Dataset
Generation RFC Section 3 — APPROVED AND FROZEN). Implementation only; no
architectural deviation.

CoverageStrategy owns exactly one decision: WHICH GenerationRecipes should be
produced for a batch — quality tier, reasoning type, question category,
expected-concept coverage, missing-reasoning coverage, follow-up ratio,
contradiction ratio, and off-topic ratio (RFC Section 3, "Responsibilities").
It never assembles a prompt, calls a generator, validates a
`GenerationOutput`, or computes `DatasetManifest` statistics (RFC Section 3,
"Non-Responsibilities") — those remain `synthetic_generation_pipeline.py`'s,
`generation_validation.py`'s, and a not-yet-built module's jobs respectively.
`GenerationRecipe` remains responsible for HOW an individual example is
generated (concept-status/reasoning-severity sampling); this module only
decides WHICH recipes get sampled in the first place — the same
CoverageStrategy/GenerationRecipe separation the RFC names explicitly.

INTERFACE NOTE (RFC Section 3: "SyntheticGenerationPipeline should require
minimal modification"): `synthetic_generation_pipeline.generate_batch`
already accepts an explicit `tier_cycle` tuple and selects a tier via
`tier_cycle[index % len(tier_cycle)]`. Handing it a `tier_cycle` exactly as
long as `units` therefore makes every index resolve to its own assigned
tier with ZERO code changes to `synthetic_generation_pipeline.py` — the
"minimal modification" is simply calling `generate_batch(plan.units,
tier_cycle=plan.quality_tiers, ...)` instead of relying on the default
`DEFAULT_TIER_CYCLE`. `DEFAULT_TIER_CYCLE` itself is left in place as
pipeline.py's own standalone fallback for callers who don't use a
CoverageStrategy (its own tests still cover it); this module supersedes its
ROLE as the production coverage policy without deleting or altering it.

FOLLOW-UP RATIO — A NOTED SCHEMA GAP (documented, not silently patched):
none of `BatchUnit`, `GenerationRecipe`, or `TrainingExample` represent
"this example originated as a follow-up question" anywhere in their frozen
schemas — that concept was never part of any approved RFC revision for
those models. Rather than adding a field to a frozen schema to satisfy this
section, `CoverageUnit.is_follow_up` below is a property of THIS module's
own pool-input type (never persisted, never part of a TrainingExample) —
CoverageStrategy selects a target proportion of pool entries the caller
already marked as follow-up; it never invents the flag or writes it
anywhere downstream. If follow-up provenance ever needs to be persisted on
a `TrainingExample`, that is a new RFC decision, not something decided here.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from question_families import ReasoningType
from question_specification import QuestionSpecification
from synthetic_generation_pipeline import BatchUnit
from training_example import QualityTier

# The five genuine quality bands (Off-topic/Contradictory are sampled
# independently below — RFC Section 3: "Contradiction is independent of
# quality" / "Off-topic is also independent of quality"). Order matches the
# RFC's own listing exactly; remainder allocation reads this list left to
# right ("beginning from Excellent downward").
_CORE_TIERS: tuple[QualityTier, ...] = (
    QualityTier.EXCELLENT, QualityTier.GOOD, QualityTier.ADEQUATE, QualityTier.WEAK, QualityTier.POOR,
)


@dataclass(frozen=True)
class CoverageUnit:
    """One available (specification, question, reasoning_type,
    expected_concepts) combination CoverageStrategy may draw a `BatchUnit`
    from — the candidate pool a caller (Planner/Realizer output, or a
    curated question bank) supplies. This module never invents one of
    these; it only selects among what it's given.

    `is_follow_up` marks a unit as representing a follow-up-style question
    rather than a primary one (see module docstring's "FOLLOW-UP RATIO"
    note) — set by the caller, never inferred or invented here.
    """

    specification: QuestionSpecification
    question_text: str
    reasoning_type: ReasoningType
    expected_concepts: tuple[str, ...] = ()
    is_follow_up: bool = False


@dataclass(frozen=True)
class CoverageConfig:
    """Tunable ratios (RFC Section 3: "a configurable percentage" for
    follow-up/contradiction/off-topic). Defaults are conservative starting
    points the RFC explicitly leaves to implementation, not RFC-mandated
    constants — the 20/20/20/20/20 core-tier split IS an RFC-mandated
    default and should only be overridden if a future RFC revision changes
    it."""

    follow_up_ratio: float = 0.175       # RFC: "approximately 15-20%"
    contradiction_ratio: float = 0.05
    off_topic_ratio: float = 0.05
    core_tier_weights: tuple[float, float, float, float, float] = (0.2, 0.2, 0.2, 0.2, 0.2)

    def __post_init__(self) -> None:
        for name, value in (
            ("follow_up_ratio", self.follow_up_ratio),
            ("contradiction_ratio", self.contradiction_ratio),
            ("off_topic_ratio", self.off_topic_ratio),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be within [0.0, 1.0], got {value}")
        if self.contradiction_ratio + self.off_topic_ratio > 1.0:
            raise ValueError("contradiction_ratio + off_topic_ratio must not exceed 1.0")
        if len(self.core_tier_weights) != len(_CORE_TIERS):
            raise ValueError(f"core_tier_weights must have {len(_CORE_TIERS)} entries")
        if abs(sum(self.core_tier_weights) - 1.0) > 1e-9:
            raise ValueError(f"core_tier_weights must sum to 1.0, got {sum(self.core_tier_weights)}")


@dataclass(frozen=True)
class CoveragePlan:
    """The batch CoverageStrategy assembled: `units` and `quality_tiers` are
    parallel, equal-length tuples — `quality_tiers[i]` is the tier assigned
    to `units[i]`. Pass both straight into
    `synthetic_generation_pipeline.generate_batch(plan.units,
    tier_cycle=plan.quality_tiers, ...)` — see module docstring's
    "INTERFACE NOTE"."""

    units: tuple[BatchUnit, ...]
    quality_tiers: tuple[QualityTier, ...]

    def __post_init__(self) -> None:
        if len(self.units) != len(self.quality_tiers):
            raise ValueError("units and quality_tiers must be the same length")


# ═════════════════════════════════════════════════════════════════════════════
# Determinism helpers — same crc32 discipline as generation_recipe.py
# ═════════════════════════════════════════════════════════════════════════════


def _stable_key(*parts: str) -> int:
    return zlib.crc32("::".join(parts).encode("utf-8"))


def _shuffle_sequence(seq: tuple, seed: str, salt: str) -> tuple:
    """A crc32-keyed stable sort of `seq`'s ORIGINAL POSITIONS — the same
    'probabilistic across the dataset, deterministic within one call'
    discipline `generation_recipe.py` already uses, generalized to
    reordering a sequence without Python's `random` module. Keying by
    original index (not content) means duplicate elements never collapse
    the sort into an unstable/ambiguous comparison."""
    order = sorted(range(len(seq)), key=lambda i: _stable_key(seed, salt, str(i)))
    return tuple(seq[i] for i in order)


def _allocate_counts(total: int, weights: tuple[float, ...]) -> tuple[int, ...]:
    """Integer allocation of `total` across `weights` (must sum to 1.0),
    remainder distributed one-at-a-time starting from index 0 (RFC Section
    3: "Any remainder should be distributed deterministically beginning
    from Excellent downward" — index 0 here is always Excellent, per
    `_CORE_TIERS`'s declared order)."""
    raw = [total * w for w in weights]
    counts = [int(r) for r in raw]  # floor
    remainder = total - sum(counts)
    for i in range(remainder):
        counts[i] += 1
    return tuple(counts)


def _split_batch(batch_size: int, config: CoverageConfig) -> tuple[int, int, tuple[int, ...]]:
    """Off-topic and contradiction counts are carved out of `batch_size`
    FIRST and independently of the core-tier split (RFC Section 3: both are
    "independent of quality" and must not be "tied to weak/poor tiers");
    everything left over is what the 20/20/20/20/20 core-tier distribution
    divides."""
    off_topic_count = int(batch_size * config.off_topic_ratio)
    contradiction_count = int(batch_size * config.contradiction_ratio)
    remaining = batch_size - off_topic_count - contradiction_count
    core_counts = _allocate_counts(remaining, config.core_tier_weights)
    return off_topic_count, contradiction_count, core_counts


# ═════════════════════════════════════════════════════════════════════════════
# Candidate selection — reasoning-type/category coverage, duplicate avoidance
# ═════════════════════════════════════════════════════════════════════════════


class _BucketCursor:
    """Round-robins a bucket of `CoverageUnit`s first by reasoning type (in
    `ReasoningType`'s declared enum/registry order, restricted to types
    actually present in the bucket — RFC Section 3: "No reasoning type
    should be starved simply because it appears later in registry
    ordering"), then within a type by original pool order (which, in
    practice, spreads `QuestionCategory` values too, since a real pool's
    units naturally vary by category within a reasoning type — RFC Section
    3: "approximately uniform coverage across the batch", not exact
    equality). Cursors never reset across the batch, so repeated draws from
    the same bucket advance rather than immediately repeat (RFC Section 3's
    duplicate-avoidance intent: "maximize diversity before repeating
    combinations")."""

    def __init__(self, bucket: tuple[CoverageUnit, ...]) -> None:
        self._bucket = bucket
        by_reasoning: dict[ReasoningType, list[int]] = {}
        for idx, unit in enumerate(bucket):
            by_reasoning.setdefault(unit.reasoning_type, []).append(idx)
        self._by_reasoning: dict[ReasoningType, tuple[int, ...]] = {
            rt: tuple(idxs) for rt, idxs in by_reasoning.items()
        }
        self._reasoning_order = tuple(rt for rt in ReasoningType if rt in self._by_reasoning)
        self._reasoning_pos = 0
        self._type_pos: dict[ReasoningType, int] = {rt: 0 for rt in self._reasoning_order}

    def next(self) -> CoverageUnit:
        reasoning_type = self._reasoning_order[self._reasoning_pos % len(self._reasoning_order)]
        self._reasoning_pos += 1
        indices = self._by_reasoning[reasoning_type]
        pos = self._type_pos[reasoning_type]
        idx = indices[pos % len(indices)]
        self._type_pos[reasoning_type] = pos + 1
        return self._bucket[idx]


def plan_batch(
    pool: tuple[CoverageUnit, ...],
    batch_size: int,
    batch_seed: str,
    config: CoverageConfig = CoverageConfig(),
) -> CoveragePlan:
    """
    Deterministically plan one batch: `batch_size` `BatchUnit`s paired with
    an assigned `QualityTier` each (RFC Section 3's full responsibility
    list). Given identical `(pool, batch_size, batch_seed, config)`, always
    produces an identical `CoveragePlan` (RFC Section 3: "Determinism") —
    no `random` module use anywhere in this call graph.

    `pool` is never mutated or invented from; a unit is drawn from it
    (round-robin, see `_BucketCursor`) once per assigned batch slot, and the
    same pool unit may be drawn multiple times if `batch_size` exceeds the
    pool's diversity (each draw still gets a distinct `recipe_id`, so
    downstream `GenerationRecipe` sampling is independent per slot even when
    the underlying specification/question repeats).
    """
    if not pool:
        raise ValueError("pool must not be empty")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    off_topic_count, contradiction_count, core_counts = _split_batch(batch_size, config)
    raw_tiers: list[QualityTier] = []
    for tier, count in zip(_CORE_TIERS, core_counts):
        raw_tiers.extend([tier] * count)
    raw_tiers.extend([QualityTier.OFF_TOPIC] * off_topic_count)
    raw_tiers.extend([QualityTier.CONTRADICTORY] * contradiction_count)
    tier_sequence = _shuffle_sequence(tuple(raw_tiers), batch_seed, "tier_shuffle")

    follow_up_count = int(batch_size * config.follow_up_ratio)
    raw_followup = [True] * follow_up_count + [False] * (batch_size - follow_up_count)
    followup_sequence = _shuffle_sequence(tuple(raw_followup), batch_seed, "followup_shuffle")

    followup_pool = tuple(u for u in pool if u.is_follow_up)
    primary_pool = tuple(u for u in pool if not u.is_follow_up)
    followup_cursor = _BucketCursor(followup_pool) if followup_pool else None
    primary_cursor = _BucketCursor(primary_pool) if primary_pool else None
    if followup_cursor is None and primary_cursor is None:
        raise ValueError("pool must contain at least one unit")  # unreachable given the earlier `if not pool` guard

    units = []
    for i in range(batch_size):
        wants_follow_up = followup_sequence[i]
        # Graceful degradation (RFC's "never invented" discipline applied
        # here): if the requested bucket has no candidates, fall back to
        # whichever bucket does — never invent a follow-up/primary unit
        # that isn't actually in the pool.
        if wants_follow_up and followup_cursor is not None:
            cursor = followup_cursor
        elif not wants_follow_up and primary_cursor is not None:
            cursor = primary_cursor
        else:
            cursor = followup_cursor if followup_cursor is not None else primary_cursor

        unit = cursor.next()
        units.append(BatchUnit(
            recipe_id=f"{batch_seed}::unit{i:04d}",
            specification=unit.specification,
            question_text=unit.question_text,
            reasoning_type=unit.reasoning_type,
            expected_concepts=unit.expected_concepts,
        ))

    return CoveragePlan(units=tuple(units), quality_tiers=tier_sequence)
