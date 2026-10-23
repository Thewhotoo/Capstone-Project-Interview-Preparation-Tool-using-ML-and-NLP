"""
Resume Evidence Evaluator — evidence-based scoring for candidate-specific
resume-interview questions (isolated, additive, NOT DEPLOYED).

WHY (architectural conclusion): the resume interview's 21 question families are
all EXPERIENTIAL ("what did YOU build / decide / learn"), so an answer's factual
technical correctness cannot be established without a per-question answer key,
which cannot be authored without inventing candidate facts. Therefore this
evaluator does NOT claim technical correctness. It scores the evidence that IS
available — relevance, consistency with the résumé grounding, concrete
implementation detail, demonstrated (grounded) ownership, consistency with the
candidate's prior answers this session — and exposes technical correctness only
as a STATUS: "verified" when an AnswerKey exists, otherwise
"not_independently_verified".

REUSE, NOT A PARALLEL FRAMEWORK: every underlying signal is the SAME one the
existing heuristic stack already computes — `_semantic_similarity`,
`_grounding_text`/`_grounding_terms`, `_has_ownership_language`,
`_contradiction_flag`, `_rescale` (imported from `heuristic_evaluator`), the
four diagnostic dimensions (`HeuristicDiagnosticsEngine`, preserved verbatim in
the payload), and the deterministic degeneracy gate (`correctness_nli_scorer.
degeneracy`). What is NEW is only (a) the honest RE-COMPOSITION of those signals
into an overall that never rewards length / first-person-alone / jargon-density /
generic-textbook / confident tone, and (b) the missing evidence signals
(concreteness, non-answer, self-correction, prior-answer consistency).

NOT DEPLOYED: imported by nothing in the live stack; v5_1088 remains the active
production evaluator and rollback. API payload (EvaluationResult) is unchanged;
the four canonical diagnostic dimensions are preserved.
"""

from __future__ import annotations

import collections
import dataclasses
import os
import re
import threading
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from correctness_nli_scorer import degeneracy
from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult
from heuristic_diagnostics import CANONICAL_DIMENSION_KEYS, HeuristicDiagnosticsEngine
from heuristic_evaluator import (
    _ACCURACY_SIMILARITY_CEILING,
    _ACCURACY_SIMILARITY_FLOOR,
    _GROUNDING_SIMILARITY_CEILING,
    _GROUNDING_SIMILARITY_FLOOR,
    _contradiction_flag,
    _grounding_terms,
    _grounding_text,
    _has_ownership_language,
    _rescale,
    _semantic_similarity,
)
from question_families import ReasoningType

_CONFIDENCE_SOURCE = "resume_evidence_heuristic"

_NON_ANSWER_MARKERS = (
    "i don't know", "i dont know", "i do not know", "not sure", "no idea",
    "can't remember", "cannot remember", "don't recall", "didn't work on",
    "did not work on", "not familiar", "no clue", "beats me",
)
_SELF_CORRECTION_MARKERS = (
    "actually", "i mean", "to correct", "let me correct", "let me rephrase",
    "on second thought", "i misspoke", "scratch that", "correction,",
    "what i meant", "rather,",
)
# Numeric/quantitative tokens (metrics like "50ms", "2s", "p95", "99.9%").
# Matches digit runs directly — a trailing \b would fail on digit+unit tokens.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# ── Fabricated-technology check: reuses the resume engine's own curated
# tech vocabulary (resume_engine/technology_gazetteer.py) rather than
# maintaining a second list — same "shared, single source of truth"
# discipline that module already enforces between ProjectParser/SkillsParser.
try:
    from resume_engine.technology_gazetteer import TECHNOLOGIES as _GAZETTEER_TECHNOLOGIES
except Exception:  # pragma: no cover - gazetteer is optional, never hard-fails scoring
    _GAZETTEER_TECHNOLOGIES = ()

from implementation_vocabulary import IMPLEMENTATION_TERMS

