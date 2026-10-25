# colab_training — v4_1003 single-overall DeBERTa training package

Trains the **same architecture** (`microsoft/deberta-v3-base` + one shared
`CoralOrdinalHead`, `overall_score_model.OverallScoreModel`) and **same
core hyperparameters** as the deployed 220-example baseline
(`deberta_v3_base_overall_single_v3_epoch6`: val QWK 0.7111, test QWK
0.6667, test accuracy 0.5185, test within-1 accuracy 0.9259, test MAE
0.5556), on the new, audited, **frozen 1,003-example** dataset
(`four_dim_overall_v4_5000`: 220 frozen + 783 Claude-authored, split
702/150/151), for a fair, apples-to-apples comparison.

This package does not train anything by itself — it is code you run.
**No training has occurred in the environment that produced this
package.**

---

## 1. What's in this directory

| File | Purpose |
|---|---|
| `dataset_loader.py` | Loads/verifies the 1,003-example dataset + split; loads batch metadata for analysis. Not run directly. |
| `train_overall.py` | Trains the model. `--dry-run` (local, safe) or `train` (GPU required). |
| `evaluate_overall.py` | Evaluates the best checkpoint on val + test, plus the qualitative breakdowns (humanized, length, hard-case A–L, B, H, grounding-heavy, project family). |
| `evaluate_on_v4.py` | Evaluates the best checkpoint against the V4 diagnostic benchmark (58 hypothetical stress-test examples). |
| `requirements.txt` | Extra pip packages Colab doesn't already have. |

## 2. GPU recommendation

Any Colab GPU runtime works; the baseline run used a **Tesla T4** (Colab's
free-tier GPU) and completed 8 epochs over 166 training examples in a few
minutes. With 702 training examples (~4.2x more), expect training to take
**roughly 15–30 minutes on a T4** — still comfortably free-tier. A100/L4
(Colab Pro) will be faster but is not required.

`train_overall.py train` **refuses to run on CPU** (same discipline as the
original baseline script) — it exits immediately if `torch.cuda.is_available()`
is `False`. Make sure Colab's runtime type is set to GPU
(`Runtime → Change runtime type → T4 GPU`) before running `train`.

## 3. Approximate memory requirements

- **GPU VRAM:** `deberta-v3-base` + batch size 8 + max_length 256 fits comfortably
  in a T4's 16GB VRAM (the original 220-example run used the same config on a T4).
- **Disk:** the saved checkpoint (`best_checkpoint_weights.pt`) is the full model
  state dict — expect **~700MB** (the 220-example checkpoint was 735,421,149 bytes).
- **Download of `microsoft/deberta-v3-base`:** ~370MB, downloaded once by
  `transformers` on first run (cached afterward in the Colab runtime).

## 4. Repository setup

```bash
!git clone https://github.com/Thewhotoo/Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP.git
%cd Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP/main_cap/cap
```

## 5. Package installation

```bash
!pip install -q -r colab_training/requirements.txt
```

Do **not** `pip install torch` — Colab's preinstalled, CUDA-matched torch
build is what you want; reinstalling risks breaking the CUDA match.

## 6. Dataset setup — **required manual step, read this**

`artifacts/` is `.gitignore`'d in this repo (see `.gitignore` line 20:
`main_cap/cap/artifacts/`) — **the dataset, the batch files, and the V4
diagnostic benchmark are NOT included in the `git clone` above.** You must
upload them into the cloned repo at the exact same relative paths they have
in your local environment:

```
main_cap/cap/artifacts/four_dim_overall_v4_5000/dataset/examples.jsonl   # required for training + evaluation
main_cap/cap/artifacts/four_dim_overall_v4_5000/dataset/split.json       # required for training + evaluation
main_cap/cap/artifacts/four_dim_overall_v4_5000/batches/*.jsonl          # required for evaluate_overall.py's breakdown analysis only (not for training itself)
main_cap/cap/artifacts/v4_diagnostic/v4_diagnostic_58.jsonl              # required for evaluate_on_v4.py only
```

Easiest path: zip the `artifacts/four_dim_overall_v4_5000/` and
`artifacts/v4_diagnostic/` directories locally, upload the zip to Colab
(`files.upload()` or mount Google Drive), and unzip into
`main_cap/cap/artifacts/`:

```python
from google.colab import files
uploaded = files.upload()   # upload your artifacts.zip
!unzip -q artifacts.zip -d main_cap/cap/artifacts/
```

**Do not regenerate the dataset or the split in Colab.** Only upload the
exact files already produced and audited locally
(`python v4_5000_build.py assemble` was already run; its output is what you
are uploading). `train_overall.py` and `evaluate_overall.py` both hard-stop
with a clear error if the uploaded files don't match the expected
1,003/702/150/151 counts — this is intentional, not a bug to work around.

