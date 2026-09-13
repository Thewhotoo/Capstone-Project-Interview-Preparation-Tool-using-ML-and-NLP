"""
Deployment Evaluator Bootstrap — wires the trained DeBERTa evaluator into
the live application's evaluator registry, with `HeuristicEvaluator` as the
mandatory fallback.

A2 CUTOVER (four-dimension migration, final model decision: A2 selected as
the production evaluator after the completed A0/A1/A2 loss-weighting
ablation + B0 architecture ablation + frozen V4 diagnostic benchmark
comparison -- see docs/architecture/V5_Ablation_Design_Review.md,
V6_Experiment_B_Design_Review.md, and the V4-on-A2 inference report).
`DEPLOYED_MODEL_DIR` now points at `deployed_model_a2/` (four canonical
dimensions: technical_correctness, depth_specificity,
relevance_completeness, grounding_ownership; `max_length=256`, matching
A2's own training/inference config exactly -- see
`run_four_dim_training.py`'s `v3_expA2` entry and
`artifacts/v4_diagnostic/a2_inference/`). The PREVIOUS legacy deployment
(`deployed_model/`, the 12-dimension `experiment_4` checkpoint) is left
COMPLETELY UNTOUCHED on disk -- this is a code-level cutover only, so
rollback is a one-line revert of this file's constants (or of the commit
that changed them), never a data-recovery operation. `LEGACY_DEPLOYED_MODEL_DIR`
below documents exactly where that untouched deployment still lives.

A2's architecture is the SAME `MultiTaskModel`/`CoralOrdinalHead` shape as
every other four-dimension experiment (A0/A1/B0) -- `use_private_mlp=False`
(A2 does NOT use B0's private-MLP architecture; that remains a separate,
not-selected experiment). `mlp_hidden_dim`/`mlp_dropout` below are passed
explicitly (not merely relying on `load_checkpoint_artifact`'s own
defaults) purely for architecture-reconstruction clarity/self-documentation
at this call site -- they have no effect while `use_private_mlp=False`.

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

A2-SPECIFIC HYBRID NOTE (deliberate, inspected, not a defect): A2's four
canonical dimension names never match any of `HeuristicEvaluator`'s legacy
dimension names (`technical_accuracy`, `technical_depth`, `communication`,
`completeness`, `resume_grounding`, etc.) -- `hybrid_evaluator.py`'s own
per-dimension `heuristic_by_name.get(t_dim.name)` lookup is `None` for
every one of A2's dimensions on every turn. `HybridEvaluator` already has a
dedicated, pre-existing code path for exactly this ("no overlapping
dimensions to compare", `hybrid_evaluator.py`'s `evaluate()`): the
Dimension Plausibility Guardrail never fires (it requires a non-None
`h_dim`), so A2's `dimensions`/`overall_score`/`grade` pass through
completely UNMODIFIED; `confidence` degrades honestly to
`trained_result.confidence` alone (`confidence_source=ConfidenceSource.MODEL`,
with an explicit rationale string already saying so) instead of a
fabricated agreement score. This was verified by reading
`hybrid_evaluator.py` line-by-line (see the code review that accompanied
this cutover) -- `hybrid_evaluator.py` itself is INTENTIONALLY left
unchanged: no new heuristic-to-canonical dimension mapping was invented,
and no legacy heuristic score is ever allowed to overwrite an A2 score.

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
environments, no hardcoded absolute path.
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
from training_experimentation import Checkpoint, PromotionDecision

logger = logging.getLogger(__name__)

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()

# A2 (four-dimension, canonical) -- the ACTIVE deployment target.
DEPLOYED_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model_a2")
DEPLOYED_WEIGHTS_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint_weights.pt")
DEPLOYED_CHECKPOINT_PATH = os.path.join(DEPLOYED_MODEL_DIR, "best_checkpoint.json")
DEPLOYED_PROMOTION_DECISION_PATH = os.path.join(DEPLOYED_MODEL_DIR, "final_promotion_decision.json")

# Legacy (12-dimension, experiment_4) deployment -- left COMPLETELY
# UNTOUCHED on disk by this cutover, documented here only so rollback is
# discoverable without spelunking git history. Not read by this module's
# bootstrap logic; kept purely as a pointer for a manual rollback decision.
LEGACY_DEPLOYED_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed_model")

# Must match the architecture the deployed checkpoint was actually trained
# with -- not recoverable from the checkpoint metadata itself, so kept as
# explicit, documented constants here rather than invented/guessed. A2's
# values, exactly matching `run_four_dim_training.py`'s `v3_expA2` entry
# and `artifacts/v4_diagnostic/a2_inference/`'s own inference config.
_DEPLOYED_BACKBONE_HF_MODEL_ID = "microsoft/deberta-v3-base"
_DEPLOYED_MAX_LENGTH = 256
# A2 does NOT use B0's private-MLP architecture -- False is A2's real,
# trained value. mlp_hidden_dim/mlp_dropout are passed explicitly below
# purely for architecture-reconstruction self-documentation at the call
# site; they have no effect while use_private_mlp=False.
_DEPLOYED_USE_PRIVATE_MLP = False
_DEPLOYED_MLP_HIDDEN_DIM = 128
_DEPLOYED_MLP_DROPOUT = 0.1


def bootstrap_production_evaluator() -> None:
    """
    Attempts to load the trained evaluator from `DEPLOYED_MODEL_DIR` and
    activate a `HybridEvaluator` wrapping it alongside a fresh
    `HeuristicEvaluator`. Falls back to activating a bare `HeuristicEvaluator`
    if any step fails for any reason -- this function never raises; a
    broken/missing deployment checkpoint must never crash the application.
    """
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
            "Production evaluator ACTIVE: %r (trained checkpoint %r is authoritative for scoring on any "
            "turn it succeeds on; HeuristicEvaluator supplies feedback text, the confidence/disagreement "
            "signal, and is the fallback scorer if the trained model fails; dataset_version=%r, loaded "
            "from %r, promotion decision approved: %s)",
            hybrid_evaluator.name, checkpoint.model_version, checkpoint.dataset_version,
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
