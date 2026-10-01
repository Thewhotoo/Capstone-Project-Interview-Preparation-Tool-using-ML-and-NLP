"""Grade a technical-interview answer against the question's key points.

    score = 0.85 x key-point coverage + 0.15 x similarity to the reference answer

Key-point coverage is judged by meaning: the answer is cut into overlapping
chunks, and for each key point the NLI cross-encoder (nli-deberta-v3-base) gives
the probability that some chunk ENTAILS it; MiniLM embedding similarity only
rescues borderline cases:
    covered   entailment >= 0.6, or entailment >= 0.2 and similarity >= 0.8
    partial   entailment >= 0.05 and (similarity >= 0.6 or entailment >= 0.3)
    missing   otherwise
The reference-answer similarity term is scaled down when few key points are
met (full weight from half the points up), so an on-topic answer that states
nothing correct cannot earn it.
Evaluated on 100 hand-checked answers over 25 bank questions (grader_eval/):
key-point agreement 85% (MiniLM NLI: 72%), "covered" precision 90% / recall
85%, score correlation with human scores r = 0.80; confidently wrong answers
average 0.34 (MiniLM: 0.66). A contradiction veto was tried and dropped: correct answers
often have some chunk the model calls contradictory. A missed point triggers
its prepared follow-up, giving the candidate a second chance.
Why entailment: calibration on real bank questions showed embedding similarity
alone rewards shared words -- "context switching is when the context switches"
out-scored a correct answer (0.71 vs 0.55) -- while entailment gives such
echoes ~0 and correct answers 0.8-0.95. (The Resume Discussion evaluator keeps
NLI out of its score because entailment rewarded echoing a *question*; here the
hypothesis is a key point the candidate never saw.)
Similarity to the reference answer is rescaled so an unrelated answer scores ~0.

Clarity signals, used by the follow-up policy (followup.py), not the score:
  fillers       "um", "uh", "you know", "I mean", "kind of" ... (browser speech-to-
                text often drops these, so for spoken answers vagueness and length
                carry most of the signal)
  dont_know     "I don't know", "no idea", "not sure" in a short answer
  too_short     fewer than MIN_WORDS words
  vague         hedges and placeholders ("something like", "stuff", "etc.")
  repetitive    the same few words over and over
Adapted from the legacy RAG grader (rag_tester/evaluate.py: junk-input gate,
semantic + concept matching), scoring against the bank's verified key points
instead of guessing concepts from raw slide text.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Callable, Sequence

import numpy as np

from .bank import KeyPoint, Question

logger = logging.getLogger(__name__)

EMBED_MODEL = "all-MiniLM-L6-v2"
NLI_MODEL = "cross-encoder/nli-deberta-v3-base"
COVERED_ENTAIL, RESCUE_ENTAIL, RESCUE_SIM = 0.60, 0.20, 0.80
PARTIAL_ENTAIL, PARTIAL_SIM, PARTIAL_ENTAIL_ALONE = 0.05, 0.60, 0.30
FALLBACK_COVERED, FALLBACK_PARTIAL = 0.55, 0.40   # word-overlap / embedding-only fallbacks
REF_SIM_FLOOR, REF_SIM_CEIL = 0.35, 0.80   # rescale answer<->reference cosine to 0..1
REF_FULL_AT = 0.5                          # key-point score from which the reference term counts fully
KEYPOINT_WEIGHT = 0.85
MIN_WORDS = 8
FILLER_RATIO = 0.06
CHUNK_WINDOWS = ((20, 10), (40, 20))   # (words, stride)

_FILLER_WORDS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "hmm", "hm", "ah", "eh"}
_FILLER_PHRASES = ("you know", "i mean", "kind of", "sort of", "i guess", "basically like", "like like")
_DONT_KNOW_RE = re.compile(
    r"\b(i\s+(really\s+)?(do\s*n[o']?t|dont)\s+know|no\s+idea|not\s+sure|i'?m\s+not\s+sure|"
    r"(do\s*n[o']?t|can'?t|cannot)\s+(remember|recall)|i\s+forgot|no\s+clue|skip(\s+this)?|pass)\b", re.I)
_VAGUE_MARKERS = ("something like", "some kind of", "stuff", "things like that", "and so on",
                  "etc", "whatever", "something something", "i think maybe", "not exactly sure")

Embed = Callable[[Sequence[str]], np.ndarray]


Entail = Callable[[Sequence[str], str], float]


class _LazyModels:
    """Private lazy singletons (project convention: each module owns its copies)."""
    _embed = None
    _nli = None
    _entail_idx = None

    @classmethod
    def embedder(cls):
        if cls._embed is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._embed = SentenceTransformer(EMBED_MODEL)
            except Exception as exc:  # pragma: no cover - environment-dependent
                logger.warning("SentenceTransformer unavailable, grading by word overlap: %s", exc)
                cls._embed = False
        return cls._embed if cls._embed is not False else None

    @classmethod
    def nli(cls):
        if cls._nli is None:
            try:
                from sentence_transformers import CrossEncoder
                cls._nli = CrossEncoder(NLI_MODEL)
                labels = {v.lower(): int(k) for k, v in cls._nli.model.config.id2label.items()}
                cls._entail_idx = labels.get("entailment", 1)
            except Exception as exc:  # pragma: no cover - environment-dependent
                logger.warning("NLI model unavailable, grading by embeddings only: %s", exc)
                cls._nli = False
        return cls._nli if cls._nli is not False else None


def default_embed(texts: Sequence[str]) -> np.ndarray | None:
    model = _LazyModels.embedder()
    if model is None:
        return None
    return model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)


def default_entail(premises: Sequence[str], hypothesis: str) -> float | None:
    """Highest probability that one of the premises entails the hypothesis."""
    model = _LazyModels.nli()
    if model is None:
        return None
    logits = np.asarray(model.predict([(p, hypothesis) for p in premises], show_progress_bar=False))
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return float((e / e.sum(axis=1, keepdims=True))[:, _LazyModels._entail_idx].max())


@dataclass
class Clarity:
    words: int = 0
    fillers: int = 0
    filler_ratio: float = 0.0
    dont_know: bool = False
    too_short: bool = False
    vague: bool = False
    repetitive: bool = False

    @property
    def unclear(self) -> bool:
        """Worth asking the candidate to say it more clearly."""
        return self.filler_ratio >= FILLER_RATIO or self.vague or self.repetitive


@dataclass
class Grade:
    score: float
    keypoint_score: float
    reference_similarity: float
    covered: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    point_scores: dict[str, dict] = field(default_factory=dict)   # point -> {entailment, similarity}
    clarity: Clarity = field(default_factory=Clarity)
    core: str = ""        # covered | partial | missing for the question's main idea ("" = none in the bank)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["clarity"]["unclear"] = self.clarity.unclear
        return d


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def analyse_clarity(answer: str) -> Clarity:
    words = _words(answer)
    n = len(words)
    low = " " + " ".join(words) + " "
    fillers = sum(1 for w in words if w in _FILLER_WORDS) + sum(low.count(f" {p} ") for p in _FILLER_PHRASES)
    vague_hits = sum(low.count(f" {m} ") for m in _VAGUE_MARKERS)
    return Clarity(
        words=n,
        fillers=fillers,
        filler_ratio=round(fillers / n, 3) if n else 0.0,
        dont_know=bool(_DONT_KNOW_RE.search(answer)) and n <= 25,
        too_short=n < MIN_WORDS,
        vague=vague_hits >= 2 or (vague_hits >= 1 and n < 20),
        repetitive=n > 10 and len(set(words)) / n < 0.4,
    )


_FILLER_RE = re.compile(
    r"\b(" + "|".join(sorted(_FILLER_WORDS, key=len, reverse=True)) + r")\b[,.]?\s*"
    r"|\b(you know|i mean|kind of|sort of|i guess)\b[,]?\s*", re.I)


def strip_fillers(answer: str) -> str:
    """Remove hesitation words before judging content: they confuse the entailment
    model (a correct but hesitant answer otherwise scores near zero). They still
    count as a clarity signal for the follow-up decision."""
    return re.sub(r"\s{2,}", " ", _FILLER_RE.sub("", answer)).strip()


def _chunks(answer: str) -> list[str]:
    """Sentences, adjacent sentence pairs (a point is often split over two), and
    overlapping 20- and 40-word windows (spoken answers often have no punctuation)."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?;])\s+|\n+", answer) if len(p.split()) >= 3]
    pairs = [f"{a} {b}" for a, b in zip(parts, parts[1:])]
    words = answer.split()
    windows = [" ".join(words[i:i + size]) for size, stride in CHUNK_WINDOWS
               for i in range(0, max(1, len(words) - size + 1), stride)]
    return list(dict.fromkeys(parts + pairs + windows + [answer.strip()]))


