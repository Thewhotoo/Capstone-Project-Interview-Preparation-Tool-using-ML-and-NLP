# 🎓 Capstone Interview System - Integrated Workflow Guide

## Project Overview

This capstone project integrates multiple AI systems into a cohesive **Interview Preparation & Evaluation Platform**. The system automates the entire interview process:

```
Resume Upload → Domain Classification → RAG-Based Question Generation → 
Adaptive Interview → Answer Evaluation → Performance Feedback
```

---

## 📁 Project Structure

### Folder Reorganization

The project has been reorganized with professional folder names:

```
Capstone_project/Project/
├── rag_system/                    # ✅ RENAMED (was "for mayo")
│   ├── rag_tester/                # Main RAG implementation
│   │   ├── knowledge_base/        # Vector indices & chunks
│   │   ├── samples/               # Sample PDFs for ingestion
│   │   ├── ingestor.py            # PDF → FAISS indexing
│   │   ├── retrieval.py           # Semantic search
│   │   ├── generate.py            # FLAN-T5 question generation
│   │   ├── evaluate.py            # Answer evaluation
│   │   └── main.py                # Standalone RAG pipeline
│   └── rag-llm-interview-tester/  # Alternative implementation
│
├── main_cap/                      # Integrated Flask Application
│   └── cap/
│       ├── app.py                 # Flask API with all endpoints
│       ├── rag_integration.py      # RAG system wrapper (NEW)
│       ├── custom_capstone_sbert/  # Fine-tuned SBERT model
│       ├── meta_grader_model.pkl   # Random Forest scorer
│       ├── dataset.json            # Question bank
│       └── templates/index.html    # Web UI
│
├── resume_classifier/             # Resume Parsing & Domain Classification
│   ├── src/
│   │   ├── parser.py              # Extract text from resume
│   │   ├── features.py            # Extract skills, experience
│   │   └── models.py              # SBERT + BERT ensemble
│   ├── data/                      # Training & test data
│   └── predict.py                 # CLI interface
│
└── Roberta/roberta-multitask-model/  # Interview Question Classification
    ├── inference/                     # Prediction modules
    │   ├── predict_intent.py          # Q type: definition, explanation, etc.
    │   ├── predict_difficulty.py      # Q difficulty: easy, medium, hard
    │   └── predict_topic.py           # Q topic: DSA, OOP, OS, CN, DBMS
    ├── adaptive/                      # Adaptive learning
    │   ├── session_manager.py         # User session tracking
    │   └── user_profile.py            # Learning progress
    └── main.py                        # Standalone adaptive CLI
```

---

## 🔄 Unified Interview Workflow

### Complete Flow (Resume → Test → RAG Questions → Interview)

```
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 1: Resume Upload                         │
│              (Resume Parser Module)                              │
│  Input: PDF/DOCX Resume  →  Output: Parsed text + structured   │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              STEP 2: Domain Classification                       │
│          (Resume Classifier - SBERT + BERT)                     │
│  Input: Resume text  →  Output: Domain (Data Science, etc.)     │
│         Extracts: Skills, Experience, Contact info              │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│         STEP 3: RAG Knowledge Base Selection                     │
│           (RAG System - Knowledge Base)                          │
│  Input: Topic/Domain  →  Output: Select appropriate PDFs        │
│         Options: Computer Networks, OS, DSA, DBMS, etc.         │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│       STEP 4: Domain-Specific Question Generation                │
│          (RAG + FLAN-T5 LLM)                                     │
│  Input: PDF knowledge base + topics  →  Questions + answers     │
│  Process: Semantic search → Context retrieval → Q generation    │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│     STEP 5: Question Classification (Multi-task)                 │
│          (RoBERTa - Intent, Difficulty, Topics)                 │
│  Input: Generated question  →  Output: Intent, difficulty,      │
│         topics, confidence scores                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│           STEP 6: Adaptive Interview Session                     │
│         (Session Manager - Tracks user performance)             │
│  Input: Question  →  Output: Next question (adaptive            │
│         difficulty based on user performance)                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│             STEP 7: Answer Evaluation                            │
│     (SBERT + NLI + Random Forest Meta-Grader)                    │
│  Input: User answer, reference answer  →  Score (0-1)           │
│  Metrics: Semantic similarity, NLI contradiction,                │
│           Word count, Grammar quality                            │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│         STEP 8: Adaptive Feedback & Recommendations              │
│        (User Profile Tracking - Weak areas identified)           │
│  Output: Performance feedback, learning recommendations,        │
│          next topic suggestions                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints

### 1. Resume Classification
```
POST /predict
Content-Type: multipart/form-data

