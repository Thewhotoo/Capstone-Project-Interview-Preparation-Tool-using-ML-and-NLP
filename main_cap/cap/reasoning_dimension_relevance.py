"""
Reasoning-Type -> Dimension Relevance — Phase 3 (RFC Section 6 — APPROVED
AND FROZEN). Implemented exactly as specified.

Which evaluation dimensions are expected to matter for a given
`ReasoningType`. This is configuration the scoring framework and evaluator
implementations CONSULT — it is deliberately NOT part of the `Evaluator`
interface itself (RFC Section 6: "this stays a config table, not an
interface change").

Keyed by `ReasoningType` (Chapter 16's closed, stable cognitive taxonomy),
not by question `family` (Phase 2's open, phrasing-oriented registry) — see
the RFC's explicit rationale and the accepted coarseness trade-off (Section
6): several families can share one ReasoningType (e.g. "testing" and
"deployment" both map to APPLICATION), which is a known, deliberate loss of
precision in exchange for a stable axis that generalizes to any future
evaluator, which never needs to know what a "family" is.
"""

from __future__ import annotations

from typing import Optional

from question_families import ReasoningType
from question_specification import QuestionCategory

# ── The full dimension "menu" (RFC Section 4) ───────────────────────────────
TECHNICAL_ACCURACY = "technical_accuracy"
TECHNICAL_DEPTH = "technical_depth"
COMMUNICATION = "communication"
COMPLETENESS = "completeness"
ARCHITECTURE = "architecture"
TRADEOFFS = "tradeoffs"
OWNERSHIP = "ownership"
DEBUGGING = "debugging"
TESTING = "testing"
SCALABILITY = "scalability"
RESUME_GROUNDING = "resume_grounding"
AUTHENTICITY = "authenticity"

ALL_DIMENSIONS: tuple[str, ...] = (
    TECHNICAL_ACCURACY, TECHNICAL_DEPTH, COMMUNICATION, COMPLETENESS,
    ARCHITECTURE, TRADEOFFS, OWNERSHIP, DEBUGGING, TESTING, SCALABILITY,
    RESUME_GROUNDING, AUTHENTICITY,
)

# Dimensions relevant to every turn regardless of reasoning type — every
# answer is judged for basic correctness, clarity, completeness, and
# alignment with the resume's own claims, no matter what cognitive task the
# question targeted.
_ALWAYS_RELEVANT: frozenset[str] = frozenset({
    TECHNICAL_ACCURACY, COMMUNICATION, COMPLETENESS, RESUME_GROUNDING,
})

# Authenticity is diagnostic-only until independently validated (RFC
# Section 4: "may not contribute numerically to overall_score early on...
# until validated") — never contributes by default, regardless of
# reasoning type.
_NEVER_CONTRIBUTES_BY_DEFAULT: frozenset[str] = frozenset({AUTHENTICITY})

# Additional dimensions relevant on TOP of the always-relevant set, per
# reasoning type (RFC Section 6).
DIMENSION_RELEVANCE: dict[ReasoningType, frozenset[str]] = {
    ReasoningType.RECALL: frozenset({TECHNICAL_DEPTH}),
    ReasoningType.EXPLANATION: frozenset({TECHNICAL_DEPTH, ARCHITECTURE}),
    ReasoningType.APPLICATION: frozenset({TECHNICAL_DEPTH, TESTING}),
    ReasoningType.TRADE_OFF_ANALYSIS: frozenset({TRADEOFFS, ARCHITECTURE}),
    ReasoningType.DEBUGGING: frozenset({DEBUGGING, TECHNICAL_DEPTH}),
    ReasoningType.DESIGN: frozenset({ARCHITECTURE, TRADEOFFS}),
    ReasoningType.OPTIMIZATION: frozenset({SCALABILITY, TECHNICAL_DEPTH}),
    ReasoningType.REFLECTION: frozenset({OWNERSHIP}),
    ReasoningType.OWNERSHIP: frozenset({OWNERSHIP, COMMUNICATION}),
    ReasoningType.DECISION_MAKING: frozenset({TRADEOFFS, ARCHITECTURE}),
}


# Phase 6 (question-specific dimensions): a narrow, evidenced exclusion
# layer on TOP of DIMENSION_RELEVANCE, keyed by the (reasoning_type,
# category) PAIR rather than reasoning_type alone. reasoning_type is a
# deliberately coarse axis (this module's own docstring: "several
# families can share one ReasoningType... a known, deliberate loss of
# precision in exchange for a stable axis") -- coarse enough that the
# SAME reasoning_type can be reached from a well-evidenced question and
# a weakly-evidenced one. Confirmed live (Phase 6 investigation):
# "decision_making" family (reasoning_type=DECISION_MAKING) is
# registered applicable to PROJECT_OVERVIEW, PROJECT_DEEP_DIVE, AND
# SKILL_IN_CONTEXT. For the first two, DECISION_MAKING's dimensions
# (architecture, tradeoffs) are genuinely meaningful -- the question is
# about a real project-level decision. For SKILL_IN_CONTEXT, the only
# evidence is a bare technology name co-occurring somewhere in a
# project's text (candidate_profile_mapper._gazetteer_matches -- no
# comparison language, no architecture-decision signal, the same
# evidence gap Phase 5 already found and fixed at the QUESTION-TEXT
# level for this exact category). Scoring an answer to "Why did you take
# the approach you did for Linux in AI SOC Analyst?" on `architecture`/
# `tradeoffs` presupposes a decision the resume evidence never
# established.
#
# Deliberately an EXCLUSION table, not a parallel inclusion system: every
# (reasoning_type, category) pair not listed here behaves EXACTLY as
# `relevant_dimensions(reasoning_type)` already does -- this is
# additive/subtractive config on the existing table, not a second
# registry, and adding an entry can only ever narrow, never widen, a
# reasoning_type's own set.
DIMENSION_EXCLUSIONS_BY_CATEGORY: dict[tuple[ReasoningType, QuestionCategory], frozenset[str]] = {
    (ReasoningType.DECISION_MAKING, QuestionCategory.SKILL_IN_CONTEXT): frozenset({ARCHITECTURE, TRADEOFFS}),
}


def relevant_dimensions(
    reasoning_type: ReasoningType, category: Optional[QuestionCategory] = None,
) -> frozenset[str]:
    """Dimensions relevant for this reasoning type: the always-relevant set
    plus whatever `DIMENSION_RELEVANCE` adds for this specific type.

    `category` is optional and defaults to `None` — every existing caller
    that doesn't pass it gets EXACTLY today's behavior, unchanged. When
    supplied, the result is further narrowed by
    `DIMENSION_EXCLUSIONS_BY_CATEGORY` if this exact (reasoning_type,
    category) pair has an entry; otherwise `category` has no effect at
    all (the pair simply isn't in the table)."""
    base = _ALWAYS_RELEVANT | DIMENSION_RELEVANCE.get(reasoning_type, frozenset())
    if category is None:
        return base
    return base - DIMENSION_EXCLUSIONS_BY_CATEGORY.get((reasoning_type, category), frozenset())


def contributes_by_default(dimension_name: str) -> bool:
    """Whether `dimension_name` should default to `contributes_to_overall
    =True`. An evaluator implementation MAY still override this per result
    (e.g. mark a dimension non-contributing for a specific low-confidence
    call), but this is the baseline every implementation should start
    from."""
    return dimension_name not in _NEVER_CONTRIBUTES_BY_DEFAULT