# tolerant of inflections: "salt" also matches "salts"/"salted", "retry" matches "retries" via its own entry
_IMPLEMENTATION_TERM_RE = {
    term: re.compile(r"(?<![\w])" + re.escape(term) + r"(?:s|es|ed|d|ing)?(?![\w])") for term in IMPLEMENTATION_TERMS
}
# Acronyms (XR, TTL, LLM, p95 handled by the vocabulary) and hyphenated technical compounds
# (rule-based, at-least-once) are specific in any domain, so they count without a vocabulary entry.
_ACRONYM_RE = re.compile(r"(?<![\w])[A-Z][A-Z0-9]{1,5}(?![\w])")
_HYPHEN_COMPOUND_RE = re.compile(r"(?<![\w-])[a-z0-9]+(?:-[a-z0-9]+)+(?![\w-])")
_NOT_SPECIFIC = frozenset({"ok", "okay", "ui", "ux", "ai", "it", "us"}) | {"well-known", "first-time", "real-world",
                                                                       "end-to-end", "so-called", "full-stack"}
# Question types where the answer is expected to EXPLAIN why/how; for the others
# (what did you own / build / how was it structured) describing it specifically is the substance.
_WHY_REASONING_TYPES = frozenset({"trade_off_analysis", "debugging", "optimization", "explanation", "reflection"})

_GAZETTEER_TECH_RE = {
    term: re.compile(r"(?<![\w.])" + re.escape(term.lower()) + r"(?![\w])")
    for term in _GAZETTEER_TECHNOLOGIES
}

# Someone other than the candidate credited with doing the work.
_OTHER_PERSON_MARKERS = (
    "my teammate", "my team mate", "my colleague", "my coworker", "my co-worker",
    "my partner", "my manager", "my mentor", "my lead", "my supervisor",
    "someone else", "another team member", "a teammate", "a colleague",
)
_CREDIT_VERBS = ("handled", "did", "built", "wrote", "designed", "implemented", "owned", "set up", "configured")
_SOLO_CLAIM_MARKERS = ("solo", "by myself", "on my own", "single-handedly", "independently built", "alone")

# Short names candidates use for technologies the résumé spells out in full
# (or the reverse) — so "Postgres" / "Kafka" in an answer is not mistaken for
# a technology missing from a grounding that says "PostgreSQL" / "Apache Kafka".
_TECH_ALIASES = {
    "postgres": "postgresql", "postgresql": "postgres", "mongo": "mongodb", "mongodb": "mongo",
    "node": "node.js", "node.js": "node", "k8s": "kubernetes", "kubernetes": "k8s",
    "js": "javascript", "javascript": "js", "ts": "typescript", "typescript": "ts",
    "express": "express.js", "express.js": "express", "react": "react.js", "react.js": "react",
}

# ── Explanation-substance signals (scoring v2). Length-independent: each is a
# capped PRESENCE count, so a 25-word answer with one "because" and one "I
# switched ..." can score as high as a 120-word one.
# Reasoning connectives: the answer explains why/how, not just names things.
_REASONING_RE = re.compile(
    r"\b(because|since|so that|so|which means|that way|otherwise|instead of|instead|rather than|"
    r"to avoid|in order to|the reason|trade-?offs?|the problem was|the issue was|that's why|"
    r"meaning|until|unless|whereas|but|if|when|then)\b", re.I)
# First-person (or team) action clauses: "I turned off auto-commit", "we moved X".
_ACTION_RE = re.compile(
    r"\b(i|we)\s+(?:\w+\s+){0,2}?(\w+ed|built|wrote|made|kept|chose|put|set|split|ran|moved|picked|"
    r"went|did|added|turned|switched|found|saw|used|write|make|keep|check|commit|store|use|run|pick|"
    r"move|add|measure|tune|fix|got|owned|own|build|hold|cut)\b", re.I)
# Textbook / generic register: describes the topic in general instead of what THEY did.
_GENERIC_RE = re.compile(
    r"\b(well-known|is used to|are used to|is widely used|widely used|typically|in general|generally|"
    r"there are many ways|is very important|it is important|is important|modern systems|"
    r"best practices?|commonly|always challenging|my approach is to|is becoming)\b", re.I)
_STOPWORDS = frozenset(
    "the a an and or of to in on for with is are was were it that this i we my our you be as at by from "
    "so but if then they them their there here have has had not no do did does just about into out up "
    "very really also all any can could would should will".split())


def _grade_from_score(score: float) -> str:
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


