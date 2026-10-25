"""
Tech-consistency flag — a narrow, ADDITIVE side-channel for project-grounded
resume-interview questions. Checks whether the technologies a candidate
*describes* in their answer are consistent with the technologies the resume
itself already lists for that project (`spec.grounding.project.technologies`
-- nothing invented, nothing authored; the resume is its own answer key).

NOT a score term. This never touches `overall_score`/`grade` -- it mirrors
`resume_evidence_evaluator`'s posture that technical correctness is exposed
as a STATUS, never folded into the score, because the resume interview's
question families are experiential and a wrong-but-fluent claim should not
silently pass, but also should never be accused of lying on a shaky signal.

CALIBRATION NOTE (real-resume battery, 2 real resumes / 8 project-grounded
turns, genuine vs. a synthetically fabricated tech-stack answer of matched
length/fluency): the underlying keyless NLI model occasionally mis-flags a
genuine, resume-grounded answer as "contradicting" purely on phrasing
(1 of 6 genuine cases scored contradiction=0.84 even though it was true).
Requiring BOTH a very high contradiction score (>=0.85) AND near-zero support
(<=0.20) keeps that genuine case (support was still 0.19, contradiction 0.84
-- just under the bar) out of the flagged bucket, while still catching 4 of 5
fabricated-stack answers in the same battery. The one miss (a fabricated
stack that only weakly registered as a contradiction) is an accepted false
negative: under-flagging is the acceptable failure mode here, over-accusing a
truthful candidate is not. UI copy using this flag must stay soft ("worth
double-checking"), never an accusation.

SECOND CALIBRATION ROUND (5 real resumes, an adversarial battery including a
genuinely off-topic answer -- candidate talks about a hobby, never engages
with the project at all): the contradiction/support gate above fired on that
off-topic answer too (1 of 5 resumes) -- a real false positive, since there
was no tech CLAIM to contradict, just no answer. Root cause: an
answer that says nothing about the project and one that makes a wrong claim
about it can both show near-zero `support`/high `contradiction` against the
resume's tech key points, because neither one's sentences entail them.
Measured fix: cosine similarity between the raw answer and the project's own
title+summary separates these cleanly on the same battery -- off-topic
answers scored <=0.108 in every resume, while even a "natural" fabricated-tech
answer that doesn't parrot the project's title/summary (unlike the synthetic
`wrong_tech` fixture used in round one) scored >=0.140. PROJECT_RELEVANCE_FLOOR
sits at 0.12, in that gap. Only gates the already-rare POSSIBLE_MISMATCH path
(the NOT_INDEPENDENTLY_VERIFIED fallback below it is untouched), and fails
CLOSED (treated as "not engaged", so it suppresses rather than forces the
flag) if the embedding call itself errors -- consistent with this module's
standing rule that a shaky signal must never escalate to an accusation.
"""
from __future__ import annotations

from typing import Callable, Optional

from answer_key import AnswerKey
from correctness_nli_scorer import CoverageNLIScorer
from evaluation_request import EvaluationRequest
from question_specification import ProjectGrounding, QuestionCategory

CONTRADICTION_FLAG_THRESHOLD = 0.85
SUPPORT_CEILING_FOR_FLAG = 0.20
MIN_ANSWER_WORDS = 12  # below this there's too little claim to judge either way
PROJECT_RELEVANCE_FLOOR = 0.12  # cosine(answer, project title+summary); see 2nd calibration note

POSSIBLE_MISMATCH = "possible_mismatch"
NOT_INDEPENDENTLY_VERIFIED = "not_independently_verified"

_EMB_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"  # same default model correctness_nli_scorer uses

_scorer = CoverageNLIScorer()
_embed_model = None  # lazy-loaded; test-injectable via the module-level `_embed` function object


def _lazy_embed(texts: list[str]):
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(_EMB_MODEL_ID)
    import numpy as np
    return np.asarray(_embed_model.encode(texts, normalize_embeddings=True), dtype=float)


_embed: Callable = _lazy_embed


def _engages_with_project(answer_text: str, project: ProjectGrounding) -> bool:
    """Whether the answer semantically touches the project AT ALL (title +
    summary), independent of whether its tech claim is right or wrong. Fails
    CLOSED (returns False -- not engaged, suppressing the mismatch verdict)
    on any embedding error, per this module's "never over-accuse" rule."""
    try:
        import numpy as np
        vecs = _embed([answer_text, f"{project.title}. {project.summary}".strip()])
        a, p = vecs[0], vecs[1]
        sim = float(np.dot(a, p) / (np.linalg.norm(a) * np.linalg.norm(p) + 1e-9))
    except Exception:
        return False
    return sim >= PROJECT_RELEVANCE_FLOOR


def _names_unlisted_technology(answer: str, project) -> bool:
    """A "the technologies you described don't match your résumé" warning needs the answer to
    actually NAME a technology the résumé doesn't list for this project (alias-aware: Postgres =
    PostgreSQL, Kafka = Apache Kafka). Found in a visual check of the report: an answer about
    Chronos's leases that only mentioned Postgres was flagged, because the NLI contradiction score
    against bare technology names is noisy when the answer simply doesn't discuss most of them."""
    try:
        from resume_evidence_evaluator import _unlisted_technology
    except Exception:
        return True   # can't check: fall back to the NLI gates alone (previous behaviour)
    terms = tuple(project.technologies) + tuple(project.concepts)
    grounding = f"{project.title} {project.summary}".lower()
    return _unlisted_technology(answer.lower(), terms, grounding) is not None


def check_tech_consistency(request: EvaluationRequest) -> Optional[str]:
    """Returns POSSIBLE_MISMATCH, NOT_INDEPENDENTLY_VERIFIED, or None
    (not applicable: not a project question, no technologies listed on the
    resume for this project, or the answer is too short to carry a
    verifiable technical claim). Never raises; a scorer failure (e.g. model
    unavailable) degrades to None rather than breaking the turn."""
    spec = request.specification
    if spec.category not in (QuestionCategory.PROJECT_DEEP_DIVE, QuestionCategory.PROJECT_OVERVIEW):
        return None
    project = spec.grounding.project
    if project is None:
        return None
    technologies = tuple(t for t in project.technologies if t and t.strip())
    if not technologies:
        return None
    if len(request.answer_text.split()) < MIN_ANSWER_WORDS:
        return None

    try:
        result = _scorer.score_answer(request.answer_text, AnswerKey(key_points=technologies))
    except Exception:
        return None

    if result["degenerate"]:
        return None

    if (result["contradiction"] >= CONTRADICTION_FLAG_THRESHOLD and result["support"] <= SUPPORT_CEILING_FOR_FLAG
            and _names_unlisted_technology(request.answer_text, project)
            and _engages_with_project(request.answer_text, project)):
        return POSSIBLE_MISMATCH
    return NOT_INDEPENDENTLY_VERIFIED
