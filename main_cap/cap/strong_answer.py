"""
Improved Answer generator — deterministic, no LLM.

REDESIGN (approved): this is no longer a template that writes a fresh answer.
It is an interview-coach EDITOR that takes the candidate's OWN answer and
returns a stronger version of THAT SAME answer:

    interview question + candidate answer + grounding + expected concepts
        + DeBERTa evaluation  ->  Improved Answer

It preserves the candidate's structure, intent and technical approach, removes
repetition, and appends grounded first-person additions that (a) insert the
specific missing concepts the evaluator/grounding identified and (b) prompt
the weak reasoning to elaborate.

STRICT DIVISION (approved): DeBERTa is for EVALUATION ONLY. Its outputs
(grade, `missing_reasoning`) are used purely as EDITING SIGNALS — which weak
areas to prompt elaboration on, whether to show anything at all — never as a
text generator. No implementation specifics are fabricated.

PHASE 8 FIX (do not revert without re-reading the investigation): concepts
INSERTED into the rewritten answer come from exactly one source —
`concept_analysis.concept_pool()`'s `proj.concepts`, the concepts actually
matched (KeyBERT + `concept_gazetteer.py`) against THIS candidate's own
project bullet text. The expected-concepts registry (generic per-technology
textbook concepts, e.g. "fastapi" -> ASGI/dependency injection/routing) and
the evaluator's own `concept_coverage` omitted/superficial list (itself
sourced from that same registry, not from resume text) are deliberately
EXCLUDED from this pool — live-reproduced: a candidate who truthfully wrote
"I used FastAPI to build the backend REST APIs" was told to add "I'd also
work in ASGI, dependency injection and routing," none of which the resume,
question, or answer ever established. Those two sources remain legitimate
EVALUATOR signals (dashboard Concept Coverage, `missing_reasoning`
severity) — untouched anywhere else in the codebase — they are simply no
longer eligible to be ghost-written into the candidate's own answer.

DETERMINISTIC-ONLY LIMITATION (documented, not a bug): without an LLM we can't
truly paraphrase or interleave concepts inside the candidate's existing
sentences. The additions are appended as grounded connective sentences rather
than woven mid-paragraph. True in-place weaving is the one thing that requires
an LLM, which is excluded by design.

Scope: `strong_answer.py` internals rewritten; `build_improved_answer` takes
the candidate answer (the one new input) and is called from the same single
site in conversation_engine.py.
"""

from __future__ import annotations

import re
from typing import Optional

from concept_analysis import missing_concepts
from evaluation_result import EvaluationResult, MissingReasoningItem
from interview_question import InterviewQuestion

_MAX_MISSING_CONCEPTS = 3
_MAX_WEAK_AREAS = 2
_MIN_ANSWER_WORDS = 12       # below this there is nothing meaningful to strengthen
_TARGET_MAX_WORDS = 180      # soft ceiling; we never delete the candidate's own content to hit it

# missing_reasoning category (DeBERTa) -> a short first-person clause naming
# what to elaborate. NOT a template engine: a flat editing-signal lookup.
# Grounded ONLY in "this dimension scored weak" -- never a candidate-specific
# fact -- which is what makes these safe to state unconditionally. Sharpened
# (Coaching Note content-quality investigation, item 1) to match the actual
# desired direction per dimension instead of a vague restatement of the
# category name; still says nothing about WHAT the candidate did or didn't
# build, only what the answer should additionally make explicit.
#
# NOTE: "example" is deliberately NOT in this table. Unlike every other
# category here, an "example" missing_reasoning item names specific project
# technologies/concepts (`missing_terms`, heuristic_evaluator.py) computed
# against the WHOLE project's grounding, not scoped to the current
# question -- live-reproduced (investigation, mayurans_resume.pdf real
# session): an architecture question with zero technology-name relevance
# and a React-specific question both surfaced the identical unfiltered
# "React, FastAPI" pair. A static clause here would risk telling the
# candidate to "give an example using X" on a question that never asked
# about X. See `_weak_areas` below for the question-relevance filter that
# replaces it -- and note there is deliberately no generic fallback string:
# when no missing term survives that filter, the example clause is dropped
# entirely rather than reverting to a vague, unscoped sentence.
_WEAK_AREA_CLAUSES: dict[str, str] = {
    "tradeoff": "the alternatives I considered and why I chose this approach over them",
    "architecture": "the specific components involved, their responsibilities, and how they interact",
    "testing": "the concrete test cases or edge cases I used to verify it worked",
    "debugging": "the specific hard cases I ran into and how I worked through them",
    "metrics": "the results that showed it worked",
    "edge_case": "the edge cases I handled",
    "scalability": "how this would hold up as usage or data grows, and what would need to change",
    "design_decision": "the reasoning behind that decision",
    "ownership": "which parts of this I personally implemented or decided, versus what the team or project did overall",
    "communication": "the explanation more clearly and in order",
}

