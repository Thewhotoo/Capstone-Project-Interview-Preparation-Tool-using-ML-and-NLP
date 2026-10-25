# deployed_model_a2/ — A2 (four-dimension canonical) production deployment

**Status: this directory is the new active target of
`deployment_evaluator.bootstrap_production_evaluator()`.** The previous
legacy deployment (`../deployed_model/`, the 12-dimension `experiment_4`
checkpoint) is left completely untouched on disk — this is a code-level
cutover, not a data migration. See `deployment_evaluator.py`'s module
docstring for the full rationale.

## Expected files (exactly 3, mirroring `../deployed_model/`'s layout)

1. **`best_checkpoint_weights.pt`** — **NOT YET PRESENT in this local
   environment.** A2 was trained on Colab (per this project's established
   pattern for every four-dimension experiment — see
   `artifacts/four_dim_training_v3_expA2/README.md` /
   `artifacts/v4_diagnostic/a2_inference/README.md`). Copy the real file
   from `artifacts/four_dim_training_v3_expA2/best_checkpoint_weights.pt`
   (produced by `run_four_dim_training.py train v3_expA2` on a GPU-backed
   Colab runtime) into this directory, unrenamed, before
   `bootstrap_production_evaluator()` can actually activate A2.

2. **`best_checkpoint.json`** — **NOT YET PRESENT** for the same reason.
   Copy the real file from
   `artifacts/four_dim_training_v3_expA2/best_checkpoint.json`, unrenamed
   and unmodified. This repo does not fabricate a substitute for this file
   — its `experiment_config.parameters` (`dimension_pos_weights`, the
   exact Colab `environment` report, `artifact_uri`, `created_at`, etc.)
   are real training-run provenance that only the actual Colab run
   produced; inventing plausible-looking values for them here would
   misrepresent real experiment data, so this step is intentionally left
   as a manual copy-in rather than synthesized.

3. **`final_promotion_decision.json`** — **PRESENT**, authored this
   session using the real `training_experimentation.PromotionDecision`
   Pydantic model (via `experiment_dataset_io.save_json`, the same
   serialization the legacy deployment's file used) — schema-correct, not
   hand-typed JSON. `approved=True`, `checkpoint_model_version=
   "deberta_v3_base_four_dim_training_v3_expA2_epoch7"` (the exact
   `model_version` string `run_four_dim_training.py`'s `train()` produces
   for A2's real best epoch, 7 — deterministic from that code, not a
   guess). The `rationale` is a **manual, human promotion decision**, not
   an automated `run_benchmark`/`decide_promotion` threshold check —
   that mechanism scores a single legacy `overall_label.grade` and
   structurally does not apply to the four-dimension per-dimension
   ordinal scheme (`run_four_dim_training.py`'s own module docstring says
   so explicitly: "`run_benchmark`/`decide_promotion` are NOT reused").
   The rationale cites A2's real, previously-reported metrics (val/test
   mean QWK, per-dimension QWK, V4 pair-separation counts vs. A0/A1) —
   every number in it was reported earlier in this project's own session
   history, not invented here.

## Until file 1 and file 2 are copied in

`bootstrap_production_evaluator()` will fail at `load_json(Checkpoint,
DEPLOYED_CHECKPOINT_PATH)` (file not found) and fall back to activating a
bare `HeuristicEvaluator` — the same safe, documented, never-crashes
degradation path this module has always had for a missing/broken
deployment. This is expected, verified behavior (see
`test_deployment_evaluator.py::TestBootstrapFallback` and the new A2
cutover tests in `test_deployment_evaluator_a2.py`), not a bug.

## Architecture this checkpoint must have been trained with

- `microsoft/deberta-v3-base`, `max_length=256`
- Four canonical dimensions (`evaluation_dimensions.all_keys()`):
  `technical_correctness`, `depth_specificity`, `relevance_completeness`,
  `grounding_ownership`
- `use_private_mlp=False` (A2 does NOT use B0's private-MLP architecture)
- CORAL ordinal heads, 5 classes (0–4), unchanged `CoralOrdinalHead`
- Trained with A2's smoothed loss weighting (`loss_weighting.A2_ALPHA =
  0.4`, on `technical_correctness`/`relevance_completeness` only) — this
  is a TRAINING-time-only detail; `load_checkpoint_artifact`/
  `TrainedEvaluator` never re-apply loss weighting at inference, they only
  load the resulting trained weights.

If the real checkpoint file does not match this architecture exactly,
`model.load_state_dict(state_dict)` in `model_checkpoint_io.
load_checkpoint_artifact` will raise a `RuntimeError` (strict mode) —
loudly, not silently — which `bootstrap_production_evaluator()`'s
try/except will catch and degrade to the `HeuristicEvaluator` fallback,
logged as a warning.
