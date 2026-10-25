"""
Answer-engagement signal for Resume Discussion scoring.

ROOT-CAUSE CONTEXT. The live overall score is
`0.8 x OverallSingleEvaluator(DeBERTa v5_1088) + 0.2 x HeuristicEvaluator`
(see `averaged_evaluator.py`). The DeBERTa term -- 80% of the score -- is
answer-INSENSITIVE on a grounded resume: it scores largely from the
question + resume context and barely reads the answer. `answer_gate` already
floors the hard non-answers (idk / keyword dump / deflection). A measured
battery of answer archetypes (scored against real questions on real resumes)
showed the base model otherwise orders RELEVANT answers correctly
(vague < decent < strong), with one remaining smooth-middle defect the gate
does not touch:

  * ECHO / PARROT answers (restating the question back) scored up to 0.56
    ("adequate"). Measured content-novelty-beyond-the-question: 0.0 for echo
    vs >= 0.93 for every genuine archetype -- a clean, large-margin separator.

This module turns that into ONE general, question/resume-agnostic, downward-only
factor in [0, 1]: ~1.0 (no change) for any real answer; near 0 for a pure echo.
It never raises a score, mirroring `answer_gate`'s discipline.

WHAT THIS MODULE DELIBERATELY DOES NOT DO (documented so it is not re-added as a
"fix"): an OFF-TOPIC detector via similarity-to-grounding was built and then
REJECTED on measurement. Grounding similarity cannot separate off-topic
rambling from an on-topic answer about a different technical aspect: a genuine
"I wrote the CI pipeline in GitHub Actions" has near-zero similarity to a
"Secure P2P chat" project's grounding. On the validation battery that signal
attenuated STRONG to x0.72, DECENT to x0.54, and 23/40 genuine answers (min
x0.0). Off-topic replies ("the best part was the free snacks") were never a
reported problem and still score only "weak"; penalizing them is not worth
zeroing real answers. The echo signal below has NO such false positives, since
echo requires the reply to be a near-verbatim restatement of the question.

Deterministic given the shared SBERT encoder (reused from heuristic_evaluator);
degrades to that module's word-overlap fallback when the encoder is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from heuristic_evaluator import _grounding_text, _semantic_similarity  # noqa: F401 (grounding kept for callers)

# ── Calibration (from the measured archetype battery; see module docstring) ──
# Echo attenuation fires ONLY when the reply is BOTH a near-duplicate of the
# question (high semantic similarity) AND adds almost no new content (low
# novelty). ECHO measured qsim=1.0 / novelty=0.0; every genuine archetype
# measured qsim<=0.25 and novelty>=0.93, so neither condition fires on a real
# answer -- a real answer whose wording differs from the question (qsim below
# the threshold) is never treated as echo, whatever its novelty.
_ECHO_QSIM_MIN = 0.55
_NOVELTY_FULL = 0.25

_FUNCTION_WORDS = frozenset(
    """a an the this that these those it its they them their we our us i you your me my he she his her
    is are was were be been being am do does did has have had can could will would shall should may might must
    of in on at to for with from by as into over under about per through between during without within across
    and or but so if then than because however therefore thus while when where which who whom whose what how why
    not no nor yes such very more most less least much many some any each every both all""".split()
)


def _content_words(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in _FUNCTION_WORDS and len(t) > 1}


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


@dataclass(frozen=True)
class EngagementVerdict:
    multiplier: float            # downward-only factor in [0, 1]
    novelty: float               # content-beyond-question ratio
    question_similarity: float
    reason: str = ""             # "" or "echo"


def engagement_multiplier(question_text: str, answer_text: str) -> EngagementVerdict:
    """Downward-only engagement factor for one answer. Returns 1.0 for any real
    reply; drops toward 0 only for a near-verbatim restatement of the question.
    Never raises a score. (`grounding_text` is intentionally not a parameter --
    see the module docstring on why grounding-relevance was rejected.)"""
    answer = (answer_text or "").strip()
    if not answer:
        return EngagementVerdict(1.0, 0.0, 0.0, "")  # empty handled upstream by the gate

    answer_content = _content_words(answer)
    novelty = len(answer_content - _content_words(question_text)) / max(len(answer_content), 1)
    qsim = _semantic_similarity(answer, question_text or "")
    echo_factor = _clamp01(novelty / _NOVELTY_FULL) if qsim >= _ECHO_QSIM_MIN else 1.0

    return EngagementVerdict(
        multiplier=round(echo_factor, 3),
        novelty=round(novelty, 3), question_similarity=round(qsim, 3),
        reason="echo" if echo_factor < 0.999 else "",
    )


def apply_engagement(request, result):
    """Attenuate `result.overall_score` for a pure-echo reply (downward only).
    A result already floored to <= 0.1 (by answer_gate or the model) is returned
    unchanged, as is any answer that is not an echo (multiplier ~1.0)."""
    if result.overall_score <= 0.1:
        return result
    verdict = engagement_multiplier(request.question_text, request.answer_text)
    if verdict.multiplier >= 0.999:
        return result

    from evaluation_result import EvidenceLinkedClaim
    from averaged_evaluator import _grade  # same cutpoints the live score uses

    new_score = round(result.overall_score * verdict.multiplier, 3)
    weakness = EvidenceLinkedClaim(
        claim="The reply mostly restated the question instead of answering it.",
        dimension=result.dimensions[0].name if result.dimensions else "relevance_completeness",
        evidence=f"answer_engagement:{verdict.reason}",
    )
    return result.model_copy(update={
        "overall_score": new_score,
        "grade": _grade(new_score),
        "strengths": result.strengths if new_score >= 0.30 else (),
        "weaknesses": (weakness,) + tuple(result.weaknesses),
    })
