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
"""
from __future__ import annotations

from typing import Optional

from answer_key import AnswerKey
from correctness_nli_scorer import CoverageNLIScorer
from evaluation_request import EvaluationRequest
from question_specification import QuestionCategory

CONTRADICTION_FLAG_THRESHOLD = 0.85
SUPPORT_CEILING_FOR_FLAG = 0.20
MIN_ANSWER_WORDS = 12  # below this there's too little claim to judge either way

POSSIBLE_MISMATCH = "possible_mismatch"
NOT_INDEPENDENTLY_VERIFIED = "not_independently_verified"

_scorer = CoverageNLIScorer()


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

    if result["contradiction"] >= CONTRADICTION_FLAG_THRESHOLD and result["support"] <= SUPPORT_CEILING_FOR_FLAG:
        return POSSIBLE_MISMATCH
    return NOT_INDEPENDENTLY_VERIFIED
