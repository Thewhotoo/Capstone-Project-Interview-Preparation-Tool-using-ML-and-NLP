# 🎓 Subject-Based Interview Preparation Tool

> **Latest Update**: Folder "for mayo" has been renamed to **"rag_system"** and fully integrated with the capstone application.

## 📌 Quick Summary

This is a complete **AI-powered Subject-Based Interview Preparation Tool** that integrates:

1. **Resume Classifier** - Analyzes resumes & classifies candidate domains
2. **RAG System** - Generates domain-specific interview questions from PDF knowledge bases
3. **RoBERTa Model** - Classifies questions (intent, difficulty, topics) & adapts to user performance
4. **Flask API** - Unified endpoint serving all components
5. **Answer Evaluator** - Grades answers using SBERT + NLI + ML models

## 👥 Team Workflow

This repo is organized so the team can work in parallel without stepping on each other:

- `main` stays as the stable integration branch.
- `adaptive-engine` should carry the interview workflow, RAG, RoBERTa, and API integration work.
- `resume_classifier` should carry the resume model work.
- Use feature branches for each change and merge back through pull requests.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch workflow and review process.

**The Complete Workflow:**
```
Resume Upload → Domain Classification → RAG Question Generation → 
RoBERTa Classification → Adaptive Interview → Answer Evaluation → Feedback
```

---

## 🚀 Getting Started (5 minutes)

### 1. Install Dependencies
```bash
# Install main_cap dependencies
cd main_cap/cap
pip install -r ../requirements.txt

# Install RAG system dependencies  
cd ../../rag_system/rag_tester
pip install -r requirements.txt

# Install resume classifier
cd ../../../resume_classifier
pip install -r requirements.txt

# Install RoBERTa
cd ../Roberta/roberta-multitask-model
pip install -r requirements.txt
```

### 2. Start the Server
```bash
cd main_cap/cap
python app.py
```
Server runs on: `http://localhost:5000`

### 3. Test the Unified Workflow
```bash
curl -X POST http://localhost:5000/workflow/interview \
  -F "resume_file=@sample_resume.pdf" \
  -F "pdf_knowledge_base=computer_networks" \
  -F "topics[]=TCP/IP" \
  -F "topics[]=DNS" \
  -F "num_questions_per_topic=2" \
  -F "user_id=candidate_001"
```

---

## 📂 Folder Structure

```
.
├── rag_system/                    ⭐ RAG Question Generation (renamed from "for mayo")
│   ├── rag_tester/                Main RAG pipeline
│   │   ├── knowledge_base/        Vector indices for PDFs
│   │   ├── samples/               Sample PDF files
│   │   ├── ingestor.py            PDF → FAISS indexing
│   │   ├── retrieval.py           Semantic search
│   │   ├── generate.py            Question generation (FLAN-T5)
│   │   └── main.py                Standalone RAG CLI
│   └── rag-llm-interview-tester/  Alternative RAG implementation
│
├── main_cap/                      Flask API + Integration
│   └── cap/
│       ├── app.py                 Main Flask application ⭐ UPDATED
│       ├── rag_integration.py      RAG wrapper (NEW)
│       ├── custom_capstone_sbert/  Fine-tuned SBERT model
│       ├── meta_grader_model.pkl   Answer scorer
│       └── dataset.json            Fallback question bank
│
├── resume_classifier/             Resume Analysis
│   ├── src/
│   │   ├── parser.py              Text extraction
│   │   ├── features.py            Skill/experience extraction
│   │   └── models.py              SBERT + BERT classification
│   └── data/                      Training data
│
├── Roberta/roberta-multitask-model/  Question Classification
│   ├── inference/                    Prediction modules
│   │   ├── predict_intent.py         Question type
│   │   ├── predict_difficulty.py     Difficulty level
│   │   └── predict_topic.py          Technical topics
│   ├── adaptive/                     Learning adaptation
│   │   ├── session_manager.py        User session tracking
│   │   └── user_profile.py           Performance history
│   └── eval/                         Evaluation scripts
│
└── WORKFLOW_INTEGRATION_GUIDE.md  📖 Complete documentation
```

---

## 📡 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/predict` | POST | Resume classification |
| `/rag/available-subjects` | GET | List RAG knowledge bases |
| `/rag/setup-knowledge-base` | POST | Initialize RAG from PDF |
| `/rag/generate-questions` | POST | Generate RAG questions |
| `/roberta/classify` | POST | Classify question (intent/difficulty/topics) |
| `/api/evaluate` | POST | Grade answer using SBERT+NLI+RF |
| `/adaptive/session` | POST | Start adaptive learning session |
| **/workflow/interview** | POST | **Complete unified workflow** ⭐ |

> **See [WORKFLOW_INTEGRATION_GUIDE.md](WORKFLOW_INTEGRATION_GUIDE.md) for full API documentation**

---

## 🔄 The Unified Workflow (Recommended)

**Single endpoint that does everything:**

```bash
POST /workflow/interview
```

This endpoint:
1. ✅ Parses your resume
2. ✅ Classifies your domain/skills
3. ✅ Generates domain-specific questions from RAG
4. ✅ Creates an adaptive learning session
5. ✅ Returns everything needed to start the interview

**Request:**
```json
{
  "resume_file": "<PDF/DOCX file>",
  "pdf_knowledge_base": "computer_networks",
  "topics": ["TCP/IP", "DNS", "IP Routing"],
  "num_questions_per_topic": 2,
  "user_id": "candidate_001"
}
```

