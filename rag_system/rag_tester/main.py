"""
Main RAG Pipeline - Complete PDF-based Question Generation and Answer Evaluation
with difficulty, MCQ support, progress tracking, and multi‑language coding.
"""
from retrieval import retrieve_relevant_content, get_best_context, load_test_cases
from generate import (
    generate_interview_question,
    generate_reference_answer,
    generate_question_by_type,
    generate_mcq,
    generate_test_cases
)
from evaluate import evaluate_answer
from tracking import log_evaluation, get_stats, get_history
from tqdm import tqdm
from pathlib import Path

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "knowledge_base"

# --------------------------------------------------
# Subject selection
# --------------------------------------------------
def get_available_subjects():
    if not KNOWLEDGE_BASE_DIR.exists():
        return []
    return sorted(
        folder.name
        for folder in KNOWLEDGE_BASE_DIR.iterdir()
        if folder.is_dir()
    )

def setup_knowledge_base():
    print("\n" + "=" * 60)
    print("📚 AVAILABLE KNOWLEDGE BASES")
    print("=" * 60)
    subjects = get_available_subjects()
    if not subjects:
        print("No indexed subjects found.")
        print("Run dynamic_ingestor.py first.")
        return None
    for i, subject in enumerate(subjects, start=1):
        print(f"{i}. {subject}")
    while True:
        choice = input("\nSelect subject: ").strip()
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(subjects):
                return subjects[choice - 1]
        print("Invalid selection.")

# --------------------------------------------------
# Difficulty, type, and language helpers
# --------------------------------------------------
def get_difficulty():
    print("\nSelect difficulty:")
    print("1. Easy")
    print("2. Medium")
    print("3. Hard")
    while True:
        d = input("Choice (1-3): ").strip()
        if d in ['1', '2', '3']:
            return ['easy', 'medium', 'hard'][int(d)-1]
        print("Invalid choice.")

def get_question_type():
    print("\nSelect question type:")
    print("1. Open-ended")
    print("2. Multiple Choice (MCQ)")
    print("3. Pseudocode")
    print("4. Coding/Design")
    while True:
        t = input("Choice (1-4): ").strip()
        if t in ['1', '2', '3', '4']:
            return ['open', 'mcq', 'pseudocode', 'coding'][int(t)-1]
        print("Invalid choice.")

