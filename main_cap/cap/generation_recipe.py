"""
GenerationRecipe — Stage A Synthetic Dataset Generation Pipeline (Dataset
Generation RFC Section 5/6, Promptbook RFC Section 5/6 — both APPROVED AND
FROZEN).

A recipe is the fully-resolved, deterministic set of PER-EXAMPLE targets a
prompt is built from: which quality tier, which concept gets which target
status, which reasoning categories are deliberately made to feel missing,
and (rarely) which single contradiction type to introduce. Sampling a
recipe is entirely separate from choosing WHICH quality tier a given
generation call is for — that decision belongs to the batch/coverage
strategy (Dataset Generation RFC Section 3, out of scope here) and is
passed in as `quality_tier`, not sampled by this module.

DETERMINISM: exactly the same discipline as `question_realizer.py` —
`zlib.crc32`, never Python's salted `hash()`, so the same
(recipe_id, specification, quality_tier) always produces the same recipe,
forever, on any machine. "Probabilistic across the dataset, deterministic
within one call" (Promptbook Section 5) is implemented literally: the
probability TABLES below are what vary the pattern across many recipe_ids;
one recipe_id always resolves to the same concrete targets.
"""

from __future__ import annotations

import zlib
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from evaluation_result import ConceptObservationStatus, MissingReasoningCategory
from question_families import ReasoningType
from question_specification import QuestionSpecification
from reasoning_dimension_relevance import relevant_dimensions
from training_example import (
    ConceptInclusionTarget,
    ContradictionType,
    QualityTier,
    ReasoningCategoryTarget,
)


def _stable_unit(*parts: str) -> float:
    """A deterministic value in [0.0, 1.0) derived from `parts` — the same
    crc32-based approach `question_realizer._stable_index` uses, generalized
    to a continuous value for probability-threshold sampling."""
    digest = zlib.crc32("::".join(parts).encode("utf-8"))
    return (digest % 1_000_000) / 1_000_000.0


def _stable_choice(parts: tuple[str, ...], options: tuple) -> object:
    if not options:
        raise ValueError("options must not be empty")
    digest = zlib.crc32("::".join(parts).encode("utf-8"))
    return options[digest % len(options)]


# ═════════════════════════════════════════════════════════════════════════════
# Tier-conditioned probability tables (Dataset Generation RFC Section 5)
# ═════════════════════════════════════════════════════════════════════════════
#
# Per-concept target-status distribution, conditioned on quality tier.
# Deliberately probabilistic, not rigid, so the model never learns a
# spurious "any gap => overall poor" shortcut (Dataset Generation RFC
# Section 5's explicit rationale) — an EXCELLENT-tier example can still
# superficially or omit a concept some of the time, and a POOR-tier example
# can still demonstrate one occasionally.

_CONCEPT_STATUS_DISTRIBUTION: dict[QualityTier, tuple[tuple[ConceptObservationStatus, float], ...]] = {
    QualityTier.EXCELLENT: (
        (ConceptObservationStatus.DEMONSTRATED, 0.80),
        (ConceptObservationStatus.SUPERFICIAL, 0.15),
        (ConceptObservationStatus.OMITTED, 0.05),
    ),
    QualityTier.GOOD: (
        (ConceptObservationStatus.DEMONSTRATED, 0.55),
        (ConceptObservationStatus.SUPERFICIAL, 0.30),
        (ConceptObservationStatus.OMITTED, 0.15),
    ),
    QualityTier.ADEQUATE: (
        (ConceptObservationStatus.DEMONSTRATED, 0.30),
        (ConceptObservationStatus.SUPERFICIAL, 0.40),
        (ConceptObservationStatus.OMITTED, 0.30),
    ),
    QualityTier.WEAK: (
        (ConceptObservationStatus.DEMONSTRATED, 0.10),
        (ConceptObservationStatus.SUPERFICIAL, 0.35),
        (ConceptObservationStatus.OMITTED, 0.55),
    ),
    QualityTier.POOR: (
        (ConceptObservationStatus.DEMONSTRATED, 0.05),
        (ConceptObservationStatus.SUPERFICIAL, 0.20),
        (ConceptObservationStatus.OMITTED, 0.75),
    ),
}

# Per-relevant-category present-probability + severity band, conditioned on
# quality tier (Dataset Generation RFC Section 5 / Promptbook Section 6).
# Higher tiers are less likely to have a deliberate gap, and when they do,
# it skews toward minor severity; lower tiers skew the opposite way.
_REASONING_GAP_PROFILE: dict[QualityTier, tuple[float, float, float]] = {
    # (present_probability, severity_low, severity_high)
    QualityTier.EXCELLENT: (0.10, 0.10, 0.30),
    QualityTier.GOOD: (0.30, 0.20, 0.45),
    QualityTier.ADEQUATE: (0.55, 0.35, 0.60),
    QualityTier.WEAK: (0.75, 0.50, 0.80),
    QualityTier.POOR: (0.90, 0.65, 0.95),
}