def _overlap(a: str, b: str) -> float:
    """Word-overlap fallback when no embedding model is available."""
    stop = {"the", "a", "an", "of", "to", "is", "and", "in", "it", "that", "for", "on", "by", "with", "as", "are"}
    wa, wb = set(_words(a)) - stop, set(_words(b)) - stop
    return len(wa & wb) / len(wb) if wb else 0.0


VARIANT_TOP_CHUNKS = 4       # answer slices each informal variant is checked against
CORE_FLOORS = {"covered": 0.75}   # key-point score floor when the main idea is clearly stated


def _similarities(chunks: list[str], targets: list[str], embed: Embed | None) -> np.ndarray:
    """targets x chunks similarity matrix."""
    vecs = embed(chunks + targets) if embed else None
    if vecs is None:
        return np.array([[_overlap(c, t) for c in chunks] for t in targets])
    c, t = vecs[:len(chunks)], vecs[len(chunks):]
    return t @ c.T


def classify_point(entail: float | None, sim: float) -> str:
    """covered | partial | missing for one key point (see module docstring)."""
    if entail is None:                                   # no NLI model: similarity alone
        return "covered" if sim >= FALLBACK_COVERED else "partial" if sim >= FALLBACK_PARTIAL else "missing"
    if entail >= COVERED_ENTAIL or (entail >= RESCUE_ENTAIL and sim >= RESCUE_SIM):
        return "covered"
    if entail >= PARTIAL_ENTAIL and (sim >= PARTIAL_SIM or entail >= PARTIAL_ENTAIL_ALONE):
        return "partial"
    return "missing"


