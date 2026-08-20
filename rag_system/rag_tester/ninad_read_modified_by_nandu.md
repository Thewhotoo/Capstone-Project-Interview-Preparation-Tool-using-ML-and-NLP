# RAG-Based Interview Preparation System
## Project Documentation & Handover Guide

---

# 1. Project Overview

This project is a **dynamic Retrieval-Augmented Generation (RAG)** system for interview preparation.

Instead of storing questions manually or training a model for every subject, the system takes a PDF, converts it into a searchable knowledge base, retrieves the most relevant information for a topic, and uses a Large Language Model (Qwen2.5) to generate interview questions and reference answers.

The student's answer is then evaluated using semantic similarity and concept matching.

The important thing is:

> **The model is NOT trained on our PDFs.**

It simply **retrieves** the correct information from the uploaded PDF and answers based on that.

This means the same system can work for **any subject** provided we first ingest the PDF.

---

# 2. Current Architecture

```
                PDF
                 │
                 ▼
        dynamic_ingestor.py
                 │
                 ▼
      Chunking + Embeddings
                 │
                 ▼
        knowledge_base/
        ├── index.faiss
        └── chunks.json
        └── bm25.pkl (BM25 index)
        └── tests.json (optional test cases)
                 │
                 ▼
           retrieval.py
       (Hybrid: FAISS + BM25)
                 │
                 ▼
     Retrieve Relevant Context
                 │
                 ▼
           generate.py
      (Qwen2.5-1.5B Instruct)
        │                 │
        ▼                 ▼
 Interview Question   Reference Answer
   (w/ difficulty)      (w/ citations)
        │                 │
        ▼                 ▼
    MCQ / Coding        Reference Code
                 │
                 ▼
          evaluate.py
     (Rubric‑based + code eval)
                 │
                 ▼
         code_evaluator.py
   (Multi‑language syntax, compilation,
    batch & real‑time execution)
                 │
                 ▼
 Semantic + Concept + Clarity + Tests
                 │
                 ▼
             main.py
                 │
                 ▼
       tracking.py (progress)
```

---

# 3. Folder Structure

```
rag_tester/
│
├── main.py
├── dynamic_ingestor.py
├── retrieval.py
├── generate.py
├── evaluate.py
├── tracking.py
├── code_evaluator.py
├── bm25_utils.py
├── knowledge_base/
│     ├── cn/
│     │     ├── index.faiss
│     │     ├── chunks.json
│     │     ├── bm25.pkl
│     │     └── tests.json (optional)
│     ├── ooad/
│     │     ├── index.faiss
│     │     └── chunks.json
│     └── ...
├── samples/
│      ├── CN.pdf
│      ├── OOAD.pdf
│      └── ...
├── user_progress/            (JSON tracking per user)
└── requirements.txt
```

---

# 4. Explanation of Every File

## main.py
Entry point. Shows menu with:
- Subject selection
- Interactive mode (with difficulty & question type)
- MCQ quiz mode
- Progress view
- Batch generation

Calls retrieval, generation, evaluation, and tracking.

## dynamic_ingestor.py
Converts PDF to searchable knowledge base with improved chunking:
- **Preserves headings**, definitions, examples
- **Merges short sections**
- **Semantic chunking** for long pages (overlap)
- Extracts concepts and builds rich embedding text
- Also builds **BM25** index for hybrid retrieval
- Supports **multiple PDFs per subject** (folder‑based or filename grouping)

Run once per subject (PDF changes are detected via hash).

## retrieval.py
Performs **hybrid retrieval**:
- FAISS (semantic)
- BM25 (keyword)
- Scores fused with weighted combination (α = 0.6)
- Optional **reranking** via cross‑encoder
- **Adjacent chunk merging** for page coherence
- Loads test cases from `tests.json` (if available)

## generate.py
Loads `Qwen2.5-1.5B-Instruct` (cached). Generates:
- **Interview questions** (open‑ended) with difficulty levels
- **MCQs** with distractors
- **Pseudocode** and **coding** questions
- **Reference answers** with strict grounding and **citations** (page numbers)
- **Test cases** automatically (when none are pre‑defined)
- **Explanations** for topics

Model uses a **grounding system prompt** to avoid hallucination.

## evaluate.py
Evaluates student answers using:
- **Semantic similarity** (MiniLM)
- **Weighted concept matching** (core concepts have higher weight)
- **Clarity score** (length, sentence structure)
- Returns **rubric breakdown** (`semantic_score`, `concept_score`, `clarity_score`, `overall_score`)

For **coding/pseudocode** answers, it routes to `code_evaluator.py`.

## code_evaluator.py
Performs full code evaluation with support for **Python, Java, C++, and JavaScript**:
- **Syntax checking** (`ast.parse`, `javac`, `g++`, `node --check`)
- **Compilation** (for Java and C++)
- **Batch execution** of unit tests (input/output comparison)
- **Real‑time execution** – streams output line by line as the code runs (interactive mode)
- **Semantic similarity** using **CodeBERT** (`microsoft/codebert-base`)
- **Detailed feedback** via Qwen with chain‑of‑thought reasoning
- Language selection is integrated into the interactive menu

## tracking.py
Tracks user progress using **JSON storage** (per user):
- Stores sessions with topic, difficulty, type, score, grade
- Provides statistics (average, max, grade distribution)
- Recommends weak topics (below threshold)

## knowledge_base/
Auto‑generated folder containing:
- `index.faiss` – FAISS vector index
- `chunks.json` – chunk metadata (text, headings, concepts, pages)
- `bm25.pkl` – BM25 index (for hybrid retrieval)
- `tests.json` – optional test cases per topic (for coding questions)