@dataclass(frozen=True)
class EvidenceBreakdown:
    relevance: float            # answer ↔ question topical alignment
    grounding: float            # answer ↔ résumé-grounding consistency (also specificity-to-their-project)
    concreteness: float         # concrete detail: numbers + actual résumé-term use (NOT length)
    ownership: float            # demonstrated ownership, GATED by grounding/concreteness
    tech_correctness_status: str  # "verified" | "not_independently_verified"
    flags: tuple[str, ...]
    on_topic: float = 1.0       # v2 gate: is the answer about this question / this project at all
    substance: float = 0.5      # v2: does it explain why/how
    specificity: float = 0.5    # v2: implementation-level mechanism terms, not topic buzzwords
    first_person: bool = True   # v2: whether ownership was claimed at all (no claim = neutral, not penalised)
    asks_why: bool = True       # v2: question expects an explanation (trade-off/debugging/...) vs a description


def _concreteness(answer: str, answer_lower: str, terms: tuple[str, ...]) -> tuple[float, int, int]:
    """Concrete detail WITHOUT rewarding length: quantitative specifics
    (numbers/metrics) + how many of the candidate's ACTUAL résumé technologies/
    concepts they used in the answer. A 15-word answer with a number and a real
    project term scores high; a 200-word answer with neither scores ~0."""
    numbers = len(_NUMBER_RE.findall(answer))
    mentioned = [t for t in terms if t and t.lower() in answer_lower]
    term_cov = (len(mentioned) / len(terms)) if terms else 0.0
    num_signal = min(1.0, numbers / 2.0)
    # weight résumé-term use a bit above raw numbers; both are length-independent.
    score = 0.4 * num_signal + 0.6 * min(1.0, term_cov * 1.5)
    return round(min(1.0, score), 3), numbers, len(mentioned)


def _explanation_signals(answer: str, terms: tuple[str, ...]) -> dict:
    """Counts behind the v2 substance score and the keyword-list / textbook flags."""
    # dots are allowed inside words ("Node.js") but a sentence-final period is not part of the word
    words = [w.rstrip(".-") for w in re.findall(r"[A-Za-z][\w.+#-]*", answer)]
    n_words = max(1, len(words))
    content = [w.lower() for w in words if w.lower() not in _STOPWORDS and len(w) > 2]
    top_repeat = max((content.count(w) for w in set(content)), default=0)
    term_words = {part for t in terms for part in t.lower().split()}
    return {
        "reasoning": len(_REASONING_RE.findall(answer)),
        "actions": len(_ACTION_RE.findall(answer)),
        "generic": len(_GENERIC_RE.findall(answer)),
        "list_density": (answer.count(",") + len(re.findall(r"\band\b", answer, re.I))) / n_words,
        "term_density": sum(1 for w in words if w.lower() in term_words) / n_words,
        "top_repeat": top_repeat,
        "top_repeat_share": top_repeat / max(1, len(content)),
    }


def _substance(sig: dict) -> float:
    """0..1: does the answer explain why/how (reasoning connectives)."""
    return round(min(1.0, sig["reasoning"] / 2.0), 3)


def _specificity(answer: str, question: str) -> tuple[float, int]:
    """0..1: distinct implementation-level mechanism terms (implementation_vocabulary.py),
    plus acronyms and hyphenated technical compounds (half weight), that the question did
    not already contain. Capped presence count, so it does not grow with length."""
    answer_lower, question_lower = answer.lower(), question.lower()
    found = {term for term, pattern in _IMPLEMENTATION_TERM_RE.items()
             if pattern.search(answer_lower) and not pattern.search(question_lower)}
    extra = {m for m in _ACRONYM_RE.findall(answer) if m not in question and m.lower() not in _NOT_SPECIFIC}
    extra |= {m for m in _HYPHEN_COMPOUND_RE.findall(answer_lower)
              if m not in question_lower and m not in _NOT_SPECIFIC and not any(m in t for t in found)}
    count = len(found) + 0.5 * len(extra)
    return round(min(1.0, count / 3.0), 3), len(found) + len(extra)


def _is_keyword_list(sig: dict) -> bool:
    """Résumé terms strung together, or one term repeated, without explaining anything."""
    list_like = sig["list_density"] >= 0.2 or sig["term_density"] >= 0.2
    stuffed = sig["top_repeat"] >= 4 and sig["top_repeat_share"] >= 0.2
    return (list_like and sig["reasoning"] == 0) or stuffed


def _is_generic(sig: dict) -> bool:
    """Textbook register and nothing the candidate actually did."""
    return sig["generic"] >= 2 and sig["actions"] == 0


