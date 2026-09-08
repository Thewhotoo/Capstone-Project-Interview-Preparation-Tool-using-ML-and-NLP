# Running the Four-Dimension Training Experiment on Google Colab

This is the canonical entry point for the first real DeBERTa-v3-base
four-dimension training experiment (`run_four_dim_training.py`). It
**requires a GPU runtime** — it deliberately refuses to run on CPU (a real
attempt on a 7.5GB-RAM local machine stalled under disk paging).

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
!python run_four_dim_training.py --dry-run
```
This is always safe (never downloads the real model, never trains) — it
prints an environment report (Python/torch/transformers versions, CUDA
availability, GPU name) and confirms the frozen 170-example pool + split
load correctly. Confirm `cuda_available: true` and a GPU name are reported
before continuing. If `cuda_available: false`, fix the runtime type (step 2)
before proceeding — the next command will refuse to run.

## 6. Run the canonical four-dimension training command
```
!python run_four_dim_training.py train
```
This:
1. Fails immediately if CUDA is unavailable (re-checked here too, not just in `--dry-run`).
2. Loads the frozen 170-example pool and the frozen split (`artifacts/four_dim_experiment_v1/split.json` — 128 train / 20 val / 22 test). Never regenerates it.
3. Builds canonical four-dimension dataloaders (`dimension_names=CANONICAL_DIMENSION_KEYS`).
4. Initializes a **fresh** `microsoft/deberta-v3-base` + `MultiTaskModel(dimension_names=CANONICAL_DIMENSION_KEYS)` — never the old 12-dimension checkpoint.
5. Trains for `CONFIG["num_epochs"]` epochs (see the script's `CONFIG` dict for the full, recorded hyperparameter set), benchmarking every epoch on validation.
6. Selects the best epoch by mean validation QWK across the four dimensions (the untrained epoch-0 point is benchmarked but never eligible for selection).
7. Evaluates the selected checkpoint on the held-out test set — exactly once, after selection.
8. Runs the `TrainedEvaluator` smoke test on 3 real test examples.
9. Writes everything to `artifacts/four_dim_training_v1/`.

Expect this to take substantially less time than a CPU run (a synthetic
single-batch timing probe on CPU took ~5–6s/batch at batch_size=4; a T4 GPU
should be roughly one to two orders of magnitude faster per batch).

## 7. Locate the output checkpoint
```
artifacts/four_dim_training_v1/best_checkpoint_weights.pt   # the model weights
artifacts/four_dim_training_v1/best_checkpoint.json          # Checkpoint metadata (model_version, dataset_version, experiment_config)
```
`best_checkpoint.json`'s `model_version` is `deberta_v3_base_four_dim_training_v1_epoch<N>` —
distinguishable from the production/legacy checkpoint's own `model_version`
by construction.

## 8. Retrieve the metrics/report
```
artifacts/four_dim_training_v1/epoch_curve.json           # per-epoch train/val loss + val metrics for all four dimensions
artifacts/four_dim_training_v1/test_metrics.json          # final held-out test metrics (per-dimension + secondary aggregate)
artifacts/four_dim_training_v1/test_predictions.json      # per-example true/predicted tiers for all four dimensions (qualitative error analysis)
artifacts/four_dim_training_v1/evaluator_smoke_test.json  # TrainedEvaluator end-to-end check on 3 real test examples
```
Copy the whole `artifacts/four_dim_training_v1/` directory back into the
repository (it is gitignored, same convention as every other dataset/model
artifact in this project) to continue the analysis locally.

## Do NOT
- Do not modify `artifacts/four_dim_experiment_v1/split.json` or regenerate the split in Colab.
- Do not add TechQA, rewrites, or any example outside the frozen 170.
- Do not overwrite `main_cap/cap/deployed_model/` (the production/legacy checkpoint) with this experimental checkpoint.
- Do not commit/push from the Colab session.
