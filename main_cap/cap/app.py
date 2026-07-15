"""
Capstone Interview System - Flask API
Integrates with existing UI and all components
"""

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import sys
import logging

# Load .env file (GEMINI_API_KEY etc.)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Startup validation: GEMINI_API_KEY ──────────────────────────────────────
_gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not _gemini_key:
    logger.error(
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  GEMINI_API_KEY is NOT set!                                ║\n"
        "║  Resume upload and Gemini features will not work.          ║\n"
        "║  Set GEMINI_API_KEY in main_cap/cap/.env                   ║\n"
        "╚══════════════════════════════════════════════════════════════╝"
    )
else:
    logger.info("GEMINI_API_KEY loaded (%s...)", _gemini_key[:8])

app = Flask(__name__, template_folder="templates")

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "../..")

# Add resume_classifier to path for real parsing and classification
RESUME_CLASSIFIER_DIR = os.path.join(PROJECT_ROOT, "resume_classifier")
if RESUME_CLASSIFIER_DIR not in sys.path:
    sys.path.insert(0, RESUME_CLASSIFIER_DIR)

# ── RAG Integration ───────────────────────────────────────────────────────────
try:
    from rag_integration import rag_generator as _rag_gen
    _rag_available = _rag_gen.rag_available and bool(_rag_gen.get_available_subjects())
except ImportError:
    _rag_available = False
    _rag_gen = None

# Ensure resume_classifier stays at top of sys.path (RAG path may have shadowed it)
if RESUME_CLASSIFIER_DIR in sys.path:
    sys.path.remove(RESUME_CLASSIFIER_DIR)
sys.path.insert(0, RESUME_CLASSIFIER_DIR)

# ── RoBERTa Multitask Model ───────────────────────────────────────────────────
ROBERTA_DIR = os.path.join(PROJECT_ROOT, "Roberta", "roberta-multitask-model")
if ROBERTA_DIR not in sys.path:
    sys.path.insert(0, ROBERTA_DIR)

_roberta_predictors = None

def _get_roberta_predictors():
    """Lazy-load the three RoBERTa prediction functions."""
    global _roberta_predictors
    if _roberta_predictors is None:
        try:
            from inference.predict_intent import predict_intent
            from inference.predict_difficulty import predict_difficulty
            from inference.predict_topic import predict_topic
            _roberta_predictors = {
                "intent": predict_intent,
                "difficulty": predict_difficulty,
                "topic": predict_topic,
            }
            logger.info("RoBERTa inference pipeline loaded (rule-based fallback)")
        except ImportError as e:
            logger.warning(f"RoBERTa inference unavailable: {e}")
            _roberta_predictors = False
    return _roberta_predictors if _roberta_predictors is not False else None

# Module-level RAG question cache for /api/next_question
_rag_question_pool = []      # list of question dicts
_rag_question_counter = 0    # auto-incrementing ID for RAG questions
_asked_rag_ids = set()       # IDs already asked

# Module-level adaptive session storage
_adaptive_sessions = {}      # session_id -> session state dict

import time

# ═══════════════════════════════════════════════════════════════════════════
# WEB UI ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    """Serve the web UI"""
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "ok"}), 200

@app.route("/api/get-domain-quiz", methods=["POST"])
def get_domain_quiz():
    """
    Generate Resume Discussion questions from the Candidate Profile.

    Request:
        {"session_id": "...", "domain": "...", "skills": [...]}

    If session_id maps to a stored Candidate Profile, questions are derived
    from projects, interview_seeds, experience, technologies, and skills.

    Falls back to hardcoded MCQ banks when no profile is available.
    """
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id", "")
        domain = data.get("domain", "Software Engineer")
        skills = data.get("skills", [])

        # Try to load the Candidate Profile (single source of truth)
        profile = _candidate_profiles.get(session_id) if session_id else None

        if profile:
            questions = _generate_resume_discussion_questions(profile)
            return jsonify({
                "status": "success",
                "mode": "resume_discussion",
                "domain": domain,
                "total_questions": len(questions),
                "quiz": questions,
            }), 200

        # Fallback: hardcoded MCQs when no profile available
        quiz_questions = _hardcoded_quiz(domain)
        return jsonify({
            "status": "success",
            "mode": "quiz",
            "domain": domain,
            "total_questions": len(quiz_questions),
            "quiz": quiz_questions,
        }), 200

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 400


