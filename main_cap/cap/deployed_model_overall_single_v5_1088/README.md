# deployed_model_overall_single_v5_1088/ — v5_1088 production deployment (Tier 1)

**Status: the PRIMARY deployment target.** `deployment_evaluator.
bootstrap_production_evaluator()` attempts to load THIS directory first.
`../deployed_model_overall_single_v3/` (the previous Tier 1) is now the
Tier-2 rollback, `../deployed_model_a2/` is Tier 3, and a bare
`HeuristicEvaluator` is the unconditional Tier-4 fallback — see
`deployment_evaluator.py`'s module docstring for the exact four-tier order
and rationale. Neither v3, A2, nor the legacy `../deployed_model/`
deployment is modified, moved, or deleted by this cutover — all three
remain byte-for-byte exactly as they were, fully reachable rollback paths.

## Expected files (exactly 3, mirroring `../deployed_model_overall_single_v3/`'s layout)

1. **`best_checkpoint_weights.pt`** — copy, unrenamed, extracted from the
   `overall_single_v5_1088.zip` Colab download (produced by
   `colab_training/train_overall_v5.py train` on a GPU-backed Colab
   runtime). **Real Colab-trained weights only — never fabricated locally.**

2. **`best_checkpoint.json`** — copy, unrenamed and unmodified, extracted
   from the same zip. Real training-run provenance
   (`experiment_config.parameters`, `created_at`, `artifact_uri`,
   `model_version="deberta_v3_base_overall_single_v5_1088_epoch8"`,
   `dataset_version="overall_v5_1088"`) — never synthesized here.

3. **`final_promotion_decision.json`** — authored via the real
   `training_experimentation.PromotionDecision` Pydantic model
   (`experiment_dataset_io.save_json`, same serialization every other
   deployment's promotion file uses). `approved=True`,
   `checkpoint_model_version="deberta_v3_base_overall_single_v5_1088_epoch8"`.
   Manual human promotion decision citing the real, reported training-run
   metrics: validation QWK 0.8643, test QWK 0.8529, test accuracy 0.6225,
   test within-1 accuracy 0.9735, test MAE 0.4040 (n=151, the SAME 151
   `example_id`s as v3's own test split).

## Dataset this checkpoint was trained on

`overall_v5_1088` — the frozen, audited 1,003-example `four_dim_overall_v4_5000`
dataset (702/150/151 split, unmodified, untouched) with the 85-example
`v5_short_quality_calibration_80` calibration set appended to **TRAIN ONLY**
(787/150/151 total). The 151-example test split and 150-example validation
split are byte-identical `example_id`s to the baseline split used to train
`deberta_v3_base_overall_single_v3_epoch6` and the intermediate (never
deployed) `deberta_v3_base_overall_single_v4_1003_epoch7` — see
`build_v5_1088_pool.py` and `colab_training/dataset_loader_v5.py` for the
merge rule and the integrity checks that guarantee this. Result: the
old-vs-new comparison on the 151-example test set is apples-to-apples.

## Architecture this checkpoint must have been trained with

- `microsoft/deberta-v3-base`, `max_length=256`
- **ONE** shared `CoralOrdinalHead` (`overall_score_model.OverallScoreModel`)
  predicting a single overall ordinal 0–4 score — NOT
  `model_heads.MultiTaskModel`'s per-dimension `DimensionOrdinalHeads` shape.
  `deployment_evaluator.py` reconstructs this exact architecture via
  `overall_score_model.load_overall_checkpoint_artifact` — never
  `model_checkpoint_io.load_checkpoint_artifact`.
- Training target: the deterministic equal-weight mean of the four
  canonical dimension labels (`overall_dataset.py`'s documented policy),
  binned into the same 5-tier ordinal scale — no new policy invented.
- Unweighted CORAL loss (no A1/A2 `pos_weight` loss weighting).
- Seed 42, learning rate 2e-5, batch size 8, 8 epochs, AdamW, weight decay
  0.01, no scheduler, default DeBERTa dropout (0.1) — identical
  hyperparameters to v3 and v4_1003; dataset composition was the only
  variable changed for this experiment.

## The four DIAGNOSTIC dimensions shown alongside this score

`overall_single_evaluator.OverallSingleEvaluator` pairs this learned
overall score with `heuristic_diagnostics.HeuristicDiagnosticsEngine` — a
fully deterministic, model-free engine producing exactly
`technical_correctness`/`depth_specificity`/`relevance_completeness`/
`grounding_ownership`. These are DIAGNOSTIC ONLY:
- never fed into the DeBERTa forward pass (the model's own input is built
  from `question_text`/grounding/`expected_concepts`/`answer_text` alone —
  see `overall_single_evaluator.evaluate()`),
- never able to overwrite `overall_score`/`grade` (every diagnostic
  `DimensionScore` is constructed with `contributes_to_overall=False`, and
  the evaluator never recomputes `overall_score` from them).

## Rollback

If this directory's checkpoint fails to load for any reason (missing file,
corrupt state dict, unapproved promotion decision), `bootstrap_production_evaluator()`
falls back to `../deployed_model_overall_single_v3/` (Tier 2), then
`../deployed_model_a2/` (Tier 3), then a bare `HeuristicEvaluator` (Tier 4) —
the same documented, tested, never-crashes degrade path this module has
always had. `activate_a2_rollback()` remains available as an explicit,
standalone way to force A2 (or heuristic-only) live without attempting
either single-overall-score tier at all.