Request:
{
  "file": <PDF/DOCX resume file>
}

Response:
{
  "predicted_domain": "Software Engineer",
  "confidence": 0.92,
  "experience": {
    "years": 5,
    "level": "Senior"
  },
  "skills": ["Python", "React", "AWS", ...],
  "email": "candidate@example.com",
  "phone": "+1-555-0123"
}
```

### 2. RAG: Available Knowledge Bases
```
GET /rag/available-subjects

Response:
{
  "subjects": [
    "computer_networks",
    "operating_systems",
    "data_structures",
    ...
  ]
}
```

### 3. RAG: Setup Knowledge Base
```
POST /rag/setup-knowledge-base
Content-Type: application/json

Request:
{
  "subject_name": "computer_networks",
  "pdf_path": "/path/to/CN_Unit1.pdf"
}

Response:
{
  "success": true,
  "message": "Knowledge base 'computer_networks' created successfully",
  "subject": "computer_networks"
}
```

### 4. RAG: Generate Questions
```
POST /rag/generate-questions
Content-Type: application/json

Request:
{
  "subject_name": "computer_networks",
  "topic": "TCP/IP Protocol",
  "num_questions": 3
}

Response:
{
  "status": "success",
  "subject": "computer_networks",
  "topic": "TCP/IP Protocol",
  "questions": [
    {
      "question": "Explain the three-way handshake in TCP.",
      "reference_answer": "The three-way handshake is...",
      "topic": "TCP/IP Protocol",
      "source_pages": [5, 6],
      "context": "..."
    },
    ...
  ],
  "count": 3
}
```

### 5. Question Classification (RoBERTa)
```
POST /roberta/classify
Content-Type: application/json

Request:
{
  "text": "Explain the difference between TCP and UDP."
}

Response:
{
  "intent": "explanation",
  "difficulty": "medium",
  "confidence": 0.85,
  "topics": "networking",
  "intent_confidence": 0.92,
  "difficulty_confidence": 0.78
}
```

### 6. Answer Evaluation
```
POST /api/evaluate
Content-Type: application/json

Request:
{
  "user_answer": "TCP uses a three-way handshake...",
  "reference_answer": "The three-way handshake in TCP...",
  "question": "Explain TCP handshake.",
  "user_fill_mask": "SYN",
  "reference_fill_mask": "SYN"
}

Response:
{
  "score": 0.82,
  "marks": 8,
  "feedback": "Good answer with technical accuracy.",
  "fill_correct": true
}
```

### 7. Adaptive Session
```
POST /adaptive/session
Content-Type: application/json

Request:
{
  "user_id": "candidate_001",
  "num_questions": 5
}

Response:
{
  "status": "success",
  "result": {
    "user_id": "candidate_001",
    "questions": [...],
    "adaptive_info": {...}
  }
}
```

### 8. **⭐ UNIFIED WORKFLOW (Resume → Test → RAG → Interview)**
```
POST /workflow/interview
Content-Type: multipart/form-data

Request Parameters:
{
  "resume_file": <PDF/DOCX file>,
  "pdf_knowledge_base": "computer_networks",
  "topics[]": ["TCP/IP", "DNS", "IP Routing"],
  "num_questions_per_topic": 2,
  "user_id": "candidate_001"
}

Response:
{
  "status": "success",
  "resume_analysis": {
    "predicted_domain": "Network Engineer",
    "confidence": 0.87,
    "skills": ["networking", "TCP/IP", "Linux"],
    "experience": {
      "years": 3,
      "level": "Mid-level"
    },
    "email": "candidate@example.com",
    "phone": "+1-555-0123"
  },
  "questions": [
    {
      "question": "Explain TCP three-way handshake",
      "reference_answer": "...",
      "topic": "TCP/IP",
      "source_subject": "computer_networks",
      "source_pages": [5, 6]
    },
    {
      "question": "What is the role of DNS?",
      "reference_answer": "...",
      "topic": "DNS",
      "source_subject": "computer_networks",
      "source_pages": [12]
    },
    ...
  ],
  "session": {
    "user_id": "candidate_001",
    "total_questions": 6,
    "session_data": {...}
  }
}
```

---

## 🚀 Quick Start Guide

### 1. Start the Flask Server
```bash
cd main_cap/cap
python app.py
```
The server will start on `http://localhost:5000`

