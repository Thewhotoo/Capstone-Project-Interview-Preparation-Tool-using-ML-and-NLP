# 🎓 AI-Powered Resume Discussion & Interview Prep Tool

## 📌 Quick Summary

This is an **AI-powered interview preparation tool** built around a candidate's own resume. Its core flow:

1. **Resume Upload** — a PDF/DOCX/DOC/TXT resume is parsed and turned into a structured **Candidate Profile** by a single Gemini call.
2. **Resume Discussion** — a 10-question conversational interview is planned and asked directly against that profile (projects, experience, skills), not a generic question bank.
3. **Evaluation** — each answer is scored by a trained **DeBERTa** evaluator (with an automatic heuristic fallback if the trained model isn't available), producing per-dimension scores, strengths/weaknesses, and an **Improved Answer** (a strengthened rewrite of the candidate's own response).
4. **Dashboard** — a results dashboard summarizes scores, concept coverage, and the discussion timeline.

The repo also contains supporting/exploratory subsystems that ship alongside the main app but are not wired into its primary UI flow: a RAG-based question generator (`rag_system/`), a standalone resume domain classifier (`resume_classifier/`), and a RoBERTa multitask question-classification model (`Roberta/`).

## 👥 Team Workflow

This repo is organized so the team can work in parallel without stepping on each other:

- `main` stays as the stable integration branch.
- Use feature branches for each change and merge back through pull requests.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch workflow and review process.

---

## 🚀 Getting Started (5 minutes)

### 1. Install Dependencies

The main application only needs its own requirements file:

```bash
cd main_cap/cap
pip install -r requirements.txt
```

The other subsystems (RAG, resume classifier, RoBERTa) are optional and only needed if you're working on those components directly:

```bash
# RAG system (optional — powers open-ended question variety in /api/next_question)
cd rag_system/rag_tester
pip install -r requirements.txt

# Resume classifier (optional — standalone domain classifier, separate from the
# Gemini-based Candidate Profile parser the main app uses)
cd resume_classifier
pip install -r requirements.txt

# RoBERTa multitask model (optional — powers the /roberta and /adaptive endpoints)
cd Roberta/roberta-multitask-model
pip install -r requirements.txt
```

### 2. Configure environment variables

The main app needs a Gemini API key to parse resumes and run the Resume Discussion flow. Create `main_cap/cap/.env`:

```
GEMINI_API_KEY=your_key_here
```

Without it, resume upload and the Resume Discussion flow will not work; the app still starts and logs a clear warning.

### 3. Start the Server

```bash
cd main_cap/cap
python app.py
```

Server runs on: `http://localhost:5000`

On startup the app tries to load the deployed DeBERTa evaluator from `main_cap/cap/deployed_model/` (checkpoint metadata + weights). If the weights file (`best_checkpoint_weights.pt`) isn't present or fails to load, it automatically falls back to a deterministic `HeuristicEvaluator` — the app never fails to start because of this. Check the startup logs to see which evaluator is actually active.

### 4. Use the app

Open `http://localhost:5000` in a browser:

1. Upload a resume (PDF/DOCX/DOC/TXT).
2. Start the Resume Discussion — answer up to 10 questions generated from your own resume.
3. View the results dashboard, including per-answer feedback, Concept Coverage, and Improved Answer suggestions.

There is also a separate, simpler quiz-style flow (topic/difficulty MCQs + fill-in-the-blank) available from the same UI, backed by `/api/next_question` and `/api/evaluate`.

---

## 📂 Folder Structure

