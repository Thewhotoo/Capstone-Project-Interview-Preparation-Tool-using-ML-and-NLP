# A1-on-V4 Inference (Experiment A, weighted-loss checkpoint)

**Status: read-only inference + analysis. No training, no model/data
modification.** Isolated subdirectory of `artifacts/v4_diagnostic/` — does
not overwrite or modify any A0/V3 artifact in the parent directory.

## Checkpoint provenance

- `main_cap/cap/artifacts/four_dim_training_v3_expA1/best_checkpoint_weights.pt`
  (701.4 MB) + `best_checkpoint.json`, copied in from Colab this session.
- Verified by `../sanity_check_a1_checkpoint.py` (prints to stdout only,
  writes nothing): reproduces the reported A1 real-test-set metrics **exactly**
  (TC 0.2734, Depth 0.8921, Relevance 0.2325, Grounding 0.4983, mean 0.4741 —
  matched to 4 decimal places on the real 27-example `four_dim_experiment_v2`
  test split).
- Checkpoint metadata (`best_checkpoint.json`) confirms `experiment:
  "v3_expA1"`, `loss_weighting: "train_derived_pos_weight"`, and
  `dimension_pos_weights` values matching exactly what
  `loss_weighting.compute_dimension_pos_weights` computes from the real
  train split (`[0.333, 0.333, 0.333, 0.747]` for technical_correctness,
  `[0.333, 0.333, 0.350, 0.711]` for relevance_completeness).
- State dict has the same 4 canonical CORAL head names
  (`technical_correctness`, `depth_specificity`, `relevance_completeness`,
  `grounding_ownership`) and the same 216-key shape as the V3/A0 checkpoint.

## Files

- `run_a1_inference_on_v4.py` — same procedure as `../run_v3_inference_on_v4.py`
  (production `build_dimension_pair`/`grounding_to_text`/`tokenize_pair`/
  `coral_predict`), pointed at the A1 checkpoint. Writes
  `a1_predictions_on_v4.json`.
- `a1_predictions_on_v4.json` — 58 rows, same schema as `../v3_predictions_on_v4.json`.
- `analyze_a1_on_v4.py` — reads `a1_predictions_on_v4.json` and (read-only)
  `../v3_predictions_on_v4.json` to build the A0-vs-A1 comparison. Writes
  `a1_on_v4_report.json`.
- `a1_on_v4_report.json` — aggregate metrics, per-category metrics, 20-group
  pairwise diagnostic, group-by-group A0-vs-A1 comparison, critical-failure
  checks.

## Headline result

Relevance-alignment pair separation on V4: **A0 0/8 correctly separated →
A1 3/8 correctly separated** (1/8 incorrectly ordered, 4/8 still tied).
Relevance aggregate prediction bias: **A0 +0.74 → A1 -0.05** (near-zero).
See the parent conversation's final report for the full A0-vs-A1 analysis,
per-category table, and decision.

## Explicitly NOT done here

No training, no architecture change, no change to `v4_diagnostic_58.jsonl`
or any A0/V3 artifact (both confirmed unchanged by checksum), no V4 label
change, no new V4 examples, nothing committed or pushed.
