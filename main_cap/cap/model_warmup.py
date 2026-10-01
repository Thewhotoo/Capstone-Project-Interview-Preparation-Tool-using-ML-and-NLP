"""
Faster startup and no first-request stalls for the app's local AI models.

Two things, both called from app.py:

  use_local_models_only()   BEFORE anything imports huggingface_hub /
      sentence_transformers. When every model the app needs is already in the
      local Hugging Face cache, sets HF_HUB_OFFLINE=1 so loading a model does
      not first ask huggingface.co whether a newer version exists. Measured:
      all models 47 s -> 9 s at startup (each check is a network round-trip of
      several seconds). On a machine where a model is still missing (a fresh
      clone) nothing changes: the models download on first use as before, and
      the next start is fast. An explicit HF_HUB_OFFLINE in the environment
      is always respected.

  start_background_warmup()  loads every model in a background thread right
      after startup, so the first resume upload / Round 1 answer / technical
      answer doesn't wait for one (up to ~17 s before). Requests that arrive
      during warm-up simply load what they need themselves, as before.
      CAP_MODEL_WARMUP=0 disables it (tests do).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Every Hugging Face model a normal request can load (the trained backbone only
# when its weights exist -- see deployment_evaluator.py).
REQUIRED_MODELS = (
    "sentence-transformers/all-MiniLM-L6-v2",   # Round 1 evaluator, resume parsing, tech grader
    "cross-encoder/nli-MiniLM2-L6-H768",        # Round 1 evaluator
    "cross-encoder/nli-deberta-v3-base",        # tech grader
)
# The trained Round 1 evaluator's backbone (tokenizer + architecture), needed only
# when its weights file is installed. Without this, a machine that first ran the app
# without the weights and added them later would go offline with the backbone never
# downloaded, and Round 1 would silently fall back to the heuristic evaluator.
TRAINED_BACKBONE = "microsoft/deberta-v3-base"
TRAINED_WEIGHTS = (Path(__file__).resolve().parent / "deployed_model_overall_single_v5_1088"
                   / "best_checkpoint_weights.pt")


def required_models() -> tuple[str, ...]:
    return REQUIRED_MODELS + ((TRAINED_BACKBONE,) if TRAINED_WEIGHTS.exists() else ())


def _hub_cache_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _is_cached(repo_id: str) -> bool:
    snapshots = _hub_cache_dir() / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    return any((s / "config.json").exists() for s in snapshots.glob("*")) if snapshots.exists() else False


def use_local_models_only() -> bool:
    """Returns True if offline mode was switched on."""
    if "HF_HUB_OFFLINE" in os.environ:
        return os.environ["HF_HUB_OFFLINE"] not in ("", "0", "false", "False")
    missing = [m for m in required_models() if not _is_cached(m)]
    if missing:
        logger.info("Models not downloaded yet (%s): they will download on first use.", ", ".join(missing))
        return False
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    logger.info("All models are cached locally: loading them without checking huggingface.co.")
    return True


def _warm() -> None:
    t0 = time.time()
    steps = []

    def step(name, fn):
        t = time.time()
        try:
            fn()
            steps.append(f"{name} {time.time() - t:.1f}s")
        except Exception as exc:     # warm-up must never break the app
            logger.warning("Model warm-up: %s failed: %s", name, exc)

    import heuristic_evaluator
    from resume_engine import sections
    from resume_engine.parsers import project_parser
    from tech_interview import grader
    from tech_interview.bank import load_bank

    step("round1-embed", heuristic_evaluator._LazyModels.semantic)
    step("round1-nli", heuristic_evaluator._LazyModels.nli)
    step("resume-sections", sections._LazySemanticModel.get)
    step("resume-keybert", project_parser._LazyKeyBERT.get)
    step("question-bank", load_bank)

    def tech_grader():
        grader._LazyModels.embedder()
        grader._LazyModels.nli()
        bank = load_bank()
        if bank:   # one real call: the first inference on a model is slower (GPU/CPU kernels)
            grader.grade_answer(bank[0], "warm-up answer so the first real one is fast")

    step("tech-grader", tech_grader)
    logger.info("Model warm-up done in %.1fs (%s)", time.time() - t0, ", ".join(steps))


def start_background_warmup() -> threading.Thread | None:
    if os.environ.get("CAP_MODEL_WARMUP", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    thread = threading.Thread(target=_warm, name="model-warmup", daemon=True)
    thread.start()
    return thread
