"""
Startup requirement: the local LLM (Ollama) must be ready before the app serves.

The résumé interview's grading is measurably better with the background LLM
re-grade (see benchmarks/README.md), so running without it is no longer a
silent default. At startup `ensure_llm_ready()`:

  1. returns at once if the LLM was explicitly opted out
     (CAP_ALLOW_NO_LLM=1, or CAP_FACT_CHECK=0);
  2. starts `ollama serve` itself when Ollama is installed but not running;
  3. checks a supported model is pulled (qwen3:4b preferred, qwen2.5:3b also
     accepted; CAP_FACT_CHECK_MODEL picks one explicitly);
  4. warms the model up in the background so the first re-grade isn't slow.

If any of that fails it raises LLMNotReady with a message saying exactly
what to install or run; app.py prints it and exits. Mid-interview, a crashed
Ollama still degrades gracefully (answers keep their fast score) — the
requirement is enforced at startup, not by breaking a live session.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time

from fact_checker import PREFERRED_MODELS, OllamaFactChecker

logger = logging.getLogger(__name__)

SERVER_START_WAIT_SECONDS = 60.0   # a cold start took 12-25+ s on the 4 GB laptop


class LLMNotReady(RuntimeError):
    """Raised when the required local LLM can't be made ready; the message is user-facing."""


def _opted_out() -> bool:
    if os.environ.get("CAP_ALLOW_NO_LLM", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return os.environ.get("CAP_FACT_CHECK", "auto").strip().lower() in ("0", "false", "no", "off")


def _find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidate = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    return candidate if os.path.isfile(candidate) else None


def _start_server(binary: str) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)


def _warm_up(checker: OllamaFactChecker) -> None:
    def run():
        try:
            checker._chat("Reply with JSON only.", 'Return {"score": 1}', 5)
            logger.info("LLM warm-up done (%s)", checker.model)
        except Exception as exc:  # warm-up is a convenience; the re-grade handles its own failures
            logger.info("LLM warm-up skipped: %s", exc)
    threading.Thread(target=run, name="llm-warmup", daemon=True).start()


def ensure_llm_ready(start_server=_start_server, find_ollama=_find_ollama,
                     checker: OllamaFactChecker | None = None, warm_up=_warm_up,
                     wait_seconds: float = SERVER_START_WAIT_SECONDS) -> str | None:
    """Returns the model name in use, or None when the LLM was explicitly opted out.
    Raises LLMNotReady with instructions otherwise."""
    if _opted_out():
        logger.warning("Running WITHOUT the local LLM (CAP_ALLOW_NO_LLM / CAP_FACT_CHECK=0): "
                       "résumé answers get the fast evidence score only.")
        return None
    checker = checker or OllamaFactChecker()
    installed = checker._installed_models(timeout=3.0)
    if installed is None:                                   # server not answering
        binary = find_ollama()
        if binary is None:
            raise LLMNotReady(
                "Ollama is required but isn't installed.\n"
                "  Install it:   winget install Ollama.Ollama   (macOS/Linux: https://ollama.com/download)\n"
                f"  Then run:     ollama pull {PREFERRED_MODELS[0]}\n"
                "  (To run without it anyway, set CAP_ALLOW_NO_LLM=1.)")
        logger.info("Ollama isn't running; starting it (%s serve)...", binary)
        start_server(binary)
        deadline = time.monotonic() + wait_seconds
        while installed is None and time.monotonic() < deadline:
            time.sleep(1.0)
            installed = checker._installed_models(timeout=3.0)
        if installed is None:
            raise LLMNotReady(
                "Ollama is installed but its server didn't start.\n"
                "  Start it yourself:  ollama serve   (or open the Ollama app), then start this app again.")
    if not checker.available():
        wanted = os.environ.get("CAP_FACT_CHECK_MODEL") or " or ".join(PREFERRED_MODELS)
        raise LLMNotReady(
            f"Ollama is running but the model ({wanted}) isn't downloaded.\n"
            f"  Run:  ollama pull {os.environ.get('CAP_FACT_CHECK_MODEL') or PREFERRED_MODELS[0]}\n"
            f"  ({PREFERRED_MODELS[0]} grades best; {PREFERRED_MODELS[-1]} is lighter on memory.)")
    logger.info("Local LLM ready: %s", checker.model)
    warm_up(checker)
    return checker.model
