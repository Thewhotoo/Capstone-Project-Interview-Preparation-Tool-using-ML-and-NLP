"""
Deterministic Rewrite Generator — Experiment 4 (Rewrite Augmentation)
Stage, API-FREE variant.

Produces a `GenerationOutput` via pure local text transforms, satisfying
the exact same shape `rewrite_validation.validate_rewrite` /
`rewrite_assembler.assemble_rewritten_example` already expect from a
Gemini-produced `GenerationOutput` — no LLM call, no network, no
dependency beyond what's already in this repo (regex + stdlib; SBERT is
only needed downstream, in `rewrite_validation.py`'s existing similarity
gate and `rewrite_verifier_client.SBERTDriftVerifierClient`).

Design constraint (grounded generation, never invented content — see
project ML design preferences): every transform is purely STRUCTURAL
(filler-phrase removal/insertion, sentence-starter connectives,
contractions) — never introduces a new noun, technology name, claim, or
fact. Concept evidence and the contradiction note are carried forward
VERBATIM from the source example's own already-validated labels, never
re-derived — a documented, deliberate deviation from
`rewrite_assembler.py`'s normal "rebuilt from the rewrite's own submitted
evidence" framing, which assumes a generator (an LLM) capable of reading
evidence back out of freshly produced prose. A deterministic transform
has no such capability, so instead of fabricating that ability, it reuses
the evidence a human/LLM already validated for the *same underlying
facts* — the facts don't change, only the surrounding prose does.

Deterministic in the literal sense: no `random` module, no seeding — the
same (source_example, style) pair always produces the same output byte
for byte, so an unaccepted attempt can never be retried into a different
one (see `deterministic_rewrite_pipeline.py`, which makes exactly one
attempt per unit for this reason).
"""

from __future__ import annotations

import re
from collections import OrderedDict

from evaluation_result import ConceptObservationStatus
from generation_client import ConceptEvidenceEntry, GenerationOutput
from training_example import TrainingExample

# ═════════════════════════════════════════════════════════════════════════════
# Shared text utilities
# ═════════════════════════════════════════════════════════════════════════════

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,!?])")


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text).strip()
    # A filler phrase removed right before sentence-ending punctuation
    # (e.g. "...directly [and can walk through what I did] .") leaves a
    # stray space before the period — cosmetic cleanup, not new content.
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)


def _lowercase_first_word(text: str) -> str:
    """Lowercase the first letter of `text` UNLESS its first word is the
    pronoun "I" (which is always capitalized regardless of sentence
    position) — used when splicing a lowercase connective in front of an
    existing sentence."""
    if not text:
        return text
    first_word_end = text.find(" ")
    first_word = text if first_word_end == -1 else text[:first_word_end]
    if first_word in ("I", "I'm", "I've", "I'd", "I'll"):
        return text
    return text[0].lower() + text[1:]


def _deterministic_index(seed: str, n: int) -> int:
    """A stable, non-random pick in [0, n) from a string seed — used to
    vary WHICH connective/filler phrase a rewrite uses across different
    source examples without introducing any randomness (no `random`
    module, per this pipeline's standing determinism rule)."""
    if n <= 0:
        return 0
    return sum(ord(c) for c in seed) % n


# ═════════════════════════════════════════════════════════════════════════════
# Style transforms — purely structural, never introduce new content
# ═════════════════════════════════════════════════════════════════════════════

_FILLER_PATTERNS = [
    re.compile(rf"\b{phrase}\b,?\s*", re.IGNORECASE)
    for phrase in (
        "basically", "actually", "essentially", "you know", "i mean",
        "sort of", "kind of", "honestly", "to be honest", "at the end of the day",
        "just", "really", "very", "quite",
        "and can walk through what i did",
    )
]
_IN_ORDER_TO_RE = re.compile(r"\bin order to\b", re.IGNORECASE)

# This repository's own synthetic dataset (Experiment 1/2, generated via
# `generation_client.FakeGenerationClient` — never real Gemini prose, see
# module docstring) overwhelmingly uses this exact per-concept sentence
# template: "I used {concept} — {detail}." repeated once per concept,
# where {detail} is one of two fixed boilerplate qualifier phrases. Since
# this IS the actual corpus a Track B run draws from, compressing this
# specific, recognizable shape is the single highest-leverage concise
# transform available — merging N parallel "I used X — detail." sentences
# sharing the same detail phrase into one "I used X, Y, and Z — detail."
# sentence removes the repeated "I used"/"— detail." boilerplate while
# keeping every technology name and its qualifier level fully intact (no
# information loss, nothing invented). Sentences that don't match this
# shape (a genuinely free-form answer) simply pass through untouched —
# this is additive, not a requirement.
_ITEM_SENTENCE_RE = re.compile(r"^I used (.+?) — (.+)\.$", re.IGNORECASE)
_BOILERPLATE_DETAIL_SHORTENINGS = [
    (re.compile(r"\bdemonstrated with concrete functional detail\b", re.IGNORECASE), "in depth"),
]


