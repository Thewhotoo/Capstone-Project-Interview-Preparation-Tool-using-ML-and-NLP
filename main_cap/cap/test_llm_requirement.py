"""Startup requirement for the local LLM (llm_requirement.ensure_llm_ready), model-free:
a fake checker stands in for Ollama. Covers: no opt-out, ready, auto-starting the
server, not installed, server that won't start, and model not downloaded."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import llm_requirement
from llm_requirement import LLMNotReady, ensure_llm_ready


class _FakeChecker:
    def __init__(self, installed_sequence, available=True, model="qwen3:4b"):
        self._seq = list(installed_sequence)   # successive _installed_models() results
        self._available, self.model = available, model

    def _installed_models(self, timeout):
        return self._seq.pop(0) if len(self._seq) > 1 else self._seq[0]

    def available(self, timeout=2.0):
        return self._available


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(llm_requirement.time, "sleep", lambda s: None)


def _ready(**overrides):
    kwargs = dict(start_server=lambda b: None, find_ollama=lambda: "ollama", warm_up=lambda c: None, wait_seconds=0.05)
    kwargs.update(overrides)
    return ensure_llm_ready(**kwargs)


def test_there_is_no_opt_out(monkeypatch):
    monkeypatch.setenv("CAP_ALLOW_NO_LLM", "1")      # the old switch does nothing now
    monkeypatch.setenv("CAP_FACT_CHECK", "0")
    with pytest.raises(LLMNotReady, match="install.py"):
        _ready(checker=_FakeChecker([None]), find_ollama=lambda: None)


def test_ready_returns_the_model_and_warms_it():
    warmed = []
    assert _ready(checker=_FakeChecker([{"qwen3:4b"}]), warm_up=warmed.append) == "qwen3:4b"
    assert len(warmed) == 1


def test_starts_the_server_when_installed_but_not_running():
    started = []
    model = _ready(checker=_FakeChecker([None, {"qwen3:4b"}]), start_server=started.append, wait_seconds=5)
    assert started == ["ollama"] and model == "qwen3:4b"


def test_not_installed_explains_how_to_install():
    with pytest.raises(LLMNotReady, match="isn't installed"):
        _ready(checker=_FakeChecker([None]), find_ollama=lambda: None)


def test_server_that_never_comes_up_explains_what_to_do():
    with pytest.raises(LLMNotReady, match="didn't start"):
        _ready(checker=_FakeChecker([None]))


def test_missing_model_says_which_to_pull():
    with pytest.raises(LLMNotReady, match="isn't downloaded"):
        _ready(checker=_FakeChecker([{"llama3:8b"}], available=False))
