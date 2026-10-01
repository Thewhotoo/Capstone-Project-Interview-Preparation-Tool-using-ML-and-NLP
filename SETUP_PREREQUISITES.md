# Setup prerequisites: what you need before running this project

Everything a new machine needs, beyond `git clone`. The short version is in [`README.md`](README.md#quick-start); this file lists the things that are easy to miss.

---

## 1. To run the app

### System

| Need | Details |
|---|---|
| **OS** | Tested on Windows 11. Nothing is Windows-specific, so Linux and macOS should work but haven't been tested. |
| **Python 3.12** (64-bit) | Tested on 3.12.10. Tick "Add python.exe to PATH" when installing on Windows. |
| **RAM** | The server uses about **2.8 GB** once all models are loaded (measured). 8 GB minimum; 16 GB is comfortable with a browser open. |
| **Disk** | About **5 GB** free: Python packages (0.5 GB with CPU-only PyTorch, about 2.5 GB with the CUDA build), models downloaded on first run (about 1.8 GB, see below) and the evaluator weights (735 MB). |
| **GPU** | **Not needed.** Everything the app does at interview time runs on the CPU. |
| **Internet** | Needed on the **first run** (model downloads) and **whenever the page loads**: the browser fetches MediaPipe (face tracking) from `cdn.jsdelivr.net` and fonts from Google Fonts. |

### Python packages

```bash
# no NVIDIA GPU? install the small CPU-only PyTorch first:
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r Requirements_Global.txt
```

### Git LFS, for the Round 1 evaluator weights

The trained Round 1 evaluator is a 735 MB file, stored in the repository with **Git LFS** (GitHub's large-file storage):

```
main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt
```

**Install Git LFS before cloning** (it ships with Git for Windows; elsewhere see [git-lfs.com](https://git-lfs.com)), run `git lfs install` once, then clone as usual; the file downloads with the clone. If you cloned without it, you have a ~130-byte text "pointer" instead of the model: run `git lfs install` and then `git lfs pull` in the repository.

The repository's free LFS allowance is about **1 GB of downloads per month** across everyone, which is roughly one full clone of this file. Clone once and copy the file to teammates instead of each of you cloning. If the monthly allowance runs out, `git lfs pull` fails until it resets, and the app still works (below).

To check your copy is intact, it should be exactly **735,421,149 bytes** with this SHA-256:

```
277ad4f69834991275c715727cfa58444284b23eb9e54cdf102964f4543a3cef
```

Windows: `certutil -hashfile best_checkpoint_weights.pt SHA256`. Linux/macOS: `sha256sum best_checkpoint_weights.pt`.

**Without the file the app still works**: Round 1 uses the heuristic evaluator instead, and the startup log says which one is active (`Production evaluator ACTIVE: ...`).

### Models downloaded automatically on the first run (about 1.8 GB)

From Hugging Face, into `~/.cache/huggingface/hub/`:

| Model | Size | Used for |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | ~90 MB | Resume parsing, Round 1 evaluator, technical grader |
| `cross-encoder/nli-MiniLM2-L6-H768` | ~320 MB | Round 1 evaluator |
| `cross-encoder/nli-deberta-v3-base` | ~720 MB | Technical grader |
| `microsoft/deberta-v3-base` | ~710 MB | Round 1 trained evaluator (only if the weights file above is installed) |

The first start is therefore slow; after that the app loads them offline in a background thread (a running server in about 2 s). On Windows, Hugging Face may warn that symlinks are unavailable. That is harmless; turning on Windows Developer Mode silences it and saves some disk space.

### Browser and hardware for the interview itself

- **Google Chrome or Microsoft Edge** (recent version). Voice answers use the browser's built-in speech recognition, which only Chromium browsers provide and which needs internet.
- A **webcam** (required: the interview won't start without one, and the camera setup check runs first), plus a **microphone** if you want to answer by voice.
- Allow **camera, microphone and full screen** when the browser asks. The interview is proctored: leaving full screen, switching tabs or copy-pasting ends it.
- A reasonably lit room: the camera check and the live monitor warn about low light, blur and a second person in frame.

### Nothing else to configure

- The SQLite database, its migrations and the Flask secret key are created automatically on first start under `main_cap/cap/instance/` (not in git).
- No API key is needed to run the app. `GEMINI_API_KEY` is used only by optional developer tools.
- Port **5000** must be free (change it in `app.run` at the bottom of `main_cap/cap/app.py`).
- Optional settings are listed in the README's Configuration table.

Run:

```bash
cd main_cap/cap
python app.py          # then open http://localhost:5000
```

This is Flask's development server, fine for local use and demos, not a production deployment.

---

## 2. To run the tests

- **pytest**, which is in `Requirements_Global.txt`.
- **Node.js** 18 or newer (tested on 24) for the frontend tests (`node test_*.js`); no npm packages needed.
- Some grader tests load the real models; `CAP_SKIP_MODEL_TESTS=1` skips them.
- The parser benchmark in `parser_tests/` needs real resumes that are **not in git** (personal data); ask the team for them if you need that benchmark. The rest of the test suite doesn't depend on them.

Commands are in the README's Tests section.

---

## 3. Only to rebuild the question bank (optional, offline)

The app only reads `rag_system/rag_tester/question_bank/*.json`, which is in git. You need the following only to regenerate or extend the bank:

| Need | Details |
|---|---|
| **Lecture slides** | The five subjects' slide PDFs in `rag_system/rag_tester/sources/`. **Not in git** (course material); get them from the team. |
| **Ollama** | [ollama.com](https://ollama.com), tested with 0.34, then `ollama pull qwen3:8b` (about 5 GB). Ollama must be running. |
| **NVIDIA GPU** | Strongly recommended: tested on an 8 GB laptop GPU (about 45 tokens/s). A full generation pass is about 4 hours of GPU time; enrichment about 80 minutes. |
| **CUDA PyTorch** | Only for the optional vision step (`slide_rag.vision`, `Qwen/Qwen3-VL-2B-Instruct`, about 4 GB download). |
| **Run from a normal terminal** | Long jobs are resumable (cached per question), so an interrupted run continues where it stopped. |

Steps are in the README ("Rebuilding the question bank").

---

## 4. Things that are local-only by design (not in the repository)

| What | Why | Where it lives locally |
|---|---|---|
| Database, uploaded resumes, secret key | User data | `main_cap/cap/instance/` |
| Lecture slides and the search indexes built from them | Course material | `rag_system/rag_tester/sources/`, `knowledge_base*/` |
| Question-generation caches | Regenerable | `rag_system/rag_tester/.qbank_cache/`, `.enrich_cache/` |
| Real test resumes and their parsed outputs | Personal data | `parser_tests/resumes/`, `baseline/`, `metadata/` |
| Backups and superseded docs | Project history | `archive/` |