def _tech_is_listed(term_lower: str, listed: set[str], grounding_text_lower: str) -> bool:
    if term_lower in listed or term_lower in grounding_text_lower:
        return True
    alias = _TECH_ALIASES.get(term_lower)
    if alias and (alias in listed or alias in grounding_text_lower):
        return True
    # "Kafka" vs a grounding entry "Apache Kafka"
    return any(re.search(r"(?<![\w.])" + re.escape(term_lower) + r"(?![\w])", entry) for entry in listed)


def _unlisted_technology(answer_lower: str, terms: tuple[str, ...], grounding_text_lower: str = "") -> Optional[str]:
    """First gazetteer technology the answer claims to have used that is NOT
    part of THIS question's résumé grounding (e.g. claiming Flink on a
    project whose grounding lists Kafka/Redis/Postgres only). Conservative:
    only the narrow per-question grounding is checked (the evaluator has no
    access to the candidate's full résumé), so this is a caution signal, not
    proof of fabrication — a candidate may genuinely use an adjacent tool the
    grounding snapshot didn't list."""
    listed = {t.lower() for t in terms}
    for term, pattern in _GAZETTEER_TECH_RE.items():
        if _tech_is_listed(term.lower(), listed, grounding_text_lower):
            continue
        if pattern.search(answer_lower):
            return term
    return None


def _attributes_work_to_other_person(answer_lower: str, grounding_text_lower: str) -> bool:
    """Flags an answer that credits the described work to someone other than
    the candidate when the résumé grounding claims solo ownership of it (e.g.
    grounding says "built solo"; answer says "my teammate handled it"). NLI
    contradiction over the whole keyword-stuffed grounding blob misses this
    (validated: it did not fire on this exact case), so this is a dedicated,
    narrow marker check rather than a tweak to the general-purpose NLI
    threshold."""
    if not any(m in grounding_text_lower for m in _SOLO_CLAIM_MARKERS):
        return False
    return any(person in answer_lower and any(verb in answer_lower for verb in _CREDIT_VERBS)
               for person in _OTHER_PERSON_MARKERS)


def compute_evidence(request: EvaluationRequest) -> EvidenceBreakdown:
    """Pure evidence extraction from AVAILABLE signals (reused helpers). No
    length term anywhere; first-person and jargon are never rewarded on their
    own."""
    answer = (request.answer_text or "").strip()
    answer_lower = answer.lower()
    flags: list[str] = []

    gtext = _grounding_text(request.specification)
    raw_relevance = _semantic_similarity(answer, request.question_text) if answer else 0.0
    raw_grounding = _semantic_similarity(answer, gtext) if (answer and gtext) else 0.0
    relevance = _rescale(raw_relevance, _ACCURACY_SIMILARITY_FLOOR, _ACCURACY_SIMILARITY_CEILING)
    grounding = _rescale(raw_grounding, _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING)
    # v2 on-topic gate: raw similarity to EITHER the question or the résumé entry. Used only as a gate —
    # similarity saturates for any on-topic text and is highest for keyword-stuffed answers, so it must
    # not add credit on its own.
    on_topic = _rescale(max(raw_relevance, raw_grounding), 0.08, 0.22)
    terms = _grounding_terms(request.specification)
    concreteness, n_numbers, n_terms = _concreteness(answer, answer_lower, terms)
    unlisted_tech = _unlisted_technology(answer_lower, terms, gtext.lower()) if answer else None
    signals = _explanation_signals(answer, terms)
    substance = _substance(signals)
    specificity, _ = _specificity(answer, request.question_text or "")

    # first-person action clauses ("I turned off auto-commit") count as ownership language too
    has_ownership = _has_ownership_language(answer_lower) or signals["actions"] > 0
    self_correction = any(m in answer_lower for m in _SELF_CORRECTION_MARKERS)
    non_answer = (not answer) or any(m in answer_lower for m in _NON_ANSWER_MARKERS)
    deg = degeneracy(answer)
    contradiction = _contradiction_flag(answer, gtext) if (answer and gtext) else False
    other_person_credit = _attributes_work_to_other_person(answer_lower, gtext.lower()) if (answer and gtext) else False
    if other_person_credit:
        contradiction = True  # same evidentiary status as an NLI-flagged contradiction

    # Ownership is EVIDENCE-GATED: first-person language alone is not rewarded.
    if not has_ownership:
        ownership = 0.2
    else:
        support = max(grounding, concreteness)          # is the ownership claim backed by anything?
        if contradiction and not self_correction:
            ownership = 0.15                            # ownership claim conflicts with the résumé → caution
            flags.append("unsupported_or_conflicting_ownership")
        else:
            ownership = round(0.30 + 0.70 * support, 3)  # grounded/specific ownership earns credit; bare "I" ~0.30
            if support < 0.2:
                flags.append("first_person_without_supporting_evidence")

    # generic-textbook: on-topic but not about THEIR project and no concrete detail
    if (relevance >= 0.55 and grounding < 0.35 and n_terms == 0 and concreteness < 0.25 and not has_ownership) \
            or _is_generic(signals):
        flags.append("generic_textbook")
    if answer and _is_keyword_list(signals):
        flags.append("keyword_list")
    if non_answer:
        flags.append("non_answer")
    if deg.is_degenerate:
        flags.append("degenerate:" + ",".join(deg.reasons))
    if self_correction:
        flags.append("self_correction")
    if unlisted_tech:
        flags.append(f"mentions_technology_not_in_grounding:{unlisted_tech}")
    # Credits the described work to someone else while the résumé claims solo
    # ownership — independent of _has_ownership_language's first-person-phrase
    # match, since the disclaiming phrasing ("my teammate did X, not me") is
    # exactly the case that marker list does not match.
    if other_person_credit and not self_correction:
        ownership = min(ownership, 0.15)
        if "unsupported_or_conflicting_ownership" not in flags:
            flags.append("unsupported_or_conflicting_ownership")
        flags.append("contradicts_solo_ownership_claim")

    # prior-answer consistency (reuses the NLI contradiction helper)
    prior = getattr(request.conversation_context, "prior_answers_for_this_spec", ())
    if prior and answer:
        if _contradiction_flag(answer, " ".join(prior)) and not self_correction:
            flags.append("contradicts_prior_answer")

    verified = request.answer_key is not None and request.answer_key.has_key_points
    return EvidenceBreakdown(
        relevance=round(relevance, 3), grounding=round(grounding, 3),
        concreteness=concreteness, ownership=ownership,
        tech_correctness_status="verified" if verified else "not_independently_verified",
        flags=tuple(flags), on_topic=round(on_topic, 3), substance=substance,
        specificity=specificity, first_person=has_ownership,
        asks_why=getattr(request.reasoning_type, "value", request.reasoning_type) in _WHY_REASONING_TYPES,
    )


