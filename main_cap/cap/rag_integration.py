"""
RAG System Integration Module
Connects the RAG question generation system with the Flask app.
Generates both MCQ (quiz) and open-ended (chat) questions from retrieved content.
"""
import os
import sys
import logging
import random
import re

logger = logging.getLogger(__name__)

# ── Path Setup for RAG System ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_SYSTEM_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../rag_system/rag_tester"))
RAG_SAMPLES_DIR = os.path.join(RAG_SYSTEM_DIR, "samples")
RAG_KB_DIR = os.path.join(RAG_SYSTEM_DIR, "knowledge_base")

if RAG_SYSTEM_DIR not in sys.path:
    sys.path.insert(0, RAG_SYSTEM_DIR)

# ── RAG Module Imports ────────────────────────────────────────────────────────
try:
    from ingestor import ingest_subject
    from retrieval import retrieve_relevant_content, get_context_with_pages
    from generate import generate_interview_question, generate_reference_answer
    RAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RAG system not fully initialized: {e}")
    RAG_AVAILABLE = False


# ── Domain-to-Subject Mapping ─────────────────────────────────────────────────
DOMAIN_TO_RAG_SUBJECT = {
    "Network Engineer": "cn_unit1",
}

# Sub-topic queries for varied retrieval
TOPIC_VARIANTS = {
    "TCP": ["TCP protocol", "TCP connection", "TCP reliable data transfer", "TCP three-way handshake", "TCP congestion control"],
    "DNS": ["Domain Name System", "DNS name resolution", "DNS hierarchy", "DNS record types"],
    "IP Routing": ["IP routing", "routing algorithms", "forwarding tables", "link state routing"],
    "UDP": ["UDP protocol", "connectionless transport", "UDP vs TCP", "UDP applications"],
    "OSI": ["OSI model", "protocol layers", "network layering", "OSI seven layers"],
    "Congestion Control": ["congestion control", "TCP congestion window", "network congestion avoidance", "TCP slow start"],
    "All": ["networking fundamentals", "internet protocols", "computer networks", "transport layer"],
}

# Garbage patterns to reject from generated questions
_BAD_Q_PATTERNS = [
    r"how many words",
    r"how many characters",
    r"what is the (title|header|label|name) of",
    r"what (page|chapter|section)",
]


