# 🧪 Testing Guide - Capstone Interview System

## Prerequisites Check

Before testing, verify everything is in place:

```bash
# Navigate to project root
cd "c:\Users\Surya Srikhar\OneDrive\Documents\Desktop\Capstone_project\Project"

# Check folder structure
dir
```

Expected output:
```
rag_system/                    ✅ (renamed from "for mayo")
main_cap/
resume_classifier/
Roberta/
README.md
WORKFLOW_INTEGRATION_GUIDE.md
```

---

## Step 1: Install Dependencies

### 1.1 Main Flask App Dependencies
```bash
cd main_cap/cap
pip install flask werkzeug sentence-transformers transformers joblib
```

### 1.2 RAG System Dependencies
```bash
cd ../../rag_system/rag_tester
pip install faiss-cpu transformers torch sentence-transformers tqdm pdfplumber
```

### 1.3 Resume Classifier Dependencies
```bash
cd ../../../resume_classifier
pip install scikit-learn pandas numpy sentence-transformers transformers pdfplumber python-docx
```

### 1.4 RoBERTa Dependencies
```bash
cd ../Roberta/roberta-multitask-model
pip install torch transformers scikit-learn pandas
```

---

## Step 2: Start the Flask Server

```bash
cd "c:\Users\Surya Srikhar\OneDrive\Documents\Desktop\Capstone_project\Project\main_cap\cap"
python app.py
```

**Expected output:**
```
 * Running on http://127.0.0.1:5000
 * WARNING: This is a development server. Do not use it in production.
 * Press CTRL+C to quit
```

✅ **Server is running on**: `http://localhost:5000`

Keep this terminal open while testing!

---

## Step 3: Test Individual Components

Open a **NEW terminal/PowerShell** to run test commands.

### Test 3.1: Health Check
```bash
curl http://localhost:5000/health
```

**Expected response:**
```json
{"status":"ok"}
```

---

### Test 3.2: Resume Classification

**Option A: Using curl with a sample resume**

First, let's create a simple test resume file:

```powershell
# Create a test resume file (for testing purposes)
$resumeContent = @"
John Doe
Email: john@example.com
Phone: +1-555-0123

EXPERIENCE
- Software Engineer at Google (5 years)
- Python, React, AWS, Machine Learning
- Led team of 3 engineers

SKILLS
Python, JavaScript, React, SQL, AWS, Docker, Kubernetes, CI/CD, Machine Learning
"@

$resumeContent | Out-File -Encoding UTF8 "test_resume.txt"
```

Then upload a real PDF resume:

```bash
# If you have a resume PDF, use:
curl -X POST -F "file=@C:\path\to\your\resume.pdf" http://localhost:5000/predict
```

**Expected response:**
```json
{
  "predicted_domain": "Software Engineer",
  "confidence": 0.85,
  "experience": {
    "years": 5,
    "level": "Senior"
  },
  "skills": ["Python", "React", "AWS", ...],
  "email": "john@example.com",
  "phone": "+1-555-0123"
}
```

---

### Test 3.3: Check RAG Available Subjects

```bash
curl http://localhost:5000/rag/available-subjects
```

**Expected response:**
```json
{
  "subjects": [
    "cn_unit1",
    "operating_systems",
    ...
  ]
}
```

> **Note**: If subjects list is empty, RAG PDFs haven't been processed yet. This is normal - we'll setup knowledge base in Test 3.4.

---

### Test 3.4: Setup RAG Knowledge Base (Important!)

Before generating questions, initialize a knowledge base from a PDF:

```bash
curl -X POST http://localhost:5000/rag/setup-knowledge-base \
  -H "Content-Type: application/json" \
  -d "{
    \"subject_name\": \"computer_networks\",
    \"pdf_path\": \"C:/Users/Surya Srikhar/OneDrive/Documents/Desktop/Capstone_project/Project/rag_system/rag_tester/samples/CN_UNIT1_MERGE.pdf\"
  }"
```