def _compose_overall(ev: EvidenceBreakdown) -> float:
    """Weighted evidence overall (length-independent), then gates/penalties.
    Weights sum to 1.0; correctness is NOT a term (unverified for résumé Qs)."""
    overall = (0.30 * ev.relevance + 0.30 * ev.grounding
               + 0.25 * ev.concreteness + 0.15 * ev.ownership)
    if "generic_textbook" in ev.flags:
        overall *= 0.75
    if "unsupported_or_conflicting_ownership" in ev.flags:
        overall *= 0.75
    if "contradicts_solo_ownership_claim" in ev.flags:
        overall *= 0.5   # stronger than generic unsupported-ownership: an explicit, detected credit-to-someone-else
    if any(f.startswith("mentions_technology_not_in_grounding") for f in ev.flags):
        overall *= 0.6    # caution signal: claims a technology this project's grounding never listed
    if "contradicts_prior_answer" in ev.flags:
        overall *= 0.85
    # hard caps for non-answers / degenerate text (never rescued by other signals)
    if "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
        overall = min(overall, 0.10)
    return round(max(0.0, min(1.0, overall)), 3)


def _compose_overall_v2(ev: EvidenceBreakdown) -> float:
    """v2: similarity only GATES (is it on topic); the score itself comes from
    whether the answer explains why/how, gives concrete detail, and shows
    grounded ownership. Fixes v1's failure where textbook definitions and
    keyword lists scored like real answers because relevance + grounding
    similarity (60% of v1) saturate for any on-topic text."""
    # an answer that claims no ownership is neutral here; only unsupported/conflicting claims lose credit
    ownership = ev.ownership if ev.first_person or ev.ownership < 0.2 else 0.5
    if ev.asks_why:    # "why did you..." — the explanation is the answer
        quality = 0.35 * ev.substance + 0.35 * ev.specificity + 0.15 * ev.concreteness + 0.15 * ownership
    else:              # "what did you own / how was it structured" — specific description is the answer
        quality = 0.15 * ev.substance + 0.50 * ev.specificity + 0.20 * ev.concreteness + 0.15 * ownership
    overall = ev.on_topic * (0.10 + 0.90 * quality)
    if "generic_textbook" in ev.flags:
        overall *= 0.55
    if "keyword_list" in ev.flags:
        overall *= 0.50
    if "unsupported_or_conflicting_ownership" in ev.flags:
        overall *= 0.75
    if "contradicts_solo_ownership_claim" in ev.flags:
        overall *= 0.5
    if any(f.startswith("mentions_technology_not_in_grounding") for f in ev.flags):
        overall *= 0.6
    if "contradicts_prior_answer" in ev.flags:
        overall *= 0.85
    # optional LLM fact check: confirmed = flagged by both passes, suspected = first pass only
    if "factual_error_confirmed" in ev.flags:
        overall *= FACT_CONFIRMED_FACTOR
    elif "factual_error_suspected" in ev.flags:
        overall *= FACT_SUSPECTED_FACTOR
    if "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
        overall = min(overall, 0.10)
    return round(max(0.0, min(1.0, overall)), 3)


