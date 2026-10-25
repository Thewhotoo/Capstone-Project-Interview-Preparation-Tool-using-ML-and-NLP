# B0-on-V4 Inference (Experiment B0, private per-dimension MLP architecture)

**Status: read-only inference + analysis. No training, no model/data
modification.** Isolated subdirectory of `artifacts/v4_diagnostic/` — does
not overwrite or modify any A0/V3/A1/A2 artifact in the parent directory
or `../a1_inference/`/`../a2_inference/`.

## Checkpoint provenance

- `main_cap/cap/artifacts/four_dim_training_v3_expB0/best_checkpoint_weights.pt`,
  trained on Colab. **Best epoch: 6** (selected by validation mean QWK on
  the frozen `four_dim_experiment_v2` split, never by V4 — V4 is
  strictly downstream diagnostic-only, per the V6 Ablation Design Review
  §17).
- Architecture: `use_private_mlp=True`, `mlp_hidden_dim=128`,
  `mlp_dropout=0.1` — each of the four canonical dimensions
  (`technical_correctness`, `depth_specificity`, `relevance_completeness`,
  `grounding_ownership`) gets its own private
  `Linear(768→128) → GELU → Dropout(0.1)` projection
  (`model_heads.DimensionPrivateProjection`) inserted between the shared
  DeBERTa pooled representation and its (architecturally unchanged)
  `CoralOrdinalHead`. See `model_heads.py` and
  `docs/architecture/V6_Experiment_B_Design_Review.md` for the full design
  rationale.
- Loss weighting: **unweighted A0 loss** (`loss_weighting="none"`,
  identical to `v3_expA0`) — B0's primary comparison is A0-vs-B0
  (architecture is the ONLY variable). B0 does **not** combine with A1/A2's
  loss weighting; that remains explicitly out of scope for this experiment
  (V6 review §10, §20).
- `sanity_check_b0_checkpoint.py` verifies, against the real checkpoint
  file (not a synthetic stand-in):
  1. it loads successfully with `use_private_mlp=True` (the architecture it
     was trained with), and every dimension's `CoralOrdinalHead` was
     constructed with `in_features=128` as expected;
  2. loading the SAME file with `use_private_mlp=False` (the wrong
     architecture) fails loudly with a `RuntimeError` (strict
     `load_state_dict` shape mismatch) rather than silently loading wrong
     weights;
  3. reproduces real QWK numbers on the frozen `four_dim_experiment_v2`
     test split (printed to stdout — no target numbers are hardcoded/
     asserted here, since none were given ahead of running this check
     against the real checkpoint; this script reports what the checkpoint
     actually does).
- Same 4 canonical CORAL head names and same overall shape as the V3/A0/
  A1/A2 checkpoints, except `CoralOrdinalHead`'s `in_features` (128 instead
  of 768) and the added `dimension_heads.projections.*` parameters — see
  `model_heads.DimensionOrdinalHeads`'s docstring.

## Files

- `run_b0_inference_on_v4.py` — same procedure as `../run_v3_inference_on_v4.py`,
  `../a1_inference/run_a1_inference_on_v4.py`, and
  `../a2_inference/run_a2_inference_on_v4.py` (production
  `build_dimension_pair`/`grounding_to_text`/`tokenize_pair`/
  `coral_predict`, tokenizer, `max_length=256`), pointed at the B0
  checkpoint with the three architecture flags
  (`use_private_mlp=True, mlp_hidden_dim=128, mlp_dropout=0.1`) required to
  reconstruct it before `load_state_dict`. Writes
  `b0_predictions_on_v4.json`.
- `sanity_check_b0_checkpoint.py` — verifies correct-architecture loading,
  wrong-architecture hard-failure, and reproduces real test-set QWK numbers
  before trusting the checkpoint for V4 inference. Writes nothing.
- `b0_predictions_on_v4.json` — 58 rows, same schema as
  `../v3_predictions_on_v4.json` / `../a1_inference/a1_predictions_on_v4.json`
  / `../a2_inference/a2_predictions_on_v4.json`. (Produced by running
  `run_b0_inference_on_v4.py`; not regenerated here without the checkpoint
  present.)
- `analyze_b0_on_v4.py` — reads `b0_predictions_on_v4.json` and (read-only)
  `../v3_predictions_on_v4.json` (A0, required), plus
  `../a1_inference/a1_predictions_on_v4.json` /
  `../a2_inference/a2_predictions_on_v4.json` (A1/A2, included for
  reference when present) to build the A0-vs-B0 primary comparison and the
  A0/A1/A2/B0 reference table. Writes `b0_on_v4_report.json`.
- `b0_on_v4_report.json` — aggregate metrics, per-category metrics,
  20-group pairwise diagnostic (including relevance-alignment pair
  separation), group-by-group A0-vs-A1-vs-A2-vs-B0 comparison,
  critical-failure checks. (Produced by running `analyze_b0_on_v4.py`.)

## Primary comparison

**A0 vs. B0** — both use the exact same unweighted CORAL loss, same V2
220-example pool, same frozen 166/27/27 split, same seed/hyperparameters;
the ONLY difference is architecture (no private MLP vs. private MLP). This
isolates whether giving each dimension private representational capacity
improves V4's relevance-alignment pair separation, per the V6 review's
hypothesis. A1/A2 results are carried through for reference only, to show
what loss weighting alone achieved on the same benchmark — not as a
combined B0+weighting result (that remains explicitly out of scope).

## Not committed

The 700+ MB checkpoint file itself
(`artifacts/four_dim_training_v3_expB0/best_checkpoint_weights.pt`) is
**not** committed to this repo (same policy as V3/A0/A1/A2's checkpoints)
— it must be present locally (copied from Colab/Drive) before
`run_b0_inference_on_v4.py` or `sanity_check_b0_checkpoint.py` can run.
`b0_predictions_on_v4.json` and `b0_on_v4_report.json` are likewise not
committed in this pass since they require the checkpoint to produce; only
the inference/analysis scripts and this README are committed here so the
workflow can be run in any environment that has the checkpoint.

## How to run (in an environment with the B0 checkpoint present)

```bash
cd main_cap/cap
python artifacts/v4_diagnostic/b0_inference/sanity_check_b0_checkpoint.py   # confirms correct-architecture load, wrong-architecture hard failure, real test QWKs
python artifacts/v4_diagnostic/b0_inference/run_b0_inference_on_v4.py       # writes b0_predictions_on_v4.json (58 rows)
python artifacts/v4_diagnostic/b0_inference/analyze_b0_on_v4.py            # writes b0_on_v4_report.json
```

## Explicitly NOT done here

No training, no architecture change beyond what B0 was already approved
and implemented with, no change to `v4_diagnostic_58.jsonl` or any
A0/V3/A1/A2 artifact, no V4 label change, no new V4 examples, no tuning of
B0 (or anything else) based on V4, no combination with A1/A2 loss
weighting.