```
.
├── main_cap/                          Main Flask application (the app you run)
│   └── cap/
│       ├── app.py                     Flask entrypoint + all HTTP routes
│       ├── conversation_engine.py     Resume Discussion session orchestration (v2 — used by the UI)
│       ├── discussion_engine.py       Earlier Resume Discussion implementation (legacy, still present)
│       ├── planner.py / topic_pool.py Question planning over the Candidate Profile
│       ├── question_realizer.py       Turns a planned specification into question text
│       ├── evaluation_engine.py       Builds evaluation requests and dispatches to the active evaluator
│       ├── model_evaluator.py         Trained DeBERTa evaluator
│       ├── heuristic_evaluator.py     Deterministic fallback evaluator
│       ├── deployment_evaluator.py    Startup wiring: loads the deployed DeBERTa model, falls back to heuristic
│       ├── deployed_model/            Deployed checkpoint metadata + weights (weights are large and git-ignored)
│       ├── concept_analysis.py        Shared lexical concept-coverage detector
│       ├── strong_answer.py           Improved Answer generator (deterministic, grounded in concept_analysis)
│       ├── candidate_profile_generator.py  Resume → Candidate Profile via Gemini
│       ├── rag_integration.py         Optional RAG wrapper used by /api/next_question
│       └── templates/index.html       Web UI
│
├── rag_system/                        RAG question generation (optional subsystem)
│   └── rag_tester/
│       ├── knowledge_base/            Vector indices for PDFs
│       ├── ingestor.py                PDF → FAISS indexing
│       ├── retrieval.py               Semantic search
│       └── generate.py                Question generation
│
├── resume_classifier/                 Standalone resume domain classifier (optional subsystem)
│   └── src/
│       ├── parser.py                  Text extraction (also used by the main app for DOCX/DOC/TXT)
│       ├── features.py                Skill/experience extraction
│       └── models.py                  Domain classification models
│
├── Roberta/roberta-multitask-model/   Question classification + adaptive session engine (optional subsystem)
│   ├── inference/                     Prediction modules (intent, difficulty, topic)
│   └── adaptive/                      Adaptive session/profile tracking
│
└── docs/architecture/                 Design docs for the Resume Discussion pipeline
```

---

## 📡 API Endpoints

Endpoints actually used by the shipped web UI:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve the web UI |
| `/health` | GET | Health check |
| `/api/classify-resume` | POST | Upload a resume, get back a Candidate Profile + session ID |
| `/api/resume-discussion-v2/start` | POST | Start a Resume Discussion session for a Candidate Profile |
| `/api/resume-discussion-v2/reply` | POST | Submit an answer, get evaluation + the next question (or completion) |
| `/api/resume-discussion-v2/end` | POST | End the session and get the full summary/report |
| `/api/next_question` | POST | Get the next quiz-style question (RAG-backed if available, else hardcoded bank) |
| `/api/evaluate` | POST | Score a quiz-style answer + fill-in-the-blank |

