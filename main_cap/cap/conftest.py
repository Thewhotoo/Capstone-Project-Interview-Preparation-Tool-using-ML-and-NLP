"""Shared pytest setup for main_cap/cap.

The résumé interview re-grades answers with a local LLM when Ollama is running
(CAP_FACT_CHECK defaults to "auto"). Tests must not depend on whether Ollama
happens to be up on the machine running them, so it is off by default here;
tests of the re-grade itself set CAP_FACT_CHECK explicitly (monkeypatch).
The same goes for the technical interview's LLM re-grade (CAP_TECH_LLM_GRADE).
"""

import os

os.environ.setdefault("CAP_FACT_CHECK", "0")
os.environ.setdefault("CAP_TECH_LLM_GRADE", "0")


import pytest


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """Every test logs in from the same address, so failed-login counts (account_routes'
    rate limit) would add up across tests; start each test with none."""
    yield
    from live_store import get_store
    store = get_store()
    data = getattr(store, "_data", None)
    if isinstance(data, dict):
        for key in [k for k in data if k.startswith("loginfail:")]:
            data.pop(key, None)
