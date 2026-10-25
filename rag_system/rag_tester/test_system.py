"""
Test Script - Verify RAG system components
"""
import os
import sys

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    try:
        import fitz
        print("  ✅ PyMuPDF")
    except:
        print("  ❌ PyMuPDF")
    
    try:
        import faiss
        print("  ✅ FAISS")
    except:
        print("  ❌ FAISS")
    
    try:
        from sentence_transformers import SentenceTransformer
        print("  ✅ SentenceTransformer")
    except:
        print("  ❌ SentenceTransformer")
    
    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        print("  ✅ Transformers")
    except:
        print("  ❌ Transformers")
    
    try:
        import numpy
        print("  ✅ NumPy")
    except:
        print("  ❌ NumPy")
    
    print()


def test_pdf_exists():
    """Check if PDF exists"""
    print("🔍 Checking PDF file...")
    pdf_path = "samples/CN_UNIT1_MERGE.pdf"
    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path) / (1024 * 1024)
        print(f"  ✅ Found: {pdf_path} ({size:.1f} MB)")
    else:
        print(f"  ❌ Not found: {pdf_path}")
    print()


def test_ingestion():
    """Test PDF ingestion"""
    print("🔍 Testing PDF ingestion...")
    try:
        from ingestor import ingest_subject
        
        success = ingest_subject("samples/CN_UNIT1_MERGE.pdf", "cn_unit1_test")
        
        if success:
            print("  ✅ Ingestion successful")
            
            # Check files created
            if os.path.exists("knowledge_base/cn_unit1_test.index"):
                print("  ✅ Index file created")
            if os.path.exists("knowledge_base/cn_unit1_test_chunks.json"):
                print("  ✅ Chunks file created")
        else:
            print("  ❌ Ingestion failed")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()


def test_retrieval():
    """Test retrieval module"""
    print("🔍 Testing retrieval...")
    try:
        from retrieval import retrieve_relevant_content, get_best_context
        
        # Check if knowledge base exists
        if not os.path.exists("knowledge_base/cn_unit1.index"):
            print("  ⚠️  Knowledge base not found. Run ingestor.py first.")
            return
        
        results = retrieve_relevant_content("cn_unit1", "network protocol", top_k=2)
        
        if results:
            print(f"  ✅ Retrieved {len(results)} results")
            for i, r in enumerate(results, 1):
                print(f"     [{i}] Page {r['page']}: {r['text'][:50]}...")
        else:
            print("  ❌ No results found")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()


def test_generation():
    """Test question generation"""
    print("🔍 Testing question generation...")
    try:
        from generate import generate_interview_question
        
        context = "The OSI model is a conceptual framework for network protocols. It has 7 layers."
        question = generate_interview_question(context, concept="OSI Model")
        
        if question and len(question) > 10:
            print("  ✅ Generated question:")
            print(f"     {question}")
        else:
            print("  ❌ Question generation failed")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()


def test_evaluation():
    """Test answer evaluation"""
    print("🔍 Testing evaluation...")
    try:
        from evaluate import evaluate_answer
        
        student = "The OSI model has 7 layers for network communication"
        reference = "The OSI model consists of 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, and Application"
        
        result = evaluate_answer(student, reference)
        
        print(f"  ✅ Evaluation complete:")
        print(f"     Score: {result['score']:.1f}/100")
        print(f"     Grade: {result['grade']}")
        print(f"     Feedback: {result['feedback']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 RAG SYSTEM DIAGNOSTIC TEST")
    print("="*60 + "\n")
    
    test_imports()
    test_pdf_exists()
    
    print("="*60)
    print("Running integration tests (this may take a moment)...")
    print("="*60 + "\n")
    
    test_ingestion()
    test_retrieval()
    test_generation()
    test_evaluation()
    
    print("="*60)
    print("✅ Diagnostic test complete!")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. If all tests passed: python main.py")
    print("   2. If some tests failed: install missing packages")
    print("   3. Make sure CN_UNIT1_MERGE.pdf is in samples/ folder")


if __name__ == "__main__":
    main()
