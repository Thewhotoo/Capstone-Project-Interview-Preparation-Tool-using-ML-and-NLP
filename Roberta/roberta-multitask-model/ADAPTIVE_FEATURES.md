# Adaptive Learning System - Feature Guide

## Overview

The system now includes an **Adaptive Learning System** that personalizes question selection based on each user's performance, skill level, and weak areas. The system continuously learns from user interactions to provide increasingly targeted practice.

---

## Key Features

### 1. **User Profile Tracking**
Each user gets a personalized profile that tracks:
- **Overall Performance**: Total questions attempted, correct answers, accuracy percentage
- **Topic Performance**: Accuracy for each topic (OS, DBMS, CN, OOP, DSA, General)
- **Intent Performance**: How well they handle different question types (definition, explanation, comparison, procedure, reasoning)
- **Difficulty Progression**: Current level and adaptive difficulty targets

### 2. **Automatic Level Detection**
The system automatically classifies users into three levels:
- **Beginner**: Accuracy < 60% | Just starting out
- **Intermediate**: Accuracy 60-80% | Building confidence
- **Advanced**: Accuracy ≥ 80% | Mastering the topics

### 3. **Weak & Strong Topic Identification**
The system identifies:
- **Weak Topics**: Areas where user struggles (< 60% accuracy)
- **Strong Topics**: Areas where user excels (≥ 80% accuracy)
- **Performance by Difficulty**: Tracks how user performs on easy/medium/hard questions per topic

### 4. **Intelligent Question Selection**
Questions are selected using a weighted strategy:
- **60% from Weak Topics**: Focus on areas that need improvement
- **30% from Weak Intents**: Practice question types you're less comfortable with
- **10% Random/Review**: Maintain well-rounded practice

### 5. **Adaptive Difficulty Adjustment**
Difficulty automatically adjusts based on:
- **User Level**: Beginners get mostly easy questions, advanced users get harder ones
- **Topic-Specific Performance**: Easy questions on weak topics, harder questions on strong topics
- **Recent Accuracy**: If user is doing well, difficulty increases; if struggling, decreases

### 6. **Answer Evaluation**
The system uses the trained RoBERTa classifiers to evaluate answers by:
- Predicting the intent and topics of the user's response
- Comparing them with the expected question characteristics
- Using heuristics (answer length, topic coverage) for more accurate scoring

### 7. **Persistent User Profiles**
User data is saved to `user_profiles/{user_id}.json` allowing:
- Continuous learning across sessions
- Progress tracking over time
- Personalized recommendations

---

## How to Use

### Starting the System

```bash
python main.py
```

### Main Menu
```
1. Classify a Single Question  → Analyze a specific question
2. Start Adaptive Learning     → Interactive practice session
3. Exit
```

### Adaptive Learning Session

**Step 1: Enter Username**
```
Enter your username: john_doe
```

**Step 2: Choose an Option**
```
1. View Your Profile & Stats    → See your performance
2. Start Practice Session        → Answer questions
3. Get Personalized Recommendation → Get tailored advice
4. Return to Main Menu
```

**Step 3: Practice Questions**
- System shows a question with topic, difficulty, and type
- You provide your answer
- System evaluates and provides feedback
- Your profile updates automatically

---

## User Profile Structure

Each user profile tracks:

```json
{
  "user_id": "john_doe",
  "current_level": "intermediate",
  "overall_accuracy": 72.5,
  "total_attempted": 20,
  "total_correct": 15,
  
  "topic_stats": {
    "OS": {
      "correct": 8,
      "attempted": 10,
      "easy_correct": 4,
      "easy_attempted": 4,
      "medium_correct": 4,
      "medium_attempted": 5,
      "hard_correct": 0,
      "hard_attempted": 1,
      "accuracy": 80.0,
      "strength_level": "strong"
    },
    "DSA": {
      "correct": 5,
      "attempted": 7,
      "accuracy": 71.4,
      "strength_level": "moderate"
    }
    // ... other topics
  },
  
  "intent_stats": {
    "definition": {"correct": 6, "attempted": 8},
    "explanation": {"correct": 5, "attempted": 7},
    "comparison": {"correct": 2, "attempted": 3},
    "procedure": {"correct": 2, "attempted": 2},
    "reasoning": {"correct": 0, "attempted": 0}
  }
}
```

---

## Personalization Examples

### Example 1: New User (Beginner)
- Starts with all "easy" difficulty questions
- Gets varied topics to assess strengths
- System learns weak areas and focuses on them

### Example 2: Intermediate User with Weak DSA
- Mostly "easy" and "medium" DSA questions
- Occasional harder questions if accuracy is high
- Mixes in other topics for well-rounded learning

### Example 3: Advanced User
- Gets mostly "medium" and "hard" questions
- Focuses on weak topics even if difficult
- Challenges with complex reasoning questions

---

## Answer Evaluation Heuristics

The system evaluates answers based on:

