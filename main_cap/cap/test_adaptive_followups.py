"""Tests for adaptive follow-up probing (conversation_engine).

The trigger decision is unit-tested model-free. The end-to-end behavior is
exercised against the live evaluator: a weak-but-real answer draws a deeper
probe when the feature is ON and never when it's OFF, follow-ups stay within the
question budget, no more than MAX_FOLLOWUPS_PER_PROJECT probes per topic, and no
more than MAX_FOLLOWUPS_PER_SESSION probes in total.
Default-off (all existing behavior) is covered by test_conversation_engine.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conversation_engine as ce
from conversation_engine import (
    MAX_FOLLOWUPS_PER_PROJECT,
    MAX_FOLLOWUPS_PER_SESSION,
    RESUME_DISCUSSION_QUESTION_BUDGET,
    _answer_warrants_followup,
)


# ── trigger decision (model-free) ────────────────────────────────────────────

def test_warrants_followup_only_for_weak_but_real():
    assert _answer_warrants_followup(SimpleNamespace(overall_score=0.30))   # weak-but-real → probe
    assert _answer_warrants_followup(SimpleNamespace(overall_score=0.50))
    assert not _answer_warrants_followup(SimpleNamespace(overall_score=0.75))  # strong → move on
    assert not _answer_warrants_followup(SimpleNamespace(overall_score=0.60))  # good boundary → move on
    assert not _answer_warrants_followup(SimpleNamespace(overall_score=0.10))  # gated non-answer → don't badger
    assert not _answer_warrants_followup(SimpleNamespace(overall_score=0.0))


# ── end-to-end (uses the live evaluator, like the app) ───────────────────────

_WEAK_ANSWER = ("I used React and Node with a Postgres database, and I set up the main API "
                "endpoints and the auth flow for it.")


def _run_interview(enable: bool):
    import deployment_evaluator
    deployment_evaluator.bootstrap_production_evaluator()
    from experiment_profile_library import all_experiment_profiles
    profile = all_experiment_profiles()[0]
    resp, code = ce.start_conversation(profile, enable_adaptive_followups=enable)
    assert code == 200
    cid = resp["conversation_id"]
    turns = []
    for _ in range(RESUME_DISCUSSION_QUESTION_BUDGET + 5):
        r, _c = ce.advance_conversation(cid, _WEAK_ANSWER)
        nq = r.get("next_question") or {}
        turns.append(bool(nq.get("is_followup")))
        if r.get("is_completed") or r.get("next_question") is None:
            break
    return turns


def test_followups_on_only_when_enabled_and_within_budget():
    off = _run_interview(enable=False)
    on = _run_interview(enable=True)
    off_followups = sum(off)
    on_followups = sum(on)
    assert off_followups == 0                      # feature off → never probes
    assert on_followups >= 1                        # feature on → probes weak answers
    assert on_followups > off_followups             # the flag is what causes it
    assert on_followups <= MAX_FOLLOWUPS_PER_SESSION  # session cap holds
    assert len(on) <= RESUME_DISCUSSION_QUESTION_BUDGET   # budget still respected


def test_no_two_consecutive_followups():
    # A probe is always followed by a non-probe turn (the next topic or
    # completion), never a second probe back-to-back: MAX_FOLLOWUPS_PER_PROJECT == 1
    # means a project is never probed twice in a row, and every probe leaves the
    # spec un-advanced so the very next turn answers it (a non-probe).
    on = _run_interview(enable=True)
    assert MAX_FOLLOWUPS_PER_PROJECT == 1
    assert not any(on[i] and on[i + 1] for i in range(len(on) - 1))