# Fixed suffix heuristic_evaluator._missing_reasoning uses when building an
# EXAMPLE item's `evidence` field (f"{terms} not found in the answer") --
# parsed back out below to recover the specific terms without re-deriving
# them from scratch or fragile splitting on `explanation`'s prose. If that
# template ever changes, `_example_terms` degrades to "no terms available"
# (clause suppressed), never a crash or a wrong parse.
_EXAMPLE_EVIDENCE_SUFFIX = " not found in the answer"


def _example_terms(item: MissingReasoningItem) -> list[str]:
    """The specific project technologies/concepts named in an EXAMPLE
    missing_reasoning item, recovered from its `evidence` field. Returns []
    if the evidence doesn't match the expected shape."""
    if not item.evidence.endswith(_EXAMPLE_EVIDENCE_SUFFIX):
        return []
    joined = item.evidence[: -len(_EXAMPLE_EVIDENCE_SUFFIX)]
    return [t.strip() for t in joined.split(",") if t.strip()]


# ── text helpers ────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _dedup_sentences(sentences: list[str]) -> list[str]:
    """Drop unnecessary repetition: a later sentence whose words are exactly,
    or wholly contained in, an earlier kept sentence (>=3-word guard so tiny
    sentences aren't wrongly collapsed). Preserves first occurrence + order."""
    kept: list[str] = []
    kept_tokens: list[set[str]] = []
    for s in sentences:
        toks = set(_norm(s).split())
        if not toks:
            continue
        redundant = False
        for kt in kept_tokens:
            if toks == kt or (len(toks) >= 3 and toks.issubset(kt)):
                redundant = True
                break
        if not redundant:
            kept.append(s)
            kept_tokens.append(toks)
    return kept


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


# ── editing signals (deterministic; grounding + evaluator, never generated) ──
# Concept detection is the shared `concept_analysis` module (imported above),
# so the Improved Answer and the dashboard's Concept Coverage use one detector.

def _weak_areas(result: EvaluationResult) -> list[str]:
    """Top NON-example missing_reasoning categories (by severity) mapped to
    first-person elaboration clauses. "example" is handled separately by
    `_example_sentence` below -- it needs the current question's own text
    to filter for relevance, and (per the Coaching Note wording fix) it
    reads as its own direct, actionable sentence rather than a fragment
    folded into "I'd also be explicit about ..."."""
    ordered = sorted(result.missing_reasoning, key=lambda m: -m.severity)
    clauses: list[str] = []
    for m in ordered:
        if m.category == "example":
            continue
        clause = _WEAK_AREA_CLAUSES.get(m.category)
        if clause and clause not in clauses:
            clauses.append(clause)
        if len(clauses) >= _MAX_WEAK_AREAS:
            break
    return clauses


def _example_sentence(result: EvaluationResult, question_text: str) -> Optional[str]:
    """A direct, actionable instruction naming the missing project
    technologies/concepts that are also actually relevant to the CURRENT
    question (i.e. literally present in `question_text`) -- see
    `_WEAK_AREA_CLAUSES`'s docstring for why unfiltered project-wide terms
    are unsafe to name. Returns None (never a generic fallback sentence)
    when there is no EXAMPLE item, or when none of its terms survive the
    relevance filter. Deliberately its OWN sentence, not folded into the
    "I'd also be explicit about ..." clause list: an instruction like "give
    a concrete example" reads as actionable advice, not as one more thing
    to "be explicit about" alongside dimension-level clauses."""
    q_lower = question_text.lower()
    for m in sorted(result.missing_reasoning, key=lambda m: -m.severity):
        if m.category != "example":
            continue
        terms = [t for t in _example_terms(m) if t.lower() in q_lower]
        if not terms:
            return None
        return f"Give a concrete example of how you used {_join(terms)} in this project."
    return None


# ── shared computation (single source of truth for both public entry points) ─

