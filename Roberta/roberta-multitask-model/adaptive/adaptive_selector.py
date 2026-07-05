"""Adaptive question selection based on user profile."""

from __future__ import annotations

import json
import random
from pathlib import Path
from dataclasses import dataclass

from adaptive.user_profile import UserProfile


@dataclass
class Question:
    """Represents a question from the dataset."""
    text: str
    intent: str
    difficulty: str
    topics: list[str]
    
    @staticmethod
    def from_dict(data: dict) -> Question:
        """Create Question from dictionary."""
        return Question(
            text=data["text"],
            intent=data["intent"],
            difficulty=data["difficulty"],
            topics=data["topics"]
        )


class QuestionDataset:
    """Load and manage question dataset."""
    
    def __init__(self, dataset_path: str | Path = "data/dataset.json"):
        self.dataset_path = Path(dataset_path)
        self.questions = self._load_questions()
    
    def _load_questions(self) -> list[Question]:
        """Load questions from JSON file."""
        if not self.dataset_path.exists():
            print(f"Warning: Dataset not found at {self.dataset_path}")
            return []
        
        with open(self.dataset_path, "r") as f:
            data = json.load(f)
        
        return [Question.from_dict(q) for q in data]
    
    def filter_by_topic(self, topic: str) -> list[Question]:
        """Get questions for a specific topic."""
        return [q for q in self.questions if topic in q.topics]
    
    def filter_by_difficulty(self, difficulty: str) -> list[Question]:
        """Get questions of a specific difficulty."""
        return [q for q in self.questions if q.difficulty == difficulty]
    
    def filter_by_intent(self, intent: str) -> list[Question]:
        """Get questions of a specific intent."""
        return [q for q in self.questions if q.intent == intent]
    
    def filter_by_multiple(
        self,
        topics: list[str] | None = None,
        difficulties: list[str] | None = None,
        intents: list[str] | None = None,
    ) -> list[Question]:
        """Filter questions by multiple criteria."""
        filtered = self.questions
        
        if topics:
            filtered = [q for q in filtered if any(t in q.topics for t in topics)]
        
        if difficulties:
            filtered = [q for q in filtered if q.difficulty in difficulties]
        
        if intents:
            filtered = [q for q in filtered if q.intent in intents]
        
        return filtered


class AdaptiveSelector:
    """Select questions adaptively based on user profile."""
    
    def __init__(self, dataset: QuestionDataset):
        self.dataset = dataset
    
    def select_next_question(self, profile: UserProfile) -> Question | None:
        """Select the next question adaptively."""
        # Strategy:
        # 1. Focus on weak topics (60% chance)
        # 2. Mix in weak intents (30% chance)
        # 3. Include some random/review questions (10% chance)
        
        strategy = random.choices(
            ["weak_topic", "weak_intent", "random"],
            weights=[60, 30, 10],
            k=1
        )[0]
        
        question = None
        
        if strategy == "weak_topic":
            question = self._select_from_weak_topic(profile)
        elif strategy == "weak_intent":
            question = self._select_from_weak_intent(profile)
        else:
            question = self._select_random_question(profile)
        
        return question
    
    def _select_from_weak_topic(self, profile: UserProfile) -> Question | None:
        """Select question from a weak topic."""
        weak_topics = profile.get_weak_topics()
        if not weak_topics:
            return None
        
        # Pick a random weak topic
        topic = random.choice(weak_topics)
        
        # Get questions for this topic
        candidates = self.dataset.filter_by_topic(topic)
        
        if not candidates:
            return None
        
        # Adjust difficulty based on user level
        difficulty = self._get_adaptive_difficulty(profile, topic)
        
        # Filter by difficulty
        filtered = [q for q in candidates if q.difficulty == difficulty]
        
        # If no questions at target difficulty, use any difficulty
        if not filtered:
            filtered = candidates
        
        return random.choice(filtered) if filtered else None
    
    def _select_from_weak_intent(self, profile: UserProfile) -> Question | None:
        """Select question with a weak intent."""
        weak_intents = profile.get_weak_intents()
        
        if not weak_intents:
            # If no weak intents, pick from any
            weak_intents = list(profile.intent_stats.keys())
        
        intent = random.choice(weak_intents)
        
        candidates = self.dataset.filter_by_intent(intent)
        
        if not candidates:
            return None
        
        # Filter by appropriate difficulty
        difficulty = self._get_adaptive_difficulty(profile)
        filtered = [q for q in candidates if q.difficulty == difficulty]
        
        if not filtered:
            filtered = candidates
        
        return random.choice(filtered) if filtered else None
    
    def _select_random_question(self, profile: UserProfile) -> Question | None:
        """Select a random question for review."""
        if not self.dataset.questions:
            return None
        
        # Pick appropriate difficulty
        difficulty = self._get_adaptive_difficulty(profile)
        filtered = [q for q in self.dataset.questions if q.difficulty == difficulty]
        
        if not filtered:
            filtered = self.dataset.questions
        
        return random.choice(filtered) if filtered else None
    
    def _get_adaptive_difficulty(
        self,
        profile: UserProfile,
        topic: str | None = None
    ) -> str:
        """
        Determine adaptive difficulty level.
        Respects profile.target_difficulty if explicitly set during progression.
        """
        # First priority: use target_difficulty if set (from progression system)
        if profile.target_difficulty in ["easy", "medium", "hard"]:
            # For weak topics, might go easier than target
            if topic and topic in profile.topic_stats:
                topic_accuracy = profile.topic_stats[topic].accuracy
                if topic_accuracy < 40:
                    return "easy"
            return profile.target_difficulty
        
        # Topic-specific difficulty adjustment
        if topic and topic in profile.topic_stats:
            topic_accuracy = profile.topic_stats[topic].accuracy
            
            # For weak topics, start easier
            if topic_accuracy < 40:
                return "easy"
            elif topic_accuracy < 65:
                return "medium"
            else:
                return random.choice(["medium", "hard"])
        
        # Use overall accuracy as fallback
        accuracy = profile.overall_accuracy
        
        if accuracy >= 80:
            # Advanced user - mix medium and hard
            return random.choice(["medium", "hard"])
        elif accuracy >= 60:
            # Intermediate user - mostly medium
            return random.choice(["medium", "medium", "hard"])
        else:
            # Beginner user - mostly easy
            return random.choice(["easy", "easy", "medium"])
    
    def get_session_summary(
        self,
        profile: UserProfile,
        questions_attempted: list[tuple[Question, bool]],
    ) -> dict:
        """Generate a summary of the session."""
        if not questions_attempted:
            return {
                "total_questions": 0,
                "correct": 0,
                "accuracy": 0.0,
                "level_detected": profile.current_level,
                "weak_topics": profile.get_weak_topics(),
                "strong_topics": profile.get_strong_topics(),
            }
        
        correct = sum(1 for _, is_correct in questions_attempted if is_correct)
        total = len(questions_attempted)
        
        return {
            "total_questions": total,
            "correct": correct,
            "accuracy": (correct / total) * 100,
            "level_detected": profile.current_level,
            "weak_topics": profile.get_weak_topics(),
            "strong_topics": profile.get_strong_topics(),
            "next_recommendation": self._get_recommendation(profile),
        }
    
    def _get_recommendation(self, profile: UserProfile) -> str:
        """Generate a recommendation based on profile."""
        weak_topics = profile.get_weak_topics()
        level = profile.current_level
        
        if weak_topics:
            return f"Focus on {', '.join(weak_topics)} to improve. You're at {level} level."
        else:
            return f"Great progress! You're at {level} level. Try more challenging questions."
