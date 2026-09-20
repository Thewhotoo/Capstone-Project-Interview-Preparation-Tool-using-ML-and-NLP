"""
Deployment Evaluator Bootstrap — wires the production evaluator into the
live application's evaluator registry, with a four-tier fallback chain
that never crashes the application.

V5_1088 CUTOVER (this session, additive): the PRIMARY deployment target is
now `deployed_model_overall_single_v5_1088/` -- the SAME
`overall_single_evaluator.OverallSingleEvaluator` architecture v3 already
used (ONE shared `CoralOrdinalHead` via `overall_score_model.
OverallScoreModel` predicting a single learned overall 0-4 score, paired
with `heuristic_diagnostics.HeuristicDiagnosticsEngine`'s four fully
deterministic DIAGNOSTIC dimensions -- technical_correctness,
depth_specificity, relevance_completeness, grounding_ownership -- see
`overall_single_evaluator.py`'s module docstring for the full architecture
and the enforced "heuristics never touch overall_score" guarantee), just
trained on a larger dataset (`overall_v5_1088`: the frozen 1003-example
`four_dim_overall_v4_5000` set + 85 `v5_short_quality_calibration_80`
examples appended to train only -- see
`deployed_model_overall_single_v5_1088/README.md`). v3 (the PREVIOUS Tier
1) is now the Tier-2 rollback -- `_try_activate_overall_single_v3()` below
is unchanged, only its position in the chain moved.

FOUR-TIER FALLBACK CHAIN (explicit deployment decision, in priority order):
  1. `deployed_model_overall_single_v5_1088/` -- the new evaluator, tried first.
  2. `deployed_model_overall_single_v3/` -- the PREVIOUS primary tier, tried
     if and only if step 1 fails for any reason. Nothing about its own
     loading/wiring logic changed; still the same, fully intact evaluator.
  3. `deployed_model_a2/` -- the four-dimension A2 evaluator
     (`HybridEvaluator`-wrapped), tried if and only if steps 1-2 fail. This
     is A2's explicit, always-reachable ROLLBACK PATH -- nothing about A2's
     own loading/wiring logic changed; `_try_activate_a2()` below is
     unchanged.
  4. A bare `HeuristicEvaluator` -- tried if and only if steps 1-3 fail.
     Always succeeds; this is the same, unconditional final fallback this
     module has always had.
`activate_a2_rollback()` (below) additionally exposes tier 3+4 as a
STANDALONE, directly callable function -- an explicit way to force A2 (or
heuristic-only) live without going through either single-overall-score tier
at all, for a manual rollback decision, without needing to touch
`deployed_model_overall_single_v5_1088/` or `deployed_model_overall_single_v3/`
on disk.

Neither `deployed_model_overall_single_v3/`, `deployed_model_a2/`, nor
`deployed_model/` (the legacy 12-dimension `experiment_4` checkpoint) is
modified, moved, or deleted by this cutover -- all three remain byte-for-
byte exactly as they were. `LEGACY_DEPLOYED_MODEL_DIR` documents where the
legacy deployment still lives (not read by this module's bootstrap logic,
kept purely as a rollback pointer).

ARCHITECTURE MISMATCH, HANDLED DELIBERATELY: both single-overall-score
tiers' checkpoints are `overall_score_model.OverallScoreModel` (one shared
`CoralOrdinalHead`), NOT `model_heads.MultiTaskModel`'s per-dimension
`DimensionOrdinalHeads` shape A2/the legacy deployment use -- so both are
loaded via `overall_score_model.load_overall_checkpoint_artifact`, never
`model_checkpoint_io.load_checkpoint_artifact` (that function's
reconstructed architecture would not match this checkpoint's state dict).
`OverallSingleEvaluator` is registered DIRECTLY (not wrapped in
`HybridEvaluator`) -- it already carries its own, internal, non-overwriting
heuristic diagnostics (see its module docstring); `HybridEvaluator`'s
dimension-reconciliation/guardrail machinery is specific to pairing
`HeuristicEvaluator` with `model_evaluator.TrainedEvaluator` and is neither
needed nor applicable here. No new heuristic-to-canonical-dimension mapping
is invented anywhere in this file.

NOT A NEW SUBSYSTEM: reuses `evaluator_registry.register_evaluator`
directly (duck-typed against the `Evaluator` Protocol -- `OverallSingleEvaluator`
already satisfies it, so no `promote_trained_model`-style glue is needed
for it), `overall_score_model.load_overall_checkpoint_artifact`,
`model_checkpoint_io.load_checkpoint_artifact` (still used for A2's tier),
`model_backbone.{BackboneConfig, build_tokenizer}`, and
`experiment_dataset_io.load_json` exactly as the training scripts already
use them.

DEPLOYMENT_DIR constants are resolved relative to this file's own location
(`os.path.dirname(__file__)`) -- portable across machines/environments, no
hardcoded absolute path.
"""