FACT_CONFIRMED_FACTOR = 0.45
FACT_SUSPECTED_FACTOR = 0.80
LLM_BLEND_WEIGHT = 0.5   # share of the optional local-LLM rubric grade in the final score


# The live grade and the background LLM re-grade (conversation_engine) evaluate the
# SAME request; caching its evidence (similarity + NLI on the CPU) means the re-grade
# only adds the LLM calls instead of recomputing everything alongside the live flow.
_EVIDENCE_CACHE: "collections.OrderedDict[tuple, EvidenceBreakdown]" = collections.OrderedDict()
_EVIDENCE_CACHE_SIZE = 64
_EVIDENCE_CACHE_LOCK = threading.Lock()


def _cached_evidence(request: EvaluationRequest) -> EvidenceBreakdown:
    key = (request.request_id, request.question_text, request.answer_text)
    with _EVIDENCE_CACHE_LOCK:
        if key in _EVIDENCE_CACHE:
            _EVIDENCE_CACHE.move_to_end(key)
            return _EVIDENCE_CACHE[key]
    ev = compute_evidence(request)
    with _EVIDENCE_CACHE_LOCK:
        _EVIDENCE_CACHE[key] = ev
        while len(_EVIDENCE_CACHE) > _EVIDENCE_CACHE_SIZE:
            _EVIDENCE_CACHE.popitem(last=False)
    return ev


def _fact_check_note(fact_check) -> str:
    if fact_check is None:
        return ""
    if fact_check.status != "checked":
        return f"\nAutomated fact check unavailable ({fact_check.model})."
    if not fact_check.suspected_claims:
        return f"\nAutomated fact check ({fact_check.model}): no clearly false technical claims found."
    level = "likely false" if fact_check.false_claims else "possibly false"
    claims = fact_check.false_claims or fact_check.suspected_claims
    return (f"\nAutomated fact check ({fact_check.model}) found {level} technical claims: "
            + "; ".join(f"\"{c['claim']}\" — {c['correction']}" for c in claims[:2]))

_COMPOSERS = {"v1": _compose_overall, "v2": _compose_overall_v2}


