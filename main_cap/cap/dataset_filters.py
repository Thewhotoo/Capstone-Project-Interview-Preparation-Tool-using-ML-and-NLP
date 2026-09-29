"""
Dataset Leakage / Quality Filters — Step 3 dataset-generation infra.

Reusable, side-effect-free detectors that run AFTER generation+judging and
before an example is admitted to the dataset. They target exactly the failure
modes the Step-3 audit found in the deployed dataset (self-describing quality
phrases, duplicate/near-duplicate answers, one answer reused thousands of
times, malformed answers, hallucinated grounding). Kept as pure functions so
they can be reused both per-example (in the pipeline) and in bulk (in the
acceptance gate).

No new similarity model is introduced: near-duplicate detection reuses the
existing SBERT accessor in `rewrite_verifier_client`, and grounding-fidelity
reuses the technology vocabulary in `generation_validation`.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

# ── A. / B. duplicate detection ──────────────────────────────────────────────

def normalize_for_dedup(text: str) -> str:
    """Casefold + whitespace-collapse so trivial formatting differences don't
    hide an otherwise-exact duplicate."""
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def exact_qa_duplicate_indices(pairs: Sequence[tuple[str, str]]) -> list[int]:
    """Indices of (question, answer) pairs that repeat an earlier pair
    (normalized). The first occurrence is kept; later ones are flagged."""
    seen: set[tuple[str, str]] = set()
    dups: list[int] = []
    for i, (q, a) in enumerate(pairs):
        key = (normalize_for_dedup(q), normalize_for_dedup(a))
        if key in seen:
            dups.append(i)
        else:
            seen.add(key)
    return dups


def duplicate_answer_counts(answers: Sequence[str]) -> dict[str, int]:
    """Normalized-answer -> count, for answers that appear more than once."""
    counts = Counter(normalize_for_dedup(a) for a in answers)
    return {a: c for a, c in counts.items() if c > 1}


# ── C. banned self-describing quality phrases ────────────────────────────────
# The answer must never narrate its own quality (the deployed dataset's core
# leak). These patterns catch the observed offenders and close variants.
BANNED_QUALITY_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"mention(?:ed|ing)?\s+briefly", re.IGNORECASE),
    re.compile(r"demonstrat(?:ed|ing|es)?\s+with\s+concrete", re.IGNORECASE),
    re.compile(r"generated\s+to\s+target", re.IGNORECASE),
    re.compile(r"target\s+tier", re.IGNORECASE),
    re.compile(r"quality\s+tier", re.IGNORECASE),
    re.compile(r"\b(?:excellent|weak|strong|poor|adequate|good|high[- ]quality)\s+answer\b", re.IGNORECASE),
    re.compile(r"\bthis\s+is\s+a\s+(?:detailed|thorough|complete|high[- ]quality)\s+answer\b", re.IGNORECASE),
    re.compile(r"\bi\s+demonstrat(?:e|ed)\b", re.IGNORECASE),
    re.compile(r"\bstrong\s+ownership\b", re.IGNORECASE),
    re.compile(r"\bconcrete\s+functional\s+detail\b", re.IGNORECASE),
)


def find_banned_phrases(text: str) -> list[str]:
    """Every banned-quality-phrase match found in `text` (the matched
    substrings). Empty list == clean."""
    found: list[str] = []
    for pattern in BANNED_QUALITY_PATTERNS:
        found.extend(m.group(0) for m in pattern.finditer(text or ""))
    return found


# ── D. near-duplicate answers (reuses existing SBERT) ────────────────────────

def _default_similarity(a: str, b: str) -> float:
    """Reuses the existing SBERT cosine accessor — no second similarity
    implementation. Imported lazily so importing this module never loads the
    embedding model, and tests can inject their own similarity_fn instead."""
    from rewrite_verifier_client import _semantic_similarity
    return _semantic_similarity(a, b)


def near_duplicate_pairs(
    answers: Sequence[str],
    threshold: float = 0.92,
    similarity_fn: Optional[Callable[[str, str], float]] = None,
) -> list[tuple[int, int, float]]:
    """(i, j, similarity) for answer pairs whose similarity >= `threshold`.
    O(n^2) — intended for modest batches / the acceptance gate, not the hot
    path. `similarity_fn` defaults to the reused SBERT cosine; tests inject a
    cheap deterministic function."""
    sim = similarity_fn or _default_similarity
    hits: list[tuple[int, int, float]] = []
    for i in range(len(answers)):
        for j in range(i + 1, len(answers)):
            score = sim(answers[i], answers[j])
            if score >= threshold:
                hits.append((i, j, score))
    return hits


# ── E. answer-per-question cap ───────────────────────────────────────────────

def answers_per_question(pairs: Sequence[tuple[str, str]]) -> dict[str, int]:
    """Normalized-question -> number of examples using it."""
    return dict(Counter(normalize_for_dedup(q) for q, _ in pairs))


def questions_over_cap(pairs: Sequence[tuple[str, str]], cap: int) -> dict[str, int]:
    return {q: c for q, c in answers_per_question(pairs).items() if c > cap}


# ── F. malformed / empty answers ─────────────────────────────────────────────

_MIN_ANSWER_WORDS = 3


def is_malformed_answer(answer_text: str, min_words: int = _MIN_ANSWER_WORDS) -> bool:
    """Empty or implausibly short — same threshold as
    generation_validation.check_malformed_output."""
    stripped = (answer_text or "").strip()
    return not stripped or len(stripped.split()) < min_words


# ── G. grounding fidelity (reuses generation_validation vocabulary) ──────────
#
# REPAIR (seed_v1 forensic analysis): the plain vocabulary-membership check
# above produced two classes of false positive, found by inspecting all 6
# `hallucinated_technologies` flags on the 100-example seed:
#   1. Spelling/casing variants of the SAME technology are separate entries
#      in generation_validation._KNOWN_TECHNOLOGY_VOCABULARY (e.g. "postgres"
#      and "postgresql" are both listed there as distinct strings), but the
#      grounding's allowed-list only ever carries one literal spelling (e.g.
#      "PostgreSQL") — so mentioning the tech under its OTHER listed spelling
#      flagged a real, grounded technology as hallucinated (seed_v1_010,
#      _076, _084, all "postgres" vs. a grounding of "PostgreSQL").
#   2. The check has no notion of a technology being mentioned as a
#      considered-and-REJECTED alternative rather than claimed as used (seed_
#      v1_025's "Alternatives like RabbitMQ...", seed_v1_075's "I looked at
#      AWS Secrets Manager briefly but Vault won out").
# Both fixes below are conservative, deterministic, closed-list lookups —
# never a semantic/NLP model — and neither one touches the genuine
# contradiction case (seed_v1_037's "aws"/SageMaker claim, which has no alias
# or rejection-context match and must keep being flagged).

# Known technology-name aliases where the grounding's literal spelling and
# the generation_validation vocabulary's separate token name the same real
# technology. Closed, additive list — only pairs where BOTH spellings are
# already present in `_KNOWN_TECHNOLOGY_VOCABULARY`.
_TECH_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"postgres", "postgresql"}),
    frozenset({"node.js", "nodejs"}),
)


def _expand_with_aliases(names: set[str]) -> set[str]:
    expanded = set(names)
    for group in _TECH_ALIAS_GROUPS:
        if names & group:
            expanded |= group
    return expanded


# Explicit markers that a technology is being mentioned as a considered-or-
# rejected alternative, not claimed as actually used. Checked within the
# SENTENCE containing the match (never full-answer scope), so a genuine
# contradiction elsewhere in the same answer is never masked. Sentence-
# scoping (rather than a fixed character count) tolerates the marker landing
# either before or after the term within the same clause -- e.g. "AWS
# Secrets Manager got a brief look from me, but Vault won out" has its
# marker ("won out") well past a small fixed window, but still clearly in
# the same sentence about the same rejected alternative.
_REJECTED_ALTERNATIVE_MARKERS: tuple[str, ...] = (
    "alternative", "alternatives", "considered", "instead of", "rather than",
    "compared to", "versus", " vs ", " vs.", "looked at", "went with",
    "won out", "wasn't chosen", "weren't chosen", "didn't go with",
    "decided against", "we chose", "we picked", "brief look", "briefly",
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;]|--")


def _all_mentions_are_rejected_alternatives(answer_lower: str, term: str) -> bool:
    """True only if EVERY occurrence of `term` sits in a sentence that also
    contains an explicit alternative/rejection marker. Errs toward NOT
    suppressing — a single unmarked occurrence keeps the flag — so a real
    contradiction (e.g. a technology claimed as actually used elsewhere in
    the same answer) is never hidden by an unrelated aside mentioning it."""
    matches = list(re.finditer(rf"\b{re.escape(term)}\b", answer_lower))
    if not matches:
        return False
    sentences = _SENTENCE_SPLIT_RE.split(answer_lower)
    for m in matches:
        # Find which sentence-scale segment contains this match by
        # accumulating segment lengths (+1 for the stripped delimiter).
        pos = 0
        local = None
        for sentence in sentences:
            seg_end = pos + len(sentence) + 1
            if pos <= m.start() < seg_end:
                local = sentence
                break
            pos = seg_end
        if local is None or not any(marker in local for marker in _REJECTED_ALTERNATIVE_MARKERS):
            return False
    return True


def hallucinated_technologies(answer_text: str, allowed_technologies: Sequence[str]) -> list[str]:
    """Known-vocabulary technology names that appear in the answer but are not
    in the grounding's allowed list — a post-hoc grounding-fidelity proxy.
    Reuses `generation_validation`'s vocabulary and word-boundary matcher
    rather than duplicating them. Alias-aware (PostgreSQL/postgres etc.) and
    ignores technologies mentioned only as a considered-and-rejected
    alternative — see the REPAIR note above."""
    from generation_validation import _KNOWN_TECHNOLOGY_VOCABULARY, _contains_term
    allowed = _expand_with_aliases({t.lower() for t in allowed_technologies})
    answer_lower = (answer_text or "").lower()
    return [
        name for name in _KNOWN_TECHNOLOGY_VOCABULARY
        if name not in allowed
        and _contains_term(answer_lower, name)
        and not _all_mentions_are_rejected_alternatives(answer_lower, name)
    ]


# ── Per-example convenience verdict ──────────────────────────────────────────

@dataclass(frozen=True)
class ExampleFilterVerdict:
    """Per-example filter outcome for the fast (non-similarity) checks. Exact
    duplicate / near-duplicate detection are corpus-level and run in the
    acceptance gate, not here."""

    accepted: bool
    reasons: tuple[str, ...] = ()


def check_example(
    answer_text: str,
    allowed_technologies: Sequence[str] = (),
) -> ExampleFilterVerdict:
    """Run the per-example, non-corpus checks (banned phrases, malformed,
    grounding fidelity). Corpus-level dedup/near-dup/caps are the acceptance
    gate's job."""
    reasons: list[str] = []
    banned = find_banned_phrases(answer_text)
    if banned:
        reasons.append(f"banned_quality_phrase: {sorted(set(banned))}")
    if is_malformed_answer(answer_text):
        reasons.append("malformed_or_empty_answer")
    hallucinated = hallucinated_technologies(answer_text, allowed_technologies)
    if hallucinated:
        reasons.append(f"hallucinated_technology: {hallucinated}")
    return ExampleFilterVerdict(accepted=not reasons, reasons=tuple(reasons))
