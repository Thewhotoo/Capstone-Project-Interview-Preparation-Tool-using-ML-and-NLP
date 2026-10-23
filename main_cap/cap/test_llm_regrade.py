"""Background LLM re-grade (conversation_engine + session_history), model-free:
a fake re-grader stands in for the Ollama-backed evaluator. Covers: nothing is
queued when CAP_FACT_CHECK is off; finished re-grades replace the live scores in
the end-of-session report; unfinished ones keep the live score; saved turns are
updated without losing per-turn extras."""

from __future__ import annotations

import concurrent.futures
import os
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conversation_engine as ce

_ANSWER = ("I put Redis in front of Postgres as a cache-aside layer with a TTL, because the redirect "
           "path was hitting the database on every request and p95 latency was too high.")


class _FakeRegrader:
    def __init__(self, score=0.99, gate: threading.Event | None = None):
        self.score, self.gate, self.calls = score, gate, 0

    def evaluate(self, request):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(120)   # held until the test releases it (generous cap so a failing test can't hang)
        from resume_evidence_evaluator import ResumeEvidenceEvaluator
        fast = ResumeEvidenceEvaluator(scoring="v2").evaluate(request)
        return fast.model_copy(update={"overall_score": self.score, "grade": "excellent"})


def _interview(monkeypatch, enabled: bool, regrader, answers=3):
    import deployment_evaluator
    from experiment_profile_library import all_experiment_profiles
    monkeypatch.setenv("CAP_FACT_CHECK", "1" if enabled else "0")
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(ce, "_get_regrader", lambda: (pool, regrader))
    deployment_evaluator.bootstrap_production_evaluator()
    resp, code = ce.start_conversation(all_experiment_profiles()[0])
    assert code == 200
    cid = resp["conversation_id"]
    live_scores = []
    for _ in range(answers):
        r, _ = ce.advance_conversation(cid, _ANSWER)
        live_scores.append(r["evaluation"]["overall_score"])
    return cid, live_scores


def test_nothing_queued_when_flag_off(monkeypatch):
    fake = _FakeRegrader()
    cid, live = _interview(monkeypatch, enabled=False, regrader=fake)
    summary, _ = ce.end_conversation(cid, wait_for_regrades=True)
    assert fake.calls == 0 and summary["regraded_turns"] == 0
    assert [e["overall_score"] for e in summary["evaluations"]] == live


def test_finished_regrades_replace_live_scores_in_report(monkeypatch):
    fake = _FakeRegrader(score=0.99)
    cid, live = _interview(monkeypatch, enabled=True, regrader=fake)
    assert all(s < 0.99 for s in live)                      # the live flow used the fast score
    summary, _ = ce.end_conversation(cid, wait_for_regrades=True)
    # the same canned answer can be off-topic for a later question (<= 0.10): those are never re-graded
    expected = [0.99 if s > 0.10 else s for s in live]
    assert summary["regraded_turns"] == sum(s > 0.10 for s in live) > 0
    assert [e["overall_score"] for e in summary["evaluations"]] == expected


def test_unfinished_regrades_keep_the_live_score(monkeypatch):
    gate = threading.Event()                                 # re-grades block until released
    try:
        cid, live = _interview(monkeypatch, enabled=True, regrader=_FakeRegrader(gate=gate), answers=2)
        summary, _ = ce.end_conversation(cid, wait_for_regrades=False)
    finally:
        gate.set()
    assert summary["regraded_turns"] == 0
    assert [e["overall_score"] for e in summary["evaluations"]] == live


def test_finished_regrades_are_found_by_another_server(monkeypatch):
    # The re-grade is saved in the live store, so the server that ends the interview
    # (or this one after a restart) uses it without the future that produced it.
    fake = _FakeRegrader(score=0.99)
    cid, live = _interview(monkeypatch, enabled=True, regrader=fake)
    with ce._regrade_futures_lock:
        futures = [f for (c, _), f in ce._regrade_futures.items() if c == cid]
        for key in [k for k in ce._regrade_futures if k[0] == cid]:
            del ce._regrade_futures[key]
    for future in futures:
        future.result(timeout=120)
    ce._cache.drop(cid)                                      # nothing left in this process
    summary, _ = ce.end_conversation(cid, wait_for_regrades=False)
    assert summary["regraded_turns"] == sum(s > 0.10 for s in live) > 0


def test_non_answers_are_not_regraded(monkeypatch):
    fake = _FakeRegrader()
    import deployment_evaluator
    from experiment_profile_library import all_experiment_profiles
    monkeypatch.setenv("CAP_FACT_CHECK", "1")
    monkeypatch.setattr(ce, "_get_regrader", lambda: (concurrent.futures.ThreadPoolExecutor(1), fake))
    deployment_evaluator.bootstrap_production_evaluator()
    cid = ce.start_conversation(all_experiment_profiles()[0])[0]["conversation_id"]
    ce.advance_conversation(cid, "I don't know")
    summary, _ = ce.end_conversation(cid, wait_for_regrades=True)
    assert fake.calls == 0 and summary["regraded_turns"] == 0


def test_saved_turns_take_regraded_scores_and_keep_extras():
    from session_history import _apply_regrades
    turns = [SimpleNamespace(turn_number=1, overall_score=0.5, grade="adequate",
                             evaluation={"overall_score": 0.5, "coaching_note": "keep me"}),
             SimpleNamespace(turn_number=2, overall_score=0.4, grade="weak", evaluation={"overall_score": 0.4})]
    session = SimpleNamespace(turns=turns)
    _apply_regrades(session, [{"overall_score": 0.8, "grade": "good", "reasoning": "llm"},
                              {"overall_score": 0.4, "grade": "weak"}])
    assert (turns[0].overall_score, turns[0].grade) == (0.8, "good")
    assert turns[0].evaluation["coaching_note"] == "keep me" and turns[0].evaluation["llm_regraded"]
    assert turns[1].evaluation == {"overall_score": 0.4}   # unchanged turn untouched


def test_saved_turns_untouched_on_count_mismatch():
    from session_history import _apply_regrades
    turn = SimpleNamespace(turn_number=1, overall_score=0.5, grade="adequate", evaluation={})
    _apply_regrades(SimpleNamespace(turns=[turn]), [{"overall_score": 0.9}, {"overall_score": 0.9}])
    assert turn.overall_score == 0.5