**Expected response:**
```json
{
  "success": true,
  "message": "Knowledge base 'computer_networks' created successfully",
  "subject": "computer_networks"
}
```

✅ If you get an error about PDF not found, check the file path exists.

---

### Test 3.5: Generate RAG Questions

Now generate questions from the knowledge base:

```bash
curl -X POST http://localhost:5000/rag/generate-questions \
  -H "Content-Type: application/json" \
  -d "{
    \"subject_name\": \"computer_networks\",
    \"topic\": \"TCP\",
    \"num_questions\": 2
  }"
```

**Expected response:**
```json
{
  "status": "success",
  "subject": "computer_networks",
  "topic": "TCP",
  "questions": [
    {
      "question": "Explain the three-way handshake in TCP.",
      "reference_answer": "The three-way handshake is a process used by TCP to establish...",
      "topic": "TCP",
      "source_pages": [5, 6],
      "context": "..."
    },
    {
      "question": "What is the purpose of TCP flow control?",
      "reference_answer": "TCP flow control ensures that...",
      "topic": "TCP",
      "source_pages": [8],
      "context": "..."
    }
  ],
  "count": 2
}
```

✅ **Questions generated successfully!**

---

### Test 3.6: RoBERTa Question Classification

```bash
curl -X POST http://localhost:5000/roberta/classify \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Explain the three-way handshake in TCP.\"
  }"
```

**Expected response:**
```json
{
  "intent": "explanation",
  "difficulty": "medium",
  "confidence": 0.87,
  "topics": "networking",
  "intent_confidence": 0.92,
  "difficulty_confidence": 0.85
}
```

✅ **Question classified successfully!**

---

### Test 3.7: Answer Evaluation

```bash
curl -X POST http://localhost:5000/api/evaluate \
  -H "Content-Type: application/json" \
  -d "{
    \"user_answer\": \"The three-way handshake is a process where the client sends SYN, server responds with SYN-ACK, and client sends ACK.\",
    \"reference_answer\": \"The three-way handshake in TCP is a process to establish connection. The client sends a SYN packet, the server responds with a SYN-ACK packet, and the client sends an ACK packet back.\",
    \"question\": \"Explain the three-way handshake in TCP.\",
    \"user_fill_mask\": \"SYN\",
    \"reference_fill_mask\": \"SYN\"
  }"
```

**Expected response:**
```json
{
  "score": 0.82,
  "marks": 8,
  "feedback": "Good answer with technical accuracy.",
  "fill_correct": true
}
```

✅ **Answer evaluated successfully!**

---

## Step 4: Test the UNIFIED Workflow (Complete End-to-End)

This is the **most important test** - it combines everything!

### Prepare a Test Resume File

Create a sample resume PDF (or use an existing one):

```powershell
# If you don't have a resume, I'll help create a test one
# For now, use an existing resume or we can create a text file
```

### Run the Unified Workflow

```bash
curl -X POST http://localhost:5000/workflow/interview ^
  -F "resume_file=@C:\path\to\your\resume.pdf" ^
  -F "pdf_knowledge_base=computer_networks" ^
  -F "topics[]=TCP" ^
  -F "topics[]=DNS" ^
  -F "num_questions_per_topic=2" ^
  -F "user_id=test_candidate_001"
```

**Expected response:**
```json
{
  "status": "success",
  "resume_analysis": {
    "predicted_domain": "Network Engineer",
    "confidence": 0.87,
    "experience": {
      "years": 3,
      "level": "Mid-level"
    },
    "skills": ["networking", "TCP/IP", "Linux"],
    "email": "candidate@example.com",
    "phone": "+1-555-0123"
  },
  "questions": [
    {
      "question": "Explain the three-way handshake in TCP.",
      "reference_answer": "The three-way handshake...",
      "topic": "TCP",
      "source_subject": "computer_networks",
      "source_pages": [5, 6]
    },
    {
      "question": "What is DNS and how does it work?",
      "reference_answer": "DNS (Domain Name System) is...",
      "topic": "DNS",
      "source_subject": "computer_networks",
      "source_pages": [12]
    },
    {
      "question": "Explain TCP flow control",
      "reference_answer": "TCP flow control...",
      "topic": "TCP",
      "source_subject": "computer_networks",
      "source_pages": [8]
    },
    {
      "question": "What are DNS record types?",
      "reference_answer": "DNS record types include...",
      "topic": "DNS",
      "source_subject": "computer_networks",
      "source_pages": [14]
    }
  ],
  "session": {
    "user_id": "test_candidate_001",
    "total_questions": 4,
    "session_data": {...}
  }
}
```

