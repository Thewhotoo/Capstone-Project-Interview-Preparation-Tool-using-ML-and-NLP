"""
Question Families — Phase 2 of ResumeDiscussion_v2 (Chapter 12).

A "family" is a phrasing angle a senior engineer might take on a topic
(overview, architecture, trade-offs, debugging, ...). This module is
deliberately open for extension: new families are added by calling
`register_family(...)` — nothing here needs to change to support a new one,
and nothing that already depends on `families_for_category`/`get_family`
needs to change either (Phase 2, Task 3's "support adding additional
families without modifying existing code").

Families are phrasing angles ONLY (Chapter 12: the Question Realizer never
decides WHAT to ask). Which family applies to which QuestionSpecification
category is fixed here (mirroring and extending Chapter 12.2's original
per-category style lists); WHICH family is chosen for a given turn is the
Discussion Policy's job (discussion_policy.py), not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from question_specification import QuestionCategory


class ReasoningType(str, Enum):
    """
    The cognitive-task taxonomy (Chapter 16) — NOT a difficulty band.
    Extends Chapter 16.2's original mapping table with the additional
    types OQ2 names as the eventual full taxonomy (Design, Decision Making
    as its own type, distinct from the smaller original style set).
    """

    RECALL = "recall"
    EXPLANATION = "explanation"
    APPLICATION = "application"
    TRADE_OFF_ANALYSIS = "trade_off_analysis"
    DEBUGGING = "debugging"
    DESIGN = "design"
    OPTIMIZATION = "optimization"
    REFLECTION = "reflection"
    OWNERSHIP = "ownership"
    DECISION_MAKING = "decision_making"


@dataclass(frozen=True)
class PhrasingContext:
    """Everything a phrasing-variant function needs, derived once from a
    QuestionSpecification's provenance/grounding — never anything outside
    what the specification itself already claims (Chapter 12.3)."""

    category: QuestionCategory
    text_seed: str | None
    title: str            # project title, or "" if not project-grounded
    technologies: tuple[str, ...]
    role: str              # experience role, or ""
    company: str           # experience company, or ""
    certification_name: str  # or ""
    source_id: str


PhrasingVariant = Callable[[PhrasingContext], str]


@dataclass(frozen=True)
class FamilyDefinition:
    """One registered question family: which categories it applies to,
    which cognitive task it represents (Chapter 16), and its phrasing
    variants (Chapter 12.2's "2 hand-written phrasing variants per style,
    so a single style never sounds identical twice either")."""

    name: str
    reasoning_type: ReasoningType
    applicable_categories: frozenset[QuestionCategory]
    phrasing_variants: tuple[PhrasingVariant, ...]


_FAMILY_REGISTRY: dict[str, FamilyDefinition] = {}


class DuplicateFamilyError(ValueError):
    """Raised by `register_family` if a family name is already registered —
    re-registering under the same name would silently shadow an existing
    family rather than genuinely adding a new one."""


def register_family(definition: FamilyDefinition) -> None:
    if definition.name in _FAMILY_REGISTRY:
        raise DuplicateFamilyError(f"family {definition.name!r} is already registered")
    if not definition.phrasing_variants:
        raise ValueError(f"family {definition.name!r} must have at least one phrasing variant")
    _FAMILY_REGISTRY[definition.name] = definition


def get_family(name: str) -> FamilyDefinition:
    return _FAMILY_REGISTRY[name]


def families_for_category(category: QuestionCategory) -> tuple[str, ...]:
    """Every registered family applicable to `category`, in a fixed,
    deterministic (alphabetical) order — never registration order, which
    would depend on module import order."""
    return tuple(sorted(
        name for name, defn in _FAMILY_REGISTRY.items()
        if category in defn.applicable_categories
    ))


def all_family_names() -> tuple[str, ...]:
    return tuple(sorted(_FAMILY_REGISTRY.keys()))


# ═════════════════════════════════════════════════════════════════════════════
# Shared phrasing helpers
# ═════════════════════════════════════════════════════════════════════════════

def _join_naturally(items: list[str]) -> str:
    """"A, B, and C" instead of "A, B, C" — matches discussion_engine.py's
    helper of the same purpose; kept local so this module has no import-time
    dependency on discussion_engine.py (which is Realizer-adjacent legacy
    integration code, not planning or family-definition code)."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _project_or_generic(ctx: PhrasingContext) -> str:
    return ctx.title or "that project"


def _tech_phrase(ctx: PhrasingContext) -> str:
    techs = _join_naturally(list(ctx.technologies[:3]))
    return f" using {techs}" if techs else ""


def _seed_clause(ctx: PhrasingContext) -> str:
    return (ctx.text_seed or "your approach").rstrip("?.").strip()


def _experience_label(ctx: PhrasingContext) -> str:
    """Renders "Role at Company" when both are known; the role alone, or the
    company alone, when only one is known -- e.g. when
    experience_parser.py's institution-marker fallback correctly left
    `role` empty rather than inventing a job title for an entry like "CAVE
    Labs - PES University EC Campus" (an organization hosted at a
    university, not a personal title). Templates that hardcode "as"
    immediately before this label use `_experience_preposition_label`
    below instead -- "as <company name>" would misrepresent an
    organization as a job title."""
    if ctx.role and ctx.company:
        return f"{ctx.role} at {ctx.company}"
    return ctx.role or ctx.company or "that role"


def _experience_preposition_label(ctx: PhrasingContext) -> str:
    """The full "as <role...>" / "at <company>" phrase for templates that
    would otherwise hardcode "as" immediately before an experience label.
    Never produces "as <company name>" -- when role is unknown (see
    `_experience_label`), the phrase uses "at <company>" instead, which
    is factually accurate (the candidate worked AT that organization)
    without claiming an organization name is a personal job title."""
    if ctx.role:
        return f"as {_experience_label(ctx)}"
    if ctx.company:
        return f"at {ctx.company}"
    return "in that role"


def _capitalize_first(text: str) -> str:
    """Capitalizes only the first character, unlike `str.capitalize()`
    (which also lowercases the rest of the string -- destructive to a
    proper-noun-heavy company name like "CAVE Labs"). Used for sentence-
    initial phrasing variants."""
    return text[:1].upper() + text[1:] if text else text


# ═════════════════════════════════════════════════════════════════════════════
# Registered families
# ═════════════════════════════════════════════════════════════════════════════

register_family(FamilyDefinition(
    name="overview",
    reasoning_type=ReasoningType.RECALL,
    applicable_categories=frozenset({QuestionCategory.PROJECT_OVERVIEW, QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"I noticed you built {_project_or_generic(ctx)}{_tech_phrase(ctx)}. Can you walk me through what it does and what your role was?",
        lambda ctx: f"Tell me about {_project_or_generic(ctx)}{_tech_phrase(ctx)} — what problem was it solving, and what did you personally build?",
    ),
))

register_family(FamilyDefinition(
    name="architecture",
    reasoning_type=ReasoningType.EXPLANATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_OVERVIEW, QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"How did you structure {_project_or_generic(ctx)} — what did the overall architecture look like?",
        lambda ctx: f"Walk me through how the pieces of {_project_or_generic(ctx)} fit together.",
    ),
))

register_family(FamilyDefinition(
    name="implementation",
    reasoning_type=ReasoningType.APPLICATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.SKILL_IN_CONTEXT}),
    phrasing_variants=(
        lambda ctx: f"I noticed {_project_or_generic(ctx)} involved {_seed_clause(ctx)}. Can you walk me through how you implemented that?",
        lambda ctx: f"How did you go about building {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="skill_application",
    reasoning_type=ReasoningType.APPLICATION,
    applicable_categories=frozenset({QuestionCategory.SKILL_IN_CONTEXT}),
    phrasing_variants=(
        # Phase 4 (ownership audit): SKILL_IN_CONTEXT's only evidence is
        # that a technology NAME co-occurs somewhere in a project's text
        # (candidate_profile_mapper._gazetteer_matches -- plain substring
        # match, no verb/ownership signal). "implementation" family's
        # "how did you go about BUILDING {tech}" wording asserted the
        # candidate built/implemented the technology itself -- confirmed
        # live against the real resume as fabricated ownership (e.g. "Built
        # an AI-assisted SOC platform using FastAPI" describes building the
        # PLATFORM, not FastAPI). Deliberately never verb-detects near the
        # mention instead -- proximity-based detection would misattribute
        # "Built" to FastAPI in that exact sentence, reproducing the same
        # bug via a different mechanism. "used"/"worked with" is the
        # strongest claim that's always true regardless of the real
        # (unknown) ownership level: a candidate who genuinely designed or
        # built this technology can still truthfully answer "how did you
        # use it" -- nothing is downgraded, only the unproven assumption is
        # removed.
        lambda ctx: f"How did you use {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
        lambda ctx: f"What was your experience working with {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="skill_context",
    reasoning_type=ReasoningType.RECALL,
    applicable_categories=frozenset({QuestionCategory.SKILL_IN_CONTEXT}),
    phrasing_variants=(
        # Phase 5 (Linux/tradeoff grounding audit): SKILL_IN_CONTEXT's only
        # evidence is a bare technology NAME co-occurring somewhere in a
        # project's text (candidate_profile_mapper._gazetteer_matches --
        # plain substring match, no comparison-language signal). The
        # "tradeoffs" family's "what tradeoffs did you weigh around
        # {tech}" wording presupposed a deliberate comparison/decision the
        # evidence never established -- confirmed live against the real
        # resume ("Windows, Linux and CSV logs" names Linux as one of
        # several supported log formats, not a weighed tradeoff).
        # seed_synthesis.py's tradeoff_probe already has the correct,
        # strict precondition for a genuine tradeoff claim (two
        # already-extracted technologies AND the resume's own comparison
        # language -- "instead of"/"chose X over Y"/etc. -- within a
        # small character window); SKILL_IN_CONTEXT structurally has no
        # equivalent evidence to check, so this family asks about context
        # instead of presupposing a decision, an architectural role, or an
        # ownership level ever happened at all -- "what role did it play"
        # is true of literally any occurrence, deliberate or incidental.
        lambda ctx: f"What role did {_seed_clause(ctx)} play in {_project_or_generic(ctx)}?",
        lambda ctx: f"Can you tell me more about how {_seed_clause(ctx)} fit into {_project_or_generic(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="tradeoffs",
    reasoning_type=ReasoningType.TRADE_OFF_ANALYSIS,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.SKILL_IN_CONTEXT}),
    phrasing_variants=(
        lambda ctx: f"What tradeoffs did you weigh around {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
        lambda ctx: f"Were there other options you considered for {_seed_clause(ctx)}, and why didn't you go with them?",
    ),
))

register_family(FamilyDefinition(
    name="decision_making",
    reasoning_type=ReasoningType.DECISION_MAKING,
    applicable_categories=frozenset({
        QuestionCategory.PROJECT_OVERVIEW, QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.SKILL_IN_CONTEXT,
    }),
    phrasing_variants=(
        lambda ctx: f"Why did you take the approach you did for {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
        lambda ctx: f"What made you settle on that specific approach for {_project_or_generic(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="debugging",
    reasoning_type=ReasoningType.DEBUGGING,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"Did {_seed_clause(ctx)} in {_project_or_generic(ctx)} give you any trouble? How did you work through it?",
        lambda ctx: f"What was the trickiest bug or edge case you ran into with {_seed_clause(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="optimization",
    reasoning_type=ReasoningType.OPTIMIZATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"How did {_seed_clause(ctx)} hold up at scale in {_project_or_generic(ctx)} — did you have to optimize anything there?",
        lambda ctx: f"Did {_seed_clause(ctx)} ever become a performance bottleneck, and if so, what did you do about it?",
    ),
))

register_family(FamilyDefinition(
    name="scaling",
    reasoning_type=ReasoningType.OPTIMIZATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"How would {_project_or_generic(ctx)} need to change if usage grew by 10x?",
        lambda ctx: f"Where do you think {_project_or_generic(ctx)} would hit its first scaling limit?",
    ),
))

register_family(FamilyDefinition(
    name="testing",
    reasoning_type=ReasoningType.APPLICATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"How did you approach testing {_seed_clause(ctx)} in {_project_or_generic(ctx)}?",
        lambda ctx: f"What gave you confidence that {_project_or_generic(ctx)} actually worked correctly?",
    ),
))

register_family(FamilyDefinition(
    name="deployment",
    reasoning_type=ReasoningType.APPLICATION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE}),
    phrasing_variants=(
        lambda ctx: f"How did you deploy and run {_project_or_generic(ctx)} in practice?",
        lambda ctx: f"What did shipping {_project_or_generic(ctx)} to something real actually look like?",
    ),
))

register_family(FamilyDefinition(
    name="failures",
    reasoning_type=ReasoningType.DEBUGGING,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.EXPERIENCE}),
    phrasing_variants=(
        lambda ctx: f"Did anything about {_project_or_generic(ctx) if ctx.title else _experience_label(ctx)} go wrong along the way? What happened?",
        lambda ctx: f"Looking back, was there a moment things broke that you didn't expect?",
    ),
))

register_family(FamilyDefinition(
    name="lessons_learned",
    reasoning_type=ReasoningType.REFLECTION,
    applicable_categories=frozenset({QuestionCategory.EXPERIENCE, QuestionCategory.PROJECT_OVERVIEW}),
    phrasing_variants=(
        lambda ctx: f"Looking back at {_project_or_generic(ctx) if ctx.title else _experience_label(ctx)}, what's the biggest thing you learned?",
        lambda ctx: f"What would you tell someone starting something similar today, based on what you learned there?",
    ),
))

register_family(FamilyDefinition(
    name="future_improvements",
    reasoning_type=ReasoningType.REFLECTION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_OVERVIEW}),
    phrasing_variants=(
        lambda ctx: f"If you were to revisit {_project_or_generic(ctx)} today, what would you change or improve?",
        lambda ctx: f"What's the next thing you'd add to {_project_or_generic(ctx)} if you kept working on it?",
    ),
))

register_family(FamilyDefinition(
    name="reflection",
    reasoning_type=ReasoningType.REFLECTION,
    applicable_categories=frozenset({QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.EXPERIENCE}),
    phrasing_variants=(
        lambda ctx: f"With more time, what would you have done differently with {_seed_clause(ctx)}?",
        lambda ctx: f"What did building this part actually teach you?",
    ),
))

register_family(FamilyDefinition(
    name="responsibilities",
    reasoning_type=ReasoningType.OWNERSHIP,
    applicable_categories=frozenset({QuestionCategory.EXPERIENCE}),
    phrasing_variants=(
        lambda ctx: f"You worked {_experience_preposition_label(ctx)}. What were your day-to-day responsibilities there?",
        lambda ctx: f"What did a typical day look like for you {_experience_preposition_label(ctx)}?",
    ),
))

register_family(FamilyDefinition(
    name="team_collaboration",
    reasoning_type=ReasoningType.OWNERSHIP,
    applicable_categories=frozenset({QuestionCategory.EXPERIENCE}),
    phrasing_variants=(
        lambda ctx: f"During your time {_experience_preposition_label(ctx)}, how did you collaborate with your team on technical decisions?",
        lambda ctx: f"{_capitalize_first(_experience_preposition_label(ctx))}, how did you work with the rest of your team day to day?",
    ),
))

register_family(FamilyDefinition(
    name="ownership",
    reasoning_type=ReasoningType.OWNERSHIP,
    applicable_categories=frozenset({QuestionCategory.EXPERIENCE, QuestionCategory.PROJECT_OVERVIEW}),
    phrasing_variants=(
        lambda ctx: f"What specifically were YOU responsible for in {_project_or_generic(ctx) if ctx.title else _experience_label(ctx)}, versus the rest of the team?",
        lambda ctx: f"Which part of {_project_or_generic(ctx) if ctx.title else _experience_label(ctx)} did you personally own end to end?",
    ),
))

register_family(FamilyDefinition(
    name="motivation",
    reasoning_type=ReasoningType.REFLECTION,
    applicable_categories=frozenset({QuestionCategory.CERTIFICATION}),
    phrasing_variants=(
        lambda ctx: f"What motivated you to pursue the {ctx.certification_name} certification?",
        lambda ctx: f"What made you decide to go after the {ctx.certification_name} certification?",
    ),
))

register_family(FamilyDefinition(
    name="application",
    reasoning_type=ReasoningType.APPLICATION,
    applicable_categories=frozenset({QuestionCategory.CERTIFICATION}),
    phrasing_variants=(
        lambda ctx: f"Has the {ctx.certification_name} certification influenced how you approach your projects or work?",
        lambda ctx: f"Where have you actually applied what you learned from the {ctx.certification_name} certification?",
    ),
))
