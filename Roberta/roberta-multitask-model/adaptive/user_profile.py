"""User profile and performance tracking for adaptive learning."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field


@dataclass
class TopicStats:
    """Performance statistics for a specific topic."""
    correct: int = 0
    attempted: int = 0
    easy_correct: int = 0
    medium_correct: int = 0
    hard_correct: int = 0
    easy_attempted: int = 0
    medium_attempted: int = 0
    hard_attempted: int = 0
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage for the topic."""
        if self.attempted == 0:
            return 0.0
        return (self.correct / self.attempted) * 100
    
    @property
    def strength_level(self) -> str:
        """Determine strength level for the topic."""
        if self.attempted < 3:
            return "untested"
        if self.accuracy >= 80:
            return "strong"
        elif self.accuracy >= 60:
            return "moderate"
        else:
            return "weak"


@dataclass
class UserProfile:
    """User profile tracking performance and learning preferences."""
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Overall statistics
    total_correct: int = 0
    total_attempted: int = 0
    total_time_seconds: float = 0.0
    
    # Performance by topic
    topic_stats: dict[str, TopicStats] = field(default_factory=dict)
    
    # Performance by intent
    intent_stats: dict[str, dict[str, int]] = field(default_factory=lambda: {
        "definition": {"correct": 0, "attempted": 0},
        "explanation": {"correct": 0, "attempted": 0},
        "comparison": {"correct": 0, "attempted": 0},
        "procedure": {"correct": 0, "attempted": 0},
        "reasoning": {"correct": 0, "attempted": 0},
    })
    
    # Difficulty progression
    last_difficulty: str = "easy"
    target_difficulty: str = "easy"  # Start all users at easy difficulty
    
    def __post_init__(self):
        """Initialize topic stats if they don't exist."""
        for topic in ["OS", "DBMS", "CN", "OOP", "DSA", "General"]:
            if topic not in self.topic_stats:
                self.topic_stats[topic] = TopicStats()
    
    @property
    def overall_accuracy(self) -> float:
        """Calculate overall accuracy percentage."""
        if self.total_attempted == 0:
            return 0.0
        return (self.total_correct / self.total_attempted) * 100
    
    @property
    def current_level(self) -> str:
        """Determine current user level (beginner/intermediate/advanced)."""
        if self.total_attempted < 5:
            return "beginner"
        
        accuracy = self.overall_accuracy
        if accuracy >= 80:
            return "advanced"
        elif accuracy >= 60:
            return "intermediate"
        else:
            return "beginner"
    
    def record_attempt(
        self,
        score: float,
        topic: str,
        intent: str,
        difficulty: str,
        time_seconds: float = 0.0,
    ) -> None:
        """Record a question attempt with score-based tracking (0-100)."""
        # Normalize score to 0-100
        score = max(0, min(100, score))
        
        # Count as correct if score >= 60
        correct = score >= 60
        
        # Update overall stats (using score-based calculation)
        self.total_attempted += 1
        self.total_correct += score / 100.0  # Fractional correctness
        self.total_time_seconds += time_seconds
        self.updated_at = datetime.now().isoformat()
        
        # Update topic stats
        if topic not in self.topic_stats:
            self.topic_stats[topic] = TopicStats()
        
        self.topic_stats[topic].attempted += 1
        self.topic_stats[topic].correct += score / 100.0  # Fractional correctness
        
        # Update difficulty-specific stats for topic
        if difficulty == "easy":
            self.topic_stats[topic].easy_attempted += 1
            if correct:
                self.topic_stats[topic].easy_correct += 1
        elif difficulty == "medium":
            self.topic_stats[topic].medium_attempted += 1
            if correct:
                self.topic_stats[topic].medium_correct += 1
        elif difficulty == "hard":
            self.topic_stats[topic].hard_attempted += 1
            if correct:
                self.topic_stats[topic].hard_correct += 1
        
        # Update intent stats
        if intent in self.intent_stats:
            self.intent_stats[intent]["attempted"] += 1
            if correct:
                self.intent_stats[intent]["correct"] += 1
        
        # Adjust target difficulty
        self._adjust_target_difficulty()
    
    def _adjust_target_difficulty(self) -> None:
        """
        Adjust target difficulty based on recent performance.
        
        Note: Progression is primarily handled by the session manager after 5+ questions.
        This method provides adaptive adjustments for edge cases only.
        """
        if self.total_attempted < 3:
            self.target_difficulty = "easy"
            return
        
        # Get recent accuracy (last 5 questions)
        accuracy = self.overall_accuracy
        
        # Only adjust if performance is extremely poor or excellent
        # Allow some buffer to prevent oscillation between difficulties
        
        if accuracy < 50 and self.target_difficulty != "easy":
            # Performance critically poor - downgrade to easy
            self.target_difficulty = "easy"
        elif accuracy >= 85 and self.target_difficulty == "medium" and self.total_attempted >= 8:
            # Sustained excellent performance on medium - upgrade to hard
            self.target_difficulty = "hard"
        # Otherwise, keep current target_difficulty until explicitly changed by progression system
    
    def get_weak_topics(self) -> list[str]:
        """Get topics where user is weak (accuracy < 60%)."""
        weak = []
        for topic, stats in self.topic_stats.items():
            if stats.attempted >= 2 and stats.strength_level == "weak":
                weak.append(topic)
        return weak if weak else ["DSA", "OS"]  # Default fallback
    
    def get_strong_topics(self) -> list[str]:
        """Get topics where user is strong (accuracy >= 80%)."""
        return [
            topic
            for topic, stats in self.topic_stats.items()
            if stats.attempted >= 2 and stats.strength_level == "strong"
        ]
    
    def get_weak_intents(self) -> list[str]:
        """Get intents where user performs poorly."""
        weak = []
        for intent, stats in self.intent_stats.items():
            if stats["attempted"] >= 2:
                accuracy = (stats["correct"] / stats["attempted"]) * 100
                if accuracy < 60:
                    weak.append(intent)
        return weak
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary for serialization."""
        data = asdict(self)
        # Convert TopicStats to dicts
        data["topic_stats"] = {
            topic: asdict(stats)
            for topic, stats in self.topic_stats.items()
        }
        return data
    
    @staticmethod
    def from_dict(data: dict) -> UserProfile:
        """Create profile from dictionary."""
        # Convert topic_stats dicts back to TopicStats
        topic_stats = {
            topic: TopicStats(**stats)
            for topic, stats in data.pop("topic_stats", {}).items()
        }
        profile = UserProfile(**data)
        profile.topic_stats = topic_stats
        return profile


class UserProfileManager:
    """Manage user profiles with file persistence."""
    
    def __init__(self, profile_dir: str | Path = "user_profiles"):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(exist_ok=True)
    
    def save_profile(self, profile: UserProfile) -> Path:
        """Save user profile to disk."""
        file_path = self.profile_dir / f"{profile.user_id}.json"
        with open(file_path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)
        return file_path
    
    def load_profile(self, user_id: str) -> UserProfile | None:
        """Load user profile from disk."""
        file_path = self.profile_dir / f"{user_id}.json"
        if not file_path.exists():
            return None
        
        with open(file_path, "r") as f:
            data = json.load(f)
        return UserProfile.from_dict(data)
    
    def create_profile(self, user_id: str) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(user_id=user_id)
        self.save_profile(profile)
        return profile
    
    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get existing profile or create new one."""
        profile = self.load_profile(user_id)
        if profile is None:
            profile = self.create_profile(user_id)
        return profile