from __future__ import annotations

import logging
import os

from evaluation_dimensions import all_keys as canonical_dimension_keys
from evaluator_registry import register_evaluator
from experiment_dataset_io import load_json
from heuristic_evaluator import HeuristicEvaluator
from hybrid_evaluator import HybridEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact
from model_evaluator import TrainedEvaluator, promote_trained_model
from overall_score_model import load_overall_checkpoint_artifact
from overall_single_evaluator import OverallSingleEvaluator
from training_experimentation import Checkpoint, PromotionDecision

logger = logging.getLogger(__name__)

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()

# ── Tier 1: v5_1088 single-overall-score -- the PRIMARY deployment target ───
DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088 = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "deployed_model_overall_single_v5_1088",
)
_OVERALL_SINGLE_V5_1088_WEIGHTS_PATH = os.path.join(
    DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088, "best_checkpoint_weights.pt",
)
_OVERALL_SINGLE_V5_1088_CHECKPOINT_PATH = os.path.join(
    DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088, "best_checkpoint.json",
)
_OVERALL_SINGLE_V5_1088_PROMOTION_DECISION_PATH = os.path.join(
    DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088, "final_promotion_decision.json",
)
# Must match the architecture the deployed checkpoint was actually trained
# with -- not recoverable from the checkpoint metadata itself. Matches
# colab_training/train_overall_v5.py's CONFIG exactly (identical to v3's).
_OVERALL_SINGLE_V5_1088_BACKBONE_HF_MODEL_ID = "microsoft/deberta-v3-base"
_OVERALL_SINGLE_V5_1088_MAX_LENGTH = 256

# ── Tier 2: v3 single-overall-score -- the PREVIOUS primary, now the first
# rollback tier ──────────────────────────────────────────────────────────
DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3 = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "deployed_model_overall_single_v3",
)
_OVERALL_SINGLE_V3_WEIGHTS_PATH = os.path.join(DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, "best_checkpoint_weights.pt")
_OVERALL_SINGLE_V3_CHECKPOINT_PATH = os.path.join(DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, "best_checkpoint.json")
_OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH = os.path.join(
    DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, "final_promotion_decision.json",
)
# Must match the architecture the deployed checkpoint was actually trained
# with -- not recoverable from the checkpoint metadata itself. Matches
# run_overall_single_training.py's CONFIG exactly.
_OVERALL_SINGLE_V3_BACKBONE_HF_MODEL_ID = "microsoft/deberta-v3-base"
_OVERALL_SINGLE_V3_MAX_LENGTH = 256

# ── Tier 3: A2 (four-dimension, canonical) -- the ROLLBACK deployment target ─
DEPLOYED_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model_a2")
DEPLOYED_WEIGHTS_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint_weights.pt")
DEPLOYED_CHECKPOINT_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint.json")
DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(DEPLOYED_MODEL_DIR, "final_promotion_decision.json")

# Legacy (12-dimension, experiment_4) deployment -- left COMPLETELY
# UNTOUCHED on disk by this cutover, documented here only so rollback is
# discoverable without spelunking git history. Not read by this module's
# bootstrap logic; kept purely as a pointer for a manual rollback decision.
LEGACY_DEPLOYED_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model")

# A2's own architecture constants -- unchanged from before this session.
_DEPLOYED_BACKBONE_HF_MODEL_ID = "microsoft/deberta-v3-base"
_DEPLOYED_MAX_LENGTH = 256
# A2 does NOT use B0's private-MLP architecture -- False is A2's real,
# trained value. mlp_hidden_dim/mlp_dropout are passed explicitly below
# purely for architecture-reconstruction self-documentation at the call
# site; they have no effect while use_private_mlp=False.
_DEPLOYED_USE_PRIVATE_MLP = False
_DEPLOYED_MLP_HIDDEN_DIM = 128
_DEPLOYED_MLP_DROPOUT = 0.1


