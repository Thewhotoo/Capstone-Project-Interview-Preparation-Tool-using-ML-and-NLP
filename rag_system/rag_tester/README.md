# 📚 PDF-Based RAG System for Interview Question Generation

A complete **Retrieval-Augmented Generation (RAG)** system that extracts knowledge from PDF files and generates technical interview questions using AI.

## 🎯 Features

✅ **PDF Ingestion** - Automatically extracts text from PDFs and creates embeddings  
✅ **Vector Search** - Uses FAISS for fast semantic similarity search  
✅ **Question Generation** - Generates interview questions using FLAN-T5 LLM  
✅ **Answer Evaluation** - Scores student answers against reference material  
✅ **Interactive Mode** - Ask questions about any topic in your knowledge base  
✅ **Batch Processing** - Generate questions for multiple topics at once  

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Knowledge Base from PDF

```bash
python ingestor.py
```

This will:
- Read `samples/CN_UNIT1_MERGE.pdf`
- Extract all text from PDF pages
- Create embeddings using SentenceTransformer
- Save FAISS index to `knowledge_base/`

### 3. Run Interactive RAG System

```bash
python main.py
```

Choose option **1** for interactive mode, then:
- Enter a topic (e.g., "OSI Model")
- System retrieves relevant content from PDF
- Generates an interview question
- Evaluates your answer

## 📋 System Components

### Core Modules

| Module | Purpose |
|--------|---------|
| `ingestor.py` | Extracts PDF text and builds FAISS index |
| `retrieval.py` | Searches index for relevant content |
| `generate.py` | Generates questions using FLAN-T5 |
| `evaluate.py` | Scores answers using semantic similarity |
| `test_rag.py` | Basic testing script |
| `main.py` | Interactive CLI interface |

### Knowledge Base Structure

```
knowledge_base/
├── cn_unit1.index          # FAISS vector index
└── cn_unit1_chunks.json    # Text chunks with page numbers
```

## 🔧 Usage Examples

### Interactive Mode
```bash
python main.py
# Select option 1
# Enter topic: "TCP/IP Protocol"
# System generates question
# You enter your answer
# System evaluates your response
```

### Programmatic Usage

```python
from retrieval import retrieve_relevant_content
from generate import generate_interview_question
from evaluate import evaluate_answer

# Retrieve content
results = retrieve_relevant_content("cn_unit1", "Routing Algorithms", top_k=3)

# Generate question
context = results[0]['text']
question = generate_interview_question(context)

# Evaluate answer
score = evaluate_answer("Student answer here", context)
print(f"Score: {score['score']}/100, Grade: {score['grade']}")
```

### Batch Generate Questions

Create a file `topics.txt`:
```
OSI Model Layers
TCP/IP Protocol
Network Routing
Data Transmission
Error Detection and Correction
```

Then run:
```python
from main import batch_generate_questions
batch_generate_questions("topics.txt")
```

## 📊 How It Works

```
1. INGESTION
   PDF → Text Extraction → SentenceTransformer Embeddings → FAISS Index

2. RETRIEVAL
   User Query → Encode to Vector → FAISS Search → Top-K Results

3. GENERATION
   Retrieved Context → FLAN-T5 Model → Interview Question

4. EVALUATION
   Student Answer vs Reference → Cosine Similarity → Score + Feedback
```

## 🔍 API Reference

### retrieval.py

```python
# Load knowledge base
index, chunks = load_knowledge_base("cn_unit1")

# Retrieve content
results = retrieve_relevant_content("cn_unit1", "Query", top_k=5)
# Returns: [{page, text, distance, relevance_score}, ...]

# Get best single context
context = get_best_context("cn_unit1", "Query")

# Get context with page refs
text, pages = get_context_with_pages("cn_unit1", "Query", top_k=2)
```

### generate.py

```python
# Generate question
question = generate_interview_question(context, concept="Topic")

# Generate reference answer
answer = generate_reference_answer(context)

# Generate explanation
explanation = generate_explanation(context, "Topic")
```

### evaluate.py

```python
# Evaluate single answer
result = evaluate_answer("Student answer", "Reference answer")
# Returns: {score, grade, feedback, ...}

# Compare two answers
comparison = compare_answers("Answer 1", "Answer 2")

# Evaluate multiple
results = evaluate_multiple_answers(["Answer1", "Answer2"], "Reference")
```

## ⚙️ Configuration

Edit `main.py` to customize:

```python
SUBJECT_NAME = "cn_unit1"           # Change subject
PDF_PATH = "samples/CN_UNIT1_MERGE.pdf"  # Change PDF source
```

Edit `ingestor.py` to process different PDFs:

```python
ingest_subject("path/to/your.pdf", "subject_name")
```

## 📈 Performance Tips

1. **First Run**: Ingestion may take 2-5 minutes depending on PDF size
2. **Model Loading**: FLAN-T5 loads on first use (~1GB memory)
3. **Embeddings**: Cached in FAISS index for fast retrieval
4. **GPU Support**: Install CUDA for faster inference (optional)

## 🐛 Troubleshooting

### Knowledge base not found
```
Solution: Run python ingestor.py first
```

### Model download fails
```
Solution: Ensure internet connection, or pre-download:
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('google/flan-t5-small')"
```

### Slow question generation
```
Solution: Use smaller model or GPU acceleration
```

## 📚 Example Output

```
Topic: OSI Model layers

Retrieved Content (Top 2 matches):
  [1] Page 5 - Relevance: 85%
      "The OSI model has 7 layers: Physical, Data Link, Network..."

Generated Question:
  What are the seven layers of the OSI model and what is the primary function of the Transport layer?

Reference Answer:
  The OSI model consists of Physical, Data Link, Network, Transport, Session, Presentation, and Application layers...

Your Answer:
  "The OSI model has 7 layers used for network communication..."

Evaluation:
  Score: 72.5/100
  Grade: B
  Feedback: Good! Your answer is mostly correct and covers key points.
```

## 🔄 Advantages Over Web Scraping

| Aspect | PDF-Based RAG | Web Scraping |
|--------|---------------|-------------|
| **Cost** | Free (one-time) | Expensive API calls |
| **Reliability** | Consistent data | Variable quality |
| **Setup Time** | ~5 minutes | Setup + API keys |
| **Data Control** | Full control | Limited |
| **Latency** | Instant local search | Network dependent |
| **Scalability** | Add PDFs easily | Need more API credits |

## 📝 Notes

- PDF text extraction quality depends on PDF format
- Semantic search finds conceptually similar content, not keyword matches
- Answer evaluation uses cosine similarity on embeddings
- Models are loaded on first use (~2GB total memory)

## 🛠️ Future Enhancements

- [ ] Support for multiple PDFs
- [ ] Fine-tuning question generation for specific domains
- [ ] Multi-language support
- [ ] Web interface with Flask/Streamlit
- [ ] Answer key management
- [ ] Student progress tracking
- [ ] Difficulty level adjustment

## 📄 License

Free to use for educational purposes.

---

**Built with ❤️ for Computer Science Education**