def _generate_resume_discussion_questions(profile: dict, num_questions: int = 10):
    """
    Build open-ended Resume Discussion questions from the Candidate Profile.

    Priority order:
        1. interview_seeds (from projects)
        2. project titles / summaries
        3. experience entries
        4. technologies (from projects)
        5. skills

    Returns a list of dicts compatible with the existing quiz renderer:
        {question, options, answer, difficulty, _discussion: True}
    """
    import random

    questions: list[dict] = []
    used_seeds: set[str] = set()

    # ── 1. Questions from interview_seeds ──────────────────────────────
    for project in profile.get("projects", []):
        title = project.get("title", "your project")
        for seed in project.get("interview_seeds", []):
            if seed.lower() in used_seeds:
                continue
            used_seeds.add(seed.lower())
            q_text = f"Regarding {title}: {seed}"
            questions.append({
                "question": q_text,
                "options": [
                    "I'd like to discuss this in detail",
                    "Let me explain my approach",
                ],
                "answer": 0,
                "difficulty": "Medium",
                "_discussion": True,
            })

    # ── 2. Questions about project technologies ────────────────────────
    for project in profile.get("projects", []):
        title = project.get("title", "your project")
        techs = project.get("technologies", [])
        if techs:
            tech_str = ", ".join(techs[:3])
            q_text = f"I see {tech_str} listed under {title}. Can you walk me through how you used them?"
            questions.append({
                "question": q_text,
                "options": [
                    "I'd like to discuss this in detail",
                    "Let me explain my approach",
                ],
                "answer": 0,
                "difficulty": "Medium",
                "_discussion": True,
            })

    # ── 3. Questions from experience ───────────────────────────────────
    for exp in profile.get("experience", []):
        role = exp.get("role", "")
        company = exp.get("company", "")
        if role and company:
            q_text = (
                f"Tell me about your time as {role} at {company}. "
                "What were the most technically challenging aspects?"
            )
            questions.append({
                "question": q_text,
                "options": [
                    "I'd like to discuss this in detail",
                    "Let me explain my approach",
                ],
                "answer": 0,
                "difficulty": "Medium",
                "_discussion": True,
            })

    # ── 4. Technology-specific questions ───────────────────────────────
    all_techs: list[str] = []
    for project in profile.get("projects", []):
        all_techs.extend(project.get("technologies", []))
    for tech in list(dict.fromkeys(all_techs))[:4]:
        q_text = (
            f"I notice {tech} in your projects. "
            f"Why did you choose {tech}, and what alternatives did you consider?"
        )
        questions.append({
            "question": q_text,
            "options": [
                "I'd like to discuss this in detail",
                "Let me explain my approach",
            ],
            "answer": 0,
            "difficulty": "Medium",
            "_discussion": True,
        })

    # ── 5. Skill-based questions ───────────────────────────────────────
    skills = profile.get("skills", [])
    if skills:
        q_text = (
            f"You list {skills[0]} as a key skill. "
            "Can you describe a project where you applied it in production?"
        )
        questions.append({
            "question": q_text,
            "options": [
                "I'd like to discuss this in detail",
                "Let me explain my approach",
            ],
            "answer": 0,
            "difficulty": "Medium",
            "_discussion": True,
        })

    # ── Shuffle and cap ────────────────────────────────────────────────
    random.shuffle(questions)
    return questions[:num_questions]


