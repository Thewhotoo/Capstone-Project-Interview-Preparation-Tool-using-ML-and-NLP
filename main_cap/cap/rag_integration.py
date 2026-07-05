"""
RAG System Integration Module
Connects the RAG question generation system with the Flask app
"""
import os
import sys
import logging
from pathlib import Path

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


class RAGQuestionGenerator:
    """
    Wrapper class to integrate RAG question generation with the Flask app
    """
    
    def __init__(self, knowledge_base_dir=RAG_KB_DIR):
        self.kb_dir = knowledge_base_dir
        self.loaded_subjects = {}
        self.rag_available = RAG_AVAILABLE
    
    def setup_knowledge_base(self, subject_name, pdf_path):
        """
        Initialize/load a knowledge base from a PDF file
        
        Args:
            subject_name: Name for the knowledge base (e.g., 'computer_networks')
            pdf_path: Path to the PDF file
            
        Returns:
            dict: Status of initialization
        """
        if not self.rag_available:
            return {"success": False, "error": "RAG system not available"}
        
        try:
            # Check if already exists
            index_path = os.path.join(self.kb_dir, f"{subject_name}.index")
            chunks_path = os.path.join(self.kb_dir, f"{subject_name}_chunks.json")
            
            if os.path.exists(index_path) and os.path.exists(chunks_path):
                self.loaded_subjects[subject_name] = True
                return {
                    "success": True,
                    "message": f"Knowledge base '{subject_name}' already loaded",
                    "subject": subject_name
                }
            
            # Create new knowledge base
            if not os.path.exists(pdf_path):
                return {"success": False, "error": f"PDF not found: {pdf_path}"}
            
            logger.info(f"Creating knowledge base from {pdf_path}")
            success = ingest_subject(pdf_path, subject_name)
            
            if success:
                self.loaded_subjects[subject_name] = True
                return {
                    "success": True,
                    "message": f"Knowledge base '{subject_name}' created successfully",
                    "subject": subject_name
                }
            else:
                return {"success": False, "error": "Failed to create knowledge base"}
        
        except Exception as e:
            logger.error(f"Error setting up knowledge base: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def generate_questions(self, subject_name, topic, num_questions=3):
        """
        Generate interview questions for a specific topic using RAG
        
        Args:
            subject_name: Name of the knowledge base subject
            topic: Topic/concept to generate questions for
            num_questions: Number of questions to generate
            
        Returns:
            list: Generated questions with context and sources
        """
        if not self.rag_available:
            return []
        
        try:
            questions = []
            
            for _ in range(num_questions):
                # Retrieve relevant context from knowledge base
                context_data = get_context_with_pages(topic, subject_name)
                
                if not context_data or "context" not in context_data:
                    continue
                
                context = context_data.get("context", "")
                pages = context_data.get("pages", [])
                
                # Generate question and answer from context
                question = generate_interview_question(context, concept=topic)
                reference_answer = generate_reference_answer(context, question)
                
                if question and reference_answer:
                    questions.append({
                        "question": question,
                        "reference_answer": reference_answer,
                        "context": context[:500],  # First 500 chars of context
                        "topic": topic,
                        "source_pages": pages,
                        "subject": subject_name
                    })
            
            return questions
        
        except Exception as e:
            logger.error(f"Error generating questions: {e}", exc_info=True)
            return []
    
    def get_available_subjects(self):
        """
        Get list of available knowledge bases
        
        Returns:
            list: Available subject names
        """
        try:
            if not os.path.exists(self.kb_dir):
                return []
            
            subjects = []
            for file in os.listdir(self.kb_dir):
                if file.endswith(".index"):
                    subject = file.replace(".index", "")
                    subjects.append(subject)
            
            return subjects
        except Exception as e:
            logger.error(f"Error getting subjects: {e}")
            return []


# Global RAG generator instance
rag_generator = RAGQuestionGenerator()

# Initialize with available subjects
def initialize_rag_system():
    """Initialize RAG system with available knowledge bases"""
    try:
        for subject in rag_generator.get_available_subjects():
            rag_generator.loaded_subjects[subject] = True
            logger.info(f"RAG system ready for subject: {subject}")
    except Exception as e:
        logger.warning(f"Error initializing RAG system: {e}")
