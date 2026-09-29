# Setup — Interview Preparation Tool (branch: `maburan-new`)

Everything needed to run the app with all current changes (P1 grounding fix,
non-answer/degeneracy fairness gate, honest data-driven feedback, and the new
evaluator modules).

## 1. Get the code (correct branch)
```bash
git clone <repo-url>
cd <repo>
git checkout maburan-new
```

## 2. Get the model weights (IMPORTANT — via git-LFS)
The deployed DeBERTa evaluator weights (~735 MB) are stored with **git-LFS**
(they are too large for normal git). You MUST have git-lfs installed, or you'll
only get a tiny pointer file and the app will silently fall back to a weaker
heuristic evaluator (losing the accuracy/fairness fixes).

```bash
git lfs install
git lfs pull        # downloads main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt
```
Verify it's the real file (should be ~735 MB, not ~130 bytes):
```bash
ls -l main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt
```
If git-lfs isn't available, ask the repo owner for `best_checkpoint_weights.pt`
and place it at that exact path.

## 3. Install Python dependencies (Python 3.11–3.13)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r main_cap/cap/requirements.txt
```
(See the torch note in `requirements.txt` if you're on a CPU-only machine.)

## 4. Run
```bash
cd main_cap/cap
python app.py
# open http://localhost:5000
```

## First-run notes
- On the **first** answer/evaluation the app downloads a few HuggingFace models
  (`microsoft/deberta-v3-base`, `all-MiniLM-L6-v2`, an NLI cross-encoder — ~1 GB
  total). This needs internet and a few minutes the first time; they're cached
  afterwards.
- No API key is required — résumé parsing and evaluation run fully locally. (A
  `.env` with `GEMINI_API_KEY` is optional and only used by offline
  dataset-labeling tools, not the live app; the app logs a harmless warning if
  it's absent.)
- CPU-only is fine; expect a few seconds per evaluated answer.

## What you'll see (current behavior)
- Upload a résumé → personalized, résumé-grounded interview → per-answer scores
  + four diagnostic dimensions + an end-of-session **feedback** report.
- Non-answers ("idk"), gibberish, keyword-dumps, markup/code, and off-topic
  answers correctly score **poor**; concrete, grounded answers score well.
- The report's narrative is generated from the actual per-turn signals (no fixed
  templates) and is honest that it does **not** independently verify the factual
  correctness of technical claims.

## Tests
```bash
cd main_cap/cap
python -m pytest test_correctness_nli_scorer.py test_resume_evidence_evaluator.py \
  test_interview_feedback.py test_overall_single_evaluator.py -q
```
