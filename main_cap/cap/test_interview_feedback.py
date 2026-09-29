"""Fast, model-free tests for interview_feedback.build_feedback — the honest,
data-driven end-of-session feedback that replaces the fixed frontend templates."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from interview_feedback import build_feedback


def _ev(overall, tc=0.0, depth=0.0, relv=0.0, grnd=0.0):
    return {"overall_score": overall, "grade": "poor", "dimensions": [
        {"name": "technical_correctness", "raw_score": tc},
        {"name": "depth_specificity", "raw_score": depth},
        {"name": "relevance_completeness", "raw_score": relv},
        {"name": "grounding_ownership", "raw_score": grnd},
    ]}


def test_all_idk_feedback_is_accurate_not_generic():
    evals = [_ev(0.1, relv=0.3) for _ in range(10)]  # ten non-substantive turns
    fb = build_feedback(evals)
    assert "weren't really answered" in fb["headline"].lower() or "weren't" in fb["headline"]
    assert "10 of 10" in fb["summary"]
    # It must NOT claim technical claims were inaccurate (there were no claims).
    assert "didn't hold up" not in fb["summary"].lower()
    assert "correctness" in fb["scope_note"].lower()
    assert fb["stats"]["non_substantive"] == 10
    assert fb["stats"]["substantively_answered"] == 0


def test_strong_session_feedback():
    evals = [_ev(0.8, tc=0.8, depth=0.75, relv=0.85, grnd=0.7) for _ in range(8)]
    fb = build_feedback(evals)
    assert "strong" in fb["headline"].lower()
    assert fb["stats"]["strong_answers"] == 8
    assert fb["strengths"]  # names what went well


def test_mixed_session_feedback():
    evals = [_ev(0.8, depth=0.7, relv=0.8, grnd=0.7)] * 3 + [_ev(0.1, relv=0.2)] * 3
    fb = build_feedback(evals)
    assert "mixed" in fb["headline"].lower()
    assert 0 < fb["stats"]["strong_answers"] < fb["stats"]["questions"]


def test_focus_areas_target_weak_dimensions():
    evals = [_ev(0.4, depth=0.1, relv=0.5, grnd=0.5) for _ in range(5)]  # depth is the weak spot
    fb = build_feedback(evals)
    dims = [f["dimension"] for f in fb["focus_areas"]]
    assert "depth_specificity" in dims


def test_empty_session():
    fb = build_feedback([])
    assert fb["stats"]["questions"] == 0
    assert "no answers" in fb["headline"].lower()


def test_feedback_never_asserts_verified_correctness():
    for evals in ([_ev(0.1) for _ in range(4)], [_ev(0.8, tc=0.9, depth=0.8, relv=0.8, grnd=0.8) for _ in range(4)]):
        fb = build_feedback(evals)
        blob = (fb["headline"] + " " + fb["summary"] + " " + fb["scope_note"]).lower()
        assert "verify" in fb["scope_note"].lower() or "does not" in fb["scope_note"].lower()
        assert "technically correct" not in blob and "factually correct" not in blob