def _compute(
    question: InterviewQuestion, result: EvaluationResult, answer_text: str,
) -> Optional[tuple[str, str]]:
    """Returns (base, addition) or None when there's nothing to show — the
    exact same hide-gate, dedup, and soft-length-guard logic
    `build_improved_answer` has always used, factored out so its own
    concatenated-string contract (and the ~20 existing tests asserting on
    it) stays byte-for-byte unchanged, while `coaching_note` (below) can
    expose the SAME `addition` this function settles on -- including after
    the soft-length guard drops the secondary clause -- without
    re-deriving it via fragile string-splitting on the concatenated
    result."""
    answer_text = (answer_text or "").strip()

    # Hide when the candidate already answered well, when there is no real
    # answer to strengthen, or when there is nothing concrete to add.
    if result.grade in ("good", "excellent"):
        return None
    if len(answer_text.split()) < _MIN_ANSWER_WORDS:
        return None

    missing = missing_concepts(question, result, answer_text.lower(), _MAX_MISSING_CONCEPTS)
    weak = _weak_areas(result)
    example_sentence = _example_sentence(result, question.question_text)
    if not missing and not weak and not example_sentence:
        return None

    # Base = the candidate's own answer, with repetition removed, wording and
    # order otherwise preserved.
    base = " ".join(_dedup_sentences(_sentences(answer_text))).strip()
    if base and base[-1] not in ".!?":
        base += "."

    def _build_addition(include_weak: bool) -> str:
        # Grounded first-person additions. "example" is a separate,
        # standalone actionable sentence (see `_example_sentence`), never
        # folded into the "I'd also be explicit about ..." clause list --
        # keeping the two apart is what avoids an awkward, repetitive
        # combined sentence when both an example and a dimension weakness
        # fire on the same turn (e.g. an ownership clause plus a "give a
        # concrete example of React" instruction read as two clean,
        # distinct sentences, not one run-on).
        clauses: list[str] = []
        if missing:
            clauses.append(f"work in {_join(missing)}")
        if include_weak and weak:
            clauses.append(f"be explicit about {_join(weak)}")
        parts = [f"I'd also {', and '.join(clauses)}."] if clauses else []
        if example_sentence:
            parts.append(example_sentence)
        return " ".join(parts)

    addition = _build_addition(include_weak=True)
    improved = f"{base} {addition}".strip()

    # Soft length guard: never delete the candidate's content; if we're well
    # over budget, drop the (secondary) weak-area clause first -- the
    # example sentence (when present) is kept, since it's a direct,
    # actionable instruction rather than a droppable elaboration clause.
    if len(improved.split()) > _TARGET_MAX_WORDS and missing and weak:
        addition = _build_addition(include_weak=False)

    return base, addition


# ── public entry points ─────────────────────────────────────────────────────

def build_improved_answer(
    question: InterviewQuestion, result: EvaluationResult, answer_text: str,
) -> Optional[str]:
    """
    Return a stronger version of the candidate's OWN answer, or None when it
    should be hidden. Deterministic; DeBERTa outputs are editing signals only.

    UI-honesty fix (post-demo forensic investigation): this concatenated
    string is still produced, unchanged, for any existing consumer -- but
    it is no longer what the report UI presents under a label implying a
    rewritten answer (confirmed live: every real turn in a 10-turn browser
    session retained 100% of the candidate's own wording and only ever
    appended one fixed coaching sentence). `coaching_note` (below) exposes
    that same appended sentence on its own, so the report can show "Your
    Answer" (the candidate's actual, unmodified answer_text) and "Coaching
    Note" (this function's `addition`) as two honest, separate pieces
    instead of one blob."""
    computed = _compute(question, result, answer_text)
    if computed is None:
        return None
    base, addition = computed
    return f"{base} {addition}".strip()


def coaching_note(
    question: InterviewQuestion, result: EvaluationResult, answer_text: str,
) -> Optional[str]:
    """The deterministic coaching addition alone (e.g. "I'd also be
    explicit about a concrete example."), or None under the exact same
    hide conditions as `build_improved_answer` -- same gating, same
    clauses, same soft-length-guard behavior, computed via the shared
    `_compute` helper so this can never drift from what
    `build_improved_answer` would have embedded."""
    computed = _compute(question, result, answer_text)
    if computed is None:
        return None
    _base, addition = computed
    return addition