Do not edit manually.

---

# 5. Models Used

| Model | Purpose |
|-------|---------|
| `sentence-transformers/all-MiniLM-L6-v2` | Text embeddings for retrieval, semantic evaluation |
| `microsoft/codebert-base` | Code‑specific embeddings for coding answers |
| `Qwen2.5-1.5B-Instruct` | Question/reference generation, feedback, test case generation |
| FAISS | Efficient similarity search |
| BM25 (rank‑bm25) | Keyword‑based retrieval |
| Cross‑encoder (optional) | Reranking for improved retrieval |

---

# 6. How to Add a New Subject

1. Place PDF(s) in `samples/` (e.g., `samples/dbms/` for multiple PDFs).
2. Run:
```bash
python dynamic_ingestor.py
```
3. A new folder is created in `knowledge_base/` with all indexes.
4. Run `python main.py` and select the new subject.

No model retraining required.

---

# 7. How to Run the Project

## Install dependencies
```bash
pip install -r requirements.txt
```

## Build the Knowledge Base
```bash
python dynamic_ingestor.py
```
(Only needed when adding or updating PDFs)

## Start the System
```bash
python main.py
```

---

# 8. Current Workflow

```
User enters topic
│
▼
retrieval.py (hybrid FAISS + BM25)
│
▼
Relevant chunks (with page citations)
│
▼
generate.py (Qwen)
│
▼
Question (with difficulty & type)
│
▼
Student answers (code or text)
│
▼
evaluate.py (rubric + code eval)
│
▼
code_evaluator.py (multi‑lang, real‑time if enabled)
│
▼
Score, grade, feedback, and progress logged
```

---

# 9. Implemented Features

| Feature | Status |
|---------|--------|
| Dynamic PDF ingestion | ✅ Done |
| Improved chunking (headings, definitions, merging) | ✅ Done |
| Hybrid retrieval (FAISS + BM25) | ✅ Done |
| Reranking (cross‑encoder) | ✅ Done (optional) |
| Strict grounding + citations | ✅ Done |
| Rubric‑based evaluation | ✅ Done |
| MCQ generation | ✅ Done |
| Difficulty levels (Easy/Medium/Hard) | ✅ Done |
| User progress tracking (JSON) | ✅ Done |
| Pseudocode support | ✅ Done |
| Coding interview support (Python, Java, C++, JS) | ✅ Done |
| Code evaluation (syntax, tests, CodeBERT) | ✅ Done |
| Real‑time code execution (streaming output) | ✅ Done |
| Auto‑generation of test cases | ✅ Done |
| Multiple PDFs per subject | ✅ Done |
| OCR fallback for scanned PDFs | ✅ Done |

---

# 10. Future Improvements

- Add more subjects (DBMS, OS, DS, etc.)
- Add web interface (Streamlit/Flask)
- Add API mode
- Support for diagrams and images
- Advanced analytics (concept‑level mastery)
- Support for more programming languages (Go, Rust, C#)
- Integration with real‑time code execution sandbox (Docker)

---

# 11. Google Colab Setup Guide

Google Colab with a **T4 GPU** is the recommended environment.

## Step 1 – Enable GPU
```
Runtime → Change runtime type → T4 GPU → Save
```

## Step 2 – Upload and Unzip
```python
from google.colab import files
uploaded = files.upload()
!unzip "Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP.zip"
```

## Step 3 – Navigate to Project
```python
%cd Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP/rag_system/rag_tester
```

## Step 4 – Install Dependencies
```python
!pip install -r requirements.txt
!pip install accelerate
```

## Step 5 – Build Knowledge Base (if needed)
```python
!python dynamic_ingestor.py
```

## Step 6 – Run System
```python
!python main.py
```

**Complete Colab Workflow:**
```python
from google.colab import files
uploaded = files.upload()
!unzip "Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP.zip"
%cd Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP/rag_system/rag_tester
!pip install -r requirements.txt
!pip install accelerate
!python dynamic_ingestor.py
!python main.py
```

---

# 12. Common Issues

| Issue | Solution |
|-------|----------|
| No indexed subjects found | Run `python dynamic_ingestor.py` |
| Knowledge base not found | Add PDF and run ingestor |
| CUDA Out of Memory | Use 1.5B model or restart runtime |
| ModuleNotFoundError | Run `pip install -r requirements.txt` |
| Code execution errors | Check that required compilers (javac, g++, node) are installed |
| Real‑time streaming not showing | Ensure `stream_output=True` is passed to `evaluate_code` |

---

# 13. Verification Checklist

When adding new features, verify:

✅ Project runs without errors  
✅ Generated output is better than before  
✅ Retrieval is more accurate (hybrid helps)  
✅ Reference answers are grounded and include citations  
✅ Evaluation scores are reasonable and rubric‑based  
✅ New feature works for all subjects  
✅ Adding a new PDF works without code changes  

---

# 14. Regression Testing

Before finalising any change:

- Run ingestor on all existing PDFs
- Verify retrieval still works
- Generate questions for at least 3 topics
- Verify evaluation remains reasonable
- Check no existing functionality broke

---

# 15. Important Note

> **Do NOT compare against an LLM trained on the PDF.**

The entire point is that the model never sees the PDF.

Verification should focus on:

```
PDF → Chunks → Retrieval → Generation → Evaluation
```

The goal is to make this entire pipeline better, not to make Qwen memorize the PDF.