def _clean_pdf_chunk(text):
    """Remove PDF artifacts: page headers, newlines, excessive whitespace."""
    if not text:
        return ""
    # Remove common PDF page headers/footers
    text = re.sub(r'COMPUTER\s+NETWORKS', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Chapter\s+\d+[\s:]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Unit\s+\d+[\s:]+', '', text, flags=re.IGNORECASE)
    # Collapse newlines and multiple spaces
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    # Remove page numbers
    text = re.sub(r'\b\d{1,3}\s*$', '', text)
    return text.strip()


def _is_valid_question(q):
    """Check if a generated question is a valid interview question."""
    if not q or len(q) < 10:
        return False
    q_lower = q.lower().strip()
    # Must end with ?
    if not q.endswith("?"):
        return False
    # Must start with a question word
    starters = ["what", "how", "why", "explain", "describe", "which", "when", "where"]
    if not any(q_lower.startswith(s) for s in starters):
        return False
    # Reject garbage patterns
    for pat in _BAD_Q_PATTERNS:
        if re.search(pat, q_lower):
            return False
    # Must be reasonable length
    word_count = len(q.split())
    if word_count < 4 or word_count > 30:
        return False
    return True


def _extract_clean_answer(ctx, question):
    """
    Extract a SHORT clean sentence from context to serve as the correct MCQ answer.
    Returns a single sentence, max ~100 chars.
    """
    # Clean the context first
    ctx = _clean_pdf_chunk(ctx)
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', ctx)
    # Filter: must be substantive (>=8 words), not all-caps, not a header
    good = []
    for s in sentences:
        s = s.strip()
        if len(s) < 15 or len(s) > 200:
            continue
        if s.isupper():
            continue
        wc = len(s.split())
        if wc < 4:
            continue
        # Skip sentences that look like figure/table references
        if re.match(r'^(fig|table|figure|see|ref)', s, re.IGNORECASE):
            continue
        good.append(s)

    if not good:
        # Last resort: take longest chunk of meaningful text
        words = [w for w in ctx.split() if len(w) > 3 and w.isalpha()]
        if len(words) >= 4:
            return " ".join(words[:12]) + "."
        return None

    # Pick a sentence that is informative but not too long
    # Prefer medium-length sentences (most likely to be factual statements)
    good.sort(key=lambda s: abs(len(s) - 80))
    chosen = good[0]
    # Truncate to ~100 chars at word boundary
    if len(chosen) > 100:
        chosen = chosen[:100].rsplit(' ', 1)[0]
        if not chosen.endswith('.'):
            chosen += '.'
    return chosen


def _make_clean_options(all_chunks, correct_answer, topic, count=3):
    """
    Generate clean, short MCQ options from retrieved context chunks.
    Returns short phrases/sentences suitable as MCQ options.
    """
    # Extract all candidate sentences from all chunks
    candidates = []
    for chunk in all_chunks:
        ctx = _clean_pdf_chunk(chunk.get("text", ""))
        sentences = re.split(r'(?<=[.!?])\s+', ctx)
        for s in sentences:
            s = s.strip()
            # Must be short enough to be an option, not the correct answer
            if len(s) < 15 or len(s) > 120:
                continue
            if s == correct_answer:
                continue
            if s.isupper():
                continue
            wc = len(s.split())
            if wc < 4 or wc > 20:
                continue
            candidates.append(s)

    # Deduplicate (rough)
    seen = set()
    unique = []
    for c in candidates:
        key = c.lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(c)

    if len(unique) >= count:
        return random.sample(unique, count)

    # Pad with generic distractors if not enough candidates
    generic = [
        f"This concept does not apply to {topic}.",
        f"{topic} does not use this approach.",
        f"This is not a standard {topic} mechanism.",
        f"None of the above options are correct for {topic}.",
    ]
    while len(unique) < count:
        unique.append(generic[len(unique) % len(generic)])
    return unique[:count]


class RAGQuestionGenerator:
    """
    Wrapper class to integrate RAG question generation with the Flask app.
    Generates MCQ questions for quizzes and open-ended questions for chat.
    """

    def __init__(self, knowledge_base_dir=RAG_KB_DIR):
        self.kb_dir = knowledge_base_dir
        self.loaded_subjects = {}
        self.rag_available = RAG_AVAILABLE
        self._seen_questions = set()

    def get_available_subjects(self):
        """Get list of available knowledge base subjects."""
        try:
            if not os.path.exists(self.kb_dir):
                return []
            return [
                f.replace(".index", "")
                for f in os.listdir(self.kb_dir)
                if f.endswith(".index")
            ]
        except Exception as e:
            logger.error(f"Error getting subjects: {e}")
            return []

    def get_rag_subject(self, quiz_domain):
        """Map a quiz domain to its RAG subject name, or None if no KB exists."""
        subject = DOMAIN_TO_RAG_SUBJECT.get(quiz_domain)
        if subject and subject in self.get_available_subjects():
            return subject
        return None

    def _varied_queries(self, topic, count=4):
        """Return a list of varied search queries for a topic."""
        variants = TOPIC_VARIANTS.get(topic, [])
        if variants:
            return variants[:count]
        return [topic, f"what is {topic}", f"{topic} explained", f"{topic} fundamentals"][:count]

    def _assign_difficulty(self, question, index):
        """Assign difficulty based on question characteristics."""
        wc = len(question.split())
        if wc <= 8:
            return "Easy"
        elif wc <= 14:
            return "Medium"
        return "Hard"

    def generate_mcq_questions(self, quiz_domain, topic, num_questions=6, skills=None):
        """
        Generate MCQ questions from RAG for a specific domain.
        Returns list of dicts matching the frontend contract:
        {question, options, answer, difficulty}

        Returns empty list if RAG unavailable or cannot produce quality questions.
        """
        if not self.rag_available:
            return []

        subject = self.get_rag_subject(quiz_domain)
        if not subject:
            return []

        try:
            queries = self._varied_queries(topic, count=num_questions * 3)
            all_chunks = []
            questions = []

            # Gather diverse contexts
            for q in queries:
                try:
                    results = retrieve_relevant_content(subject, q, top_k=3)
                    for r in results:
                        txt = r.get("text", "")
                        if txt and txt not in [c.get("text", "") for c in all_chunks]:
                            all_chunks.append(r)
                except Exception:
                    continue

            if not all_chunks:
                return []

            # Generate MCQs from different chunks
            used_chunks = set()
            attempts = 0
            max_attempts = len(all_chunks) * 2

            while len(questions) < num_questions and attempts < max_attempts:
                attempts += 1
                chunk = all_chunks[attempts % len(all_chunks)]
                ctx = chunk.get("text", "")
                if not ctx or ctx in used_chunks or len(ctx.strip()) < 50:
                    continue
                used_chunks.add(ctx)

                # Generate question via FLAN-T5
                question = generate_interview_question(ctx, concept=topic)
                if not _is_valid_question(question):
                    continue

                # Deduplicate
                q_key = question.lower().strip()
                if q_key in self._seen_questions:
                    continue
                self._seen_questions.add(q_key)

                # Extract clean answer and options
                correct = _extract_clean_answer(ctx, question)
                if not correct or len(correct) < 10:
                    continue

                distractors = _make_clean_options(all_chunks, correct, topic, count=3)

                # Skip if any option is identical to correct
                if correct in distractors:
                    continue

                options = [correct] + distractors
                random.shuffle(options)
                correct_idx = options.index(correct)

                questions.append({
                    "question": question,
                    "options": options,
                    "answer": correct_idx,
                    "difficulty": self._assign_difficulty(question, len(questions)),
                })

            logger.info("RAG generated %d MCQs for %s/%s", len(questions), quiz_domain, topic)
            return questions[:num_questions]

        except Exception as e:
            logger.error("RAG MCQ generation error: %s", e, exc_info=True)
            return []

    def generate_open_questions(self, subject_name, topic, num_questions=3):
        """
        Generate open-ended questions for the chat interview flow.
        Returns list of dicts with question, reference_answer, topic.
        """
        if not self.rag_available:
            return []

        try:
            queries = self._varied_queries(topic, count=num_questions * 2)
            questions = []

            for q in queries:
                if len(questions) >= num_questions:
                    break

                context, pages = get_context_with_pages(subject_name, q)
                if not context or len(context.strip()) < 30:
                    continue

                question = generate_interview_question(context, concept=topic)
                if not question or "?" not in question:
                    continue

                q_key = question.lower().strip()
                if q_key in self._seen_questions:
                    continue
                self._seen_questions.add(q_key)

                reference_answer = generate_reference_answer(context)

                questions.append({
                    "question": question,
                    "reference_answer": reference_answer,
                    "topic": topic,
                    "source_pages": pages,
                    "subject": subject_name,
                })

            return questions[:num_questions]

        except Exception as e:
            logger.error("RAG open question generation error: %s", e, exc_info=True)
            return []

    def reset_seen(self):
        """Reset the deduplication tracker (call between sessions)."""
        self._seen_questions.clear()


# Global RAG generator instance
rag_generator = RAGQuestionGenerator()


def initialize_rag_system():
    """Initialize RAG system and log available subjects."""
    try:
        subjects = rag_generator.get_available_subjects()
        for s in subjects:
            rag_generator.loaded_subjects[s] = True
            logger.info("RAG knowledge base ready: %s", s)
        if not subjects:
            logger.info("No RAG knowledge bases found")
    except Exception as e:
        logger.warning("Error initializing RAG system: %s", e)