## 7. Verify the upload (before spending any GPU time)

```bash
!python colab_training/train_overall.py --dry-run
```

Expected output ends with:
```
Dataset OK: 1003 examples (expected 1003). Split: train=702 val=150 test=151 (expected (702, 150, 151)).
Batch metadata loaded for 786 authored records (used only by evaluate_overall.py, not by training).
--dry-run complete: no download, no training.
```

If you see a `BLOCKER:` message instead, **stop and fix the upload** —
do not proceed to `train`.

## 8. Training command

```bash
!python colab_training/train_overall.py train
```

This will:
1. Verify the dataset again (same checks as `--dry-run`, plus a group-leakage check).
2. Download `microsoft/deberta-v3-base` (~370MB, cached after first run).
3. Train for 8 epochs (lr=2e-5, batch_size=8, max_length=256, AdamW, weight_decay=0.01,
   no scheduler, unweighted CORAL loss — identical to the 220-example baseline config).
4. After each epoch, evaluate on the **validation** set only and print val QWK.
5. Save a new checkpoint **only when validation QWK improves** — the test set is
   never touched during training or checkpoint selection.
6. After training, load the best-by-validation-QWK checkpoint and evaluate it on
   the **test** set exactly once.

Progress prints to stdout, one line per epoch, e.g.:
```
[14:02:11] --- epoch 3: train_loss=0.612 val_loss=0.701 val_qwk=0.6842 ---
[14:02:11]     New best checkpoint: epoch 3 (val QWK=0.6842) -- saved to '.../best_checkpoint_weights.pt'
```

## 9. Evaluation commands

```bash
# Val/test metrics + qualitative breakdowns (humanized, length, hard-case A-L, B, H, grounding-heavy, project family)
!python colab_training/evaluate_overall.py

# V4 diagnostic benchmark (58 hypothetical stress-test examples)
!python colab_training/evaluate_on_v4.py
```

Both are read-only/inference-only — they never train, never modify the
checkpoint, the dataset, or the V4 benchmark file. Each writes exactly the
JSON report files listed below; running them again just re-runs inference
and overwrites those same report files (no new checkpoint selection
happens, no test-set information leaks back into training).

## 10. Expected output files

All under `main_cap/cap/artifacts/overall_single_v4_1003/` (a brand-new
directory — this package never writes to `artifacts/overall_single_v3/`,
the 220-example baseline's directory, or `deployed_model_overall_single_v3/`):

| File | Produced by | Contents |
|---|---|---|
| `best_checkpoint_weights.pt` | `train_overall.py train` | The trained model's state dict (~700MB) |
| `best_checkpoint.json` | `train_overall.py train` | Checkpoint metadata: model_version, full `ExperimentConfig` (every hyperparameter, dataset version/size, seed, environment) |
| `epoch_curve.json` | `train_overall.py train` | Per-epoch train_loss/val_loss/val_metrics — the full training history |
| `test_metrics.json` | `train_overall.py train` | Best epoch, val_metrics, **final test_metrics**, training duration, config, environment, and a `baseline_comparison` block with the 220-example run's numbers alongside |
| `evaluate_overall_report.json` | `evaluate_overall.py` | Validation results, final test results, all breakdown analyses, full per-example test predictions |
| `v4_overall_predictions.json` | `evaluate_on_v4.py` | Per-example V4 predictions vs. derived gold |
| `v4_overall_report.json` | `evaluate_on_v4.py` | V4 overall QWK/accuracy/MAE/within-1 + per-diagnostic-category breakdown |

## 11. How to download the best checkpoint

```python
from google.colab import files
import shutil
shutil.make_archive("overall_single_v4_1003", "zip", "main_cap/cap/artifacts/overall_single_v4_1003")
files.download("overall_single_v4_1003.zip")
```

Unzip locally into `main_cap/cap/artifacts/overall_single_v4_1003/` to
inspect, or copy `best_checkpoint_weights.pt` + `best_checkpoint.json` into
a new deployment directory later — **this package never does that copy
itself; deployment is a separate, explicit decision.**

## 12. What this package deliberately does NOT do

- Does not modify `deployed_model_overall_single_v3/` or any other
  production/deployment directory.
- Does not call `evaluator_registry.register_evaluator` or touch
  `deployment_evaluator.py` — training a checkpoint here has zero effect
  on what the live application serves.
- Does not regenerate, reshuffle, or relabel the dataset or split — both
  are loaded read-only from the files you uploaded.
- Does not modify `v4_diagnostic_58.jsonl`.
- Does not evaluate the test set more than once, and never uses test QWK
  for checkpoint/model selection (validation QWK only).
- Does not commit or push anything — this whole package operates on local
  (Colab-runtime-local) files only.
