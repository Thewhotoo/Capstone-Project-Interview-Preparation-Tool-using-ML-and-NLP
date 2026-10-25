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
