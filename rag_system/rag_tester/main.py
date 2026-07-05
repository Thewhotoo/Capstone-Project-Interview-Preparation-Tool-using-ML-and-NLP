"""
Main RAG Pipeline - Complete PDF-based Question Generation and Answer Evaluation
"""
import os
from ingestor import ingest_subject
from retrieval import retrieve_relevant_content, get_best_context, get_context_with_pages
from generate import generate_interview_question, generate_reference_answer, generate_explanation
from evaluate import evaluate_answer, compare_answers
from tqdm import tqdm

# Configuration
SUBJECT_NAME = "cn_unit1"
PDF_PATH = "samples/CN_UNIT1_MERGE.pdf"


def setup_knowledge_base():
    """
    Initialize the knowledge base from PDF
    """
    print("\n" + "="*60)
    print("📚 RAG SYSTEM - PDF KNOWLEDGE BASE SETUP")
    print("="*60)
    
    if not os.path.exists(f"knowledge_base/{SUBJECT_NAME}.index"):
        print(f"\n🔄 Creating knowledge base from {PDF_PATH}...")
        success = ingest_subject(PDF_PATH, SUBJECT_NAME)
        if not success:
            print("❌ Failed to create knowledge base!")
            return False
    else:
        print(f"\n✅ Knowledge base already exists: {SUBJECT_NAME}")
    
    return True


def generate_rag_questions(topic, num_questions=3):
    """
    Generate interview questions for a specific topic
    
    Args:
        topic: Topic/concept to generate questions for
        num_questions: Number of questions to generate
    
    Returns:
        list: Generated questions with sources
    """
    print("\n" + "="*60)
    print(f"❓ GENERATING QUESTIONS FOR: {topic.upper()}")
    print("="*60)
    
    questions = []
    
    for i in range(num_questions):
        # Retrieve context
        context = get_best_context(SUBJECT_NAME, topic)
        
        if not context:
            print(f"⚠️  Could not find relevant content for: {topic}")
            break
        
        # Generate question
        question = generate_interview_question(context, concept=topic)
        
        # Get reference answer
        reference = generate_reference_answer(context)
        
        questions.append({
            'question_num': i + 1,
            'question': question,
            'reference_answer': reference,
            'source_context': context[:300] + "..."
        })
        
        print(f"\n📌 Question {i+1}:")
        print(f"   {question}")
        print(f"\n📖 Reference Answer:")
        print(f"   {reference[:200]}...")
    
    return questions


def interactive_mode():
    """
    Interactive RAG system - ask questions and get generated interview questions
    """
    print("\n" + "="*60)
    print("🎯 INTERACTIVE MODE - Ask About Any Topic")
    print("="*60)
    print("Type 'quit' to exit\n")
    
    while True:
        topic = input("📝 Enter a topic: ").strip()
        
        if topic.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if not topic:
            print("⚠️  Please enter a valid topic\n")
            continue
        
        # Retrieve relevant content
        results = retrieve_relevant_content(SUBJECT_NAME, topic, top_k=3)
        
        if not results:
            print(f"\n❌ No relevant content found for '{topic}'\n")
            continue
        
        print(f"\n✅ Found {len(results)} relevant sections:")
        print("-" * 60)
        
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] Page {result['page']} | Relevance: {result['relevance_score']:.2%}")
            print(f"    {result['text'][:150]}...")
        
        # Generate question
        context = results[0]['text']
        question = generate_interview_question(context, concept=topic)
        
        print(f"\n🤖 GENERATED QUESTION:")
        print(f"   {question}\n")
        
        # Offer to evaluate an answer
        answer = input("✍️  Enter your answer (or press Enter to skip): ").strip()
        
        if answer:
            evaluation = evaluate_answer(answer, context)
            print(f"\n📊 EVALUATION RESULT:")
            print(f"   Score: {evaluation['score']:.1f}/100")
            print(f"   Grade: {evaluation['grade']}")
            print(f"   Feedback: {evaluation['feedback']}")
            print(f"   Answer Length: {evaluation['answer_length']} words")
            print(f"   Reference Length: {evaluation['reference_length']} words")
        
        print("\n" + "-" * 60)


