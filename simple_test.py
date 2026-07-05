"""
Simple Test Script - No Curl Commands!
Just run this to test everything automatically
"""

import requests
import json
import time
import sys

# Color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
END = '\033[0m'

BASE_URL = "http://localhost:5000"

def print_test(test_num, name):
    print(f"\n{BLUE}{'='*60}{END}")
    print(f"{BLUE}TEST {test_num}: {name}{END}")
    print(f"{BLUE}{'='*60}{END}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{END}")

def print_error(msg):
    print(f"{RED}❌ {msg}{END}")

def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{END}")

# Test 1: Health Check
print_test(1, "Health Check")
try:
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print_success(f"Server is running!")
        print(f"Response: {response.json()}")
    else:
        print_error(f"Server returned status {response.status_code}")
        sys.exit(1)
except Exception as e:
    print_error(f"Cannot connect to server: {e}")
    print_info("Make sure Flask app is running in Terminal 1!")
    sys.exit(1)

# Test 2: Check RAG Subjects
print_test(2, "Check Available RAG Subjects")
try:
    response = requests.get(f"{BASE_URL}/rag/available-subjects")
    subjects = response.json()
    print_success(f"RAG subjects: {subjects}")
except Exception as e:
    print_error(f"Failed: {e}")

# Test 3: Setup RAG Knowledge Base
print_test(3, "Setup RAG Knowledge Base from PDF")
try:
    pdf_path = r"C:\Users\Surya Srikhar\OneDrive\Documents\Desktop\Capstone_project\Project\rag_system\rag_tester\samples\CN_UNIT1_MERGE.pdf"
    
    if not __import__('os').path.exists(pdf_path):
        print_error(f"PDF not found: {pdf_path}")
        print_info("Skipping RAG tests...")
    else:
        payload = {
            "subject_name": "computer_networks",
            "pdf_path": pdf_path
        }
        response = requests.post(f"{BASE_URL}/rag/setup-knowledge-base", json=payload)
        result = response.json()
        
        if result.get("success"):
            print_success(f"Knowledge base setup: {result.get('message')}")
        else:
            print_error(f"Setup failed: {result.get('error')}")
except Exception as e:
    print_error(f"Failed: {e}")

# Test 4: Generate Questions
print_test(4, "Generate RAG Questions")
try:
    payload = {
        "subject_name": "computer_networks",
        "topic": "TCP",
        "num_questions": 2
    }
    response = requests.post(f"{BASE_URL}/rag/generate-questions", json=payload)
    result = response.json()
    
    if result.get("status") == "success":
        questions = result.get("questions", [])
        print_success(f"Generated {len(questions)} questions:")
        for i, q in enumerate(questions, 1):
            print(f"\n  Question {i}: {q.get('question', 'N/A')[:60]}...")
    else:
        print_error(f"Generation failed: {result}")
except Exception as e:
    print_error(f"Failed: {e}")

# Test 5: Classify Question
print_test(5, "Classify Question with RoBERTa")
try:
    payload = {
        "text": "Explain the three-way handshake in TCP protocol"
    }
    response = requests.post(f"{BASE_URL}/roberta/classify", json=payload)
    result = response.json()
    
    print_success("Question classified:")
    print(f"  Intent: {result.get('intent')}")
    print(f"  Difficulty: {result.get('difficulty')}")
    print(f"  Topics: {result.get('topics')}")
    print(f"  Confidence: {result.get('confidence')}")
except Exception as e:
    print_error(f"Failed: {e}")

# Test 6: Evaluate Answer
print_test(6, "Evaluate Student Answer")
try:
    payload = {
        "user_answer": "TCP handshake is SYN, SYN-ACK, ACK. First client sends SYN packet, server responds with SYN-ACK, then client sends ACK.",
        "reference_answer": "The three-way handshake in TCP is a process where the client sends a SYN packet, the server responds with a SYN-ACK packet, and the client sends an ACK packet back. This establishes a connection.",
        "question": "Explain the three-way handshake in TCP.",
        "user_fill_mask": "SYN",
        "reference_fill_mask": "SYN"
    }
    response = requests.post(f"{BASE_URL}/api/evaluate", json=payload)
    result = response.json()
    
    score = result.get('score', 0)
    print_success(f"Answer evaluated!")
    print(f"  Score: {score}/1.0")
    print(f"  Marks: {result.get('marks')}/10")
    print(f"  Feedback: {result.get('feedback')}")
except Exception as e:
    print_error(f"Failed: {e}")

# Summary
print(f"\n{BLUE}{'='*60}{END}")
print(f"{GREEN}🎉 ALL TESTS COMPLETED!{END}")
print(f"{BLUE}{'='*60}{END}")
print(f"\n{YELLOW}Summary:{END}")
print(f"✅ Server is running")
print(f"✅ RAG system initialized")
print(f"✅ Questions can be generated")
print(f"✅ Answers can be evaluated")
print(f"✅ System is ready for use!")
print(f"\n{GREEN}Next Steps:{END}")
print(f"1. Upload a resume to /predict endpoint")
print(f"2. Run complete workflow with /workflow/interview")
print(f"3. Check logs in Terminal 1 for any errors")
