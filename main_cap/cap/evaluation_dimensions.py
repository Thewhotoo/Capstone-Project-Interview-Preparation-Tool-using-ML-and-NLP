"""
Canonical Four-Dimension Evaluation Schema — Next-Phase Step 1.

The single source of truth for the FOUR (and only four) dimensions on which a
resume-grounded interview answer is judged going forward:

    1. Technical Correctness   (technical_correctness)
    2. Depth & Specificity     (depth_specificity)
    3. Relevance & Completeness (relevance_completeness)
    4. Grounding & Ownership   (grounding_ownership)

WHY THIS IS A SEPARATE, ADDITIVE MODULE (read before changing anything):
- The legacy 12-dimension set lives in `reasoning_dimension_relevance.py` and
  is consumed by the deployed DeBERTa model, its heads, the dataset collate
  path, the heuristic evaluator, and the hybrid policy. NONE of that is
  touched here. This module introduces the canonical four as data only; it is
  not yet wired into the model, the dataset, or any evaluator. Wiring
  (input-context change, relabel, retrain) is later steps, deliberately out of
  scope for Step 1.
- `DimensionScore.name` (evaluation_result.py) is a free-form string with no
  closed-set validation, so defining new canonical keys here cannot break any
  existing result, request, or evaluator.

DESIGN NOTES:
- These are NOT the legacy 12 renamed. The keys are new and distinct
  (`technical_correctness` != legacy `technical_accuracy`, etc.), and each
  dimension has its own written 0-4 rubric with explicit non-overlap
  boundaries so the four stay genuinely independent.
- Scoring is ordinal 0..4 (five tiers), matching the CORAL formulation the
  backbone already uses -- so a future 4-head model can reuse the existing
  ordinal machinery without a scale change.
- `LEGACY_DIMENSION_MAP` is a pure-data compatibility bridge: it groups every
  one of the legacy 12 dimensions under exactly one canonical dimension. It
  exists so later aggregation/relabel code can translate legacy signal into
  the canonical four WITHOUT importing or modifying the frozen legacy module.
  This module stays dependency-free on purpose (no imports from the question/
  evaluation stack) so training/eval code can consume it in isolation; a unit
  test cross-checks the map against the real legacy set instead of coupling
  at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Ordinal scale shared with the backbone's CORAL heads: tiers 0..4.
NUM_TIERS: int = 5
TIER_LABELS: tuple[str, ...] = ("poor", "weak", "adequate", "good", "excellent")


class EvaluationDimension(str, Enum):
    """The canonical four. Values are the STABLE keys other systems persist
    and key on -- do not change a value without a schema-version bump and a
    migration, exactly as with any other stored identifier."""

    TECHNICAL_CORRECTNESS = "technical_correctness"
    DEPTH_SPECIFICITY = "depth_specificity"
    RELEVANCE_COMPLETENESS = "relevance_completeness"
    GROUNDING_OWNERSHIP = "grounding_ownership"


@dataclass(frozen=True)
class DimensionRubric:
    """A complete, self-contained rubric for one canonical dimension.

    `tiers` maps each ordinal 0..4 to a precise description of what an answer
    at that tier looks like. `increases`/`decreases` list the concrete
    evidence that should move a score up or down. `must_not_overlap_with`
    names the OTHER canonical dimensions this one is explicitly kept distinct
    from, with the reason, so annotators and future models don't collapse
    them."""

    key: EvaluationDimension
    display_name: str
    definition: str
    tiers: dict[int, str]
    increases: tuple[str, ...]
    decreases: tuple[str, ...]
    must_not_overlap_with: dict[EvaluationDimension, str]
    applies_to: str


# ── The rubrics ──────────────────────────────────────────────────────────────

_TECHNICAL_CORRECTNESS = DimensionRubric(
    key=EvaluationDimension.TECHNICAL_CORRECTNESS,
    display_name="Technical Correctness",
    definition=(
        "Whether the technical claims the candidate makes are factually and "
        "conceptually TRUE and sound for the specific technologies, mechanisms, "
        "and approaches referenced. Judges the truth of the content only -- "
        "never how much detail it has, how relevant it is to the question, or "
        "how fluently/confidently it is stated. "
        "CONTENTLESS ANSWERS: an answer that makes NO verifiable technical claim "
        "at all (pure generality/buzzwords -- 'we followed best practices', "
        "'it's built to scale well' -- with nothing concrete enough to be true "
        "or false) is NOT the same thing as an answer that makes a claim and "
        "gets it wrong. There is nothing here to contradict, so do not score it "
        "low on that basis alone; see tier 3. The absence of substance belongs "
        "to Depth & Specificity (and, if the question went unaddressed, "
        "Relevance & Completeness) -- never re-penalized here a second time."
    ),
    tiers={
        0: "Fundamentally wrong: the core claims reflect a real misconception or are factually incorrect.",
        1: "Mostly incorrect: a few right terms, but the key statements are wrong, misused, or self-contradictory.",
        2: "Mixed: some claims correct, others incorrect or materially imprecise; at least one notable error.",
        3: "Largely correct: the substance is accurate, with only minor imprecisions that don't undermine it. "
           "ALSO score 3 when the answer contains NO verifiable technical claim at all (pure generality, "
           "nothing concrete enough to check) -- there is nothing wrong stated, so treat it as this tier by "
           "default rather than tier 0-2; the lack of substance is Depth & Specificity's/Relevance & "
           "Completeness's job to penalize, not this dimension's.",
        4: "Fully correct: every technical claim is accurate and sound, including any nuance/edge cases raised. "
           "Requires actual substantive claims to be right about -- a contentless answer stops at tier 3, "
           "since there is no nuance/edge-case handling to be 'fully' correct about.",
    },
    increases=(
        "verifiably accurate mechanisms and cause->effect reasoning",
        "correct, precise use of technical terminology",
        "accurate statements about how the named technology actually behaves",
    ),
    decreases=(
        "factual errors or misconceptions about how something works",
        "misused or conflated terminology",
        "internally contradictory technical claims",
    ),
    must_not_overlap_with={
        EvaluationDimension.DEPTH_SPECIFICITY: (
            "A terse, shallow answer can be fully correct (high here, low on depth); "
            "a long detailed answer can be wrong (low here, high on depth). Judge truth, not amount of detail."
        ),
        EvaluationDimension.RELEVANCE_COMPLETENESS: (
            "A true statement about the wrong thing is still correct here, even though it fails relevance. "
            "Correctness does not require answering the question."
        ),
        EvaluationDimension.GROUNDING_OWNERSHIP: (
            "A generic textbook fact can be perfectly correct while being ungrounded/unowned. "
            "Correctness is about general truth, not about the candidate's own project."
        ),
    },
    applies_to="all question intents (architecture, implementation, tech choice, debugging, trade-offs, testing, scalability, security, ownership, challenges/failures).",
)

_DEPTH_SPECIFICITY = DimensionRubric(
    key=EvaluationDimension.DEPTH_SPECIFICITY,
    display_name="Depth & Specificity",
    definition=(
        "How concretely and specifically the answer explains the HOW and WHY -- "
        "actual mechanisms, named components, concrete decisions, quantities, and "
        "reasoning about alternatives -- as opposed to generic, hand-wavy, or merely "
        "verbose statements. Length is not depth: a long answer with no specifics is shallow."
    ),
    tiers={
        0: "No substance: pure generality or buzzwords ('used best practices', 'made it scalable').",
        1: "Vague: names things but gives no mechanism ('used caching to make it faster').",
        2: "Some specifics: a partial mechanism and a few concrete details, but mostly high-level.",
        3: "Concrete: explains how it actually works with specific components and decisions.",
        4: "Deep and precise: specific mechanisms, quantitative detail, and reasoning about alternatives/edge cases.",
    },
    increases=(
        "named components, concrete steps, and specific configurations",
        "quantitative detail (numbers, sizes, latencies, thresholds)",
        "specific decisions accompanied by the reasoning behind them",
    ),
    decreases=(
        "generic phrasing and buzzwords with no mechanism",
        "verbosity that repeats or pads without adding concrete content",
        "hand-waving over the part the question actually probes",
    ),
    must_not_overlap_with={
        EvaluationDimension.TECHNICAL_CORRECTNESS: (
            "Detail can be wrong and generality can be right; depth measures concreteness of explanation, "
            "not whether it is true."
        ),
        EvaluationDimension.RELEVANCE_COMPLETENESS: (
            "Rich detail on a tangent is still off-topic; depth is about specificity of what is said, "
            "not whether it answers the question."
        ),
        EvaluationDimension.GROUNDING_OWNERSHIP: (
            "A detailed answer can still be a generic textbook recital not tied to the candidate's own work; "
            "depth is not the same as first-hand grounding."
        ),
    },
    applies_to="all question intents; especially implementation details, trade-offs, debugging, scalability, and security.",
)

_RELEVANCE_COMPLETENESS = DimensionRubric(
    key=EvaluationDimension.RELEVANCE_COMPLETENESS,
    display_name="Relevance & Completeness",
    definition=(
        "Whether the answer actually addresses the SPECIFIC question asked and covers "
        "its important parts (and any expected concepts for the turn) -- regardless of "
        "whether the content is correct or detailed. This is about alignment and coverage, "
        "not truth or specificity."
    ),
    tiers={
        0: "Off-topic: does not address the question that was asked.",
        1: "Barely relevant: touches the general subject but not what was actually asked.",
        2: "Partially answers: addresses part of the question but misses major parts or expected concepts.",
        3: "Answers the question: covers most of what was asked, with only minor gaps.",
        4: "Fully answers: directly addresses every part of the question and the expected concepts.",
    },
    increases=(
        "directly addressing the specific focus the question asked about",
        "covering each sub-part of a multi-part question",
        "addressing the expected concepts associated with the turn",
    ),
    decreases=(
        "answering a different question than the one asked",
        "ignoring parts of a multi-part question or omitting expected concepts",
        "padding with material unrelated to the question",
    ),
    must_not_overlap_with={
        EvaluationDimension.TECHNICAL_CORRECTNESS: (
            "An on-topic, complete answer can still be factually wrong; relevance is about coverage/alignment, "
            "not truth."
        ),
        EvaluationDimension.DEPTH_SPECIFICITY: (
            "A relevant, complete answer can be shallow; this measures whether the question was answered, "
            "not how deeply."
        ),
        EvaluationDimension.GROUNDING_OWNERSHIP: (
            "An answer can address the question fully yet be a generic recital rather than the candidate's own work; "
            "coverage is separate from grounding."
        ),
    },
    applies_to="all question intents; the primary check for follow-up/multi-part and expected-concept questions.",
)

_GROUNDING_OWNERSHIP = DimensionRubric(
    key=EvaluationDimension.GROUNDING_OWNERSHIP,
    display_name="Grounding & Ownership",
    definition=(
        "Whether the answer is grounded in the candidate's OWN stated project/experience "
        "context and demonstrates first-hand understanding and personal contribution -- as "
        "opposed to a generic textbook answer, an unsupported/inflated claim, or credit that "
        "conflicts with the resume. Two linked signals: (a) is it tied to their actual "
        "resume/project context, and (b) does it show the candidate personally understands and "
        "did the work."
    ),
    tiers={
        0: "Ungrounded or contradictory: a generic textbook answer unconnected to their project, or a claim that conflicts with their own stated context.",
        1: "Mostly generic: little tie to the actual project; vague collective 'we' with no personal role.",
        2: "Some grounding: references the project, but first-hand detail or ownership is thin or partly unsupported.",
        3: "Grounded: clearly tied to their project, with evidence of personal involvement in the work discussed.",
        4: "Strongly grounded and owned: specific to their real project and decisions, clear personal contribution, fully consistent with the resume.",
    },
    increases=(
        "references to the candidate's actual project specifics (names, decisions, constraints)",
        "first-person, concrete contribution ('I designed/built/debugged ...')",
        "claims consistent with, and expanding on, the grounding/resume context",
    ),
    decreases=(
        "a generic textbook answer detached from their project",
        "unsupported or inflated claims, or collective 'we' with no personal role",
        "statements that contradict the candidate's own resume/grounding",
    ),
    must_not_overlap_with={
        EvaluationDimension.TECHNICAL_CORRECTNESS: (
            "A generic answer can be technically correct yet ungrounded; grounding is about ties to the "
            "candidate's own work, not general truth."
        ),
        EvaluationDimension.DEPTH_SPECIFICITY: (
            "An answer can be detailed yet still a generic recital not tied to the candidate's project; "
            "grounding is not the same as detail."
        ),
        EvaluationDimension.RELEVANCE_COMPLETENESS: (
            "An answer can fully address the question yet be a textbook recital rather than their own work; "
            "grounding is separate from answering the question."
        ),
    },
    applies_to="all question intents; the primary check for ownership, technology-choice, and challenge/failure questions, and for catching unsupported or textbook answers.",
)


# ── Canonical registry (fixed order) ─────────────────────────────────────────

CANONICAL_DIMENSIONS: tuple[EvaluationDimension, ...] = (
    EvaluationDimension.TECHNICAL_CORRECTNESS,
    EvaluationDimension.DEPTH_SPECIFICITY,
    EvaluationDimension.RELEVANCE_COMPLETENESS,
    EvaluationDimension.GROUNDING_OWNERSHIP,
)

RUBRICS: dict[EvaluationDimension, DimensionRubric] = {
    EvaluationDimension.TECHNICAL_CORRECTNESS: _TECHNICAL_CORRECTNESS,
    EvaluationDimension.DEPTH_SPECIFICITY: _DEPTH_SPECIFICITY,
    EvaluationDimension.RELEVANCE_COMPLETENESS: _RELEVANCE_COMPLETENESS,
    EvaluationDimension.GROUNDING_OWNERSHIP: _GROUNDING_OWNERSHIP,
}


# ── Compatibility bridge to the legacy 12-dimension set ──────────────────────
# Groups every legacy dimension name (reasoning_dimension_relevance.ALL_DIMENSIONS)
# under exactly one canonical dimension. Pure data, kept as plain strings so
# this module imports nothing from the question/evaluation stack; a unit test
# verifies this covers the real legacy set exactly (no drift). This is a
# translation aid for later aggregation/relabel work -- it does NOT change how
# the legacy model scores anything today.
LEGACY_DIMENSION_MAP: dict[EvaluationDimension, tuple[str, ...]] = {
    EvaluationDimension.TECHNICAL_CORRECTNESS: ("technical_accuracy",),
    EvaluationDimension.DEPTH_SPECIFICITY: (
        "technical_depth", "architecture", "tradeoffs", "debugging", "testing", "scalability",
    ),
    EvaluationDimension.RELEVANCE_COMPLETENESS: ("completeness", "communication"),
    EvaluationDimension.GROUNDING_OWNERSHIP: ("resume_grounding", "ownership", "authenticity"),
}


# ── Accessors ────────────────────────────────────────────────────────────────

def all_keys() -> tuple[str, ...]:
    """The four canonical dimension keys, in canonical order."""
    return tuple(d.value for d in CANONICAL_DIMENSIONS)


def rubric_for(dimension: EvaluationDimension) -> DimensionRubric:
    return RUBRICS[dimension]


def tier_label(tier: int) -> str:
    """Human-readable label for an ordinal tier 0..4."""
    if not 0 <= tier < NUM_TIERS:
        raise ValueError(f"tier must be in 0..{NUM_TIERS - 1}, got {tier}")
    return TIER_LABELS[tier]


def canonical_for_legacy(legacy_name: str) -> EvaluationDimension | None:
    """The canonical dimension a legacy dimension name maps to, or None if the
    name is unknown. Reverse view of `LEGACY_DIMENSION_MAP`."""
    for canonical, legacy_names in LEGACY_DIMENSION_MAP.items():
        if legacy_name in legacy_names:
            return canonical
    return None