def get_programming_language():
    """Prompt for programming language (only for coding/pseudocode)."""
    print("\nSelect programming language:")
    languages = ["python", "java", "cpp", "javascript"]
    for i, lang in enumerate(languages, 1):
        print(f"{i}. {lang.capitalize()}")
    while True:
        choice = input("Choice (1-4): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(languages):
            return languages[int(choice)-1]
        print("Invalid choice.")

# --------------------------------------------------
# Question generation functions
# --------------------------------------------------
def generate_rag_questions(subject, topic, num_questions=3, difficulty="medium", qtype="open"):
    print("\n" + "="*60)
    print(f"❓ GENERATING {num_questions} {qtype.upper()} QUESTION(S) ON: {topic.upper()} ({difficulty})")
    print("="*60)

    # For coding/pseudocode, ask language once (if batch, we could ask per question, but we'll do once)
    language = "python"
    if qtype in ["coding", "pseudocode"]:
        language = get_programming_language()

    questions = []
    for i in range(num_questions):
        context = get_best_context(subject, topic)
        if not context:
            print(f"⚠️  Could not find relevant content for: {topic}")
            break

        if qtype == "mcq":
            q_data = generate_mcq(context, concept=topic, difficulty=difficulty)
            question = q_data.get('question', '')
            options = q_data.get('options', [])
            correct = q_data.get('correct', '')
            questions.append({
                'question_num': i + 1,
                'question': question,
                'options': options,
                'correct_answer': correct,
                'type': 'mcq',
                'source_context': context[:300] + "..."
            })
        else:
            q_data = generate_question_by_type(context, concept=topic, difficulty=difficulty, question_type=qtype)
            question = q_data['question']
            reference = generate_reference_answer(question, context)
            questions.append({
                'question_num': i + 1,
                'question': question,
                'reference_answer': reference,
                'type': qtype,
                'source_context': context[:300] + "...",
                'language': language  # store for reference
            })

        print(f"\n📌 Question {i+1}:")
        print(f"   {question}")
        if qtype == "mcq":
            for opt in options:
                print(f"   {opt}")
            print(f"   Correct: {correct}")
        else:
            print(f"\n📖 Reference Answer (partial):")
            print(f"   {reference[:200]}...")
    return questions

# --------------------------------------------------
# Interactive mode with difficulty and MCQ
# --------------------------------------------------
def interactive_mode(subject):
    print("\n" + "="*60)
    print("🎯 INTERACTIVE MODE – Ask About Any Topic")
    print("="*60)
    print("You will be prompted for difficulty and question type.")
    print("Type 'quit' to exit.\n")

    while True:
        topic = input("📝 Enter a topic: ").strip()
        if topic.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        if not topic:
            print("⚠️  Please enter a valid topic\n")
            continue

        results = retrieve_relevant_content(subject, topic, top_k=3)
        if not results:
            print(f"\n❌ No relevant content found for '{topic}'\n")
            continue

        print(f"\n✅ Found {len(results)} relevant sections:")
        print("-" * 60)
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] Page {result['page']} | Relevance: {result['relevance_score']:.2%}")
            print(f"    {result['text'][:150]}...")

        context = results[0]['text']

        difficulty = get_difficulty()
        qtype = get_question_type()

        # Language selection for coding/pseudocode
        language = "python"
        if qtype in ["coding", "pseudocode"]:
            language = get_programming_language()

        if qtype == "mcq":
            q_data = generate_mcq(context, concept=topic, difficulty=difficulty)
            question = q_data.get('question', '')
            options = q_data.get('options', [])
            correct = q_data.get('correct', '')
            print(f"\n🤖 MCQ QUESTION ({difficulty}):")
            print(f"   {question}")
            for opt in options:
                print(f"   {opt}")
            student_answer = input("\n✍️  Enter your answer (A/B/C/D) or press Enter to skip: ").strip().upper()
            if student_answer:
                is_correct = (student_answer == correct)
                score = 100 if is_correct else 0
                grade = 'A' if is_correct else 'F'
                log_evaluation(topic, difficulty, qtype, score, grade)
                print(f"\n📊 RESULT: {'✅ Correct!' if is_correct else '❌ Incorrect'}")
                print(f"   Score: {score}/100")
                print(f"   Grade: {grade}")
                if not is_correct:
                    print(f"   Correct answer: {correct}")
            else:
                print(f"\n📖 Correct answer: {correct}")

        else:
            q_data = generate_question_by_type(context, concept=topic, difficulty=difficulty, question_type=qtype)
            question = q_data['question']
            print(f"\n🤖 {qtype.upper()} QUESTION ({difficulty}):")
            print(f"   {question}")

            test_cases = []
            if qtype in ["coding", "pseudocode"]:
                test_cases = load_test_cases(subject, topic)
                if not test_cases:
                    print("🧪 No pre‑defined test cases. Generating some automatically...")
                    test_cases = generate_test_cases(context, topic, num_cases=3)
                    if test_cases:
                        print(f"✅ Generated {len(test_cases)} test cases.")
                    else:
                        print("⚠️  Could not generate test cases; using semantic evaluation only.")

            student_answer = input("\n✍️  Enter your answer (or press Enter to skip): ").strip()
            if student_answer:
                reference = generate_reference_answer(question, context)
                evaluation = evaluate_answer(
                    student_answer,
                    reference,
                    question_type=qtype,
                    test_cases=test_cases,
                    language=language
                )
                log_evaluation(topic, difficulty, qtype, evaluation['score'], evaluation['grade'])
                print(f"\n📊 EVALUATION RESULT:")
                print(f"   Overall Score: {evaluation['score']:.1f}/100")
                print(f"   Grade: {evaluation['grade']}")

                if qtype in ["coding", "pseudocode"]:
                    # Code evaluation details
                    print(f"   Syntax Errors: {len(evaluation.get('syntax_errors', []))}")
                    print(f"   Passed Tests: {evaluation.get('passed_tests', 0)}/{evaluation.get('total_tests', 0)}")
                    print(f"   Semantic Similarity: {evaluation.get('semantic_similarity', 0.0):.2f}")
                    if evaluation.get('feedback_text'):
                        print(f"\n📝 Detailed Code Feedback:")
                        print(f"   {evaluation['feedback_text']}")
                else:
                    print(f"   Semantic: {evaluation['rubric']['semantic_score']:.1f}%")
                    print(f"   Concept Coverage: {evaluation['rubric']['concept_score']:.1f}%")
                    print(f"   Clarity: {evaluation['rubric']['clarity_score']:.1f}%")
                    print(f"   Matched Concepts: {', '.join(evaluation['matched_keywords']) or 'None'}")
                    print(f"   Missing Concepts: {', '.join(evaluation['missing_keywords'][:6]) or 'None'}")
                    print(f"\n🤖 AI Feedback:")
                    print(f"   {evaluation['ai_feedback']}")
                print(f"\n📖 Reference Answer:")
                print(f"   {reference}")
            else:
                print("\n📖 Reference Answer (for learning):")
                print(f"   {generate_reference_answer(question, context)}")

        print("\n" + "-" * 60)