### 2. Upload Resume and Get Domain Classification
```bash
curl -X POST -F "file=@resume.pdf" http://localhost:5000/predict
```

### 3. Check Available RAG Knowledge Bases
```bash
curl http://localhost:5000/rag/available-subjects
```

### 4. Generate Domain-Specific Questions
```bash
curl -X POST http://localhost:5000/rag/generate-questions \
  -H "Content-Type: application/json" \
  -d '{
    "subject_name": "computer_networks",
    "topic": "TCP/IP",
    "num_questions": 3
  }'
```

### 5. **Complete Unified Interview (Best for Production)**
```bash
curl -X POST http://localhost:5000/workflow/interview \
  -F "resume_file=@resume.pdf" \
  -F "pdf_knowledge_base=computer_networks" \
  -F "topics[]=TCP/IP" \
  -F "topics[]=DNS" \
  -F "num_questions_per_topic=2" \
  -F "user_id=candidate_001"
```

---

## 🔧 System Components

### Resume Classifier (`resume_classifier/`)
- **Purpose**: Parse resumes and classify candidates by domain
- **Models**: SBERT + BERT ensemble
- **Domains**: Software Engineer, Data Scientist, Network Engineer, etc.
- **Accuracy**: ~87% on test set
- **Features**: Extracts skills, experience level, contact info

### RAG System (`rag_system/`)
- **Purpose**: Generate interview questions from PDF knowledge bases
- **Components**:
  - **Ingestor**: Chunks PDFs and creates FAISS vector indices
  - **Retriever**: Semantic search using embeddings
  - **Generator**: FLAN-T5 LLM generates questions from context
  - **Evaluator**: Scores student answers using semantic similarity
- **Models**: FLAN-T5 small, FAISS, sentence-transformers
- **Knowledge Bases**: Computer Networks, Operating Systems, DSA, etc.

### RoBERTa Multitask Model (`Roberta/`)
- **Purpose**: Classify interview questions and track adaptive learning
- **Task 1 - Intent**: question type (definition, explanation, debugging, etc.)
- **Task 2 - Difficulty**: easy, medium, or hard
- **Task 3 - Topic**: DSA, OOP, OS, CN, DBMS
- **Adaptive Learning**: Tracks weak areas, adjusts question difficulty
- **Session Management**: Persists user profiles across sessions
- **Model**: Fine-tuned RoBERTa-base

### Flask Integration (`main_cap/cap/`)
- **Purpose**: Unified API serving all components
- **Models Loaded**:
  - Custom fine-tuned SBERT (answer evaluation)
  - Cross-encoder RoBERTa NLI model
  - Random Forest meta-grader
  - Resume classifier ensemble
  - RoBERTa multitask prediction modules
  - RAG system integration
- **Key Files**:
  - `app.py`: Main Flask application with all endpoints
  - `rag_integration.py`: Wrapper for RAG system
  - `custom_capstone_sbert/`: Fine-tuned sentence transformer
  - `meta_grader_model.pkl`: Trained Random Forest for answer scoring
  - `dataset.json`: Fallback question bank

---

## 📊 Answer Evaluation Metrics

The system evaluates answers using multiple signals:

1. **Semantic Similarity** (SBERT): Cosine similarity between answer and reference
2. **NLI Signals** (Cross-encoder):
   - Entailment score: How much of the answer is relevant
   - Contradiction score: How much contradicts reference
3. **Linguistic Quality**:
   - Word count: Length of answer
   - Grammar validity: Use of proper English words
4. **Meta-Grader** (Random Forest):
   - Combines all signals into final score (0-1)
   - Fine-tuned on labeled interview data