_RELEVANT_REASONING_CATEGORIES: tuple[str, ...] = (
    MissingReasoningCategory.TRADEOFF,
    MissingReasoningCategory.ARCHITECTURE,
    MissingReasoningCategory.EXAMPLE,
    MissingReasoningCategory.TESTING,
    MissingReasoningCategory.DEBUGGING,
    MissingReasoningCategory.METRICS,
    MissingReasoningCategory.EDGE_CASE,
    MissingReasoningCategory.SCALABILITY,
    MissingReasoningCategory.DESIGN_DECISION,
    MissingReasoningCategory.OWNERSHIP,
    MissingReasoningCategory.COMMUNICATION,
)

# Which reasoning categories are even plausible for a given ReasoningType —
# reusing the same relevance concept the live Evaluation Engine already
# applies (reasoning_dimension_relevance.py), so a generated recipe never
# targets a category the reasoning type couldn't plausibly exercise anyway
# (e.g. never targeting DEBUGGING as "present" for a pure RECALL question).
_DIMENSION_TO_CATEGORY: dict[str, str] = {
    "tradeoffs": MissingReasoningCategory.TRADEOFF,
    "architecture": MissingReasoningCategory.ARCHITECTURE,
    "debugging": MissingReasoningCategory.DEBUGGING,
    "testing": MissingReasoningCategory.TESTING,
    "scalability": MissingReasoningCategory.SCALABILITY,
    "ownership": MissingReasoningCategory.OWNERSHIP,
    "communication": MissingReasoningCategory.COMMUNICATION,
}

_CONTRADICTION_TYPES: tuple[ContradictionType, ...] = tuple(ContradictionType)


def _relevant_reasoning_categories(reasoning_type: ReasoningType) -> tuple[str, ...]:
    dims = relevant_dimensions(reasoning_type)
    categories = {
        cat for dim, cat in _DIMENSION_TO_CATEGORY.items() if dim in dims
    }
    # EXAMPLE, METRICS, EDGE_CASE, DESIGN_DECISION have no 1:1 dimension —
    # they're relevant whenever the reasoning type isn't a bare recall, i.e.
    # whenever there's substantive content to potentially omit from.
    if reasoning_type != ReasoningType.RECALL:
        categories |= {
            MissingReasoningCategory.EXAMPLE, MissingReasoningCategory.METRICS,
            MissingReasoningCategory.EDGE_CASE, MissingReasoningCategory.DESIGN_DECISION,
        }
    return tuple(cat for cat in _RELEVANT_REASONING_CATEGORIES if cat in categories)


def _resolve_distribution(value: float, distribution: tuple[tuple[object, float], ...]) -> object:
    cumulative = 0.0
    for option, prob in distribution:
        cumulative += prob
        if value < cumulative:
            return option
    return distribution[-1][0]


# ═════════════════════════════════════════════════════════════════════════════
# GenerationRecipe
# ═════════════════════════════════════════════════════════════════════════════


class GenerationRecipe(BaseModel):
    """The fully-resolved, deterministic per-example generation target set.
    Immutable once sampled (Promptbook Section 5: "a recipe, once sampled,
    is followed deterministically-in-intent by the generator")."""

    model_config = ConfigDict(frozen=True)

    recipe_id: str
    specification: QuestionSpecification
    question_text: str
    reasoning_type: ReasoningType
    expected_concepts: tuple[str, ...] = ()

    quality_tier: QualityTier
    concept_targets: tuple[ConceptInclusionTarget, ...] = ()
    reasoning_targets: tuple[ReasoningCategoryTarget, ...] = ()

    is_off_topic: bool = False
    is_contradictory: bool = False
    contradiction_type: Optional[ContradictionType] = None

    diversity_seed: str
    style_seed: str

    @model_validator(mode="after")
    def _validate(self) -> "GenerationRecipe":
        if not self.recipe_id.strip():
            raise ValueError("recipe_id must not be empty")
        if self.is_off_topic and (self.concept_targets or self.reasoning_targets):
            raise ValueError("an off-topic recipe must carry no concept/reasoning targets (Off-Topic Controller override)")
        if self.is_off_topic != (self.quality_tier == QualityTier.OFF_TOPIC):
            raise ValueError("is_off_topic must match quality_tier == OFF_TOPIC")
        if self.is_contradictory != (self.quality_tier == QualityTier.CONTRADICTORY):
            raise ValueError("is_contradictory must match quality_tier == CONTRADICTORY")
        if self.is_contradictory and self.contradiction_type is None:
            raise ValueError("contradiction_type is required when is_contradictory=True")
        if not self.is_contradictory and self.contradiction_type is not None:
            raise ValueError("contradiction_type must be None when is_contradictory=False")
        return self