# --------------------------------------------------
# MCQ Quiz Mode
# --------------------------------------------------
def mcq_quiz_mode(subject):
    print("\n" + "=" * 60)
    print("🧠 MCQ QUIZ MODE")
    print("=" * 60)
    print(f"📚 Subject: {subject.upper()}")
    print("You will be given a series of multiple‑choice questions.\n")

    topic = input("📝 Enter a topic (e.g., OSI, TCP, routing): ").strip()
    if not topic:
        print("❌ Please enter a valid topic.\n")
        return

    difficulty = get_difficulty()
    num = input("How many questions? (default: 5): ").strip()
    num = int(num) if num.isdigit() else 5

    results = retrieve_relevant_content(subject, topic, top_k=num * 2, similarity_threshold=0.15)
    if not results:
        print(f"❌ No relevant content found for '{topic}' in the '{subject}' knowledge base.\n")
        return

    print(f"\nGenerating {num} MCQ(s) on '{topic}' ({difficulty})...\n")
    correct_count = 0
    attempted = 0

    import random
    random.shuffle(results)

    for i in range(num):
        chunk_idx = i % len(results)
        context = results[chunk_idx]['text']

        q_data = generate_mcq(context, concept=topic, difficulty=difficulty, variant=i)

        if not q_data.get('question'):
            print(f"⚠️  Could not generate MCQ. Skipping question {i+1}.")
            continue

        attempted += 1
        print(f"Q{attempted}: {q_data['question']}")
        for opt in q_data['options']:
            print(f"   {opt}")

        ans = input("Your answer (A/B/C/D): ").strip().upper()
        if ans == q_data.get('correct', ''):
            correct_count += 1
            print("✅ Correct!\n")
        else:
            print(f"❌ Incorrect. Correct answer: {q_data.get('correct', 'N/A')}\n")

    if attempted == 0:
        print("No questions were generated. Exiting quiz.")
        return

    score_percent = (correct_count / attempted) * 100
    print(f"\n🎯 You got {correct_count} out of {attempted} correct ({score_percent:.1f}%).")

    grade = 'A' if score_percent >= 80 else 'B' if score_percent >= 60 else 'C' if score_percent >= 40 else 'F'
    log_evaluation(topic, difficulty, "mcq_quiz", score_percent, grade)
    print("✅ Progress saved.\n")

# --------------------------------------------------
# View Progress
# --------------------------------------------------
def view_progress():
    stats = get_stats()
    if not stats:
        print("No progress records found.")
        return
    print("\n" + "="*60)
    print("📊 YOUR PROGRESS")
    print("="*60)
    print(f"Total attempts: {stats['total_attempts']}")
    print(f"Average score: {stats['avg_score']:.1f}%")
    print(f"Best score: {stats['max_score']:.1f}%")
    print(f"Grade distribution: {stats['grade_dist']}")
    print("\n📋 Recent history (last 5):")
    history = get_history(limit=5)
    for entry in history:
        print(f"  {entry['timestamp']} | {entry['topic']} | {entry['difficulty']} | {entry['type']} | Score: {entry['score']:.1f} | Grade: {entry['grade']}")
    print("="*60)