class ResumeEvidenceEvaluator:
    """`Evaluator`-Protocol evaluator for candidate-specific résumé questions.
    Scores available evidence; never claims unverified technical correctness.
    Diagnostic dimensions come unchanged from `HeuristicDiagnosticsEngine`
    (payload compatibility). NOT deployed; v5_1088 stays active/rollback."""

    declared_dimensions = CANONICAL_DIMENSION_KEYS
    declared_reasoning_types = tuple(ReasoningType)
    requires_network = False
    def __init__(self, diagnostics_engine: Optional[HeuristicDiagnosticsEngine] = None,
                 name: Optional[str] = None, scoring: Optional[str] = None, fact_checker=None):
        # CAP_EVIDENCE_SCORING=v1 rolls back to the original composition.
        self.scoring = scoring or os.environ.get("CAP_EVIDENCE_SCORING", "v2")
        if self.scoring not in _COMPOSERS:
            raise ValueError(f"unknown scoring {self.scoring!r}; expected one of {sorted(_COMPOSERS)}")
        self.version = self.scoring
        self.diagnostics_engine = diagnostics_engine or HeuristicDiagnosticsEngine()
        self.name = name or f"resume-evidence-evaluator-{self.scoring}"
        # Optional local-LLM fact check + rubric grade (fact_checker.py), only when injected.
        # The live interview never injects one (it must stay fast); conversation_engine's
        # background re-grade does (CAP_FACT_CHECK=1). Unavailable checker = unchanged grading.
        self.fact_checker = fact_checker

    def _fact_check(self, request: EvaluationRequest, ev: EvidenceBreakdown):
        if self.fact_checker is None or "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
            return ev, None
        project = request.specification.grounding.project
        context = f"{project.title}: {project.summary}" if project is not None else ""
        try:
            fc = self.fact_checker.check(request.question_text, request.answer_text, context)
        except Exception:  # never let the optional checker break grading
            return ev, None
        if fc.severity == "none":
            return ev, fc
        return dataclasses.replace(ev, flags=ev.flags + (f"factual_error_{fc.severity}",)), fc

    def _llm_grade(self, request: EvaluationRequest, ev: EvidenceBreakdown) -> Optional[float]:
        grade_fn = getattr(self.fact_checker, "grade", None)
        if grade_fn is None or "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
            return None
        project = request.specification.grounding.project
        context = f"{project.title}: {project.summary}" if project is not None else ""
        try:
            return grade_fn(request.question_text, request.answer_text, context)
        except Exception:
            return None

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        ev = _cached_evidence(request)
        ev, fact_check = self._fact_check(request, ev)
        overall_score = _COMPOSERS[self.scoring](ev)
        llm_grade = self._llm_grade(request, ev) if self.scoring == "v2" else None
        if llm_grade is not None:
            overall_score = round(LLM_BLEND_WEIGHT * llm_grade + (1 - LLM_BLEND_WEIGHT) * overall_score, 3)
        grade = _grade_from_score(overall_score)

        dimensions = self.diagnostics_engine.compute(request)          # preserved verbatim
        strengths, weaknesses = self.diagnostics_engine.claims(dimensions)

        # confidence reflects how much EVIDENCE we had, not how confident the answer sounded.
        confidence = round(max(0.15, min(1.0, 0.25 + 0.4 * ev.grounding + 0.35 * ev.concreteness)), 3)
        if "non_answer" in ev.flags or any(f.startswith("degenerate") for f in ev.flags):
            confidence = 0.2

        reasoning = (
            f"Evidence-based score (résumé-specific question). Technical correctness: "
            f"{ev.tech_correctness_status.upper().replace('_', ' ')} — no answer key, so factual correctness of "
            f"claims was NOT judged; this score reflects only available evidence. "
            f"relevance {ev.relevance:.0%}, résumé-consistency {ev.grounding:.0%}, "
            f"concreteness {ev.concreteness:.0%}, ownership-evidence {ev.ownership:.0%}, "
            f"explanation {ev.substance:.0%}"
            + (f"; flags: {', '.join(ev.flags)}" if ev.flags else "")
            + "."
            + _fact_check_note(fact_check)
            + "\nDiagnostic breakdown (heuristic, does NOT drive this score):\n"
            + "\n".join(f"{d.name}: {d.raw_score:.0%}" for d in dimensions)
        )

        return EvaluationResult(
            result_id=f"eval_{_uuid.uuid4().hex[:12]}", request_id=request.request_id,
            evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
            specification_id=request.specification.id, source_id=request.specification.source_id,
            category=request.specification.category.value,
            project_reference=(
                request.specification.grounding.project.title
                if request.specification.grounding.project is not None else None
            ),
            reasoning_type=request.reasoning_type,
            evaluator_name=self.name, evaluator_version=self.version,
            model_version=(("similarity", "all-MiniLM-L6-v2"), ("contradiction", "cross-encoder/nli-MiniLM2-L6-H768")),
            dataset_version=None, training_date=None,
            dimensions=dimensions,
            overall_score=overall_score, grade=grade,
            confidence=confidence, confidence_source=_CONFIDENCE_SOURCE,
            confidence_rationale=(
                "Reflects the strength of the available EVIDENCE (résumé grounding + concrete detail), not the "
                f"answer's tone or length. Technical correctness is {ev.tech_correctness_status} "
                "(no answer key for this experiential question)."
            ),
            reasoning=reasoning,
            strengths=strengths, weaknesses=weaknesses,
            resume_grounding_score=ev.grounding,
            calibration_version=None,
        )
