# Colab Training Handoff

Navigation document for the next session. For full history/detail see
`artifacts/four_dim_overall_v4_5000/PROGRESS_CONTEXT.md` (dataset) and
`colab_training/README.md` (Colab mechanics) — this file does not
duplicate either, it points to them.

---

## Current state

### Dataset — FROZEN
- Final dataset: **1,003** examples (`four_dim_overall_v4_5000`)
- Frozen: 220 / Authored accepted: 783
- Split: 702 train / 150 val / 151 test
- **No more generation until explicitly decided later.** Do not create new batches.

### Audit — READY TO TRAIN
- Deep qualitative audit completed. Verdict: **READY TO TRAIN.** No RED findings.
- YELLOW findings (monitor, do not fix pre-training):
  1. word_count ↔ depth_specificity correlation r=0.76 — watch for a length shortcut
  2. Humanized examples lack delivery/content decoupling coverage (no hesitant-but-correct or confident-but-shallow humanized examples)
  3. A few vacuous/content-free answers have inconsistent `technical_correctness` scoring
  4. B/H hard-case counts grew this session (22→45, 42→46); sampled labels were read in full and are genuine, not fabricated
- **Do NOT repair or relabel the dataset before training unless explicitly instructed.**

### Baseline (220-example, already deployed)
- Model: `microsoft/deberta-v3-base`, single overall CORAL ordinal head
- Test QWK **0.6667** / Val QWK **0.7111** / Test accuracy **0.5185** / Test within-1 **0.9259** / Test MAE **0.5556**

### New training experiment — prepared, NOT run
- Dataset: 1,003 (same architecture, same core hyperparameters as baseline)
- seed=42, lr=2e-5, batch_size=8, epochs=8, max_length=256, AdamW, weight_decay=0.01, no scheduler, dropout=0.1 (default), unweighted CORAL loss
- Test set untouched for model selection; best checkpoint selected by **validation QWK**

### Colab package — `main_cap/cap/colab_training/`
- `dataset_loader.py`, `train_overall.py`, `evaluate_overall.py`, `evaluate_on_v4.py`, `requirements.txt`, `README.md`
- Already verified: `train_overall.py --dry-run` passes, all 4 scripts compile/import cleanly, dataset split verified (702/150/151), frozen 220 verified, production code untouched, **training NOT run**

---

## Next session — do this

1. Read this handoff.
2. Read `colab_training/README.md`.
3. Verify `git status`.
4. Get the dataset/artifacts into the Colab environment — `artifacts/` is `.gitignore`'d, `git clone` will NOT include it.
5. Run `python colab_training/train_overall.py --dry-run` — must pass before proceeding.
6. Only after the dry-run passes, run the actual GPU training.
7. Run `evaluate_overall.py`.
8. Run `evaluate_on_v4.py`.
9. Bring the complete training results back for analysis.
10. **Do NOT deploy the checkpoint yet.**

### Exact Colab commands (from `colab_training/README.md`)

```bash
!git clone https://github.com/Thewhotoo/Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP.git
%cd Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP/main_cap/cap
!pip install -q -r colab_training/requirements.txt
# upload artifacts/four_dim_overall_v4_5000/{dataset,batches}/ and artifacts/v4_diagnostic/v4_diagnostic_58.jsonl
# into main_cap/cap/artifacts/ at those same relative paths (see README §6)
!python colab_training/train_overall.py --dry-run
!python colab_training/train_overall.py train
!python colab_training/evaluate_overall.py
!python colab_training/evaluate_on_v4.py
```

Download the checkpoint back:
```python
from google.colab import files
import shutil
shutil.make_archive("overall_single_v4_1003", "zip", "main_cap/cap/artifacts/overall_single_v4_1003")
files.download("overall_single_v4_1003.zip")
```