def _try_activate_overall_single_v5_1088() -> bool:
    """Tier 1. Returns True and makes `OverallSingleEvaluator` active
    (backed by the v5_1088 checkpoint) iff every step succeeds; returns
    False (making NO registry change) on any failure -- missing files, a
    corrupt/mismatched checkpoint, or a `PromotionDecision` that isn't
    `approved`. Never raises. Identical logic to
    `_try_activate_overall_single_v3()`, just pointed at the new checkpoint
    directory/constants -- no behavioral change to how a single-overall-
    score checkpoint is loaded or registered."""
    try:
        checkpoint = load_json(Checkpoint, _OVERALL_SINGLE_V5_1088_CHECKPOINT_PATH)
        decision = load_json(PromotionDecision, _OVERALL_SINGLE_V5_1088_PROMOTION_DECISION_PATH)
        if not decision.approved:
            raise ValueError(f"promotion decision was not approved ({decision.rationale})")

        backbone_config = BackboneConfig(
            hf_model_id=_OVERALL_SINGLE_V5_1088_BACKBONE_HF_MODEL_ID, max_length=_OVERALL_SINGLE_V5_1088_MAX_LENGTH,
        )
        tokenizer = build_tokenizer(backbone_config)
        model = load_overall_checkpoint_artifact(_OVERALL_SINGLE_V5_1088_WEIGHTS_PATH, backbone_config)

        evaluator = OverallSingleEvaluator(checkpoint, model, tokenizer, backbone_config)
        # Registered directly -- OverallSingleEvaluator already satisfies
        # the Evaluator Protocol on its own (duck-typed), no HybridEvaluator
        # wrapping and no promote_trained_model glue needed (that helper is
        # scoped to model_evaluator.TrainedEvaluator's own promotion path).
        register_evaluator(evaluator, make_active=True)

        logger.info(
            "Production evaluator ACTIVE: %r (learned single-overall-score checkpoint %r is authoritative "
            "for overall_score/grade; heuristic diagnostics supply the four canonical dimension scores "
            "shown alongside it and can never overwrite overall_score; dataset_version=%r, loaded from "
            "%r, promotion decision approved: %s)",
            evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
            DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088, decision.rationale,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not activate the v5_1088 single-overall-score evaluator from %r (%s: %s) -- "
            "falling back to v3 (deployed_model_overall_single_v3/).",
            DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V5_1088, type(exc).__name__, exc,
        )
        return False


def _try_activate_overall_single_v3() -> bool:
    """Tier 2 / v3 rollback. Returns True and makes `OverallSingleEvaluator`
    active (backed by the v3 checkpoint) iff every step succeeds; returns
    False (making NO registry change) on any failure -- missing files, a
    corrupt/mismatched checkpoint, or a `PromotionDecision` that isn't
    `approved`. Never raises. Unchanged from before the v5_1088 cutover --
    only its position in `bootstrap_production_evaluator()`'s chain moved."""
    try:
        checkpoint = load_json(Checkpoint, _OVERALL_SINGLE_V3_CHECKPOINT_PATH)
        decision = load_json(PromotionDecision, _OVERALL_SINGLE_V3_PROMOTION_DECISION_PATH)
        if not decision.approved:
            raise ValueError(f"promotion decision was not approved ({decision.rationale})")

        backbone_config = BackboneConfig(
            hf_model_id=_OVERALL_SINGLE_V3_BACKBONE_HF_MODEL_ID, max_length=_OVERALL_SINGLE_V3_MAX_LENGTH,
        )
        tokenizer = build_tokenizer(backbone_config)
        model = load_overall_checkpoint_artifact(_OVERALL_SINGLE_V3_WEIGHTS_PATH, backbone_config)

        evaluator = OverallSingleEvaluator(checkpoint, model, tokenizer, backbone_config)
        # Registered directly -- OverallSingleEvaluator already satisfies
        # the Evaluator Protocol on its own (duck-typed), no HybridEvaluator
        # wrapping and no promote_trained_model glue needed (that helper is
        # scoped to model_evaluator.TrainedEvaluator's own promotion path).
        register_evaluator(evaluator, make_active=True)

        logger.info(
            "Production evaluator ACTIVE: %r (learned single-overall-score checkpoint %r is authoritative "
            "for overall_score/grade; heuristic diagnostics supply the four canonical dimension scores "
            "shown alongside it and can never overwrite overall_score; dataset_version=%r, loaded from "
            "%r, promotion decision approved: %s)",
            evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
            DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, decision.rationale,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not activate the v3 single-overall-score evaluator from %r (%s: %s) -- "
            "falling back to A2 (deployed_model_a2/).",
            DEPLOYED_MODEL_DIR_OVERALL_SINGLE_V3, type(exc).__name__, exc,
        )
        return False


