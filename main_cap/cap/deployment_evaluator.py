"""
Deployment Evaluator Bootstrap — wires the trained DeBERTa evaluator
(produced by the experiment/research track, e.g. `run_experiment_2_train_tuned.py`)
into the live application's evaluator registry, with `HeuristicEvaluator` as
the mandatory fallback.

HYBRID WIRING (Round 3 -- DeBERTa-primary, see hybrid_evaluator.py's module
docstring for the full rationale/evaluation numbers): when the trained
checkpoint loads and is promotion-approved, it is NOT registered as the
active evaluator directly. It's registered under its own name (inspectable,
available for a future direct rollout) and wrapped in a `HybridEvaluator`
alongside a fresh `HeuristicEvaluator` -- the HybridEvaluator is what
actually goes active. The trained model is now AUTHORITATIVE for scoring
(dimensions/overall_score/grade) whenever it produces a valid result on a
given turn; HeuristicEvaluator supplies feedback text (strengths/
weaknesses/missing_reasoning/etc.), the confidence/disagreement signal, and
is the fallback scorer ONLY when the trained model fails on that turn. If
the trained checkpoint isn't available at all, the fallback path is
unchanged: a bare HeuristicEvaluator, exactly as before this wiring
existed.

NOT A NEW SUBSYSTEM: reuses `evaluator_registry.register_evaluator`,
`model_evaluator.{TrainedEvaluator, promote_trained_model}`,
`model_checkpoint_io.load_checkpoint_artifact`, `model_backbone.{BackboneConfig,
build_tokenizer}`, and `experiment_dataset_io.load_json` exactly as the
training scripts already use them. No new registration mechanism, no
architecture change, no retraining.

STARTUP ORDER (explicit, deployment decision): loading the trained
evaluator is attempted FIRST. Only if any part of loading/promoting it
fails -- missing files, a corrupt/mismatched checkpoint, or a
`PromotionDecision` that isn't `approved` -- does the application fall back
to a bare `HeuristicEvaluator`. This guarantees the trained model
genuinely participates (via the HybridEvaluator) whenever it's available,
rather than defaulting to heuristic-only and upgrading opportunistically.

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
from hybrid_evaluator import HybridEvaluator
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


# ── Tier 1: the averaged evaluator (heuristic + a teammate's DeBERTa-v3 model,
# `overall_single_v5_1088`; resumeParser_integration.md step 5). The weights
# file (735 MB, git-ignored) must be placed in this folder by hand; without it
# bootstrap falls through to the tiers below exactly as before.
# CAP_TRAINED_EVALUATOR=0 skips it (e.g. a laptop short on memory).
OVERALL_V5_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model_overall_single_v5_1088")
_OVERALL_V5_WEIGHTS = os.path.join(OVERALL_V5_DIR, "best_checkpoint_weights.pt")
_OVERALL_V5_CHECKPOINT = os.path.join(OVERALL_V5_DIR, "best_checkpoint.json")
_OVERALL_V5_DECISION = os.path.join(OVERALL_V5_DIR, "final_promotion_decision.json")
_OVERALL_V5_BACKBONE = "microsoft/deberta-v3-base"   # must match how it was trained
_OVERALL_V5_MAX_LENGTH = 256


def _try_activate_averaged_v5() -> bool:
    """Registers AveragedEvaluator(HeuristicEvaluator, OverallSingleEvaluator)
    as active and returns True, or returns False with NO registry change on
    any problem (disabled, files missing, not approved, load error). Never raises."""
    if os.environ.get("CAP_TRAINED_EVALUATOR", "1").strip().lower() in ("0", "false", "no", "off"):
        logger.info("CAP_TRAINED_EVALUATOR=0: skipping the trained v5_1088 model.")
        return False
    missing = [os.path.basename(p) for p in (_OVERALL_V5_WEIGHTS, _OVERALL_V5_CHECKPOINT, _OVERALL_V5_DECISION)
               if not os.path.exists(p)]
    if missing or os.path.getsize(_OVERALL_V5_WEIGHTS) < 1_000_000:   # an un-pulled git-LFS pointer is ~130 bytes
        logger.info("Trained v5_1088 model not available in %r (%s); using the next evaluator tier.",
                    OVERALL_V5_DIR, ", ".join(missing) or "weights file is a git-LFS pointer, not the model")
        return False
    try:
        from averaged_evaluator import AveragedEvaluator
        from overall_score_model import load_overall_checkpoint_artifact
        from overall_single_evaluator import OverallSingleEvaluator

        checkpoint = load_json(Checkpoint, _OVERALL_V5_CHECKPOINT)
        decision = load_json(PromotionDecision, _OVERALL_V5_DECISION)
        if not decision.approved:
            raise ValueError(f"promotion decision not approved ({decision.rationale})")
        backbone_config = BackboneConfig(hf_model_id=_OVERALL_V5_BACKBONE, max_length=_OVERALL_V5_MAX_LENGTH)
        tokenizer = build_tokenizer(backbone_config)
        model = load_overall_checkpoint_artifact(_OVERALL_V5_WEIGHTS, backbone_config)
        averaged = AveragedEvaluator(HeuristicEvaluator(), OverallSingleEvaluator(checkpoint, model, tokenizer, backbone_config))
        register_evaluator(averaged, make_active=True)
        logger.info("Production evaluator ACTIVE: %r (mean of heuristic-v1 and the trained model %r, "
                    "dataset %r; heuristic supplies feedback and dimensions).",
                    averaged.name, checkpoint.model_version, checkpoint.dataset_version)
        return True
    except Exception as exc:
        logger.warning("Could not activate the trained v5_1088 model from %r (%s: %s); using the next tier.",
                       OVERALL_V5_DIR, type(exc).__name__, exc)
        return False


def _activate_heuristic_fallback(reason: str) -> None:
    logger.warning(
        "Could not activate the trained evaluator from %r (%s) -- "
        "falling back to HeuristicEvaluator as the active production evaluator.",
        DEPLOYED_MODEL_DIR, reason,
    )
    fallback = HeuristicEvaluator()
    register_evaluator(fallback, make_active=True)
    logger.info("Production evaluator ACTIVE: %r (HeuristicEvaluator fallback).", fallback.name)


def bootstrap_production_evaluator() -> None:
    """
    Attempts to load the trained evaluator from `DEPLOYED_MODEL_DIR` and
    activate a `HybridEvaluator` wrapping it alongside a fresh
    `HeuristicEvaluator`. Falls back to activating a bare `HeuristicEvaluator`
    if any step fails for any reason -- this function never raises; a
    broken/missing deployment checkpoint must never crash the application.

    The cheap checks (all three files present, promotion approved) run
    before anything heavy: building the tokenizer and model downloads/loads
    the ~700 MB pretrained backbone, which is pointless when the weights file
    isn't there -- the normal state of a fresh clone, since `*.pt` is
    git-ignored.

    Tier 1 (tried first): the averaged evaluator, if the v5_1088 model is
    installed (`_try_activate_averaged_v5`).
    """
    if _try_activate_averaged_v5():
        return
    missing = [
        os.path.basename(path)
        for path in (DEPLOYED_CHECKPOINT_PATH, DEPLOYED_PROMOTION_DECISION_PATH, DEPLOYED_WEIGHTS_PATH)
        if not os.path.exists(path)
    ]
    if missing:
        _activate_heuristic_fallback(f"missing {', '.join(missing)}; the model was not loaded")
        return

    try:
        checkpoint = load_json(Checkpoint, DEPLOYED_CHECKPOINT_PATH)
        decision = load_json(PromotionDecision, DEPLOYED_PROMOTION_DECISION_PATH)
        if not decision.approved:
            _activate_heuristic_fallback(
                f"promotion decision for {decision.checkpoint_model_version!r} is not approved; "
                "the model was not loaded"
            )
            return

        backbone_config = BackboneConfig(hf_model_id=_DEPLOYED_BACKBONE_HF_MODEL_ID, max_length=_DEPLOYED_MAX_LENGTH)
        tokenizer = build_tokenizer(backbone_config)
        model = load_checkpoint_artifact(DEPLOYED_WEIGHTS_PATH, backbone_config)

        trained_evaluator = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)
        # Registers + validates the promotion decision (raises if not
        # approved), but does NOT make the trained evaluator active on its
        # own -- it's registered under its own name only, so it stays
        # directly inspectable/available, while the HybridEvaluator below
        # is what actually serves traffic.
        promote_trained_model(checkpoint, decision, trained_evaluator, make_active=False)

        hybrid_evaluator = HybridEvaluator(HeuristicEvaluator(), trained_evaluator)
        register_evaluator(hybrid_evaluator, make_active=True)

        logger.info(
            "Production evaluator ACTIVE: %r (trained checkpoint %r is authoritative for scoring on any "
            "turn it succeeds on; HeuristicEvaluator supplies feedback text, the confidence/disagreement "
            "signal, and is the fallback scorer if the trained model fails; dataset_version=%r, loaded "
            "from %r, promotion decision approved: %s)",
            hybrid_evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
            DEPLOYED_MODEL_DIR, decision.rationale,
        )
    except Exception as exc:
        _activate_heuristic_fallback(f"{type(exc).__name__}: {exc}")