1. **Intent Matching**: Does the answer match the question type?
   - Definition questions: Short, direct answers about what something is
   - Explanation questions: Longer answers explaining how/why
   - Comparison: Answers contrasting two things
   - Procedure: Step-by-step instructions
   - Reasoning: Logical analysis

2. **Topic Coverage**: Does the answer address the right topics?
   - Must mention relevant domain knowledge
   - Should connect to the topic area

3. **Answer Length Heuristics**:
   - Definition: At least 3-5 words
   - Explanation: At least 10+ words
   - Comparison: Mentions both concepts

4. **Semantic Similarity**: RoBERTa classifier predictions on the answer text

---

## Personalization Strategy

The system uses a **multi-armed bandit** approach:

```
Each session:
  - 60% of questions from weak topics (exploitation)
  - 30% from weak intents (targeted improvement)
  - 10% random (exploration)
```

This balances:
- **Focused Learning**: Targeting weak areas
- **Well-Rounded Practice**: Not ignoring strong areas entirely
- **Exploration**: Discovering new challenges

---

## Performance Metrics

### Strength Levels
- **Strong**: Accuracy ≥ 80%
- **Moderate**: Accuracy 60-80%
- **Weak**: Accuracy < 60%
- **Untested**: Fewer than 3 attempts

### Level Progression
```
Beginner      → Intermediate → Advanced
Acc: 0-60%      Acc: 60-80%      Acc: 80%+
```

---

## Recommendations

The system provides personalized recommendations like:
- "Focus on DSA to improve. You're at intermediate level."
- "Practice explanation type questions."
- "You're doing great! Try more challenging questions."

---

## File Structure

```
roberta-multitask-model/
├── adaptive/
│   ├── __init__.py
│   ├── user_profile.py           # User profile and stats tracking
│   ├── adaptive_selector.py       # Question selection algorithm
│   └── session_manager.py         # Interactive session management
├── user_profiles/                 # (Created automatically)
│   └── {user_id}.json            # Stored user profiles
├── main.py                        # Updated with adaptive menu
├── test_adaptive_system.py        # Integration tests
└── ...
```

---

## Features in Detail

### User Profile Management
**File**: `adaptive/user_profile.py`

```python
# Create/load a user profile
profile = UserProfile(user_id="john_doe")
profile.record_attempt(
    correct=True,
    topic="OS",
    intent="explanation",
    difficulty="medium",
    time_seconds=45.0
)

# Check current level
print(profile.current_level)      # "intermediate"
print(profile.overall_accuracy)   # 72.5
print(profile.get_weak_topics())  # ["DSA", "CN"]
```

### Adaptive Question Selection
**File**: `adaptive/adaptive_selector.py`

```python
# Initialize dataset and selector
dataset = QuestionDataset()
selector = AdaptiveSelector(dataset)

# Get next question for user
next_question = selector.select_next_question(profile)
print(next_question.text)          # Question text
print(next_question.difficulty)    # "medium"
print(next_question.topics)        # ["OS", "DSA"]
```

### Interactive Session
**File**: `adaptive/session_manager.py`

```python
# Create and run a session
session = SessionManager(user_id="john_doe")
session.display_profile_summary()
session.start_session(num_questions=5)
```

---

## Example Session

```
========================================
Question 1/5
Current Level: intermediate
Overall Accuracy: 72.5%
========================================

Q: Explain the concept of deadlock in operating systems.
Topic: OS | Difficulty: medium | Type: explanation

Your answer: A deadlock occurs when two or more processes 
are waiting for resources held by each other...

✓ Correct! Well done!
Expected: explanation answer about OS

Session updated: OS accuracy now 85%
```

---

## Next Steps & Future Enhancements

Potential improvements:
1. **Semantic Similarity Scoring**: Use embeddings for better answer evaluation
2. **Time-Based Difficulty**: Adjust based on response time
3. **Spaced Repetition**: Automatically schedule reviews
4. **Study Plans**: AI-generated personalized learning paths
5. **Collaborative Filtering**: Learn from similar users
6. **Difficulty Calibration**: Better difficulty prediction
7. **Question Explanation**: Provide detailed answers
8. **Streak Tracking**: Motivate with achievement streaks

---

## Troubleshooting

### Profile Not Saving
- Check that `user_profiles/` directory exists
- Ensure write permissions in the directory

### Questions Not Loading
- Verify `data/dataset.json` exists and has valid format
- Run tests: `python test_adaptive_system.py`

### Inconsistent Recommendations
- Complete at least 5 questions for better personalization
- More attempts = better understanding of your level

---

## Summary

The adaptive system provides:
✓ **Personalization**: Questions tailored to your level and needs
✓ **Progress Tracking**: Detailed statistics on all aspects
✓ **Smart Difficulty**: Challenges that match your ability
✓ **Focused Learning**: Practice where you need it most
✓ **Recommendations**: Guidance on what to study next

**Start practicing now**: `python main.py → Option 2`
