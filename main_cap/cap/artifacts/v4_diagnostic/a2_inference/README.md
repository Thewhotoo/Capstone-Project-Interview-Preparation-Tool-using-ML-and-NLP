# A2-on-V4 Inference (Experiment A2, smoothed/power-law-dampened loss checkpoint)

**Status: read-only inference + analysis. No training, no model/data
modification.** Isolated subdirectory of `artifacts/v4_diagnostic/` — does
not overwrite or modify any A0/V3/A1 artifact in the parent directory or
`../a1_inference/`.

## Checkpoint provenance

- `main_cap/cap/artifacts/four_dim_training_v3_expA2/best_checkpoint_weights.pt`,
  trained on Colab (best epoch 7), to be copied in before running inference
  locally (not committed to this repo — see "Not committed" below).
- Reported A2 real-test-set metrics (from the Colab training run, the
  `four_dim_experiment_v2` frozen 27-example test split): TC 0.2270, Depth
  0.8920, Relevance 0.2890, Grounding 0.5050, mean QWK 0.4783. Best
  val mean QWK: 0.6372 (epoch 7).
- `sanity_check_a2_checkpoint.py` independently reproduces these numbers
  from the checkpoint before trusting it for V4 inference (prints to
  stdout only, writes nothing) — same methodology as
  `../sanity_check_v3_checkpoint.py` / `../sanity_check_a1_checkpoint.py`.
- Checkpoint metadata (`best_checkpoint.json`) is expected to confirm
  `experiment: "v3_expA2"`, `loss_weighting: "train_derived_pos_weight"`,
  `loss_weight_alpha: 0.4`, and `dimension_pos_weights` matching
  `loss_weighting.A2_ALPHA`-derived values (`[0.3471, 0.3852, 0.4197,
  0.8900]` for technical_correctness, `[0.3333, 0.5006, 0.6568, 0.8726]`
  for relevance_completeness).
- Same 4 canonical CORAL head names (`technical_correctness`,
  `depth_specificity`, `relevance_completeness`, `grounding_ownership`) and
  same architecture shape as the V3/A0/A1 checkpoints -- only the training
  loss weighting differs (see `loss_weighting.py`, `A2_ALPHA = 0.4`).

## Files

- `run_a2_inference_on_v4.py` — same procedure as `../run_v3_inference_on_v4.py`
  and `../a1_inference/run_a1_inference_on_v4.py` (production
  `build_dimension_pair`/`grounding_to_text`/`tokenize_pair`/
  `coral_predict`), pointed at the A2 checkpoint. Writes
  `a2_predictions_on_v4.json`.
- `sanity_check_a2_checkpoint.py` — reproduces the reported A2 test-set QWK
  numbers from the real `four_dim_experiment_v2` test split before trusting
  the checkpoint for V4 inference. Writes nothing.
- `a2_predictions_on_v4.json` — 58 rows, same schema as
  `../v3_predictions_on_v4.json` / `../a1_inference/a1_predictions_on_v4.json`.
  (Produced by running `run_a2_inference_on_v4.py`; not regenerated here
  without the checkpoint present.)
- `analyze_a2_on_v4.py` — reads `a2_predictions_on_v4.json` and (read-only)
  `../v3_predictions_on_v4.json` (A0) and `../a1_inference/a1_predictions_on_v4.json`
  (A1) to build the A0-vs-A1-vs-A2 comparison. Writes `a2_on_v4_report.json`.
- `a2_on_v4_report.json` — aggregate metrics, per-category metrics, 20-group
  pairwise diagnostic (including relevance-alignment pair separation),
  group-by-group A0-vs-A1-vs-A2 comparison, critical-failure checks.
  (Produced by running `analyze_a2_on_v4.py`.)

## Not committed

The 700+ MB checkpoint file itself
(`artifacts/four_dim_training_v3_expA2/best_checkpoint_weights.pt`) is
**not** committed to this repo (same policy as V3/A0/A1's checkpoints) --
it must be present locally (copied from Colab/Drive) before
`run_a2_inference_on_v4.py` or `sanity_check_a2_checkpoint.py` can run.
`a2_predictions_on_v4.json` and `a2_on_v4_report.json` are likewise not
committed in this pass since they require the checkpoint to produce; only
the inference/analysis scripts and this README are committed here so the
workflow can be run in any environment that has the checkpoint.

## How to run (in an environment with the A2 checkpoint present)

```bash
cd main_cap/cap
python artifacts/v4_diagnostic/a2_inference/sanity_check_a2_checkpoint.py
python artifacts/v4_diagnostic/a2_inference/run_a2_inference_on_v4.py
python artifacts/v4_diagnostic/a2_inference/analyze_a2_on_v4.py
```

## Explicitly NOT done here

No training, no architecture change, no change to `v4_diagnostic_58.jsonl`
or any A0/V3/A1 artifact, no V4 label change, no new V4 examples, no
tuning of A2 (or anything else) based on V4 results.