def _hardcoded_quiz(domain):
    """Return the static question bank for a domain."""
    all_questions = {
            "Software Engineer": [
                # EASY
                {"question": "What does OOP stand for?", "options": ["Object Oriented Programming", "Object Organization Protocol", "Online Operating Process", "Object Output Parameter"], "answer": 0, "difficulty": "Easy"},
                {"question": "Which of these is NOT a SOLID principle?", "options": ["Single Responsibility", "Open/Closed", "Liskov Substitution", "Interface Inheritance"], "answer": 3, "difficulty": "Easy"},
                {"question": "What is version control primarily used for?", "options": ["Encrypting data", "Tracking code changes and collaboration", "Compiling code", "Hosting websites"], "answer": 1, "difficulty": "Easy"},
                
                # MEDIUM
                {"question": "What is the difference between a class and an interface?", "options": ["Interfaces define contracts; classes implement behavior", "They are the same", "Classes are for data; interfaces are for methods", "Interfaces cannot have methods"], "answer": 0, "difficulty": "Medium"},
                {"question": "Explain the Single Responsibility Principle (SRP):", "options": ["A class should do many things", "Each class should have one reason to change", "Classes should inherit from one parent", "Functions should be very long"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is the purpose of design patterns in software development?", "options": ["To make code slower", "To provide reusable solutions for common problems", "To replace frameworks", "To eliminate functions"], "answer": 1, "difficulty": "Medium"},
                
                # HARD
                {"question": "In SOLID principles, the Liskov Substitution Principle states that:", "options": ["Objects should be open for extension but closed for modification", "Subclasses should be substitutable for their base classes without breaking the system", "High-level modules should not depend on low-level modules", "Depend on abstractions, not concrete implementations"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the primary difference between composition and inheritance in OOP?", "options": ["Inheritance is faster than composition", "Composition provides flexibility and avoids tight coupling; inheritance creates an 'is-a' relationship", "They are functionally identical", "Inheritance is only for interfaces"], "answer": 1, "difficulty": "Hard"},
                {"question": "In a microservices architecture, what is the primary challenge with distributed transactions?", "options": ["They are slower than monolithic transactions", "ACID guarantees don't hold across services; need eventual consistency and saga pattern", "Microservices don't support transactions", "They require a central database"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the difference between REST and GraphQL?", "options": ["GraphQL always requires more bandwidth", "REST uses multiple endpoints; GraphQL uses single endpoint with flexible queries", "They are identical", "REST cannot query nested data"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the difference between mutable and immutable objects in programming:", "options": ["They have no difference", "Mutable can be changed; immutable cannot; immutability aids concurrency and debugging", "Mutable objects are always slower", "Immutable objects cannot be created"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is a deadlock in concurrent programming and how do you prevent it?", "options": ["A type of lock statement", "Situation where threads wait indefinitely; prevent by lock ordering, timeouts, or deadlock detection", "A hardware issue", "Cannot be prevented"], "answer": 1, "difficulty": "Hard"},
            ],
            
            "Network Engineer": [
                # EASY
                {"question": "What does TCP stand for?", "options": ["Transfer Control Protocol", "Transmission Control Protocol", "Transfer Communication Process", "Temporary Connectivity Protocol"], "answer": 1, "difficulty": "Easy"},
                {"question": "How many layers does the OSI model have?", "options": ["5", "6", "7", "8"], "answer": 2, "difficulty": "Easy"},
                {"question": "What is the primary function of a router?", "options": ["To encrypt data", "To forward packets between networks", "To store files", "To display web pages"], "answer": 1, "difficulty": "Easy"},
                
                # MEDIUM
                {"question": "What is the difference between UDP and TCP?", "options": ["UDP is connection-oriented and reliable; TCP is connectionless and fast", "TCP is connection-oriented and reliable; UDP is connectionless and fast", "They are identical", "UDP is used for web browsing"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is DHCP used for?", "options": ["Encryption", "Automatic IP address assignment", "Domain management", "Packet filtering"], "answer": 1, "difficulty": "Medium"},
                {"question": "Explain the purpose of a firewall:", "options": ["To speed up networks", "To filter and control traffic based on security rules", "To increase bandwidth", "To replace routers"], "answer": 1, "difficulty": "Medium"},
                
                # HARD
                {"question": "What is the main purpose of the TCP window size in congestion control?", "options": ["To display network graphs", "To control how much data can be in flight before acknowledgment is needed", "To encrypt packets", "To route packets"], "answer": 1, "difficulty": "Hard"},
                {"question": "In BGP (Border Gateway Protocol), what is an AS (Autonomous System)?", "options": ["A single server", "A collection of IP networks under common administration following a single routing policy", "A type of firewall", "An encryption algorithm"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the difference between a stateless and stateful firewall?", "options": ["Stateless is more secure", "Stateless filters packets independently; stateful tracks connection states and context", "They are the same", "Stateful is only for routers"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the concept of subnetting and CIDR notation:", "options": ["A way to encrypt networks", "A method to divide networks into smaller subnets using prefix notation", "A type of firewall", "Only for IPv6"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the difference between NAT and PAT in networking?", "options": ["They are the same", "NAT maps IPs; PAT (Port Address Translation) maps IPs and ports for multiple internal hosts to share one external IP", "PAT is faster", "NAT is only for IPv4"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the three-way handshake in TCP connection establishment:", "options": ["Not necessary for TCP", "SYN -> SYN-ACK -> ACK; establishes connection, exchange of sequence numbers", "Only used in UDP", "Happens automatically without packets"], "answer": 1, "difficulty": "Hard"},
            ],
            
            "Data Scientist": [
                # EASY
                {"question": "What is the purpose of train/test split in machine learning?", "options": ["To save storage", "To evaluate model performance on unseen data", "To increase model speed", "To reduce data collection costs"], "answer": 1, "difficulty": "Easy"},
                {"question": "What does 'overfitting' mean?", "options": ["Model is too small", "Model performs well on training data but poorly on test data", "Model is very fast", "Model has too few parameters"], "answer": 1, "difficulty": "Easy"},
                {"question": "What is supervised learning?", "options": ["Learning without labels", "Learning from labeled data to predict outputs", "Learning without a teacher", "Learning only from images"], "answer": 1, "difficulty": "Easy"},
                
                # MEDIUM
                {"question": "Explain the purpose of feature scaling/normalization:", "options": ["To make data smaller", "To bring features to similar scale, improving model performance and training speed", "To remove outliers", "To reduce dimensionality"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is cross-validation and why is it important?", "options": ["Validating multiple models", "Dividing data into k folds to get robust performance estimate", "Testing on all data", "Only for deep learning"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is the difference between precision and recall?", "options": ["They are the same", "Precision: correct positives/predicted positives; Recall: correct positives/actual positives", "Recall is always higher", "Precision is only for regression"], "answer": 1, "difficulty": "Medium"},
                
                # HARD
                {"question": "What is the difference between bagging and boosting in ensemble methods?", "options": ["Bagging is faster; boosting is more accurate", "Bagging uses parallel training; boosting trains sequentially on misclassified samples", "They produce identical results", "Boosting can only be used for regression"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the vanishing gradient problem in deep neural networks:", "options": ["Learning rate too high", "Gradients become exponentially small during backpropagation, preventing weight updates in early layers", "Loss function is missing", "No gradients exist"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the purpose of batch normalization in neural networks?", "options": ["To make model smaller", "To normalize layer inputs per batch, reducing internal covariate shift and allowing higher learning rates", "To reduce parameters", "To encrypt data"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the difference between L1 and L2 regularization:", "options": ["They are the same", "L1 (Lasso) uses absolute values for feature selection; L2 (Ridge) uses squared values for weight shrinkage", "L1 is slower", "L2 cannot handle sparse data"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is a ROC curve and what does AUC represent?", "options": ["Chart of costs", "Curve plotting True Positive Rate vs False Positive Rate; AUC measures overall classification performance", "Only for regression", "Used only in clustering"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the difference between parametric and non-parametric models:", "options": ["Parametric is faster", "Parametric assumes fixed structure; non-parametric is flexible and data-driven", "They require same data size", "Non-parametric cannot make predictions"], "answer": 1, "difficulty": "Hard"},
            ],
            
            "Database Engineer": [
                # EASY
                {"question": "What does ACID stand for in databases?", "options": ["Atomicity, Consistency, Isolation, Durability", "Assessment, Configuration, Integration, Data", "Automatic, Control, Input, Database", "Analysis, Compression, Indexing, Distribution"], "answer": 0, "difficulty": "Easy"},
                {"question": "What is a primary key?", "options": ["A key that opens the database", "A unique identifier for each row in a table", "The most important column", "A type of password"], "answer": 1, "difficulty": "Easy"},
                {"question": "What is the purpose of a foreign key?", "options": ["To encrypt data", "To establish relationships between tables", "To store large files", "To speed up queries"], "answer": 1, "difficulty": "Easy"},
                
                # MEDIUM
                {"question": "Explain normalization in database design:", "options": ["Making data alphabetical", "Organizing data to minimize redundancy and improve data integrity", "Removing all columns", "Making all columns the same size"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is the difference between INNER JOIN and LEFT JOIN?", "options": ["INNER JOIN includes unmatched rows; LEFT JOIN only matched", "INNER JOIN only matched rows; LEFT JOIN includes all left table rows plus matches", "They are identical", "LEFT JOIN is always faster"], "answer": 1, "difficulty": "Medium"},
                {"question": "What is denormalization and when is it used?", "options": ["Removing a database", "Intentionally introducing redundancy for performance; used when read performance is critical", "Only for small databases", "Makes queries slower"], "answer": 1, "difficulty": "Medium"},
                
                # HARD
                {"question": "What is the difference between a clustered and non-clustered index?", "options": ["Clustered is faster; non-clustered is slower", "Clustered determines physical row order (one per table); non-clustered is separate structure (multiple allowed)", "They are identical", "Non-clustered can only be on strings"], "answer": 1, "difficulty": "Hard"},
                {"question": "In NoSQL databases, what is eventual consistency?", "options": ["Database is always consistent", "After write, reads may return stale data but will eventually reflect the write", "NoSQL has no consistency", "All nodes update simultaneously"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain the CAP theorem in distributed databases:", "options": ["It has no relevance", "Only Consistency, Availability, OR Partition tolerance can be guaranteed simultaneously; choose two", "All three can be achieved", "Only for relational databases"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is a write-heavy vs read-heavy database optimization trade-off?", "options": ["No trade-off exists", "Write-heavy prioritizes insert/update speed; read-heavy uses indexing and denormalization for fast queries", "Write-heavy is always better", "Only applies to SQL databases"], "answer": 1, "difficulty": "Hard"},
                {"question": "Explain sharding and when it is used:", "options": ["A type of password", "Horizontal partitioning of data across multiple servers; used when data is too large for single server", "Deleting old data", "Compressing database files"], "answer": 1, "difficulty": "Hard"},
                {"question": "What is the difference between pessimistic and optimistic locking?", "options": ["They are the same", "Pessimistic locks before access; optimistic assumes no conflict and checks at commit; optimistic better for low contention", "Pessimistic is always better", "Only for specific databases"], "answer": 1, "difficulty": "Hard"},
            ]
        }

    return all_questions.get(domain, all_questions["Software Engineer"])

# ── In-memory Candidate Profile store ────────────────────────────────────────
# Keyed by session: stores the full Gemini-generated profile so downstream
# modules (quiz, interview) never need to re-parse the resume.
_candidate_profiles = {}   # session_id -> Candidate Profile dict


@app.route("/api/classify-resume", methods=["POST"])
def classify_resume():
    """
    Parse an uploaded resume with a single Gemini 2.5 Flash call.
    The generated Candidate Profile is stored in memory for the lifetime of the
    session so that dashboard, quiz, and interview modules consume it directly
    without re-parsing.

    Returns the profile in the exact format the frontend already expects.
    """
    import tempfile
    import uuid

    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Validate extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".docx", ".doc", ".txt"]:
            return jsonify({"error": "Only PDF and DOCX files are supported"}), 400

        # Save to a temp file so the parser can read it from disk
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            # 1. Extract raw text from the resume
            if ext == ".pdf":
                from candidate_profile_generator import extract_text_from_pdf
                text = extract_text_from_pdf(tmp_path)
            else:
                # Fallback to existing parser for DOCX / DOC / TXT
                from src.parser import extract_text
                text = extract_text(tmp_path)

            if not text or len(text.strip()) < 50:
                return jsonify({"error": "Could not extract enough text from resume"}), 400

            # 2. Generate Candidate Profile with a single Gemini call
            from candidate_profile_generator import (
                generate_candidate_profile,
                profile_to_frontend_format,
            )

            profile = generate_candidate_profile(text)

            # 3. Store in memory (keyed by a generated session ID)
            session_id = f"profile_{uuid.uuid4().hex[:12]}"
            _candidate_profiles[session_id] = profile

            # 4. Convert to frontend format and attach session_id
            result = profile_to_frontend_format(profile)
            result["session_id"] = session_id

            logger.info(
                "Candidate profile generated for session %s: domain=%s",
                session_id,
                result.get("predicted_domain"),
            )
            return jsonify(result), 200

        finally:
            # Clean up temp file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")

    except RuntimeError as e:
        # Gemini-specific errors (rate limit, timeout, malformed JSON)
        logger.error("Gemini profile generation failed: %s", e)
        return jsonify({"error": str(e)}), 502

    except Exception as e:
        logger.error(f"Resume classification error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/candidate-profile/<session_id>", methods=["GET"])
def get_candidate_profile(session_id):
    """
    Retrieve a stored Candidate Profile by session ID.
    Downstream modules use this instead of re-parsing the resume.
    """
    profile = _candidate_profiles.get(session_id)
    if not profile:
        return jsonify({"error": "Profile not found or session expired"}), 404
    return jsonify(profile), 200

# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS FOR UI
# ═══════════════════════════════════════════════════════════════════════════

# Sample data for testing
SAMPLE_QUESTIONS = [
    {
        "sample_id": 1,
        "question": "Explain the three-way handshake in TCP.",
        "reference_answer": "The three-way handshake is a process where the client sends a SYN packet, the server responds with a SYN-ACK packet, and the client sends an ACK packet back. This establishes a TCP connection.",
        "topic": "TCP",
        "difficulty": "medium",
        "fill_mask": {"question": "What is the first packet sent in TCP handshake?", "answer": "SYN"}
    },
    {
        "sample_id": 2,
        "question": "What is the purpose of DNS?",
        "reference_answer": "DNS (Domain Name System) translates domain names into IP addresses. It allows users to access websites using human-readable names instead of IP addresses.",
        "topic": "DNS",
        "difficulty": "easy",
        "fill_mask": {"question": "DNS translates ___ into IP addresses", "answer": "domain names"}
    },
    {
        "sample_id": 3,
        "question": "Explain IP routing and how packets are forwarded.",
        "reference_answer": "IP routing is the process of forwarding packets from one network to another based on IP addresses. Routers use routing tables to determine the next hop for each packet.",
        "topic": "IP Routing",
        "difficulty": "hard",
        "fill_mask": {"question": "Routers use ___ to determine packet routing", "answer": "routing tables"}
    },
    {
        "sample_id": 4,
        "question": "What is UDP and how is it different from TCP?",
        "reference_answer": "UDP (User Datagram Protocol) is a connectionless protocol that does not establish a connection before sending data. Unlike TCP, UDP is faster but less reliable.",
        "topic": "UDP",
        "difficulty": "medium",
        "fill_mask": {"question": "UDP is a ___ protocol", "answer": "connectionless"}
    },
    {
        "sample_id": 5,
        "question": "Explain the concept of network congestion control.",
        "reference_answer": "Congestion control is a mechanism that prevents network overload by regulating the rate at which data is sent. TCP uses algorithms like Reno and Cubic for congestion control.",
        "topic": "Congestion Control",
        "difficulty": "hard",
        "fill_mask": {"question": "TCP uses ___ algorithm for congestion control", "answer": "Reno"}
    }
]

@app.route("/api/next_question", methods=["POST"])
def next_question():
    """
    Get next question for the interview.
    Tries RAG open-ended questions first (if available), falls back to hardcoded.
    Request: {"asked_ids": [], "difficulty": "medium", "topic": "All"}
    """
    global _rag_question_pool, _rag_question_counter, _asked_rag_ids

    try:
        data = request.get_json() or {}
        asked_ids = data.get("asked_ids", [])
        target_difficulty = data.get("difficulty", "medium")
        target_topic = data.get("topic", "All")

        # ── Seed RAG question pool on first call (if available) ───────────
        if _rag_available and not _rag_question_pool:
            try:
                _rag_question_counter = 0
                for topic in ["TCP", "DNS", "IP Routing", "UDP", "Congestion Control"]:
                    rags = _rag_gen.generate_open_questions("cn_unit1", topic, num_questions=2)
                    for r in rags:
                        _rag_question_counter += 1
                        # Build a fill_mask from the reference_answer
                        fill_mask = _make_fill_mask(r.get("reference_answer", ""))
                        _rag_question_pool.append({
                            "sample_id": 1000 + _rag_question_counter,
                            "question": r["question"],
                            "reference_answer": r.get("reference_answer", ""),
                            "topic": r.get("topic", topic),
                            "difficulty": "medium",
                            "fill_mask": fill_mask,
                            "_source": "rag",
                        })
                logger.info(f"Seeded {len(_rag_question_pool)} RAG questions")
            except Exception as e:
                logger.warning(f"RAG pool seeding failed: {e}")

        # ── Try RAG questions first ───────────────────────────────────────
        if _rag_question_pool:
            available_rag = [
                q for q in _rag_question_pool
                if q["sample_id"] not in _asked_rag_ids
                and q["sample_id"] not in asked_ids
                and (target_difficulty == "All" or q.get("difficulty") == target_difficulty)
                and (target_topic == "All" or target_topic in q.get("topic", ""))
            ]
            if not available_rag:
                # Relax difficulty/topic filter, just avoid already-asked
                available_rag = [
                    q for q in _rag_question_pool
                    if q["sample_id"] not in _asked_rag_ids
                    and q["sample_id"] not in asked_ids
                ]
            if available_rag:
                import random as _rng
                chosen = _rng.choice(available_rag)
                _asked_rag_ids.add(chosen["sample_id"])
                return jsonify({"status": "success", "data": chosen}), 200

        # ── Fallback: hardcoded questions ─────────────────────────────────
        available = [
            q for q in SAMPLE_QUESTIONS
            if q["sample_id"] not in asked_ids
            and (target_difficulty == "All" or q.get("difficulty") == target_difficulty)
            and (target_topic == "All" or target_topic in q.get("topic", ""))
        ]
        if not available:
            available = [q for q in SAMPLE_QUESTIONS if q["sample_id"] not in asked_ids]
        if not available:
            return jsonify({"status": "completed"}), 200

        import random
        question = random.choice(available)
        return jsonify({"status": "success", "data": question}), 200

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 400


def _make_fill_mask(reference_answer):
    """
    Create a fill-in-the-blank question from a reference answer.
    Picks the longest meaningful word (>5 chars) and blanks it out.
    """
    import re as _re
    words = _re.findall(r"[A-Za-z\-]+", reference_answer)
    technical = [w for w in words if len(w) > 5 and w.lower() not in
                 {"system", "network", "process", "protocol", "processes", "between", "before", "establish", "connection", "mechanism", "through", "different", "without", "requests", "response"}]
    if not technical:
        technical = [w for w in words if len(w) > 5]
    if not technical:
        technical = words[-2:] if len(words) >= 2 else [words[0]] if words else ["this"]

    key_term = technical[0]
    # Blank it out in the first sentence
    first_sentence = _re.split(r"[.!?]", reference_answer)[0]
    blanked = first_sentence.replace(key_term, "___", 1)
    if blanked == first_sentence:
        # If word not in first sentence, prepend a prompt
        blanked = f"Complete: ... {key_term} ..."

    return {"question": blanked, "answer": key_term}

@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """
    Evaluate user's answer with STRICT gibberish detection and LENIENT proper answers
    Request: {"user_answer": "...", "reference_answer": "...", "question": "...", "user_fill_mask": "...", "reference_fill_mask": "...", "fill_question": "..."}
    """
    try:
        data = request.get_json() or {}
        user_answer = data.get("user_answer", "").strip().lower()
        ref_answer = data.get("reference_answer", "").strip().lower()
        question = data.get("question", "").strip().lower()
        user_fill = data.get("user_fill_mask", "").strip().lower()
        ref_fill = data.get("reference_fill_mask", "").strip().lower()
        fill_question = data.get("fill_question", "").strip().lower()
        
        # ═══════════════════════════════════════════════════════════════
        # MAIN ANSWER EVALUATION (STRICT with gibberish, LENIENT with correct)
        # ═══════════════════════════════════════════════════════════════
        
        def is_gibberish(text):
            """Detect if answer is gibberish/nonsense"""
            if len(text) < 5:
                return True
            
            gibberish_patterns = [
                "routing packet",  # Wrong answer for TCP handshake
                "xxxx", "asdf", "qwerty", "zzzzz",  # keyboard gibberish
                "blah", "bla bla", "idk", "dunno", "no idea",
                "random", "whatever", "test", "hello world",
            ]
            
            for pattern in gibberish_patterns:
                if pattern in text:
                    return True
            
            # Check if answer has too many random/unrelated words
            if any(word in text for word in ["lol", "haha", "wtf", "omg"]):
                return True
                
            return False
        
        def extract_key_concepts(answer_text):
            """Extract important technical terms from answer"""
            words = set(answer_text.split())
            return words
        
        def semantic_score(user_text, ref_text, question_text):
            """Calculate semantic relevance score"""
            user_concepts = extract_key_concepts(user_text)
            ref_concepts = extract_key_concepts(ref_text)
            question_concepts = extract_key_concepts(question_text)
            
            # Check overlap with reference answer
            ref_overlap = len(user_concepts & ref_concepts)
            
            # Check overlap with question (should mention related concepts)
            question_overlap = len(user_concepts & question_concepts)
            
            # Total unique meaningful words in user answer
            answer_quality = len(user_text.split())
            
            # Calculate base score
            if ref_overlap >= 3:
                # Good overlap with reference - LENIENT
                base_score = 0.85 + (ref_overlap * 0.05)
            elif ref_overlap == 2:
                # Some overlap - MEDIUM
                base_score = 0.70
            elif ref_overlap == 1:
                # Minimal overlap
                base_score = 0.50
            elif question_overlap >= 2 and answer_quality > 10:
                # Related to question but not perfectly matching reference
                base_score = 0.65
            else:
                # No meaningful overlap - STRICT
                base_score = 0.20
            
            # Adjust for answer length (proper answers are detailed)
            if answer_quality < 5:
                base_score *= 0.6  # Too short
            elif answer_quality > 50:
                base_score *= 1.05  # Detailed
            
            return min(0.99, base_score)
        
        # Evaluate main answer
        if is_gibberish(user_answer):
            score = 0.0
            feedback = "❌ Gibberish answer detected. Please provide a meaningful technical response."
        elif not user_answer:
            score = 0.0
            feedback = "❌ No answer provided."
        elif len(user_answer) < 8:
            score = 0.25
            feedback = "⚠️ Answer too brief. Provide more technical detail."
        else:
            score = semantic_score(user_answer, ref_answer, question)
            
            if score >= 0.85:
                feedback = "✅ Excellent answer! Strong technical understanding demonstrated."
            elif score >= 0.70:
                feedback = "✓ Good answer. Core concepts are correct, though some details could be expanded."
            elif score >= 0.50:
                feedback = "△ Partially correct. You've identified some key concepts, but missed important details."
            elif score >= 0.25:
                feedback = "⚠️ Weak answer. The response shows minimal understanding of the concept."
            else:
                feedback = "❌ Incorrect. Answer does not match expected technical response."
        
        # ═══════════════════════════════════════════════════════════════
        # FILL-IN-THE-BLANK EVALUATION (Flexible with synonyms/variations)
        # ═══════════════════════════════════════════════════════════════
        
        def flexible_fill_match(user, reference):
            """Flexible matching for fill-in-the-blank with synonyms"""
            # Exact match
            if user.lower() == reference.lower():
                return True, 1.0
            
            # Abbreviation/acronym matching
            acronym_map = {
                "syn": "synchronize",
                "ack": "acknowledge",
                "fin": "finish",
                "rst": "reset",
                "syn-ack": "synchronize-acknowledge",
                "synack": "synchronize-acknowledge",
                "synack packet": "synchronize-acknowledge packet",
                "syn packet": "synchronize packet",
                "synchronize packet": "syn packet",
                "tcp": "transmission control protocol",
                "ip": "internet protocol",
                "dns": "domain name system",
                "dhcp": "dynamic host configuration protocol",
                "bgp": "border gateway protocol",
                "ospf": "open shortest path first",
            }
            
            # Check if either is a key for the other
            for short, long in acronym_map.items():
                if (user.lower() == short and reference.lower() == long) or \
                   (user.lower() == long and reference.lower() == short):
                    return True, 1.0
            
            # Partial match (contains reference)
            if reference.lower() in user.lower():
                return True, 0.95
            
            if user.lower() in reference.lower():
                return True, 0.90
            
            # Word overlap
            user_words = set(user.lower().split())
            ref_words = set(reference.lower().split())
            if user_words == ref_words:
                return True, 0.95
            
            # Key word match
            if len(user_words & ref_words) >= 2:
                return True, 0.85
            
            return False, 0.0
        
        fill_correct, fill_score = flexible_fill_match(user_fill, ref_fill)
        
        fill_feedback = ""
        if fill_correct:
            if fill_score == 1.0:
                fill_feedback = "✅ Perfect! Exact answer."
            else:
                fill_feedback = "✓ Correct! (Accepted variation)"
        else:
            fill_feedback = f"❌ Incorrect. Expected: '{ref_fill}' but got '{user_fill}'"
        
        # ═══════════════════════════════════════════════════════════════
        # COMBINE SCORES
        # ═══════════════════════════════════════════════════════════════
        
        # Main answer accounts for 70%, fill-in-the-blank for 30%
        combined_score = (score * 0.7) + (fill_score * 0.3)
        marks = round(combined_score * 10)
        
        # Adjust marks based on fill correctness
        if fill_correct and score >= 0.7:
            marks = min(10, marks + 1)  # Bonus for both correct
        
        return jsonify({
            "score": round(combined_score, 2),
            "marks": marks,
            "feedback": feedback,
            "fill_feedback": fill_feedback,
            "fill_correct": fill_correct,
            "main_score": round(score, 2),
            "fill_score": round(fill_score, 2),
        }), 200
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route("/roberta/classify", methods=["POST"])
def roberta_classify():
    """
    Classify a question using the RoBERTa multitask model (or rule-based fallback).
    Request: {"text": "What is deadlock?"}
    Returns: {intent, difficulty, topics, confidence, source}
    """
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"error": "Text required"}), 400

        predictors = _get_roberta_predictors()

        if not predictors:
            return jsonify({"error": "RoBERTa inference pipeline not available"}), 503

        intent_result = predictors["intent"](text)
        difficulty_result = predictors["difficulty"](text)
        topic_result = predictors["topic"](text)

        # Normalize: topic can be list or single label
        topics = topic_result.get("labels", [])
        if not topics and isinstance(topic_result.get("scores"), dict):
            # Pick the top-scoring topic
            scores = topic_result["scores"]
            if scores:
                topics = [max(scores, key=scores.get)]

        return jsonify({
            "intent": intent_result.get("label", "unknown"),
            "difficulty": difficulty_result.get("label", "unknown"),
            "topics": topics,
            "confidence": round(
                (intent_result.get("confidence", 0) + difficulty_result.get("confidence", 0)) / 2, 2
            ),
            "intent_confidence": round(intent_result.get("confidence", 0), 2),
            "difficulty_confidence": round(difficulty_result.get("confidence", 0), 2),
            "source": intent_result.get("source", "rule"),
        }), 200

    except Exception as e:
        logger.error(f"RoBERTa classify error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/adaptive/session", methods=["POST"])
def adaptive_session():
    """
    Start an adaptive interview session using the RoBERTa adaptive engine.
    Request: {"user_id": "...", "num_questions": 5}
    Returns: profile summary + first question
    """
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "guest")
        num_questions = int(data.get("num_questions", 5))

        predictors = _get_roberta_predictors()
        if not predictors:
            return jsonify({"error": "RoBERTa inference pipeline not available"}), 503

        from adaptive.user_profile import UserProfileManager
        from adaptive.adaptive_selector import AdaptiveSelector, QuestionDataset

        dataset_path = os.path.join(ROBERTA_DIR, "data", "dataset.json")
        dataset = QuestionDataset(dataset_path=dataset_path)
        if not dataset.questions:
            return jsonify({"error": "Question dataset not loaded"}), 500

        profile_manager = UserProfileManager()
        profile = profile_manager.get_or_create_profile(user_id)
        selector = AdaptiveSelector(dataset)

        # Pick first question
        question = selector.select_next_question(profile)
        if not question:
            return jsonify({"error": "No questions available"}), 500

        # Store session state in-memory
        session_id = f"session_{user_id}_{int(time.time())}"
        _adaptive_sessions[session_id] = {
            "user_id": user_id,
            "profile": profile,
            "profile_manager": profile_manager,
            "selector": selector,
            "dataset": dataset,
            "num_questions": num_questions,
            "asked": [],
            "scores": [],
        }

        return jsonify({
            "status": "success",
            "session_id": session_id,
            "profile": {
                "user_id": user_id,
                "level": profile.current_level,
                "overall_accuracy": round(profile.overall_accuracy, 1),
                "total_attempted": profile.total_attempted,
                "weak_topics": profile.get_weak_topics(),
            },
            "question": {
                "text": question.text,
                "intent": question.intent,
                "difficulty": question.difficulty,
                "topics": question.topics,
            },
            "num_questions": num_questions,
        }), 200

    except Exception as e:
        logger.error(f"Adaptive session error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/adaptive/next", methods=["POST"])
def adaptive_next():
    """
    Get next question in an adaptive session.
    Request: {"session_id": "..."}
    """
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id", "")

        session = _adaptive_sessions.get(session_id)
        if not session:
            return jsonify({"error": "Invalid or expired session"}), 404

        if len(session["asked"]) >= session["num_questions"]:
            return jsonify({"status": "completed"}), 200

        question = session["selector"].select_next_question(session["profile"])
        if not question:
            return jsonify({"status": "completed"}), 200

        return jsonify({
            "status": "success",
            "question": {
                "text": question.text,
                "intent": question.intent,
                "difficulty": question.difficulty,
                "topics": question.topics,
            },
            "question_num": len(session["asked"]) + 1,
            "total_questions": session["num_questions"],
        }), 200

    except Exception as e:
        logger.error(f"Adaptive next error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/adaptive/evaluate", methods=["POST"])
def adaptive_evaluate():
    """
    Evaluate user's answer in an adaptive session and update profile.
    Request: {"session_id": "...", "question_text": "...", "user_answer": "..."}
    """
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id", "")
        question_text = data.get("question_text", "")
        user_answer = data.get("user_answer", "")

        session = _adaptive_sessions.get(session_id)
        if not session:
            return jsonify({"error": "Invalid or expired session"}), 404

        predictors = _get_roberta_predictors()
        if not predictors:
            return jsonify({"error": "RoBERTa inference pipeline not available"}), 503

        # Classify the question
        q_intent = predictors["intent"](question_text)
        q_difficulty = predictors["difficulty"](question_text)
        q_topic_result = predictors["topic"](question_text)
        q_topics = q_topic_result.get("labels", ["General"])

        # Evaluate answer using intent/topic overlap + length heuristics
        a_intent = predictors["intent"](user_answer)
        a_topic_result = predictors["topic"](user_answer)
        a_topics = a_topic_result.get("labels", [])

        # Score components
        topic_overlap = len(set(q_topics) & set(a_topics))
        topic_score = min(1.0, topic_overlap / max(len(q_topics), 1))

        intent_match = 1.0 if a_intent.get("label") == q_intent.get("label") else 0.3
        comprehensiveness = min(1.0, len(user_answer.split()) / 30)

        score = round((topic_score * 0.5 + intent_match * 0.25 + comprehensiveness * 0.25) * 100, 1)
        is_correct = score >= 60

        # Record in session
        session["asked"].append(question_text)
        session["scores"].append(score)

        # Update profile
        profile = session["profile"]
        for topic in q_topics:
            profile.record_attempt(
                score=score,
                topic=topic,
                intent=q_intent.get("label", "unknown"),
                difficulty=q_difficulty.get("label", "medium"),
            )
        session["profile_manager"].save_profile(profile)

        # Grade
        if score >= 85:
            grade = "excellent"
        elif score >= 65:
            grade = "mostly_correct"
        elif score >= 40:
            grade = "partially_correct"
        else:
            grade = "blatantly_wrong"

        return jsonify({
            "status": "success",
            "score": score,
            "grade": grade,
            "is_correct": is_correct,
            "feedback": f"Score: {score}/100 ({grade})",
            "question_num": len(session["asked"]),
            "total_questions": session["num_questions"],
        }), 200

    except Exception as e:
        logger.error(f"Adaptive evaluate error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════

def _verify_gemini_connectivity():
    """Send a minimal request to Gemini to verify the API key and connectivity."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("Skipping Gemini connectivity check — no API key")
        return False
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with the word OK",
            config=types.GenerateContentConfig(
                max_output_tokens=8,
                temperature=0.0,
            ),
        )
        text = (resp.text or "").strip()
        logger.info("Gemini connectivity OK — response: %s", text)
        return True
    except Exception as e:
        logger.warning("Gemini connectivity check failed: %s", e)
        return False


if __name__ == "__main__":
    _verify_gemini_connectivity()
    logger.info("Open your browser: http://localhost:5000")
    app.run(debug=False, port=5000, threaded=True, use_reloader=False)
