from __future__ import annotations

from inference.input_validation import invalid_question_error, is_valid_question
from inference.predict_difficulty import predict_difficulty
from inference.predict_intent import predict_intent
from inference.predict_profile import predict_question_profile
from inference.predict_topic import predict_topic
from adaptive.session_manager import SessionManager


def format_topic_output(result: dict[str, object]) -> str:
    labels = result["labels"]
    if isinstance(labels, list):
        return ", ".join(labels)
    return str(labels)


def classify_single_question() -> None:
    """Classify a single question (original functionality)."""
    text = input("Enter a question or statement: ").strip()
    if not text:
        raise ValueError("Input text cannot be empty")
    if not is_valid_question(text):
        print(invalid_question_error()["error"])
        return

    profile_result = predict_question_profile(text)
    intent_result = predict_intent(text)
    difficulty_result = predict_difficulty(text)
    topic_result = predict_topic(text)

    print("\nPrediction Summary")
    print(f"Intent: {profile_result['intent']} ({intent_result['confidence']:.4f})")
    print(f"Difficulty: {profile_result['difficulty']} ({difficulty_result['confidence']:.4f})")
    print(f"Confidence: {profile_result['confidence']:.4f}")
    print(f"Topics: {format_topic_output(topic_result)}")


def start_adaptive_session() -> None:
    """Start an adaptive learning session."""
    user_id = input("Enter your username (e.g., john_doe): ").strip()
    if not user_id:
        user_id = "guest"
    
    session = SessionManager(user_id)
    
    # Show menu
    while True:
        print("\n" + "="*60)
        print(f"Adaptive Interview Practice - {user_id}")
        print("="*60)
        print("Options:")
        print("1. View Your Profile & Stats")
        print("2. Start Practice Session")
        print("3. Get Personalized Recommendation")
        print("4. Return to Main Menu")
        
        choice = input("\nSelect an option (1-4): ").strip()
        
        if choice == "1":
            session.display_profile_summary()
        elif choice == "2":
            num_q = input("How many questions? (default 5): ").strip()
            try:
                num_q = int(num_q) if num_q else 5
            except ValueError:
                num_q = 5
            session = SessionManager(user_id)  # Refresh session
            session.start_session(num_questions=num_q)
        elif choice == "3":
            print(f"\nPersonalized Recommendation for {user_id}:")
            print(f"  {session.get_recommendation()}")
        elif choice == "4":
            break
        else:
            print("Invalid option. Please select 1-4.")


def main() -> None:
    """Main menu."""
    print("\n" + "="*60)
    print("Question Classification & Adaptive Interview Practice Tool")
    print("="*60)
    
    while True:
        print("\nMain Menu:")
        print("1. Classify a Single Question")
        print("2. Start Adaptive Learning Session")
        print("3. Exit")
        
        choice = input("\nSelect an option (1-3): ").strip()
        
        if choice == "1":
            print("\n--- Single Question Classification ---")
            classify_single_question()
        elif choice == "2":
            print("\n--- Adaptive Learning Session ---")
            start_adaptive_session()
        elif choice == "3":
            print("Thank you for using the tool! Goodbye!")
            break
        else:
            print("Invalid option. Please select 1-3.")


if __name__ == "__main__":
    main()
