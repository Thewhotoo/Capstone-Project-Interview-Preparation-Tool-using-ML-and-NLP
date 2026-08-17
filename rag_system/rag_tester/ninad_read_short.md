
```markdown
# RAG-Based Interview Preparation System
## Project Documentation & Handover Guide

---

# 1. Project Overview

This project is a **dynamic Retrieval-Augmented Generation (RAG)** system for interview preparation.

Instead of storing questions manually or training a model for every subject, the system takes a PDF, converts it into a searchable knowledge base, retrieves the most relevant information for a topic, and uses a Large Language Model (Qwen2.5) to generate interview questions and reference answers.

The student's answer is then evaluated using semantic similarity and concept matching.

> **The model is NOT trained on our PDFs.**
> 
> It simply **retrieves** the correct information from the uploaded PDF and answers based on that.

This means the same system can work for **any subject** provided we first ingest the PDF.

---

# 2. Architecture

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
                 │
                 ▼
           retrieval.py
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
                 │
                 ▼
          evaluate.py
                 │
                 ▼
     Semantic Evaluation +
      Keyword/Concept Matching
                 │
                 ▼
             main.py
```

---

# 3. Folder Structure

```
rag_tester/
├── main.py
├── dynamic_ingestor.py
├── retrieval.py
├── generate.py
├── evaluate.py
├── knowledge_base/
│     ├── cn/
│     │     ├── index.faiss
│     │     └── chunks.json
│     ├── ooad/
│     │     ├── index.faiss
│     │     └── chunks.json
│     └── ...
├── samples/
│      ├── CN.pdf
│      ├── OOAD.pdf
│      └── ...
└── requirements.txt
```

---

# 4. File Explanations

## main.py
Entry point. Shows menu, handles user input, calls retrieval, generation, and evaluation.

## dynamic_ingestor.py
Converts PDF to searchable knowledge base:
1. Reads PDF
2. Extracts text
3. Splits into chunks
4. Generates embeddings using `all-MiniLM-L6-v2`
5. Stores embeddings in `index.faiss`
6. Stores chunks in `chunks.json`

Run once per PDF.

## retrieval.py
Performs semantic search:
- Embeds query using MiniLM
- Searches FAISS index
- Returns most relevant chunks as context for Qwen

## generate.py
Loads `Qwen2.5-1.5B-Instruct`:
- Generates interview questions
- Generates reference answers **only from retrieved context**

Model loads once per session (cached).

## evaluate.py
Evaluates student answers using:
- Semantic similarity (`all-MiniLM-L6-v2`)
- Keyword/concept extraction
- Weighted scoring

Does NOT use Qwen for scoring.

## knowledge_base/
Auto-generated folder containing FAISS indices and chunks for each subject. Do not edit manually.

---

# 5. Models Used

| Model | Purpose |
|-------|---------|
| `sentence-transformers/all-MiniLM-L6-v2` | Embeddings, retrieval, evaluation |
| `Qwen2.5-1.5B-Instruct` | Question & reference answer generation |
| FAISS | Efficient similarity search |

---

# 6. Adding a New Subject

1. Place PDF in `samples/` folder
2. Run:
```bash
python dynamic_ingestor.py
```
3. A new folder is created in `knowledge_base/`
4. Run `python main.py` and select the new subject

No model retraining required.

---

# 7. Running the Project

## Install dependencies
```bash
pip install -r requirements.txt
```

## Build knowledge base
```bash
python dynamic_ingestor.py
```
(Only needed when adding or updating PDFs)

## Start the system
```bash
python main.py
```

---

# 8. Current Limitations

| Area | Limitation |
|------|------------|
| Subjects | Only OOAD and CN currently available |
| Chunking | Fixed-size; sometimes splits definitions |
| Retrieval | Uses only FAISS; no hybrid search |
| Reference Answers | Qwen occasionally uses general knowledge instead of staying grounded in context |
| Evaluation | Based on similarity + keyword matching; no rubric |
| Pseudocode | Not supported yet |

---

# 9. Future Improvements

- Add more subjects
- Improve chunking strategy
- Add hybrid retrieval (BM25 + FAISS)
- Better grounding of generated answers
- Pseudocode support
- Coding interview questions
- MCQ generation
- Difficulty levels (Easy/Medium/Hard)
- User progress tracking
- Web interface (Streamlit/Flask)
- Multiple PDFs per subject

---

# 10. Google Colab Setup Guide

## Step 1 – Enable GPU
```
Runtime → Change runtime type → T4 GPU → Save
```

## Step 2 – Upload and Unzip
```python
from google.colab import files
uploaded = files.upload()
!unzip "your-project.zip"
```

## Step 3 – Navigate to Project
```python
%cd path/to/rag_tester
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

# 11. Common Issues

| Issue | Solution |
|-------|----------|
| No indexed subjects found | Run `python dynamic_ingestor.py` |
| Knowledge base not found | Add PDF and run ingestor |
| CUDA Out of Memory | Use 1.5B model or restart runtime |
| ModuleNotFoundError | Run `pip install -r requirements.txt` |

---

# 12. Verification Checklist for Improvements

When adding a new feature, verify:

✅ Project runs without errors
✅ Generated output is better than before
✅ Retrieval is more accurate
✅ Reference answers are closer to the PDF
✅ Evaluation scores are reasonable
✅ New feature works for all subjects
✅ Adding a new PDF works without code changes

---

# 13. Regression Testing

Before finalizing any change:

- Run ingestor on all existing PDFs
- Verify retrieval still works
- Generate questions for at least 3 topics
- Verify evaluation remains reasonable
- Check no existing functionality broke

---

# 14. Important Note

> **Do NOT compare against an LLM trained on the PDF.**

The entire point is that the model never sees the PDF.

Verification should focus on:

```
PDF → Chunks → Retrieval → Generation → Evaluation
```

The goal is to make this entire pipeline better, not to make Qwen memorize the PDF.
```