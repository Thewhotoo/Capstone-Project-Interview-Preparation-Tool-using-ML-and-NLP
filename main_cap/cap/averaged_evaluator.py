"""
AveragedEvaluator — Round 1 scoring as a weighted blend of a teammate's trained
model and our heuristic evaluator (integrated 2026-09-30,
resumeParser_integration.md step 5):

    overall_score = 0.8 x OverallSingleEvaluator (DeBERTa-v3, v5_1088)
                  + 0.2 x HeuristicEvaluator ("heuristic-v1")

Measured on two sets (integration_checks/eval_151.py, v4_eval.py + score_v4.py),
QWK against the gold grades:

    | | his 151 test answers | 58 hard V4 cases | pairs ordered right |
    | heuristic alone | 0.10 | 0.23 | 41 / 61 |
    | model alone     | 0.86 | 0.70 | 50 / 61 |
    | 50 / 50         | 0.68 | 0.71 | 57 / 61 |
    | 80 / 20 (used)  | 0.86 | 0.70 | 57 / 61 |

80/20 keeps the model's accuracy on ordinary answers and gains the heuristic's
ordering of tricky pairs. The model's own internal non-answer gate is disabled
(overall_single_evaluator.py): it had been crushing excellent answers (e.g. a
composite-index answer, gold 0.94 -> 0.10); the central answer_gate handles
non-answers instead. Caveat: the model's score tracks answer length (word count
vs score r = 0.70, same as its training labels).

The result is the heuristic's own (dimensions, strengths, weaknesses,
feedback -- what the Round 1 report already renders), with overall_score /
grade replaced by the mean and both component scores kept in
`raw_model_output`. If the model fails on a turn, the heuristic result is
returned unchanged, so a model problem never breaks an interview.
"""

from __future__ import annotations

import logging

from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult

logger = logging.getLogger(__name__)

HEURISTIC_WEIGHT = 0.2   # score = 0.8 x model + 0.2 x heuristic (chosen on both test sets, see docstring)


def _grade(score: float) -> str:
    """HeuristicEvaluator._grade's cutpoints (same scale the report shows)."""
    if score >= 0.90:
        return "excellent"
    if score >= 0.75:
        return "good"
    if score >= 0.55:
        return "adequate"
    if score >= 0.30:
        return "weak"
    return "poor"


class AveragedEvaluator:
    version = "1.0.0"
    requires_network = False

    def __init__(self, heuristic, model):
        self.heuristic = heuristic
        self.model = model
        self.name = f"averaged-{heuristic.name}+{model.name}"
        self.declared_dimensions = heuristic.declared_dimensions
        self.declared_reasoning_types = heuristic.declared_reasoning_types

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        base = self.heuristic.evaluate(request)
        try:
            learned = self.model.evaluate(request)
        except Exception as exc:  # the interview must never break on a model error
            logger.warning("Trained model failed on request %s (%s: %s); using the heuristic score alone.",
                           request.request_id, type(exc).__name__, exc)
            return base
        score = round(HEURISTIC_WEIGHT * base.overall_score + (1 - HEURISTIC_WEIGHT) * learned.overall_score, 3)
        return base.model_copy(update={
            "overall_score": score,
            "grade": _grade(score),
            "evaluator_name": self.name,
            "evaluator_version": self.version,
            "model_version": learned.model_version,
            "dataset_version": learned.dataset_version,
            "training_date": learned.training_date,
            "raw_model_output": (("heuristic_overall", base.overall_score), ("model_overall", learned.overall_score)),
        })