✅ **Complete workflow executed successfully!**

This shows:
- Resume was parsed and classified
- RAG generated domain-specific questions
- All components working together

---

## Step 5: Testing Scenarios

### Scenario A: Different Topics
```bash
curl -X POST http://localhost:5000/rag/generate-questions \
  -H "Content-Type: application/json" \
  -d "{
    \"subject_name\": \"computer_networks\",
    \"topic\": \"IP Routing\",
    \"num_questions\": 1
  }"
```

### Scenario B: Multiple Topics in Workflow
```bash
curl -X POST http://localhost:5000/workflow/interview ^
  -F "resume_file=@resume.pdf" ^
  -F "pdf_knowledge_base=computer_networks" ^
  -F "topics[]=TCP" ^
  -F "topics[]=IP" ^
  -F "topics[]=DNS" ^
  -F "num_questions_per_topic=1" ^
  -F "user_id=multi_topic_test"
```

### Scenario C: Test Answer Quality Scoring
```bash
# Bad answer
curl -X POST http://localhost:5000/api/evaluate \
  -H "Content-Type: application/json" \
  -d "{
    \"user_answer\": \"something\",
    \"reference_answer\": \"The three-way handshake in TCP is a process...\",
    \"question\": \"Explain TCP handshake\",
    \"user_fill_mask\": \"\",
    \"reference_fill_mask\": \"SYN\"
  }"

# Expected: score ~0.1 (low)
```

```bash
# Good answer
curl -X POST http://localhost:5000/api/evaluate \
  -H "Content-Type: application/json" \
  -d "{
    \"user_answer\": \"The three-way handshake is a process where the client sends SYN, server responds with SYN-ACK, and client sends ACK. This establishes a TCP connection.\",
    \"reference_answer\": \"The three-way handshake in TCP is a process to establish connection. The client sends a SYN packet, the server responds with a SYN-ACK packet, and the client sends an ACK packet back.\",
    \"question\": \"Explain the three-way handshake in TCP\",
    \"user_fill_mask\": \"SYN-ACK\",
    \"reference_fill_mask\": \"SYN-ACK\"
  }"

# Expected: score ~0.8-0.9 (high)
```

---

## Step 6: Check Logs & Errors

If something fails, check:

### 1. Flask Server Logs
Look at the terminal where you ran `python app.py`:
```
ERROR: RAG system not available
ERROR: Failed to load resume classifier
```

### 2. Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'sentence_transformers'` | Run: `pip install sentence-transformers` |
| `FileNotFoundError: PDF not found` | Check PDF path exists, use absolute path |
| `RAG system not available` | Ensure RAG system dependencies installed |
| `Port 5000 already in use` | Change port: `python app.py --port 5001` |
| `Resume classification failing` | Ensure resume file is valid PDF/DOCX |
| `Low answer scores` | Normal - evaluate more detailed answers |

---

## Step 7: Full Testing Checklist

Run through this checklist to ensure everything works:

```
✅ Step 1: Server starts without errors
   Command: python app.py
   Expected: Running on http://127.0.0.1:5000

✅ Step 2: Health check passes
   Command: curl http://localhost:5000/health
   Expected: {"status":"ok"}

✅ Step 3: RAG knowledge base setup
   Command: curl /rag/setup-knowledge-base
   Expected: success: true

✅ Step 4: RAG question generation
   Command: curl /rag/generate-questions
   Expected: 2+ questions with reference_answer

✅ Step 5: Question classification
   Command: curl /roberta/classify
   Expected: intent, difficulty, topics with confidence

✅ Step 6: Answer evaluation
   Command: curl /api/evaluate
   Expected: score between 0-1, feedback text

✅ Step 7: Resume classification
   Command: curl -F /predict
   Expected: predicted_domain, skills, experience

✅ Step 8: Unified workflow
   Command: curl /workflow/interview
   Expected: resume_analysis + questions + session

✅ Step 9: Adaptive session
   Command: curl /adaptive/session
   Expected: session created with questions

✅ Step 10: All systems integrated
   Verify: resume → domain → RAG questions → classification → scoring
```

---

## Quick Testing Commands (Copy-Paste Ready)

### Using PowerShell (Windows)

**Test 1: Health Check**
```powershell
curl http://localhost:5000/health
```

**Test 2: RAG Setup**
```powershell
$body = @{
    subject_name = "computer_networks"
    pdf_path = "C:/Users/Surya Srikhar/OneDrive/Documents/Desktop/Capstone_project/Project/rag_system/rag_tester/samples/CN_UNIT1_MERGE.pdf"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -Body $body `
  http://localhost:5000/rag/setup-knowledge-base
```

**Test 3: Generate Questions**
```powershell
$body = @{
    subject_name = "computer_networks"
    topic = "TCP"
    num_questions = 2
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -Body $body `
  http://localhost:5000/rag/generate-questions
```

**Test 4: Classify Question**
```powershell
$body = @{
    text = "Explain the three-way handshake in TCP."
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -Body $body `
  http://localhost:5000/roberta/classify
```

**Test 5: Evaluate Answer**
```powershell
$body = @{
    user_answer = "The three-way handshake is SYN, SYN-ACK, ACK."
    reference_answer = "The three-way handshake in TCP is a process where the client sends SYN, server responds with SYN-ACK, and client sends ACK."
    question = "Explain TCP handshake"
    user_fill_mask = "SYN"
    reference_fill_mask = "SYN"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -Body $body `
  http://localhost:5000/api/evaluate
```

---

## Expected Test Flow (Visual)

```
┌─────────────────────────────────────────┐
│  Start Flask Server                     │
│  python app.py                          │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Health Check                  │
│  curl /health → {"status":"ok"}         │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Setup RAG Knowledge Base      │
│  curl -X POST /rag/setup-kb → success   │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Generate RAG Questions        │
│  curl -X POST /rag/questions → 2 Q's    │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Classify Question             │
│  curl -X POST /roberta/classify → OK    │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Evaluate Answer               │
│  curl -X POST /api/evaluate → score     │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Resume Classification         │
│  curl -F /predict → domain classified   │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  ✅ Test: Unified Workflow              │
│  curl -F /workflow/interview            │
│  → Everything works together!           │
└─────────────────────────────────────────┘
```

---

## Success Criteria

Your system is **working correctly** when:

1. ✅ Server starts without errors
2. ✅ Health check returns `{"status":"ok"}`
3. ✅ RAG setup completes successfully
4. ✅ Questions generated with reference answers
5. ✅ Question classification provides intent/difficulty/topics
6. ✅ Answers evaluated with scores 0-1
7. ✅ Resume classified with domain & skills
8. ✅ Unified workflow returns everything in one response
9. ✅ No errors in Flask server terminal

---

## Next Steps After Testing

Once all tests pass:

1. **Explore the web UI**: Open `http://localhost:5000/` in browser
2. **Test with real resumes**: Upload actual resume PDFs
3. **Add more PDFs**: Place PDFs in `rag_system/rag_tester/samples/`
4. **Setup more knowledge bases**: Initialize different subjects
5. **Test adaptive learning**: Run multiple questions and check difficulty adjustment
6. **Deploy**: Move to production server when ready

---

**Happy Testing! 🚀**
