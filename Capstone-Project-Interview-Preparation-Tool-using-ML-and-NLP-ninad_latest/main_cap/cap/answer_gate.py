"""
Non-answer gate for Resume Discussion (Round 1) answers.

Some replies must never score well, however well the question is grounded:
"idk", "not sure", a two-word reply, a keyword dump ("Flask SQLite Python
REST API JWT Docker Redis"), a comma list of buzzwords, gibberish, pasted
markup or code. Before this gate the heuristic evaluator scored a keyword dump
0.79 ("good").

`gate(request, result)` runs on every Round 1 evaluation
(`evaluation_engine.evaluate`), whichever evaluator is active. A flagged reply
is capped at 0.1 / "poor", its strengths are cleared and one weakness says why;
anything else is returned unchanged. Deterministic, no model.

Adapted from a teammate's gate (`overall_single_evaluator._is_non_answer` +
`correctness_nli_scorer.degeneracy`, see resumeParser_integration.md), with
three fixes so real answers are never zeroed:
  * non-answer phrases match whole words only, and only in SHORT replies
    ("pass" matched "passed"; "not sure" matched "we weren't sure about the
    load, so I benchmarked three databases");
  * "repetitive" is measured over 20-word windows, not the whole answer (every
    long answer repeats "the", "data", ... so whole-answer word variety falls
    with length);
  * "code" means real code syntax, not prose ("the function should return the
    cached value", "I select the rows from the cache").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GATED_MAX_SCORE = 0.1

MIN_ANSWER_TOKENS = 3

_NON_ANSWER_RE = re.compile(
    r"\b(?:idk|(?:don'?t|dont|do\s+not|can'?t|cannot)\s+(?:really\s+|honestly\s+|quite\s+)?(?:know|remember|recall)|"
    r"(?:i'?m\s+|im\s+)?not\s+(?:really\s+|quite\s+)?sure|no\s+idea|no\s+clue|not\s+familiar|"
    r"(?:haven'?t|have\s+not|never)\s+(?:really\s+)?(?:studied|learned|learnt|covered)|"
    r"look\s+(?:it|them|that|this)\s+up|(?:didn'?t|did\s+not)\s+work\s+on|beats\s+me|pass|skip)\b",
    re.IGNORECASE,
)
# Clause fillers that carry no content ("sorry", "honestly") when judging what
# is left of a reply once its "I don't know" clauses are removed.
_FILLER_CLAUSE_WORDS = frozenset({"sorry", "honestly", "unfortunately", "so", "um", "uh", "yeah", "well", "ok", "okay"})
MAX_NON_ANSWER_WORDS = 40      # longer replies are never treated as non-answers
MIN_CONTENT_WORDS = 6          # a reply with this many words outside "don't know" clauses is a real attempt

FUNCTION_WORDS = frozenset(
    """