def batch_generate_questions(topics_file="topics.txt"):
    """
    Generate questions for multiple topics from a file
    
    Args:
        topics_file: Text file with one topic per line
    """
    if not os.path.exists(topics_file):
        print(f"❌ Topics file not found: {topics_file}")
        return
    
    print("\n" + "="*60)
    print(f"📚 BATCH GENERATING QUESTIONS FROM: {topics_file}")
    print("="*60)
    
    with open(topics_file, 'r') as f:
        topics = [line.strip() for line in f if line.strip()]
    
    all_questions = []
    
    for topic in tqdm(topics, desc="Generating questions"):
        results = retrieve_relevant_content(SUBJECT_NAME, topic, top_k=1)
        
        if results:
            context = results[0]['text']
            question = generate_interview_question(context, concept=topic)
            all_questions.append({
                'topic': topic,
                'question': question,
                'page': results[0]['page']
            })
    
    # Save to file
    output_file = "generated_questions.txt"
    with open(output_file, 'w') as f:
        for item in all_questions:
            f.write(f"Topic: {item['topic']}\n")
            f.write(f"Question: {item['question']}\n")
            f.write(f"Source Page: {item['page']}\n")
            f.write("-" * 60 + "\n")
    
    print(f"\n✅ Generated {len(all_questions)} questions!")
    print(f"   Saved to: {output_file}")


def demonstrate_rag():
    """
    Run a demonstration of the RAG system
    """
    print("\n" + "="*60)
    print("🎓 RAG SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Example topics
    demo_topics = [
        "OSI Model layers",
        "TCP/IP protocol",
        "Network routing"
    ]
    
    print(f"\nDemonstrating RAG with {len(demo_topics)} topics...\n")
    
    for topic in demo_topics:
        print(f"\n{'='*60}")
        print(f"📌 Topic: {topic}")
        print('='*60)
        
        # Retrieve
        results = retrieve_relevant_content(SUBJECT_NAME, topic, top_k=1)
        
        if results:
            result = results[0]
            print(f"\n📖 Retrieved Content:")
            print(f"  Page {result['page']} - Relevance: {result['relevance_score']:.1%}")
            print(f"  {result['text'][:200]}...")
            
            # Generate
            context = result['text']
            question = generate_interview_question(context, concept=topic)
            
            print(f"\n🤖 Generated Question:")
            print(f"  {question}")
            
            # Show evaluation demo
            sample_answer = "This concept involves network operations."
            evaluation = evaluate_answer(sample_answer, context)
            
            print(f"\n📊 Sample Evaluation (on a basic answer):")
            print(f"  Score: {evaluation['score']:.1f}/100")
            print(f"  Grade: {evaluation['grade']}")
        else:
            print(f"⚠️  No content found for this topic")


def main():
    """
    Main entry point
    """
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  PDF-BASED RAG SYSTEM FOR INTERVIEW QUESTION GENERATION  ".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # Setup knowledge base
    if not setup_knowledge_base():
        return
    
    # Menu
    while True:
        print("\n" + "="*60)
        print("MAIN MENU")
        print("="*60)
        print("1. Interactive Mode (Ask about topics)")
        print("2. Generate Questions for Specific Topics")
        print("3. Demonstrate RAG System")
        print("4. Batch Generate Questions from File")
        print("5. Exit")
        print("="*60)
        
        choice = input("📍 Select option (1-5): ").strip()
        
        if choice == "1":
            interactive_mode()
        elif choice == "2":
            topic = input("\n📝 Enter topic: ").strip()
            num = input("How many questions? (default: 3): ").strip()
            num = int(num) if num.isdigit() else 3
            generate_rag_questions(topic, num)
        elif choice == "3":
            demonstrate_rag()
        elif choice == "4":
            batch_generate_questions()
        elif choice == "5":
            print("\n👋 Thank you for using RAG System!")
            break
        else:
            print("\n⚠️  Invalid option. Please select 1-5.")


if __name__ == "__main__":
    main()
