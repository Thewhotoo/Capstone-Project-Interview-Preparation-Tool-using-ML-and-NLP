# deployed_model_overall_single_v3/ — V3 single-overall-score production deployment

**Status: an isolated, opt-in deployment target.** `deployment_evaluator.
bootstrap_production_evaluator()` attempts to load THIS directory first;
A2 (`../deployed_model_a2/`) is the explicit, always-available rollback if
loading here fails for any reason — see `deployment_evaluator.py`'s module
docstring for the exact fallback order and rationale. The legacy
`../deployed_model/` (12-dimension `experiment_4`) deployment is left
completely untouched, exactly as it was left untouched by the A2 cutover.

## Expected files (exactly 3, mirroring `../deployed_model_a2/`'s layout)

1. **`best_checkpoint_weights.pt`** — copy, unrenamed, from
   `artifacts/overall_single_v3/best_checkpoint_weights.pt` (produced by
   `run_overall_single_training.py train v3_overall_single` on a
   GPU-backed Colab runtime). **Real Colab-trained weights only — never
   fabricated locally.**

2. **`best_checkpoint.json`** — copy, unrenamed and unmodified, from
   `artifacts/overall_single_v3/best_checkpoint.json`. Real training-run
   provenance (`experiment_config.parameters`, `created_at`,
   `artifact_uri`, `model_version="deberta_v3_base_overall_single_v3_epoch6"`)
   — never synthesized here.

3. **`final_promotion_decision.json`** — **PRESENT**, authored via the real
   `training_experimentation.PromotionDecision` Pydantic model
   (`experiment_dataset_io.save_json`, same serialization every other
   deployment's promotion file uses). `approved=True`,
   `checkpoint_model_version="deberta_v3_base_overall_single_v3_epoch6"`
   (the exact `model_version` string `run_overall_single_training.py`
   produces for the real best epoch, 6). Manual human promotion decision
   citing the real, reported training-run metrics: validation QWK 0.7111,
   test QWK 0.6667, test accuracy 0.5185, test within-1 accuracy 0.9259,
   test MAE 0.5556.

## Architecture this checkpoint must have been trained with

- `microsoft/deberta-v3-base`, `max_length=256`
- **ONE** shared `CoralOrdinalHead` (`overall_score_model.OverallScoreModel`)
  predicting a single overall ordinal 0–4 score — NOT
  `model_heads.MultiTaskModel`'s per-dimension `DimensionOrdinalHeads`
  shape. `deployment_evaluator.py` reconstructs this exact architecture
  via `overall_score_model.load_overall_checkpoint_artifact` — never
  `model_checkpoint_io.load_checkpoint_artifact` (that function is typed
  to `MultiTaskModel`'s shape and would fail/mismatch against this
  checkpoint).
- Training target: the deterministic equal-weight mean of the four
  canonical dimension labels (`overall_dataset.py`'s documented policy),
  binned into the same 5-tier ordinal scale — see that module's docstring
  for the exact, existing-policy derivation (no new policy invented).
- Unweighted CORAL loss (no A1/A2 `pos_weight` loss weighting).

## The four DIAGNOSTIC dimensions shown alongside this score

`overall_single_evaluator.OverallSingleEvaluator` pairs this learned
overall score with `heuristic_diagnostics.HeuristicDiagnosticsEngine` —
a fully deterministic, model-free engine producing exactly
`technical_correctness`/`depth_specificity`/`relevance_completeness`/
`grounding_ownership`. These are DIAGNOSTIC ONLY:
- never fed into the DeBERTa forward pass (the model's own input is built
  from `question_text`/grounding/`expected_concepts`/`answer_text` alone —
  see `overall_single_evaluator.evaluate()`),
- never able to overwrite `overall_score`/`grade` (every diagnostic
  `DimensionScore` is constructed with `contributes_to_overall=False`, and
  the evaluator never recomputes `overall_score` from them — no
  weighted-dimension-average step exists in this evaluator at all, unlike
  `TrainedEvaluator`/`HeuristicEvaluator`).

## Until files 1 and 2 are copied in

`bootstrap_production_evaluator()` will fail at the checkpoint JSON/weights
load for THIS directory and fall back to A2 (`../deployed_model_a2/`), and
only fall further back to the bare `HeuristicEvaluator` if A2 itself is
unavailable too — the same documented, tested, never-crashes degrade path
this module has always had. This is expected behavior, not a bug.