def combine(keypoint_score: float, reference_similarity: float) -> float:
    """Answer score from key-point coverage and (rescaled) reference similarity."""
    ref = reference_similarity * min(1.0, keypoint_score / REF_FULL_AT)
    return KEYPOINT_WEIGHT * keypoint_score + (1 - KEYPOINT_WEIGHT) * ref


def grade_answer(question: Question, answer: str, embed: Embed | None = default_embed,
                 entail: Entail | None = default_entail) -> Grade:
    clarity = analyse_clarity(answer)
    if clarity.words == 0:
        return Grade(0.0, 0.0, 0.0, missing=[k.point for k in question.key_points], clarity=clarity)

    chunks = _chunks(strip_fillers(answer) or answer)
    points = [k.point for k in question.key_points]
    variants = [list(k.variants) for k in question.key_points]
    sims = _similarities(chunks, points + [question.reference_answer] + [v for vs in variants for v in vs], embed)
    point_best = sims[:len(points)].max(axis=1)
    ref_sim = float(sims[len(points)].max())
    variant_sims = iter(sims[len(points) + 1:])

    implied_by_question: dict[str, float] = {}

    def variant_entail(top: list[str], v: str) -> float:
        """Informal variants are short and generic ("safe state avoids deadlock"),
        so the question alone often implies them: only what the answer adds counts."""
        if v not in implied_by_question:
            implied_by_question[v] = entail([question.text], v)
        return entail(top, v) - implied_by_question[v]

    covered, partial, missing = [], [], []
    point_scores = {}
    for p, s, vs in zip(points, point_best, variants):
        e = entail(chunks, p) if entail else None
        matched = None
        for v in vs:
            # informal variants (enrich_bank.py): each is checked against only
            # the answer slices closest to it, to stay fast on a CPU
            row = next(variant_sims)
            if e is not None and e < COVERED_ENTAIL:
                top = [chunks[j] for j in np.argsort(-row)[:VARIANT_TOP_CHUNKS]]
                ev = variant_entail(top, v)
                if ev > e:
                    e, matched = ev, v
        point_scores[p] = {"entailment": None if e is None else round(e, 3), "similarity": round(float(s), 3)}
        if matched:
            point_scores[p]["matched"] = matched
        {"covered": covered, "partial": partial, "missing": missing}[classify_point(e, float(s))].append(p)
    kp_score = (len(covered) + 0.5 * len(partial)) / len(points)
    core_status = ""
    if question.core_point:
        # Stating the question's main idea correctly is a good answer even when
        # it misses slide-specific key points: an extra route to credit, never a penalty.
        core_texts = [question.core_point, *question.core_variants]
        core_rows = _similarities(chunks, core_texts, embed)
        core_e = entail(chunks, question.core_point) if entail else None
        for v, row in zip(core_texts[1:], core_rows[1:]):
            if core_e is not None and core_e < COVERED_ENTAIL:
                core_e = max(core_e, variant_entail([chunks[j] for j in np.argsort(-row)[:VARIANT_TOP_CHUNKS]], v))
        core_status = classify_point(core_e, float(core_rows[0].max()))
        kp_score = max(kp_score, CORE_FLOORS.get(core_status, 0.0))
    ref_score = float(np.clip((ref_sim - REF_SIM_FLOOR) / (REF_SIM_CEIL - REF_SIM_FLOOR), 0.0, 1.0))
    score = combine(kp_score, ref_score)
    if clarity.dont_know and not covered:
        score = min(score, 0.1)
    if clarity.too_short:
        score = min(score, 0.5)
    return Grade(round(score, 3), round(kp_score, 3), round(ref_score, 3), covered, partial, missing,
                 point_scores, clarity, core_status)


FU_COVERED_ENTAIL = 0.50     # a follow-up reply (read with its question) entails the expected answer
FU_PARTIAL_ENTAIL = 0.20
FU_PARTIAL_SIM = 0.60        # ...or is close to it in meaning: partial credit only (similarity
                             # also rewards wrong-but-related replies, so it never gives "covered")