a an the this that these those it its they them their we our us i you your he she his her
is are was were be been being am do does did has have had can could will would shall should may might must
of in on at to for with from by as into over under about per through between during without within across
and or but so if then than because however therefore thus while when where which who whom whose what how why
not no nor yes such very more most less least much many some any each every both either neither all
i'll we'll it's don't doesn't isn't aren't we're they're you're i've we've
""".split()
)

_CODE_RE = re.compile(
    r"\bdef\s+\w+\s*\(|console\.\w+\(|printf\s*\(|System\.out|\bfor\s*\(|\bwhile\s*\(|\}\s*;|"
    r"\bdrop\s+table\b|\binsert\s+into\s+\w+\s*\(|\bselect\s+\*\s+from\b|=>\s*\{|;\s*--",
    re.IGNORECASE,
)
_MARKUP_RE = re.compile(r"</?[a-z][a-z0-9]*(?:\s[^>]*)?>", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


@dataclass(frozen=True)
class GateVerdict:
    gated: bool
    reason: str = ""          # machine-readable
    explanation: str = ""     # shown to the candidate as a weakness


def _windowed_ttr(tokens: list[str], window: int = 20) -> float:
    """Mean type-token ratio over sliding windows (length-independent)."""
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    ratios = [len(set(tokens[i:i + window])) / window for i in range(0, len(tokens) - window + 1, window // 2)]
    return sum(ratios) / len(ratios)


def _is_non_answer(raw: str, n_tokens: int) -> bool:
    """A reply that only says "I don't know" (in any wording), perhaps with an
    apology: every clause either carries a non-answer phrase or is filler, and
    fewer than MIN_CONTENT_WORDS words of anything else remain. "I don't know
    the exact number, but it cut latency by 40% after I added the index" keeps
    a substantive clause, so it is a real answer."""
    if n_tokens > MAX_NON_ANSWER_WORDS or not _NON_ANSWER_RE.search(raw):
        return False
    clauses = re.split(r"[.!?;,]+|\bbut\b|\bhowever\b|\bthough\b|\bso\b", raw, flags=re.IGNORECASE)
    content = 0
    for clause in clauses:
        words = [w for w in _tokens(clause) if w not in _FILLER_CLAUSE_WORDS]
        if words and not _NON_ANSWER_RE.search(clause):
            content += len(words)
    return content < MIN_CONTENT_WORDS


def check_answer(text: str) -> GateVerdict:
    raw = (text or "").strip()
    toks = _tokens(raw)
    n = len(toks)
    if n < MIN_ANSWER_TOKENS:
        return GateVerdict(True, "too_short", "The answer was too short to show any understanding.")
    if _is_non_answer(raw, n):
        return GateVerdict(True, "non_answer", "The question wasn't answered (the reply says you don't know or skips it).")
    if any(ord(c) < 32 and c not in "\t\n\r" for c in raw):
        return GateVerdict(True, "control_characters", "The reply isn't readable text.")
    fwr = sum(t in FUNCTION_WORDS for t in toks) / n
    # Code/markup only when there is no real explanation around it: an answer
    # that shows "List<String> list = new ArrayList<>();" AND explains it is fine.
    if (_MARKUP_RE.search(raw) or _CODE_RE.search(raw)) and fwr < 0.25:
        return GateVerdict(True, "markup_or_code", "The reply is code or markup, not a spoken explanation.")
    letters = sum(c.isalpha() for c in raw)
    nonspace = sum(not c.isspace() for c in raw)
    if nonspace >= 8 and letters / nonspace < 0.5:
        return GateVerdict(True, "non_linguistic", "The reply is mostly symbols or numbers, not an explanation.")
    sentences = len([s for s in re.split(r"[.!?]+", raw) if s.strip()])
    if n >= 4 and fwr < 0.12 and sentences <= 1:
        return GateVerdict(True, "keyword_dump", "The reply is a list of keywords, not an explanation of what you did.")
    if raw.count(",") / n >= 0.12 and fwr < 0.20:
        return GateVerdict(True, "comma_list", "The reply is a list of terms, not an explanation of what you did.")
    if n >= 8:
        content_bigrams = [b for b in zip(toks, toks[1:]) if not (b[0] in FUNCTION_WORDS and b[1] in FUNCTION_WORDS)]
        rep_bigram = (1 - len(set(content_bigrams)) / len(content_bigrams)) if content_bigrams else 0.0
        if _windowed_ttr(toks) < 0.45 or rep_bigram > 0.30:
            return GateVerdict(True, "repetitive", "The reply repeats the same words instead of explaining.")
    return GateVerdict(False)


def gate(request, result):
    """`result` unchanged for a real answer; a capped copy for a non-answer."""
    verdict = check_answer(request.answer_text)
    if not verdict.gated or result.overall_score <= GATED_MAX_SCORE:
        return result
    from evaluation_result import EvidenceLinkedClaim

    dimension = result.dimensions[0].name
    weakness = EvidenceLinkedClaim(
        claim=verdict.explanation,
        dimension=dimension,
        evidence=f"non_answer_gate:{verdict.reason}",
    )
    return result.model_copy(update={
        "overall_score": GATED_MAX_SCORE,
        "grade": "poor",
        "strengths": (),
        "weaknesses": (weakness,) + tuple(result.weaknesses),
    })