def sample_recipe(
    recipe_id: str,
    specification: QuestionSpecification,
    question_text: str,
    reasoning_type: ReasoningType,
    expected_concepts: tuple[str, ...],
    quality_tier: QualityTier,
) -> GenerationRecipe:
    """
    Deterministically sample a GenerationRecipe for one intended
    `quality_tier`. `quality_tier` itself is an input, not sampled here — it
    is the batch/coverage strategy's decision (Dataset Generation RFC
    Section 3); this function only resolves the CONCEPT and REASONING
    targets conditioned on that tier (Promptbook Sections 5/6), plus the
    off-topic/contradiction override and the diversity/style seeds
    (Promptbook Sections 2/4).
    """
    if quality_tier == QualityTier.OFF_TOPIC:
        return GenerationRecipe(
            recipe_id=recipe_id, specification=specification, question_text=question_text,
            reasoning_type=reasoning_type, expected_concepts=expected_concepts,
            quality_tier=quality_tier, concept_targets=(), reasoning_targets=(),
            is_off_topic=True,
            diversity_seed=_diversity_seed(recipe_id), style_seed=_style_seed(recipe_id),
        )

    if quality_tier == QualityTier.CONTRADICTORY:
        contradiction_type = _stable_choice((recipe_id, "contradiction_type"), _CONTRADICTION_TYPES)
        # A contradictory example still carries normal concept/reasoning
        # targets sampled as if it were a GOOD-tier answer (Promptbook
        # Section 3: "otherwise fluent, plausible-quality prose, independent
        # of quality tier") — contradiction is orthogonal to quality.
        concept_targets, reasoning_targets = _sample_targets(
            recipe_id, specification, reasoning_type, expected_concepts, QualityTier.GOOD,
        )
        return GenerationRecipe(
            recipe_id=recipe_id, specification=specification, question_text=question_text,
            reasoning_type=reasoning_type, expected_concepts=expected_concepts,
            quality_tier=quality_tier, concept_targets=concept_targets, reasoning_targets=reasoning_targets,
            is_contradictory=True, contradiction_type=contradiction_type,
            diversity_seed=_diversity_seed(recipe_id), style_seed=_style_seed(recipe_id),
        )

    concept_targets, reasoning_targets = _sample_targets(
        recipe_id, specification, reasoning_type, expected_concepts, quality_tier,
    )
    return GenerationRecipe(
        recipe_id=recipe_id, specification=specification, question_text=question_text,
        reasoning_type=reasoning_type, expected_concepts=expected_concepts,
        quality_tier=quality_tier, concept_targets=concept_targets, reasoning_targets=reasoning_targets,
        diversity_seed=_diversity_seed(recipe_id), style_seed=_style_seed(recipe_id),
    )


def _sample_targets(
    recipe_id: str,
    specification: QuestionSpecification,
    reasoning_type: ReasoningType,
    expected_concepts: tuple[str, ...],
    quality_tier: QualityTier,
) -> tuple[tuple[ConceptInclusionTarget, ...], tuple[ReasoningCategoryTarget, ...]]:
    concept_distribution = _CONCEPT_STATUS_DISTRIBUTION[quality_tier]
    concept_targets = tuple(
        ConceptInclusionTarget(
            concept=concept,
            status=_resolve_distribution(
                _stable_unit(recipe_id, "concept", concept), concept_distribution,
            ),
        )
        for concept in expected_concepts
    )

    present_prob, severity_low, severity_high = _REASONING_GAP_PROFILE[quality_tier]
    reasoning_targets = []
    for category in _relevant_reasoning_categories(reasoning_type):
        roll = _stable_unit(recipe_id, "reasoning", category)
        present = roll < present_prob
        if present:
            severity_roll = _stable_unit(recipe_id, "reasoning_severity", category)
            severity = round(severity_low + severity_roll * (severity_high - severity_low), 3)
        else:
            severity = 0.0
        reasoning_targets.append(ReasoningCategoryTarget(category=category, present=present, severity=severity))
    return concept_targets, tuple(reasoning_targets)


def _diversity_seed(recipe_id: str) -> str:
    return f"diversity_{zlib.crc32(recipe_id.encode('utf-8')) % 1000:03d}"


def _style_seed(recipe_id: str) -> str:
    return f"style_{zlib.crc32((recipe_id + '::style').encode('utf-8')) % 1000:03d}"