def _shorten_boilerplate_detail_phrases(text: str) -> str:
    """Applied by EVERY style, not just concise: shortening a fixed
    boilerplate phrase to a synonym is content-neutral (same claim, fewer
    words) and, on this corpus's templated text, is often the only real
    lexical variation available to a purely structural transform —
    without it, `conversational`/`reflective` have almost nothing to
    change in a sentence like "I used orm — demonstrated with concrete
    functional detail." beyond the very first sentence, which risks
    tripping `rewrite_validation`'s near-duplicate ceiling."""
    for pattern, replacement in _BOILERPLATE_DETAIL_SHORTENINGS:
        text = pattern.sub(replacement, text)
    return text


def _merge_parallel_item_sentences(sentences: list[str]) -> list[str]:
    """Merge consecutive-shape "I used X — detail." sentences that share
    the same detail phrase into one combined sentence, at the position of
    the group's first occurrence. Sentences not matching the shape are
    left exactly where they are."""
    groups: "OrderedDict[str, list[str]]" = OrderedDict()
    for s in sentences:
        m = _ITEM_SENTENCE_RE.match(s)
        if m:
            concept, detail = m.group(1).strip(), m.group(2).strip()
            groups.setdefault(detail, []).append(concept)

    def _join_concepts(concepts: list[str]) -> str:
        if len(concepts) == 1:
            return concepts[0]
        if len(concepts) == 2:
            return f"{concepts[0]} and {concepts[1]}"
        return f"{', '.join(concepts[:-1])}, and {concepts[-1]}"

    merged_by_detail = {
        detail: f"I used {_join_concepts(concepts)} — {detail}."
        for detail, concepts in groups.items()
    }

    output: list[str] = []
    inserted_details: set[str] = set()
    for s in sentences:
        m = _ITEM_SENTENCE_RE.match(s)
        if m:
            detail = m.group(2).strip()
            if detail not in inserted_details:
                output.append(merged_by_detail[detail])
                inserted_details.add(detail)
            continue
        output.append(s)
    return output


def _rewrite_concise(answer: str) -> str:
    """Strip filler words/phrases and redundant hedges, shorten known
    boilerplate qualifier phrases, and merge parallel "I used X —
    detail." sentences that share a detail (module-level note above).
    Only ever REMOVES/COMPRESSES, never adds new sentences — guarantees
    the length-ratio can't exceed 1.0, satisfying
    `rewrite_validation._LENGTH_RATIO_BANDS["concise"]`'s upper bound
    (1.05) by construction."""
    text = answer
    text = _IN_ORDER_TO_RE.sub("to", text)
    for pattern in _FILLER_PATTERNS:
        text = pattern.sub("", text)
    text = _shorten_boilerplate_detail_phrases(text)
    text = _collapse_whitespace(text)

    sentences = _split_sentences(text)
    sentences = _merge_parallel_item_sentences(sentences)
    # A filler removed at a sentence start can leave an orphaned
    # lowercase-starting sentence after a period; re-capitalize each
    # sentence's first letter (structural cleanup, not new content).
    sentences = [s[0].upper() + s[1:] if s else s for s in sentences]
    return " ".join(sentences) if sentences else text


_CONTRACTIONS = [
    (re.compile(r"\bdo not\b", re.IGNORECASE), "don't"),
    (re.compile(r"\bdoes not\b", re.IGNORECASE), "doesn't"),
    (re.compile(r"\bdid not\b", re.IGNORECASE), "didn't"),
    (re.compile(r"\bcannot\b", re.IGNORECASE), "can't"),
    (re.compile(r"\bcan not\b", re.IGNORECASE), "can't"),
    (re.compile(r"\bis not\b", re.IGNORECASE), "isn't"),
    (re.compile(r"\bwas not\b", re.IGNORECASE), "wasn't"),
    (re.compile(r"\bwere not\b", re.IGNORECASE), "weren't"),
    (re.compile(r"\bwill not\b", re.IGNORECASE), "won't"),
    (re.compile(r"\bI am\b"), "I'm"),
    (re.compile(r"\bI have\b"), "I've"),
    (re.compile(r"\bI would\b"), "I'd"),
    (re.compile(r"\bwe have\b", re.IGNORECASE), "we've"),
    (re.compile(r"\bit is\b", re.IGNORECASE), "it's"),
    (re.compile(r"\bthat is\b", re.IGNORECASE), "that's"),
]

_CONVERSATIONAL_STARTERS = ("So, ", "Basically, ", "You know, ", "I mean, ")