**Final Score Categories**:
- 0.8-1.0: Excellent answer
- 0.6-0.8: Good answer
- 0.4-0.6: Basic understanding
- 0.0-0.4: Limited/incorrect

---

## 🎯 Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│               Flask Application                      │
│           (main_cap/cap/app.py)                      │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Resume   │  │RoBERTa   │  │ RAG Integration  │   │
│  │Classifier│  │Multitask │  │ (RAG Questions)  │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │             │                  │              │
│  ┌────▼─────────────▼──────────────────▼────────┐   │
│  │        Common API Layer                      │   │
│  │  - Question Generation & Classification      │   │
│  │  - Answer Evaluation                         │   │
│  │  - Session Management                        │   │
│  └──────────────────────────────────────────────┘   │
│                                                       │
│  ┌──────────────────────────────────────────────┐   │
│  │  Models & Utilities                          │   │
│  │  - Custom SBERT (Fine-tuned for interviews)  │   │
│  │  - NLI Model (Semantic understanding)        │   │
│  │  - Random Forest Meta-Grader                 │   │
│  │  - Session Manager (User profiles)           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Data Flow Example

**User submits resume and wants to be interviewed on networking:**

1. **Resume Upload** → Parser extracts text → SBERT+BERT classify as "Network Engineer"
2. **Topic Selection** → User selects "Computer Networks" from RAG subjects
3. **Question Generation** → RAG retrieves relevant sections from CN PDF → FLAN-T5 generates 5 questions
4. **Question Display** → Questions shown with RoBERTa classification info (difficulty, intent, topics)
5. **Answer Input** → Candidate answers each question
6. **Auto-Evaluation** → SBERT + NLI + RF Meta-Grader scores answer
7. **Adaptive Next Q** → Session Manager adjusts difficulty based on score
8. **Feedback** → Candidate gets feedback + weak areas identified
9. **Recommendations** → System suggests related topics to practice

---

## ⚙️ Configuration & Customization

### Adding New RAG Knowledge Bases

1. Place PDF in `rag_system/rag_tester/samples/`
2. Call setup endpoint:
```bash
curl -X POST http://localhost:5000/rag/setup-knowledge-base \
  -H "Content-Type: application/json" \
  -d '{
    "subject_name": "database_design",
    "pdf_path": "samples/DBMS_Advanced.pdf"
  }'
```

### Fine-tuning Models

- **Resume Classifier**: `resume_classifier/src/train.py`
- **RoBERTa**: `Roberta/roberta-multitask-model/main.py`
- **SBERT**: `main_cap/cap/custom_capstone_sbert/` (pre-trained)

### Adjusting Question Difficulty

Modify `SessionManager` in `Roberta/roberta-multitask-model/adaptive/`:
- Changes how next question difficulty is selected
- Based on user's previous answer scores

---

## 🐛 Troubleshooting

### RAG system not initializing
- Check if PDF files exist in `rag_system/rag_tester/samples/`
- Ensure FAISS indices are created in `knowledge_base/`

### Resume parser failing
- Ensure resume is valid PDF/DOCX
- Minimum 50 characters of extractable text required

### Low answer scores
- Check if reference answers in `dataset.json` are comprehensive
- Verify SBERT model is properly loaded
- Check NLI model is working

### Session manager not persisting
- Ensure write permissions in `Roberta/roberta-multitask-model/` directory
- Check `user_profile.json` is being created

---

## 📝 Future Enhancements

- [ ] Web UI dashboard for interviews
- [ ] Real-time video interview with speech-to-text
- [ ] Multi-language support
- [ ] Custom RAG fine-tuning per domain
- [ ] Interview analytics dashboard
- [ ] Competitive benchmarking (compare with other candidates)
- [ ] Export interview results as PDF report

---

## 👥 Component Owners & References

| Component | Owner | Status |
|-----------|-------|--------|
| Resume Classifier | ML Team | ✅ Production |
| RAG System | NLP Team | ✅ Production |
| RoBERTa Multitask | ML Team | ✅ Production |
| Flask Integration | Backend Team | ✅ Production |
| Web UI | Frontend Team | 🚧 In Progress |

---

**Last Updated**: April 22, 2026  
**Project Version**: 1.0.0  
**Status**: ✅ Integrated & Ready for Production
