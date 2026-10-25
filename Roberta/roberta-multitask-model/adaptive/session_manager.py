"""Interactive session manager for adaptive question practice."""

from __future__ import annotations

from typing import Optional

from inference.predict_intent import predict_intent
from inference.predict_difficulty import predict_difficulty
from inference.predict_topic import predict_topic
from inference.input_validation import is_valid_question

from adaptive.user_profile import UserProfile, UserProfileManager
from adaptive.adaptive_selector import AdaptiveSelector, QuestionDataset
from adaptive.question_specific_answers import question_specific_generator


class SessionManager:
    """Manage an interactive question-answer session."""
    
    def __init__(
        self,
        user_id: str,
        dataset: Optional[QuestionDataset] = None,
        profile_manager: Optional[UserProfileManager] = None,
    ):
        self.user_id = user_id
        self.dataset = dataset or QuestionDataset()
        self.profile_manager = profile_manager or UserProfileManager()
        self.selector = AdaptiveSelector(self.dataset)
        
        # Load or create user profile
        self.profile = self.profile_manager.get_or_create_profile(user_id)
        
        # Session tracking
        self.session_questions: list[tuple] = []
        self.asked_question_texts: set[str] = set()  # Track asked questions to avoid repeats
    
    def display_profile_summary(self) -> None:
        """Display user's current profile and stats."""
        print("\n" + "="*60)
        print(f"USER PROFILE: {self.user_id}")
        print("="*60)
        print(f"Current Level: {self.profile.current_level.upper()}")
        print(f"Overall Accuracy: {self.profile.overall_accuracy:.1f}%")
        print(f"Questions Attempted: {self.profile.total_attempted}")
        print(f"Correct Answers: {self.profile.total_correct}")
        
        print("\nTopic Performance:")
        for topic in ["OS", "DBMS", "CN", "OOP", "DSA", "General"]:
            if topic in self.profile.topic_stats:
                stats = self.profile.topic_stats[topic]
                if stats.attempted > 0:
                    print(
                        f"  {topic}: {stats.accuracy:.1f}% "
                        f"({stats.correct}/{stats.attempted}) - {stats.strength_level}"
                    )
        
        weak_topics = self.profile.get_weak_topics()
        if weak_topics:
            print(f"\nAreas to Improve: {', '.join(weak_topics)}")
        
        print("="*60 + "\n")
    
    def start_session(self, num_questions: int = 5) -> None:
        """Start an interactive session with questions."""
        print(f"\nStarting session for {self.user_id}...")
        print(f"You will be asked {num_questions} questions.")
        print("Type your answer and press Enter.")
        print("Type 'quit' to exit the session.\n")
        
        self.display_profile_summary()
        
        session_scores = []  # Track scores in this session for adaptive difficulty
        
        for i in range(num_questions):
            print(f"\n{'='*60}")
            print(f"Question {i + 1}/{num_questions}")
            print(f"Current Level: {self.profile.current_level}")
            print(f"Overall Accuracy: {self.profile.overall_accuracy:.1f}%")
            print('='*60)
            
            question = self.selector.select_next_question(self.profile)
            
            if question is None:
                print("No more questions available. Session ended.")
                break
            
            # Avoid asking the same question twice in a session
            max_attempts = 10
            attempts = 0
            while question.text in self.asked_question_texts and attempts < max_attempts:
                question = self.selector.select_next_question(self.profile)
                attempts += 1
            
            if question.text in self.asked_question_texts:
                print("No new questions available. Session ended.")
                break
            
            self.asked_question_texts.add(question.text)
            
            # Ask the question
            print(f"\nQ: {question.text}")
            print(f"Topic: {', '.join(question.topics)} | "
                  f"Difficulty: {question.difficulty} | "
                  f"Type: {question.intent}")
            
            # Get user's answer
            user_answer = input("\nYour answer: ").strip()
            
            if user_answer.lower() == 'quit':
                print("Session ended by user.")
                break
            
            # Evaluate answer with detailed scoring
            evaluation = self._evaluate_answer(user_answer, question)
            is_correct = evaluation["is_correct"]
            score = evaluation["score"]
            grade = evaluation["grade"]
            
            # Track score for difficulty progression
            session_scores.append(score)
            
            # Display feedback
            self._display_feedback(evaluation, question, user_answer)
            
            # Record attempt with score (not binary correct/incorrect)
            self.profile.record_attempt(
                score=score,
                topic=question.topics[0] if question.topics else "General",
                intent=question.intent,
                difficulty=question.difficulty,
                time_seconds=0.0
            )
            
            # Save profile
            self.profile_manager.save_profile(self.profile)
            
            # Store in session
            self.session_questions.append((question, is_correct))
        
        # Check if user should progress to harder difficulty
        self._check_difficulty_progression(session_scores)
        
        # Display session summary
        self.display_session_summary()
    
    def _check_difficulty_progression(self, session_scores: list) -> None:
        """
        Check if user should progress to next difficulty level.
        
        Current dataset thresholds (TESTING):
        - Beginner (easy) → Intermediate (medium): 80% on 5+ questions (for testing - lower threshold)
        - Future: Will increase to 10+ questions for stability when live
        """
        # Need at least 5 questions to determine readiness for intermediate level (testing)
        if len(session_scores) < 5:
            return
        
        recent_accuracy = sum(session_scores) / len(session_scores)
        
        if recent_accuracy >= 80 and self.profile.target_difficulty == "easy":
            # UPGRADE TARGET DIFFICULTY FROM EASY → MEDIUM
            prev_level = self.profile.current_level
            self.profile.target_difficulty = "medium"
            self.profile_manager.save_profile(self.profile)
            
            print("\n" + "="*70)
            print("🎉 EXCELLENT PROGRESS!")
            print(f"Average Score: {recent_accuracy:.1f}% on {len(session_scores)} questions!")
            print("\n✅ LEVEL UPGRADE DETECTED!")
            print(f"   Previous Level: {prev_level.upper()}")
            print(f"   Updated Level: INTERMEDIATE")
            print(f"   Average Score: {recent_accuracy:.1f}%")
            print(f"   Next Question Difficulty: MEDIUM")
            print("="*70 + "\n")
    
    def _evaluate_answer(self, user_answer: str, question) -> dict:
        """
        Evaluate the user's answer with nuanced scoring.
        
        Returns a dict with:
        - score: 0-100 score
        - grade: "excellent" | "mostly_correct" | "partially_correct" | "blatantly_wrong"
        - is_correct: bool (True if score >= 60)
        - reasoning: explanation of the grade
        - missing_concepts: what they missed (if applicable)
        """
        # Empty answer = blatantly wrong
        if not user_answer or len(user_answer.strip()) < 2:
            return {
                "score": 0,
                "grade": "blatantly_wrong",
                "is_correct": False,
                "reasoning": "No answer provided",
                "missing_concepts": ["Complete answer"],
            }
        
        # Basic text validation (just check it's coherent, not a question format)
        if not self._is_valid_answer(user_answer):
            return {
                "score": 5,
                "grade": "blatantly_wrong",
                "is_correct": False,
                "reasoning": "Answer doesn't seem to be coherent text",
                "missing_concepts": ["Coherent response"],
            }
        
        # Get predictions for the user's answer
        answer_intent = predict_intent(user_answer)
        answer_topic = predict_topic(user_answer)
        
        # Extract prediction data
        answer_intent_label = answer_intent.get("label", "unknown")
        answer_intent_conf = answer_intent.get("confidence", 0.0)
        answer_topics = answer_topic.get("labels", [])
        
        # Calculate component scores
        scores = self._calculate_component_scores(
            user_answer,
            question,
            answer_intent_label,
            answer_intent_conf,
            answer_topics
        )
        
        # Determine overall grade and correctness
        overall_score = scores["overall_score"]
        grade = self._determine_grade(overall_score)
        is_correct = overall_score >= 60
        
        # Identify missing concepts
        missing = self._identify_missing_concepts(
            scores, question, answer_topics, answer_intent_label
        )
        
        return {
            "score": overall_score,
            "grade": grade,
            "is_correct": is_correct,
            "reasoning": self._get_grade_explanation(grade, scores),
            "missing_concepts": missing,
            "component_scores": scores,
        }
    
    def _is_valid_answer(self, text: str) -> bool:
        """Check if answer is valid text (not a question itself)."""
        # Should be actual text, not empty
        if not text or len(text.strip()) < 2:
            return False
        
        # Simple check: has alphanumeric characters
        if not any(c.isalnum() for c in text):
            return False
        
        return True
    
    def _check_answer_coherence(self, user_answer: str) -> bool:
        """Check if answer makes sense and is coherent, not keyword spam.
        
        Returns True if the answer forms logical sentences or meaningful phrases,
        not just random keywords or code snippets.
        """
        answer_lower = user_answer.lower()
        
        # Code-like patterns are not valid answers (printf, brackets, etc)
        if any(pattern in answer_lower for pattern in ['(', ')', '{', '}', '<<', '>>', ';', '//']):
            # But allow parentheses in normal explanations like "CPU(s)" or "(e.g., Windows)"
            word_count = len(user_answer.split())
            if word_count < 5:  # Very short with code syntax = likely code snippet
                return False
        
        # Must have at least some basic sentence structure (a subject-like word or action word)
        # Include verb roots and common variations
        common_verbs = ["is ", "are ", "be ", "manag", "handle", "provid", "perform", 
                       "involv", "mean", "refer", "call", "use", "contain", "describ",
                       "explain", "show", "keep", "store", "controll", "creat", "allocat"]
        has_verb = any(verb in answer_lower for verb in common_verbs)
        
        # Or must have multiple words with at least 2 distinct "concept" words
        words = answer_lower.split()
        word_count = len(words)
        
        # If it's short and has no verbs, it needs to make sense as a phrase
        if word_count < 5 and not has_verb:
            # Very short: only 2-4 words. Needs to be meaningful phrase like "process management"
            # Not "hello world test" or random words
            return False
        
        # Longer answers (5+ words): less strict, just needs coherence
        # Check if words form meaningful semantic units (not random scrambled)
        return True
    
    def _get_grade_explanation(self, grade: str, scores: dict) -> str:
        """Get explanation text for the grade."""
        if grade == "excellent":
            return f"Excellent answer! You demonstrated strong understanding (Score: {scores.get('overall_score', 0):.0f}/100)."
        elif grade == "mostly_correct":
            return f"Good answer! You covered most of the key points (Score: {scores.get('overall_score', 0):.0f}/100)."
        elif grade == "partially_correct":
            return f"Partially correct. You addressed some aspects but missed others (Score: {scores.get('overall_score', 0):.0f}/100)."
        else:
            return f"This answer doesn't correctly address the question (Score: {scores.get('overall_score', 0):.0f}/100)."
    
    def _calculate_component_scores(
        self,
        user_answer: str,
        question,
        answer_intent: str,
        answer_intent_conf: float,
        answer_topics: list[str]
    ) -> dict:
        """Calculate component scores with 3-tier system: irrelevant (0-30), partial (40-70), correct (75-100)."""
        scores = {}
        word_count = len(user_answer.split())
        answer_lower = user_answer.lower()
        
        # CHECK COHERENCE FIRST - answer must make sense, not be keyword spam or code
        is_coherent = self._check_answer_coherence(user_answer)
        
        # FIRST CHECK: Is the answer relevant to the question topic at all?
        # This prevents stupid answers like "printf(hello)" from getting high scores
        question_topics = set(question.topics)
        topic_keywords = []
        for topic in question_topics:
            topic_keywords.extend(self._get_topic_keywords(topic))
        
        # Count how many topic keywords appear in the answer
        matching_keywords = sum(1 for keyword in topic_keywords if keyword.lower() in answer_lower)
        relevance_score = (matching_keywords / max(len(topic_keywords), 1)) if topic_keywords else 0.5
        
        # Determine topic coverage based on keyword matching AND coherence
        # Score ranges:
        # - Incoherent: 0-30 (stupid answers)
        # - Partial coherent: 40-60 (basic but relevant - 1-2 keywords)
        # - Good: 75-100 (comprehensive and relevant - 3+ keywords)
        
        if not is_coherent:
            # Answer doesn't make sense - harsh penalty even if has keywords
            scores["topic_coverage"] = 8  # Incoherent answers get near-zero
        
        elif matching_keywords >= 3:
            # Answer has MULTIPLE relevant keywords (3+) AND makes sense - good topic coverage
            answer_topics_set = set(answer_topics)
            if question_topics & answer_topics_set:
                topic_overlap = len(question_topics & answer_topics_set) / len(question_topics)
                scores["topic_coverage"] = 78 + (topic_overlap * 22)  # 78-100 (good/excellent)
            else:
                # Has keywords but topic classifier didn't match - still good
                scores["topic_coverage"] = 75 + (relevance_score * 20)  # 75-95 (good)
        
        elif matching_keywords >= 1:
            # 1-2 keywords AND coherent - PARTIAL, not comprehensive
            # Cap at 60 to keep it in "partial" range
            scores["topic_coverage"] = 45 + (relevance_score * 15)  # 45-60 (partial)
        
        elif word_count >= 5:
            # No keywords but substantial answer - might be trying to explain concept
            # Still partial at best
            scores["topic_coverage"] = 35
        
        else:
            # No keywords and short - definitely irrelevant
            scores["topic_coverage"] = 10  # Incoherent answers
        
        # SECOND CHECK: Intent alignment
        if answer_intent == question.intent:
            scores["intent_match"] = 100
        elif self._are_intents_similar(answer_intent, question.intent):
            scores["intent_match"] = 85
        else:
            # Check if answer at least has defining characteristics of the intent
            if question.intent in ["definition", "explanation"] and word_count >= 5:
                scores["intent_match"] = 65  # At least trying to explain
            else:
                scores["intent_match"] = 45  # Wrong intent type
        
        # THIRD CHECK: Comprehensiveness (but only if answer is relevant)
        if scores["topic_coverage"] < 20:
            # Irrelevant answer - no credit for comprehensiveness
            scores["comprehensiveness"] = 5
        
        elif scores["topic_coverage"] < 70:
            # PARTIAL ANSWER - keep comprehensiveness low so overall stays in 40-60 range
            # These answers have only 1 keyword, so they're incomplete
            if question.intent == "definition":
                if word_count >= 10:
                    scores["comprehensiveness"] = 55
                elif word_count >= 5:
                    scores["comprehensiveness"] = 45
                else:
                    scores["comprehensiveness"] = 30
            
            elif question.intent == "explanation":
                if word_count >= 15:
                    scores["comprehensiveness"] = 55
                elif word_count >= 10:
                    scores["comprehensiveness"] = 45
                elif word_count >= 5:
                    scores["comprehensiveness"] = 35
                else:
                    scores["comprehensiveness"] = 25
            
            else:
                # Other intents
                if word_count >= 10:
                    scores["comprehensiveness"] = 50
                elif word_count >= 5:
                    scores["comprehensiveness"] = 40
                else:
                    scores["comprehensiveness"] = 25
        
        else:
            # GOOD ANSWER (topic_coverage >= 75) - full comprehensiveness scoring
            # Score based on depth and content quality
            if question.intent == "definition":
                if word_count >= 30:
                    scores["comprehensiveness"] = 100
                elif word_count >= 20:
                    scores["comprehensiveness"] = 95
                elif word_count >= 15:
                    scores["comprehensiveness"] = 92
                elif word_count >= 10:
                    scores["comprehensiveness"] = 88
                elif word_count >= 8:
                    scores["comprehensiveness"] = 82
                elif word_count >= 5:
                    scores["comprehensiveness"] = 78
                elif word_count >= 3:
                    scores["comprehensiveness"] = 65
                else:
                    scores["comprehensiveness"] = 50
            
            elif question.intent == "explanation":
                if word_count >= 30:
                    scores["comprehensiveness"] = 100
                elif word_count >= 25:
                    scores["comprehensiveness"] = 95
                elif word_count >= 15:
                    scores["comprehensiveness"] = 90
                elif word_count >= 10:
                    scores["comprehensiveness"] = 85
                elif word_count >= 5:
                    scores["comprehensiveness"] = 70
                else:
                    scores["comprehensiveness"] = 50
            
            elif question.intent == "comparison":
                has_comparison_words = any(
                    word in answer_lower for word in ["vs", "compare", "difference", "similar", "same", "unlike", "while"]
                )
                if has_comparison_words and word_count >= 20:
                    scores["comprehensiveness"] = 95
                elif has_comparison_words and word_count >= 15:
                    scores["comprehensiveness"] = 90
                elif has_comparison_words and word_count >= 8:
                    scores["comprehensiveness"] = 80
                elif has_comparison_words:
                    scores["comprehensiveness"] = 70
                else:
                    scores["comprehensiveness"] = 40  # No actual comparison
            
            elif question.intent == "procedure":
                has_steps = any(
                    word in answer_lower
                    for word in ["step", "then", "first", "next", "finally", "1.", "2.", "->", "process"]
                )
                if has_steps and word_count >= 25:
                    scores["comprehensiveness"] = 95
                elif has_steps and word_count >= 15:
                    scores["comprehensiveness"] = 90
                elif has_steps and word_count >= 10:
                    scores["comprehensiveness"] = 80
                elif has_steps:
                    scores["comprehensiveness"] = 70
                else:
                    scores["comprehensiveness"] = 40
            
            elif question.intent == "reasoning":
                has_reasoning = any(
                    word in answer_lower
                    for word in ["because", "reason", "since", "therefore", "thus", "why", "how", "caused", "due to"]
                )
                if has_reasoning and word_count >= 20:
                    scores["comprehensiveness"] = 95
                elif has_reasoning and word_count >= 15:
                    scores["comprehensiveness"] = 90
                elif has_reasoning and word_count >= 8:
                    scores["comprehensiveness"] = 80
                elif has_reasoning:
                    scores["comprehensiveness"] = 65
                else:
                    scores["comprehensiveness"] = 40
            
            else:
                # Generic question type
                if word_count >= 20:
                    scores["comprehensiveness"] = 95
                elif word_count >= 15:
                    scores["comprehensiveness"] = 90
                elif word_count >= 10:
                    scores["comprehensiveness"] = 85
                elif word_count >= 8:
                    scores["comprehensiveness"] = 80
                elif word_count >= 5:
                    scores["comprehensiveness"] = 70
                else:
                    scores["comprehensiveness"] = 60
        
        # Calculate weighted overall score
        overall = (
            scores.get("topic_coverage", 50) * 0.50 +  # Topic is most important!
            scores.get("intent_match", 50) * 0.25 +
            scores.get("comprehensiveness", 50) * 0.25
        )
        
        # BONUS: Check how well answer matches the model answer
        # If it closely matches, reward with higher score (85-100 range)
        model_answer_bonus = self._calculate_model_answer_bonus(user_answer, question)
        
        # Apply bonus only if overall score is already good (>= 75)
        if overall >= 75 and model_answer_bonus > 0:
            # Blend current score with model answer bonus
            # Higher match = higher final score (up to 100)
            overall = overall + (model_answer_bonus * 0.25)  # Can push from 75-80 to 80-100
        
        # Cap at 100
        overall = min(overall, 100)
        
        scores["overall_score"] = min(100, max(0, overall))
        
        return scores
    
    def _determine_grade(self, score: float) -> str:
        """Determine grade from score."""
        if score >= 85:
            return "excellent"
        elif score >= 65:
            return "mostly_correct"
        elif score >= 40:
            return "partially_correct"
        else:
            return "blatantly_wrong"
    
    def _identify_missing_concepts(
        self,
        scores: dict,
        question,
        answer_topics: list[str],
        answer_intent: str
    ) -> list[str]:
        """Identify what's missing from the answer."""
        missing = []
        
        # Check topic gaps
        if scores.get("topic_coverage", 0) < 50:
            missing.append(f"Core topic knowledge ({', '.join(question.topics)})")
        
        # Check intent gaps
        if scores.get("intent_match", 0) < 50:
            missing.append(f"More {question.intent} (currently sounds like {answer_intent})")
        
        # Check comprehensiveness gaps
        if scores.get("comprehensiveness", 0) < 60:
            if question.intent == "explanation":
                missing.append("More detailed explanation")
            elif question.intent == "procedure":
                missing.append("Step-by-step process description")
            elif question.intent == "comparison":
                missing.append("Comparison of key aspects")
            elif question.intent == "reasoning":
                missing.append("Logical reasoning or justification")
            else:
                missing.append("More comprehensive answer")
        
        return missing if missing else ["Overall seems good, keep practicing!"]
    
    def _are_intents_similar(self, intent1: str, intent2: str) -> bool:
        """Check if two intents are similar."""
        similar_pairs = [
            {"definition", "explanation"},
            {"comparison", "procedure"},
        ]
        return {intent1, intent2} in similar_pairs
    
    def _get_topic_keywords(self, topic: str) -> list[str]:
        """Get keywords associated with each topic."""
        keywords = {
            "OS": ["process", "thread", "memory", "cpu", "interrupt", "scheduling", "deadlock", "paging", 
                   "virtual", "context", "operating", "system", "os", "kernel", "program", "resource", "hardware"],
            "DBMS": ["database", "query", "schema", "transaction", "index", "sql", "table", "record", "data", 
                     "manage", "store", "retrieve", "dbms", "relation", "acid"],
            "CN": ["network", "protocol", "packet", "routing", "bandwidth", "latency", "tcp", "udp", "ip", 
                   "communication", "data", "device", "connection", "internet"],
            "OOP": ["class", "object", "inheritance", "polymorphism", "encapsulation", "method", "property",
                    "oop", "programming", "instance", "attribute", "abstraction"],
            "DSA": ["array", "linked", "tree", "graph", "sort", "search", "stack", "queue", "algorithm",
                    "data", "structure", "dsa", "efficiency", "complexity"],
            "General": ["algorithm", "problem", "solution", "approach", "technique"],
        }
        return keywords.get(topic, [topic.lower()])
    
    def _calculate_model_answer_bonus(self, user_answer: str, question) -> float:
        """
        Calculate bonus score (0-100) based on how well answer matches model answer.
        
        Bonus is applied to answers that already score 75+.
        - 0-20: Poor match (20% keywords overlap)
        - 20-40: Fair match (40% keywords)
        - 40-60: Good match (60% keywords)
        - 60-80: Very good match (80% keywords)
        - 80-100: Excellent match (matches model answer structure and depth)
        """
        try:
            # Get the model answer using imported generator
            model_answer = question_specific_generator.generate_model_answer(
                question.text,
                question.intent,
                question.topics,
                question.difficulty
            )
        except:
            return 0  # No bonus if can't get model answer
        
        # Extract key terms from both answers
        user_words = set(user_answer.lower().split())
        model_words = set(model_answer.lower().split())
        
        # Remove common stopwords
        stopwords = {"a", "an", "the", "is", "are", "be", "in", "of", "to", "for", "and", "or", "it", "that", "this", "by", "on", "at", "as", "with", "from"}
        user_key_words = user_words - stopwords
        model_key_words = model_words - stopwords
        
        # Calculate keyword overlap
        if not model_key_words:
            return 0
        
        keyword_overlap = len(user_key_words & model_key_words) / len(model_key_words)
        
        # Calculate length appropriateness (user answer shouldn't be too short compared to model)
        user_word_count = len(user_answer.split())
        model_word_count = len(model_answer.split())
        
        length_ratio = min(user_word_count / max(model_word_count, 1), 1.0)
        
        # Check if user covered main concepts (first few key words from model)
        model_first_half_words = list(model_key_words)[:min(5, len(model_key_words))]
        main_concepts_covered = sum(1 for word in model_first_half_words if word in user_key_words) / len(model_first_half_words)
        
        # Combined bonus score
        bonus = (
            keyword_overlap * 40 +  # Keyword coverage: 0-40
            length_ratio * 30 +      # Length appropriateness: 0-30
            main_concepts_covered * 30  # Main concepts: 0-30
        )
        
        return bonus
    
    def _display_feedback(
        self,
        evaluation: dict,
        question,
        user_answer: str
    ) -> None:
        """Display detailed, graduated feedback based on evaluation."""
        score = evaluation["score"]
        grade = evaluation["grade"]
        reasoning = evaluation["reasoning"]
        missing = evaluation.get("missing_concepts", [])
        
        # Visual indicator
        if grade == "excellent":
            indicator = "✓✓ Excellent!"
            color_emoji = "🌟"
        elif grade == "mostly_correct":
            indicator = "✓ Good Answer!"
            color_emoji = "👍"
        elif grade == "partially_correct":
            indicator = "~ Partially Correct"
            color_emoji = "📝"
        else:  # blatantly_wrong
            indicator = "✗ Incorrect"
            color_emoji = "❌"
        
        print(f"\n{color_emoji} {indicator}")
        print(f"Score: {score:.0f}/100")
        print(f"\n{reasoning}")
        
        # Provide specific feedback
        if grade == "excellent":
            print(f"\n✓ Perfect! You correctly answered this '{question.intent}' question about {', '.join(question.topics)}.")
            print("You demonstrated strong understanding of the topic.")
        
        elif grade == "mostly_correct":
            print(f"\n✓ Good job! You covered the main points of this {question.intent} question.")
            if missing and missing[0] != "Overall seems good, keep practicing!":
                print(f"To improve further: {missing[0]}")
            else:
                print("You're on the right track—just work on a bit more depth.")
        
        elif grade == "partially_correct":
            print(f"\n~ Your answer is partially correct. You addressed some aspects but missed others.")
            print(f"Question Type: {question.intent.capitalize()} | Topics: {', '.join(question.topics)}")
            if missing:
                print("\nWhat you missed:")
                for i, concept in enumerate(missing[:3], 1):
                    print(f"  {i}. {concept}")
            
            # Show model answer
            self._display_model_answer(question)
        
        else:  # blatantly_wrong
            print(f"\n✗ This answer doesn't address the question correctly.")
            print(f"This was a '{question.difficulty}' level '{question.intent}' question about {', '.join(question.topics)}.")
            
            # Show model answer
            self._display_model_answer(question)
    
    def _display_model_answer(self, question) -> None:
        """Display the model/correct answer for reference - now question-specific."""
        print("\n" + "="*60)
        print("MODEL ANSWER")
        print("="*60)
        
        # Generate question-specific model answer
        model_answer = question_specific_generator.generate_model_answer(
            question.text,
            question.intent,
            question.topics,
            question.difficulty
        )
        print(f"\n{model_answer}\n")
        
        # Show key points that should be included
        key_points = question_specific_generator.get_key_points(
            question.intent,
            question.topics,
            question.difficulty
        )
        
        if key_points:
            print("Key aspects to include in your answer:")
            for i, point in enumerate(key_points, 1):
                print(f"  {i}. {point}")
        
        print("\n" + "="*60)
    
    def display_session_summary(self) -> None:
        """Display summary of the session."""
        if not self.session_questions:
            print("\nNo questions were answered in this session.")
            return
        
        correct = sum(1 for _, is_correct in self.session_questions if is_correct)
        total = len(self.session_questions)
        accuracy = (correct / total) * 100
        
        print("\n" + "="*60)
        print("SESSION SUMMARY")
        print("="*60)
        print(f"Questions Answered: {total}")
        print(f"Correct: {correct}")
        print(f"Session Accuracy: {accuracy:.1f}%")
        print(f"Overall Accuracy: {self.profile.overall_accuracy:.1f}%")
        print(f"Current Level: {self.profile.current_level}")
        
        # Show weak areas
        weak_topics = self.profile.get_weak_topics()
        if weak_topics:
            print(f"\nAreas to Focus On: {', '.join(weak_topics)}")
        
        # Show recommendation
        print("\nRecommendation:")
        recommendation = self.selector._get_recommendation(self.profile)
        print(f"  {recommendation}")
        
        print("="*60)
    
    def get_recommendation(self) -> str:
        """Get personalized recommendation."""
        weak_topics = self.profile.get_weak_topics()
        weak_intents = self.profile.get_weak_intents()
        level = self.profile.current_level
        
        recommendations = []
        
        if weak_topics:
            recommendations.append(f"Study {', '.join(weak_topics[:2])} to improve.")
        
        if weak_intents:
            recommendations.append(
                f"Practice {', '.join(weak_intents[:2])} type questions."
            )
        
        if level == "beginner":
            recommendations.append("Focus on foundational concepts.")
        elif level == "advanced":
            recommendations.append("You're doing great! Try more complex problems.")
        
        return " ".join(recommendations) if recommendations else "Keep practicing!"