def _rewrite_conversational(answer: str, seed: str) -> str:
    """Apply contractions throughout + a single conversational connective
    at the very start (only one, to keep the length-ratio well inside the
    generous conversational band [0.4, 2.0])."""
    text = answer
    for pattern, replacement in _CONTRACTIONS:
        text = pattern.sub(replacement, text)
    text = _shorten_boilerplate_detail_phrases(text)
    text = _collapse_whitespace(text)
    starter = _CONVERSATIONAL_STARTERS[_deterministic_index(seed, len(_CONVERSATIONAL_STARTERS))]
    if text:
        text = starter + _lowercase_first_word(text)
    return text


_REFLECTIVE_OPENERS = ("Looking back, ", "Reflecting on it, ", "In hindsight, ", "Thinking about it now, ")
_REFLECTIVE_CLOSERS = (
    "Overall, it was a valuable experience to work through.",
    "Looking back, that experience taught me a lot.",
    "It's something I still think about when tackling similar problems.",
)


_REFLECTIVE_CLOSER_MIN_WORDS = 8


def _rewrite_reflective(answer: str, seed: str) -> str:
    """Prepend a reflective connective to the first sentence and, for
    answers with enough existing content to absorb it without skewing the
    length ratio or diluting SBERT similarity, append a short GENERIC
    closing sentence — meta-commentary only, never a new factual claim
    about the specific work described (grounded-generation constraint,
    module docstring). Skipped for very short answers
    (`_REFLECTIVE_CLOSER_MIN_WORDS`), where an opener alone is already a
    proportionally large change."""
    text = _shorten_boilerplate_detail_phrases(_collapse_whitespace(answer))
    original_word_count = len(answer.split())
    opener = _REFLECTIVE_OPENERS[_deterministic_index(seed, len(_REFLECTIVE_OPENERS))]
    if text:
        text = opener + _lowercase_first_word(text)
    if text and not text.endswith((".", "!", "?")):
        text += "."
    if original_word_count < _REFLECTIVE_CLOSER_MIN_WORDS:
        return text
    closer = _REFLECTIVE_CLOSERS[_deterministic_index(seed + "|closer", len(_REFLECTIVE_CLOSERS))]
    return f"{text} {closer}".strip()


_SUPPORTED_STYLES = ("concise", "conversational", "reflective")


def apply_style_transform(answer: str, style: str, seed: str) -> str:
    """Dispatch to the transform for `style`. Raises ValueError for any
    style outside `_SUPPORTED_STYLES` — this deterministic generator
    intentionally only implements the 3 styles the Experiment 4 pilot
    actually uses; the other 5 style tags `rewrite_prompt_controllers.py`
    defines remain LLM-only for now (smallest-clean-change scope, not a
    permanent limitation)."""
    if style == "concise":
        return _rewrite_concise(answer)
    if style == "conversational":
        return _rewrite_conversational(answer, seed)
    if style == "reflective":
        return _rewrite_reflective(answer, seed)
    raise ValueError(
        f"deterministic_rewrite only supports {_SUPPORTED_STYLES}, got {style!r} "
        "(the other style tags remain LLM-only)"
    )


# ═════════════════════════════════════════════════════════════════════════════
# GenerationOutput assembly
# ═════════════════════════════════════════════════════════════════════════════


def _carried_forward_concept_evidence(source_example: TrainingExample) -> list[ConceptEvidenceEntry]:
    """Evidence carried forward VERBATIM from the source's own labels — see
    module docstring for why this is the correct, non-fabricating choice
    for a deterministic (non-LLM) generator."""
    entries = []
    for label in source_example.labels.concept_labels:
        if label.status != ConceptObservationStatus.OMITTED and (label.evidence or "").strip():
            entries.append(ConceptEvidenceEntry(concept=label.concept, evidence=label.evidence))
    return entries


def _carried_forward_contradiction_note(source_example: TrainingExample) -> str:
    if source_example.synthetic is None or not source_example.synthetic.is_contradictory:
        return ""
    explanation = (source_example.labels.contradiction_label.explanation or "").strip()
    if explanation:
        return explanation
    contradiction_type = source_example.synthetic.contradiction_type
    type_str = contradiction_type.value if contradiction_type is not None else "unspecified"
    return f"a deliberate {type_str} contradiction was introduced"


def generate_deterministic_rewrite(source_example: TrainingExample, style: str) -> GenerationOutput:
    """The API-free equivalent of a `GenerationClient.generate()` call for
    a rewrite: transforms `source_example.inputs.answer_text` per `style`
    and carries forward concept evidence / contradiction note verbatim
    from the source's own labels (module docstring). Raises ValueError for
    an unsupported style — same behavior a caller would see from an
    unregistered (generation_prompt_id, prompt_version) in the LLM path."""
    seed = source_example.metadata.example_id
    rewritten_answer = apply_style_transform(source_example.inputs.answer_text, style, seed)
    return GenerationOutput(
        answer_text=rewritten_answer,
        concept_evidence=_carried_forward_concept_evidence(source_example),
        contradiction_note=_carried_forward_contradiction_note(source_example),
    )
