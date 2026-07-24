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

from question_families import ReasoningType

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


def relevant_dimensions(reasoning_type: ReasoningType) -> frozenset[str]:
    """Dimensions relevant for this reasoning type: the always-relevant set
    plus whatever `DIMENSION_RELEVANCE` adds for this specific type."""
    return _ALWAYS_RELEVANT | DIMENSION_RELEVANCE.get(reasoning_type, frozenset())


def contributes_by_default(dimension_name: str) -> bool:
    """Whether `dimension_name` should default to `contributes_to_overall
    =True`. An evaluator implementation MAY still override this per result
    (e.g. mark a dimension non-contributing for a specific low-confidence
    call), but this is the baseline every implementation should start
    from."""
    return dimension_name not in _NEVER_CONTRIBUTES_BY_DEFAULT