Additional endpoints exist for optional/exploratory subsystems and are not called by the shipped UI:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/get-resume-discussion` | POST | Legacy MCQ-style resume discussion (superseded by v2 above) |
| `/api/resume-discussion/{start,reply,end}` | POST | Legacy (v1) Resume Discussion engine, kept for reference |
| `/api/candidate-profile/<session_id>` | GET | Fetch a stored Candidate Profile by session ID |
| `/roberta/classify` | POST | Classify a question via the RoBERTa multitask model |
| `/adaptive/{session,next,evaluate}` | POST | Adaptive question selection driven by the RoBERTa model |

---

## 🧠 System Components Explained

### Candidate Profile Generation
- **Input**: Resume (PDF/DOCX/DOC/TXT)
- **Process**: Text extraction (PyMuPDF for PDF, the `resume_classifier` parser for other formats) → a single Gemini call that produces a structured Candidate Profile (projects, experience, skills, technologies, interview seeds)
- **Output**: Candidate Profile, stored in-memory for the session and reused by every downstream module (discussion, evaluation, dashboard) so the resume is never re-parsed

### Resume Discussion (v2 — Conversation Engine)
- **Planner** (`planner.py` / `topic_pool.py`) selects the next discussion unit from the Candidate Profile in priority order.
- **Question Realizer** (`question_realizer.py`) turns that unit into natural question text.
- The session is capped at **10 questions** (`conversation_engine.RESUME_DISCUSSION_QUESTION_BUDGET`).
- Each answer is evaluated (see below) and recorded to an in-session **Evaluation Ledger**; evaluation does not currently change which question comes next.

### Answer Evaluation
- **Production evaluator**: a fine-tuned **DeBERTa-v3** classifier (`model_evaluator.py`), trained via the experiment pipeline in this repo and deployed from `main_cap/cap/deployed_model/`. It scores each answer across multiple dimensions (technical accuracy, technical depth, resume grounding, communication, completeness) and reports concept coverage and missing-reasoning categories.
- **Automatic fallback**: if the deployed checkpoint is missing, corrupted, or not promoted, the app activates a deterministic `HeuristicEvaluator` instead (`heuristic_evaluator.py`) — the app never crashes because of a missing model.
- **Known limitation** (documented, not a bug): the DeBERTa model was trained on synthetic template answers and scores natural interview answers more harshly than templated ones — this is a train/serve domain gap, not a scoring pipeline bug.

### Improved Answer
- A deterministic (no-LLM) rewrite of the candidate's **own** answer: repetition removed, plus grounded first-person additions naming the specific missing concepts and weak reasoning areas the evaluator flagged.
- Shares a single lexical concept detector (`concept_analysis.py`) with the dashboard's Concept Coverage %, so the two can never disagree.
- Hidden when the candidate's answer is already strong or when there's nothing concrete to add.

### RAG-Backed Quiz Questions (optional)
- **Input**: Topic + a pre-indexed PDF knowledge base (`rag_system/rag_tester/knowledge_base/`)
- **Output**: Open-ended interview questions with reference answers, consumed by `/api/next_question`
- If the RAG system isn't available or configured, `/api/next_question` falls back to a small hardcoded question bank per domain.

### RoBERTa Multitask Model (optional)
- **Input**: Interview question text
- **Output**: Intent (definition/explanation/etc.), difficulty, topics — used by `/roberta/classify` and the `/adaptive/*` endpoints for adaptive question selection.

---

## 🔧 Configuration

### Deploy a different DeBERTa checkpoint
Replace the three files in `main_cap/cap/deployed_model/`:
- `best_checkpoint.json` — checkpoint metadata
- `best_checkpoint_weights.pt` — model weights (large; not tracked in git)
- `final_promotion_decision.json` — promotion decision record

These are exactly what `run_experiment_2_train_tuned.py` produces. If any file is missing or the promotion decision isn't `approved`, the app falls back to `HeuristicEvaluator` automatically.

### Add New PDF Knowledge Bases (RAG)
Place a PDF in `rag_system/rag_tester/samples/` and index it using the ingestion tooling in `rag_system/rag_tester/ingestor.py` (see `rag_system/rag_tester/README.md` and `SETUP_GUIDE.md`).

### Adjust Interview Parameters
- Question budget for Resume Discussion: `RESUME_DISCUSSION_QUESTION_BUDGET` in `main_cap/cap/conversation_engine.py`
- Quiz-style question selection: `/api/next_question` in `main_cap/cap/app.py`

---

## 📖 Documentation

- `docs/architecture/ResumeDiscussion_v2.md` — Resume Discussion pipeline design
- `WORKFLOW_INTEGRATION_GUIDE.md` — earlier integration notes (some content predates the current architecture; prefer this README + the docs above for anything that conflicts)
- `resume_classifier/README.md` — resume classifier details
- `Roberta/roberta-multitask-model/README.md` — RoBERTa model info
- `rag_system/rag_tester/README.md` — RAG system documentation

---

## 🚨 Troubleshooting

### GEMINI_API_KEY not set
Resume upload and Resume Discussion will not work. Set `GEMINI_API_KEY` in `main_cap/cap/.env` and restart.

### Port 5000 already in use
`app.py` runs on a fixed port (5000). Either stop the process using that port, or edit the `app.run(...)` call at the bottom of `main_cap/cap/app.py`.

### Trained evaluator not active
Check the startup logs for `Production evaluator ACTIVE: ...`. If it reports the `HeuristicEvaluator` fallback, verify all three files exist under `main_cap/cap/deployed_model/` and that the promotion decision is `approved`.

### RAG system errors
- Check PDF files exist in `rag_system/rag_tester/samples/`
- Ensure `rag_system/rag_tester/knowledge_base/` exists and is writable
- If RAG isn't configured, `/api/next_question` still works via its hardcoded fallback bank

### Resume parser failing
- Verify the resume is a valid PDF/DOCX/DOC/TXT
- Minimum 50 characters of extractable text required

---

## ⭐ Support & Feedback

For issues, suggestions, or improvements:
1. Check `docs/architecture/ResumeDiscussion_v2.md` and the component-specific READMEs
2. Check Flask app logs (`python app.py`)
