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
from evaluation_result import EvaluationResult
from interview_question import InterviewQuestion

_MAX_MISSING_CONCEPTS = 3
_MAX_WEAK_AREAS = 2
_MIN_ANSWER_WORDS = 12       # below this there is nothing meaningful to strengthen
_TARGET_MAX_WORDS = 180      # soft ceiling; we never delete the candidate's own content to hit it

# missing_reasoning category (DeBERTa) -> a short first-person clause naming
# what to elaborate. NOT a template engine: a flat editing-signal lookup.
_WEAK_AREA_CLAUSES: dict[str, str] = {
    "tradeoff": "why I chose this approach over the alternatives",
    "architecture": "how the pieces fit together",
    "example": "a concrete example",
    "testing": "how I verified it worked",
    "debugging": "how I worked through the hard cases",
    "metrics": "the results that showed it worked",
    "edge_case": "the edge cases I handled",
    "scalability": "how it would hold up as it scales",
    "design_decision": "the reasoning behind that decision",
    "ownership": "which parts I personally owned",
    "communication": "the explanation more clearly and in order",
}


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
    """Top missing_reasoning categories (by severity) mapped to first-person
    elaboration clauses."""
    ordered = sorted(result.missing_reasoning, key=lambda m: -m.severity)
    clauses: list[str] = []
    for m in ordered:
        clause = _WEAK_AREA_CLAUSES.get(m.category)
        if clause and clause not in clauses:
            clauses.append(clause)
        if len(clauses) >= _MAX_WEAK_AREAS:
            break
    return clauses


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
    if not missing and not weak:
        return None

    # Base = the candidate's own answer, with repetition removed, wording and
    # order otherwise preserved.
    base = " ".join(_dedup_sentences(_sentences(answer_text))).strip()
    if base and base[-1] not in ".!?":
        base += "."

    # Grounded first-person additions.
    clauses: list[str] = []
    if missing:
        clauses.append(f"work in {_join(missing)}")
    if weak:
        clauses.append(f"be explicit about {_join(weak)}")
    # Join the (at most two) clauses with a comma so the sentence doesn't read
    # as a run-on chain of "and"s (each clause may already contain an "and").
    addition = f"I'd also {', and '.join(clauses)}."

    improved = f"{base} {addition}".strip()

    # Soft length guard: never delete the candidate's content; if we're well
    # over budget, drop the (secondary) weak-area clause first.
    if len(improved.split()) > _TARGET_MAX_WORDS and missing and weak:
        addition = f"I'd also work in {_join(missing)}."

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