# --------------------------------------------------
# Main menu
# --------------------------------------------------
def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  PDF-BASED RAG SYSTEM FOR INTERVIEW PREPARATION  ".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")

    subject = setup_knowledge_base()
    if subject is None:
        return

    while True:
        print("\n" + "="*60)
        print("MAIN MENU")
        print("="*60)
        print("1. Interactive Mode (ask about topics)")
        print("2. Generate Questions for a Topic")
        print("3. MCQ Quiz Mode")
        print("4. View Progress")
        print("5. Demonstrate RAG System (sample)")
        print("6. Batch Generate from File")
        print("7. Exit")
        print("="*60)
        choice = input("📍 Select option (1-7): ").strip()

        if choice == "1":
            interactive_mode(subject)
        elif choice == "2":
            topic = input("\n📝 Enter topic: ").strip()
            if not topic:
                print("No topic entered.")
                continue
            difficulty = get_difficulty()
            qtype = get_question_type()
            num = input("How many questions? (default: 3): ").strip()
            num = int(num) if num.isdigit() else 3
            generate_rag_questions(subject, topic, num, difficulty, qtype)
        elif choice == "3":
            mcq_quiz_mode(subject)
        elif choice == "4":
            view_progress()
        elif choice == "5":
            demonstrate_rag(subject)
        elif choice == "6":
            batch_generate_questions(subject)
        elif choice == "7":
            print("\n👋 Thank you for using RAG System!")
            break
        else:
            print("\n⚠️  Invalid option. Please select 1-7.")

# --------------------------------------------------
# Demonstration (unchanged)
# --------------------------------------------------
def demonstrate_rag(subject):
    print("\n" + "="*60)
    print("🎓 RAG SYSTEM DEMONSTRATION")
    print("="*60)
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
        results = retrieve_relevant_content(subject, topic, top_k=1)
        if results:
            result = results[0]
            print(f"\n📖 Retrieved Content:")
            print(f"  Page {result['page']} - Relevance: {result['relevance_score']:.1%}")
            print(f"  {result['text'][:200]}...")
            context = result['text']
            question = generate_interview_question(context, concept=topic)
            print(f"\n🤖 Generated Question:")
            print(f"  {question}")
            reference = generate_reference_answer(question, context)
            sample_answer = "This concept involves network operations."
            evaluation = evaluate_answer(sample_answer, reference)
            print(f"\n📊 Sample Evaluation (on a basic answer):")
            print(f"  Score: {evaluation['score']:.1f}/100")
            print(f"  Grade: {evaluation['grade']}")
            print(f"\n🤖 AI Feedback:")
            print(f"  {evaluation['ai_feedback']}")
        else:
            print(f"⚠️  No content found for this topic")

def batch_generate_questions(subject, topics_file="topics.txt"):
    if not Path(topics_file).exists():
        print(f"❌ Topics file not found: {topics_file}")
        return
    print("\n" + "="*60)
    print(f"📚 BATCH GENERATING QUESTIONS FROM: {topics_file}")
    print("="*60)
    with open(topics_file, 'r') as f:
        topics = [line.strip() for line in f if line.strip()]
    all_questions = []
    for topic in tqdm(topics, desc="Generating questions"):
        results = retrieve_relevant_content(subject, topic, top_k=1)
        if results:
            context = results[0]['text']
            question = generate_interview_question(context, concept=topic)
            reference = generate_reference_answer(question, context)
            all_questions.append({
                'topic': topic,
                'question': question,
                'reference': reference,
                'page': results[0]['page']
            })
    output_file = "generated_questions.txt"
    with open(output_file, 'w') as f:
        for item in all_questions:
            f.write(f"Topic: {item['topic']}\n")
            f.write(f"Question: {item['question']}\n")
            f.write(f"Reference: {item['reference']}\n")
            f.write(f"Source Page: {item['page']}\n")
            f.write("-" * 60 + "\n")
    print(f"\n✅ Generated {len(all_questions)} questions!")
    print(f"   Saved to: {output_file}")

if __name__ == "__main__":
    main()