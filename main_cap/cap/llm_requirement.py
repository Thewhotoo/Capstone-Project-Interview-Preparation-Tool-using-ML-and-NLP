"""
Startup requirement: the local LLM (Ollama + a qwen model) must be ready before the app serves.

The résumé interview's grading is measurably better with the background LLM
re-grade (see benchmarks/README.md), so by default the LLM is required, like the
packages in requirements.txt; the one-time setup (`python install.py` at the
repository root) installs it. Machines that can't run it (no GPU, little memory)
can start without it with CAP_ALLOW_NO_LLM=1: interviews then use the fast scores
only (less accurate final reports), exactly as when Ollama stops mid-interview.

At startup `ensure_llm_ready()`:
  1. starts `ollama serve` itself when Ollama is installed but not running;
  2. checks a supported model is pulled (qwen3:8b preferred, then qwen3:4b, then
     qwen2.5:3b; CAP_FACT_CHECK_MODEL picks one explicitly);
  3. warms the model up in the background so the first re-grade isn't slow.

If any of that fails it raises LLMNotReady with a message saying exactly what
to install or run; app.py and serve.py (Docker) print it and exit. When Ollama
is on another machine (CAP_OLLAMA_URL, e.g. the Docker host) it isn't started
from here, only checked. (If Ollama crashes in the middle
of an interview, that session finishes with the fast score instead of failing;
the next app start requires the LLM again.)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse

from fact_checker import PREFERRED_MODELS, OllamaFactChecker

logger = logging.getLogger(__name__)

SERVER_START_WAIT_SECONDS = 60.0   # a cold start took 12-25+ s on the 4 GB laptop
SETUP_HINT = "Run the one-time setup from the repository root:  python install.py"


class LLMNotReady(RuntimeError):
    """Raised when the required local LLM can't be made ready; the message is user-facing."""


def _is_on_this_machine(url: str) -> bool:
    return urlparse(url).hostname in ("localhost", "127.0.0.1", "::1")


def find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidate = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    return candidate if os.path.isfile(candidate) else None


def start_server(binary: str) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)


def wait_for_server(checker: OllamaFactChecker, wait_seconds: float) -> set[str] | None:
    """Installed model names once the server answers, or None if it doesn't within the wait."""
    deadline = time.monotonic() + wait_seconds
    installed = checker._installed_models(timeout=3.0)
    while installed is None and time.monotonic() < deadline:
        time.sleep(1.0)
        installed = checker._installed_models(timeout=3.0)
    return installed


def _warm_up(checker: OllamaFactChecker) -> None:
    def run():
        try:
            checker._chat("Reply with JSON only.", 'Return {"score": 1}', 5)
            logger.info("LLM warm-up done (%s)", checker.model)
        except Exception as exc:  # warm-up is a convenience; the re-grade handles its own failures
            logger.info("LLM warm-up skipped: %s", exc)
    threading.Thread(target=run, name="llm-warmup", daemon=True).start()


def ensure_llm_ready(start_server=start_server, find_ollama=find_ollama,
                     checker: OllamaFactChecker | None = None, warm_up=_warm_up,
                     wait_seconds: float = SERVER_START_WAIT_SECONDS) -> str:
    """Returns the model name in use (None when started without the LLM by CAP_ALLOW_NO_LLM=1);
    raises LLMNotReady with instructions otherwise."""
    if os.environ.get("CAP_ALLOW_NO_LLM", "").strip().lower() in ("1", "true", "yes", "on"):
        logger.warning("Starting WITHOUT the local LLM (CAP_ALLOW_NO_LLM=1): final reports use the "
                       "fast scores only and are less accurate. %s", SETUP_HINT)
        return None
    checker = checker or OllamaFactChecker()
    installed = checker._installed_models(timeout=3.0)
    if installed is None and not _is_on_this_machine(checker.base_url):
        # e.g. Docker: Ollama runs on the host, which this process can't start.
        raise LLMNotReady(
            f"Ollama is required but isn't reachable at {checker.base_url}.\n"
            f"  Install and start it on the host computer, then pull the model:  ollama pull {PREFERRED_MODELS[0]}\n"
            f"  (or {PREFERRED_MODELS[1]} on a GPU with less than 8 GB)  ({SETUP_HINT} --skip-pip)\n"
            f"  To start without it (fast scores only): set CAP_ALLOW_NO_LLM=1")
    if installed is None:                                   # server not answering
        binary = find_ollama()
        if binary is None:
            raise LLMNotReady(f"Ollama is required but isn't installed.\n  {SETUP_HINT}\n"
                              "  To start without it (fast scores only): set CAP_ALLOW_NO_LLM=1")
        logger.info("Ollama isn't running; starting it (%s serve)...", binary)
        start_server(binary)
        installed = wait_for_server(checker, wait_seconds)
        if installed is None:
            raise LLMNotReady(
                "Ollama is installed but its server didn't start.\n"
                "  Start it yourself:  ollama serve   (or open the Ollama app), then start this app again.")
    if not checker.available():
        wanted = os.environ.get("CAP_FACT_CHECK_MODEL") or PREFERRED_MODELS[0]
        raise LLMNotReady(
            f"Ollama is running but the {wanted} model isn't downloaded.\n"
            f"  {SETUP_HINT}\n  (or download just the model:  ollama pull {wanted}, or {PREFERRED_MODELS[1]}\n"
            f"  on a GPU with less than 8 GB)\n  To start without it (fast scores only): set CAP_ALLOW_NO_LLM=1")
    logger.info("Local LLM ready: %s", checker.model)
    warm_up(checker)
    return checker.model