FU_REPLY_MATCH_SIM = 0.85    # ...except a near-exact match with a known correct reply ("nope", "banker's algorithm")
FU_REPLIES_AS_HYPOTHESES = False   # short replies as NLI hypotheses too: generic ones ("it's impossible")
                                   # get confirmed by unrelated replies (wrong replies accepted 8% -> 18%)
_POLAR_QUESTION_RE = re.compile(r"^\s*(does|do|did|is|are|was|were|can|could|will|would|should|has|have|must)\b", re.I)
_YES_RE = re.compile(r"^\s*(yes|yeah|yep|yup|ya|sure|correct|right|it does|it can|it is|true)\b", re.I)
_NO_RE = re.compile(r"^\s*(no|nope|nah|not really|never|it doesn'?t|it does not|it can'?t|it cannot|it isn'?t|false)\b", re.I)


def _claims(text: str) -> list[str]:
    """The expected answer split into short claims (NLI misses long compound hypotheses)."""
    parts = re.split(r"(?<=[.!?;])\s+|,\s*(?:and|which|so|because|such as)\s+|\s+(?:because|so that|which means)\s+", text)
    return list(dict.fromkeys([p.strip(" .,") for p in parts if len(p.split()) >= 3] + [text.strip()]))


def _yes_no(question: str, expected: str, answer: str) -> str | None:
    """Yes/no follow-ups: "nope" is a complete answer when the expected answer is "No, ..."."""
    if not _POLAR_QUESTION_RE.match(question or ""):
        return None
    want = "yes" if _YES_RE.match(expected) else "no" if _NO_RE.match(expected) else None
    got = "yes" if _YES_RE.match(answer) else "no" if _NO_RE.match(answer) else None
    if want is None or got is None:
        return None
    return "covered" if want == got else "missing"


def followup_covers(key_point: KeyPoint, answer: str, embed: Embed | None = default_embed,
                    entail: Entail | None = default_entail) -> tuple[str, dict]:
    """Was the follow-up answered correctly? (covered | partial | missing, scores)

    The reply is judged against the follow-up it answers (key_point.followup)
    and its expected answer, and the key point itself:
      * "I don't know"                        -> missing
      * yes/no question, same yes/no as expected -> covered (opposite -> missing)
      * the reply entails a claim of the expected answer or the key point,
        on its own or read with the question  -> covered (>= 0.5) / partial (>= 0.2)
      * reply close in meaning to the expected answer -> partial
    Reading the reply with its question matters: "to make creating objects
    easier" only entails "the Builder pattern simplifies object creation" in
    the context of "What is the main purpose of the Builder pattern?". Only
    what the reply ADDS counts (entailment with the question minus entailment
    from the question alone), otherwise the question's own words confirm the
    claim whatever the reply says. On 35 real correct replies and 210 wrong
    ones (replies to other questions): 69% of correct replies accepted, 8% of
    wrong ones (4% fully); the yes/no rule comes on top."""
    empty = {"entailment": 0.0, "similarity": 0.0}
    if not answer.strip() or analyse_clarity(answer).dont_know:
        return "missing", empty
    question, expected = key_point.followup, key_point.followup_answer
    rule = _yes_no(question, expected, answer)
    if rule is not None:
        return rule, {**empty, "rule": "yes_no"}

    chunks = _chunks(strip_fillers(answer) or answer)
    replies = list(key_point.followup_replies)      # short correct replies (enrich_bank.py)
    hypotheses = [key_point.point] + (_claims(expected) if expected else []) \
        + ([r for r in replies if len(r.split()) >= 3] if FU_REPLIES_AS_HYPOTHESES else [])
    sims = _similarities([strip_fillers(answer) or answer], [expected or key_point.point] + replies, embed)[:, 0]
    sim = float(sims.max())
    if replies and embed is not None and float(sims[1:].max()) >= FU_REPLY_MATCH_SIM:
        return "covered", {"entailment": None, "similarity": round(float(sims[1:].max()), 3), "rule": "reply_match"}
    e = None
    if entail:
        e = max(entail(chunks, h) for h in hypotheses)
        if question:   # only what the reply adds to its question counts
            with_question = [f"{question} {c}" for c in chunks]
            e = max(e, max(entail(with_question, h) - entail([question], h) for h in hypotheses))
    scores = {"entailment": None if e is None else round(e, 3), "similarity": round(sim, 3)}
    if e is None:                                    # no NLI model: similarity alone
        return ("covered" if sim >= FALLBACK_COVERED else "partial" if sim >= FALLBACK_PARTIAL else "missing"), scores
    if e >= FU_COVERED_ENTAIL:
        return "covered", scores
    if e >= FU_PARTIAL_ENTAIL or sim >= FU_PARTIAL_SIM:
        return "partial", scores
    return "missing", scores