def _try_activate_a2() -> bool:
    """Tier 3 / A2 rollback. Identical logic to this module's pre-V3-cutover
    `bootstrap_production_evaluator()` body -- unchanged, just factored into
    its own function so it can serve as an explicit rollback tier. Returns
    True and makes the A2 `HybridEvaluator` active iff every step succeeds;
    returns False on any failure. Never raises."""
    try:
        checkpoint = load_json(Checkpoint, DEPLOYED_CHECKPOINT_PATH)
        decision = load_json(PromotionDecision, DEPLOYED_PROMOTION_DECISION_PATH)

        backbone_config = BackboneConfig(hf_model_id=_DEPLOYED_BACKBONE_HF_MODEL_ID, max_length=_DEPLOYED_MAX_LENGTH)
        tokenizer = build_tokenizer(backbone_config)
        model = load_checkpoint_artifact(
            DEPLOYED_WEIGHTS_PATH, backbone_config,
            dimension_names=CANONICAL_DIMENSION_KEYS,
            use_private_mlp=_DEPLOYED_USE_PRIVATE_MLP,
            mlp_hidden_dim=_DEPLOYED_MLP_HIDDEN_DIM,
            mlp_dropout=_DEPLOYED_MLP_DROPOUT,
        )

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
            "Production evaluator ACTIVE: %r (A2 rollback tier -- trained checkpoint %r is authoritative "
            "for scoring on any turn it succeeds on; HeuristicEvaluator supplies feedback text, the "
            "confidence/disagreement signal, and is the fallback scorer if the trained model fails; "
            "dataset_version=%r, loaded from %r, promotion decision approved: %s)",
            hybrid_evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
            DEPLOYED_MODEL_DIR, decision.rationale,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not activate the A2 trained evaluator from %r (%s: %s) -- "
            "falling back to HeuristicEvaluator as the active production evaluator.",
            DEPLOYED_MODEL_DIR, type(exc).__name__, exc,
        )
        return False


def _activate_heuristic_fallback() -> None:
    """Tier 4. Always succeeds -- the final, unconditional fallback."""
    fallback = HeuristicEvaluator()
    register_evaluator(fallback, make_active=True)
    logger.info("Production evaluator ACTIVE: %r (HeuristicEvaluator fallback).", fallback.name)


def bootstrap_production_evaluator() -> None:
    """
    Tries the four-tier fallback chain in order (see module docstring):
    v5_1088 single-overall-score -> v3 single-overall-score -> A2 -> bare
    HeuristicEvaluator. This function never raises; a broken/missing
    deployment at any tier must never crash the application.
    """
    if _try_activate_overall_single_v5_1088():
        return
    if _try_activate_overall_single_v3():
        return
    if _try_activate_a2():
        return
    _activate_heuristic_fallback()


def activate_a2_rollback() -> None:
    """
    Explicit, standalone rollback entry point: activates A2 (or, if A2
    itself is unavailable, the bare `HeuristicEvaluator`) WITHOUT
    attempting either single-overall-score tier at all -- callable directly
    by an operator/ops script to force a rollback decision, independent of
    whatever is or isn't present on disk at
    `deployed_model_overall_single_v5_1088/` or `deployed_model_overall_single_v3/`.
    Never raises.
    """
    if _try_activate_a2():
        return
    _activate_heuristic_fallback()
