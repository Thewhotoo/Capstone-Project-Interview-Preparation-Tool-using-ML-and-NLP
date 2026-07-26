"""
Deployment Evaluator Bootstrap — wires the trained DeBERTa evaluator
(produced by the experiment/research track, e.g. `run_experiment_2_train_tuned.py`)
into the live application's evaluator registry, with `HeuristicEvaluator` as
the mandatory fallback.

NOT A NEW SUBSYSTEM: reuses `evaluator_registry.register_evaluator`,
`model_evaluator.{TrainedEvaluator, promote_trained_model}`,
`model_checkpoint_io.load_checkpoint_artifact`, `model_backbone.{BackboneConfig,
build_tokenizer}`, and `experiment_dataset_io.load_json` exactly as the
training scripts already use them. No new registration mechanism, no
architecture change, no retraining.

STARTUP ORDER (explicit, deployment decision): the trained evaluator is
attempted FIRST. Only if any part of loading/promoting it fails -- missing
files, a corrupt/mismatched checkpoint, or a `PromotionDecision` that isn't
`approved` -- does the application fall back to instantiating and activating
`HeuristicEvaluator`. This guarantees the trained model is what's actually
serving traffic whenever it's genuinely available, rather than defaulting to
the heuristic and only upgrading opportunistically.

DEPLOYMENT_DIR is a module-level constant, resolved relative to this file's
own location (`os.path.dirname(__file__)`) -- portable across machines/
environments, no hardcoded absolute path. All three expected filenames are
exactly what `run_experiment_2_train_tuned.py`'s `train` phase already
produces in `artifacts/experiment_2_tuned/` -- copy them here unchanged, no
renaming.
"""

from __future__ import annotations

import logging
import os

from evaluator_registry import register_evaluator
from experiment_dataset_io import load_json
from heuristic_evaluator import HeuristicEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact
from model_evaluator import TrainedEvaluator, promote_trained_model
from training_experimentation import Checkpoint, PromotionDecision

logger = logging.getLogger(__name__)

DEPLOYED_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model")
DEPLOYED_WEIGHTS_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint_weights.pt")
DEPLOYED_CHECKPOINT_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint.json")
DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(DEPLOYED_MODEL_DIR, "final_promotion_decision.json")

# Must match the architecture the deployed checkpoint was actually trained
# with (run_experiment_2_train_tuned.py) -- not recoverable from the
# checkpoint metadata itself, so kept as an explicit, documented constant
# here rather than invented/guessed.
_DEPLOYED_BACKBONE_HF_MODEL_ID = "microsoft/deberta-v3-base"
_DEPLOYED_MAX_LENGTH = 128


def bootstrap_production_evaluator() -> None:
    """
    Attempts to load and activate the trained evaluator from
    `DEPLOYED_MODEL_DIR` first. Falls back to activating a fresh
    `HeuristicEvaluator` if any step fails for any reason -- this function
    never raises; a broken/missing deployment checkpoint must never crash
    the application.
    """
    try:
        checkpoint = load_json(Checkpoint, DEPLOYED_CHECKPOINT_PATH)
        decision = load_json(PromotionDecision, DEPLOYED_PROMOTION_DECISION_PATH)

        backbone_config = BackboneConfig(hf_model_id=_DEPLOYED_BACKBONE_HF_MODEL_ID, max_length=_DEPLOYED_MAX_LENGTH)
        tokenizer = build_tokenizer(backbone_config)
        model = load_checkpoint_artifact(DEPLOYED_WEIGHTS_PATH, backbone_config)

        trained_evaluator = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)
        promote_trained_model(checkpoint, decision, trained_evaluator, make_active=True)

        logger.info(
            "Production evaluator ACTIVE: %r (trained checkpoint %r, dataset_version=%r) "
            "loaded from %r and promoted -- promotion decision approved: %s",
            trained_evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
            DEPLOYED_MODEL_DIR, decision.rationale,
        )
    except Exception as exc:
        logger.warning(
            "Could not activate the trained evaluator from %r (%s: %s) -- "
            "falling back to HeuristicEvaluator as the active production evaluator.",
            DEPLOYED_MODEL_DIR, type(exc).__name__, exc,
        )
        fallback = HeuristicEvaluator()
        register_evaluator(fallback, make_active=True)
        logger.info("Production evaluator ACTIVE: %r (HeuristicEvaluator fallback).", fallback.name)
