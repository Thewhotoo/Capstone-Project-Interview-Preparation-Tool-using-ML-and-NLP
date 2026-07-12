"""Test the fixed RAG integration wrapper."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../resume_classifier"))

from rag_integration import rag_generator

# Test 1: Available subjects
subjects = rag_generator.get_available_subjects()
print(f"Available subjects: {subjects}")

# Test 2: Generate questions
questions = rag_generator.generate_questions("cn_unit1", "TCP/IP", num_questions=3)
print(f"Generated {len(questions)} questions")
for i, q in enumerate(questions):
    print(f"  Q{i+1}: {q['question'][:80]}")
    print(f"    Topic: {q['topic']}, Pages: {q['source_pages']}")

# Test 3: Generate questions for a different topic
questions2 = rag_generator.generate_questions("cn_unit1", "OSI model", num_questions=3)
print(f"\nGenerated {len(questions2)} questions about OSI model")
for i, q in enumerate(questions2):
    print(f"  Q{i+1}: {q['question'][:80]}")
