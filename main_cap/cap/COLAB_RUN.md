# Running the Four-Dimension Training Experiment on Google Colab

This is the canonical entry point for DeBERTa-v3-base four-dimension
training experiments (`run_four_dim_training.py`). It **requires a GPU
runtime** — it deliberately refuses to run on CPU (a real attempt on a
7.5GB-RAM local machine stalled under disk paging).

## Selecting V1 or V2 (Phase 6)

Every command below takes an optional trailing `v1`/`v2` argument:
```
python run_four_dim_training.py --dry-run [v1|v2]
python run_four_dim_training.py train [v1|v2]
```
Omitting it (or passing `v1` explicitly) is the original V1 experiment —
170-example pool, `artifacts/four_dim_experiment_v1/split.json`
(128/20/22), output to `artifacts/four_dim_training_v1/`. Passing `v2`
runs the same architecture/hyperparameters against the 220-example V2
pool, `artifacts/four_dim_experiment_v2/split.json` (166/27/27), output to
`artifacts/four_dim_training_v2/` — a **separate output directory that
never overwrites V1's**. For the V2 run described below, use `train v2`
in step 6.

**You must bring `main_cap/cap/artifacts/four_dim_experiment_v2/split.json`**
(and `main_cap/cap/artifacts/v2_targeted_50/`) too, in addition to
everything V1 needed — see step 3.

## 1. Open Google Colab
https://colab.research.google.com — new notebook.

## 2. Select a GPU runtime
`Runtime` → `Change runtime type` → Hardware accelerator → **GPU** (any
available tier, e.g. T4). Save.

## 3. Clone/open the repository
```
!git clone <your-repo-url> capstone
%cd capstone/main_cap/cap
```
(Or upload the `main_cap/cap/` directory another way — anything that gets
this script's dependencies onto the runtime works. No Google Drive mount is
required; everything this script needs is either already in the repo or
pip-installable.)

**You must bring `main_cap/cap/artifacts/four_dim_experiment_v1/split.json`**
(and the rest of `main_cap/cap/artifacts/`, since `four_dim_experiment_split.load_core_pool()`
also reads `seed_dataset_v1/`, `hand_authored_50/`, and `gap_coverage_20/`) —
`artifacts/` is gitignored, so a plain `git clone` will NOT include it.
Upload that directory alongside the code (zip it locally and use Colab's
file upload, or copy it into your clone after cloning).

## 4. Install requirements
```
!pip install -q "torch>=2.2.0" "transformers>=4.49.0" "pydantic>=2.0"
```
(Matches `Requirements_Global.txt`'s pinned floors; Colab's default PyTorch
is already CUDA-enabled, so no separate CUDA install step is needed.)

## 5. Verify CUDA
```
!python run_four_dim_training.py --dry-run        # V1 check
!python run_four_dim_training.py --dry-run v2      # V2 check
```
This is always safe (never downloads the real model, never trains) — it
prints an environment report (Python/torch/transformers versions, CUDA
availability, GPU name) and confirms the selected experiment's pool +
split load correctly (170/128/20/22 for V1, 220/166/27/27 for V2). Confirm
`cuda_available: true` and a GPU name are reported before continuing. If
`cuda_available: false`, fix the runtime type (step 2) before proceeding —
the next command will refuse to run.

## 6. Run the canonical four-dimension training command
```
!python run_four_dim_training.py train v2
```
(Use `train` with no trailing argument, or `train v1`, for the original V1
run — same command, same architecture, different pool/split/output only.)

This:
1. Fails immediately if CUDA is unavailable (re-checked here too, not just in `--dry-run`).
2. Loads the selected experiment's pool and frozen split (V2: `artifacts/four_dim_experiment_v2/split.json` — 166 train / 27 val / 27 test) and asserts the counts match exactly before proceeding. Never regenerates the split.
3. Asserts 0 source/group leakage across train/val/test as an additional pre-training check (the split was already leakage-validated at construction; this re-confirms it against the actual loaded examples).
4. Builds canonical four-dimension dataloaders (`dimension_names=CANONICAL_DIMENSION_KEYS`).
5. Initializes a **fresh** `microsoft/deberta-v3-base` + `MultiTaskModel(dimension_names=CANONICAL_DIMENSION_KEYS)` — never the V1 checkpoint, never the old 12-dimension checkpoint.
6. Trains for `CONFIG["num_epochs"]` epochs — **identical hyperparameters to V1** (`CONFIG` is shared, unparameterized by experiment; only the pool/split/output/model_version differ), benchmarking every epoch on validation.
7. Selects the best epoch by mean validation QWK across the four dimensions (the untrained epoch-0 point is benchmarked but never eligible for selection).
8. Evaluates the selected checkpoint on the held-out test set — exactly once, after selection.
9. Runs the `TrainedEvaluator` smoke test on 3 real test examples.
10. Writes everything to `artifacts/four_dim_training_v2/` — a directory distinct from V1's, so V1's artifacts are never touched or overwritten.

Expect this to take substantially less time than a CPU run (a synthetic
single-batch timing probe on CPU took ~5–6s/batch at batch_size=4; a T4 GPU
should be roughly one to two orders of magnitude faster per batch).

## 7. Locate the output checkpoint
```
artifacts/four_dim_training_v2/best_checkpoint_weights.pt   # the model weights
artifacts/four_dim_training_v2/best_checkpoint.json          # Checkpoint metadata (model_version, dataset_version, experiment_config)
```
`best_checkpoint.json`'s `model_version` is `deberta_v3_base_four_dim_training_v2_epoch<N>` —
distinguishable from both the V1 checkpoint's `model_version` and the
production/legacy checkpoint's `model_version` by construction.

## 8. Retrieve the metrics/report
```
artifacts/four_dim_training_v2/epoch_curve.json           # per-epoch train/val loss + val metrics for all four dimensions
artifacts/four_dim_training_v2/test_metrics.json          # final held-out test metrics (per-dimension + secondary aggregate)
artifacts/four_dim_training_v2/test_predictions.json      # per-example true/predicted tiers for all four dimensions (qualitative error analysis)
artifacts/four_dim_training_v2/evaluator_smoke_test.json  # TrainedEvaluator end-to-end check on 3 real test examples
```
Copy the whole `artifacts/four_dim_training_v2/` directory back into the
repository (it is gitignored, same convention as every other dataset/model
artifact in this project) to continue the analysis locally. `artifacts/four_dim_training_v1/`
(the V1 run) is untouched and remains available for comparison.

## Do NOT
- Do not modify `artifacts/four_dim_experiment_v1/split.json` or `artifacts/four_dim_experiment_v2/split.json`, or regenerate either split in Colab.
- Do not add TechQA, rewrites, or any example outside the frozen 170 (V1) / approved 220 (V2).
- Do not overwrite `main_cap/cap/deployed_model/` (the production/legacy checkpoint) with either experimental checkpoint.
- Do not overwrite `artifacts/four_dim_training_v1/` with V2 output, or vice versa — they are separate directories by construction; just don't hand-move files between them.
- Do not tune hyperparameters after seeing V2 results without explicit approval for a new experiment.
- Do not commit/push from the Colab session.