**Response:**
```json
{
  "status": "success",
  "resume_analysis": {
    "predicted_domain": "Network Engineer",
    "skills": ["TCP/IP", "networking", "Linux"],
    "experience": {...}
  },
  "questions": [
    {
      "question": "Explain TCP three-way handshake",
      "reference_answer": "...",
      "topic": "TCP/IP",
      "source_subject": "computer_networks"
    },
    ...
  ],
  "session": {
    "user_id": "candidate_001",
    "total_questions": 6
  }
}
```

---

## 🧠 System Components Explained

### Resume Classifier
- **Input**: Resume (PDF/DOCX)
- **Output**: Domain classification, skills, experience level, contact info
- **Model**: SBERT + BERT ensemble
- **Accuracy**: 87%+

### RAG System
- **Input**: Topic + PDF knowledge base
- **Output**: Interview questions with reference answers
- **Models**: FAISS (vector search), FLAN-T5 (question generation)
- **Process**: Semantic search → Context retrieval → LLM generation

### RoBERTa Multitask Model
- **Input**: Interview question text
- **Output**: Intent (definition/explanation/etc), difficulty (easy/medium/hard), topics
- **Training**: Fine-tuned on technical interview questions
- **Adaptive**: Adjusts next question difficulty based on performance

### Answer Evaluation
- **Input**: User answer + reference answer
- **Output**: Score (0-1) + feedback
- **Models**: 
  - Custom SBERT (semantic similarity)
  - Cross-encoder RoBERTa (NLI - entailment/contradiction)
  - Random Forest meta-grader (combines signals)

---

## ⚡ Key Features

✅ **Automated Resume Parsing** - Extract skills & experience automatically  
✅ **Domain-Specific Questions** - RAG generates questions from PDFs relevant to domain  
✅ **Multi-Signal Answer Evaluation** - SBERT + NLI + Machine Learning scoring  
✅ **Adaptive Difficulty** - Questions get harder/easier based on performance  
✅ **Session Persistence** - Track user progress across sessions  
✅ **Real-time Feedback** - Instant evaluation with constructive feedback  
✅ **Question Classification** - Auto-categorize by intent, difficulty, topics  
✅ **Unified API** - Single endpoint for complete workflow  

---

## 🔧 Configuration

### Add New PDF Knowledge Bases
```bash
# 1. Place PDF in rag_system/rag_tester/samples/
# 2. Initialize via API:

curl -X POST http://localhost:5000/rag/setup-knowledge-base \
  -H "Content-Type: application/json" \
  -d '{
    "subject_name": "database_design",
    "pdf_path": "samples/DBMS_Guide.pdf"
  }'
```

### Adjust Interview Parameters
Edit `main_cap/cap/app.py`:
- `MAX_FILE_SIZE`: Resume file size limit
- Difficulty thresholds in `/adaptive/session`
- Question selection criteria in `/api/next_question`

---

## 📖 Documentation

- **[WORKFLOW_INTEGRATION_GUIDE.md](WORKFLOW_INTEGRATION_GUIDE.md)** - Complete system architecture & API docs
- `resume_classifier/README.md` - Resume classifier details
- `Roberta/roberta-multitask-model/README.md` - RoBERTa model info
- `rag_system/rag_tester/README.md` - RAG system documentation

---

## 🚨 Troubleshooting

### Port 5000 already in use
```bash
python app.py --port 5001
```

### RAG system errors
- Check PDF files exist in `rag_system/rag_tester/samples/`
- Ensure `knowledge_base/` directory exists and is writable

### Resume parser failing
- Verify resume is valid PDF/DOCX
- Minimum 50 characters of extractable text required

### Low answer scores
- Check reference answers in `dataset.json` are detailed
- Ensure SBERT model loaded correctly

**For more troubleshooting, see [WORKFLOW_INTEGRATION_GUIDE.md](WORKFLOW_INTEGRATION_GUIDE.md#-troubleshooting)**

---

## 📋 What's Changed (Latest Update)

✅ **Renamed**: `for mayo/` → `rag_system/` (professional naming)  
✅ **Added**: `rag_integration.py` - RAG system wrapper  
✅ **Added**: `/rag/*` endpoints - RAG system API  
✅ **Added**: `/workflow/interview` - Unified endpoint ⭐  
✅ **Updated**: `app.py` - Integrated all components  
✅ **Created**: `WORKFLOW_INTEGRATION_GUIDE.md` - Comprehensive docs  

---

## 🎯 Example Use Cases

### Use Case 1: Campus Placement Interview
1. Student uploads resume
2. System classifies as "Software Engineer"
3. Generates 10 DSA + system design questions
4. Interview with adaptive difficulty
5. Gets performance report

### Use Case 2: Technical Interview Prep
1. Job seeker wants to prepare for "Network Engineer" role
2. Upload resume (automatically classifies domain)
3. System generates networking questions from CN PDF
4. User practices with adaptive difficulty
5. Gets feedback on weak areas

### Use Case 3: Interview Candidate Screening
1. Company uploads candidate resumes (batch)
2. System classifies and generates domain-specific questions
3. Sends interview links to candidates
4. Auto-grades answers
5. Returns candidate rankings by score

---

## ⭐ Support & Feedback

For issues, suggestions, or improvements:
1. Check [WORKFLOW_INTEGRATION_GUIDE.md](WORKFLOW_INTEGRATION_GUIDE.md)
2. Review component-specific READMEs
3. Check Flask app logs: `python app.py` (debug mode)

---

**Status**: ✅ Production Ready  
**Last Updated**: April 22, 2026  
**Version**: 1.0.0
