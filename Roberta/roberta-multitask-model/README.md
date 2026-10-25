# Adaptive Interview Practice Engine

This repository contains an adaptive engine for technical interview practice and personalized learning. It uses a fine-tuned RoBERTa model to predict a question's **Intent**, **Difficulty**, and **Topic(s)** simultaneously, while using user performance history to adapt question selection, scoring, and progression.

## 🎯 Features
- **3-in-1 Prediction:** Classifies questions into Intents (definition, explanation, comparison, procedure, reasoning), Difficulty (easy, medium, hard), and Topics (DSA, OOP, OS, CN, DBMS).
- **Hybrid Architecture:** Uses a fine-tuned RoBERTa model for probabilistic scoring, combined with a linguistic rule-based system for stable evaluation.
- **Adaptive Learning Engine:** Personalizes question selection based on user performance, identifies weak/strong topics, detects user skill level, and provides tailored recommendations.
- **Question-Specific Model Answers:** Shows reference answers that match the exact question instead of generic fallback text.

---

## 🚀 Quick Start Guide

### 1. Installation

Clone the repository and install the required dependencies. It is recommended to use a Python virtual environment.

```bash
# Clone the repository
git clone <your-repo-url>
cd roberta-multitask-model

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Training the Models (Optional but Recommended)

By default, the heavy `.bin`/`.safetensors` model weights are **not** included in this repository to save space. If you run the system without training, it will successfully use the rule-based fallback system.

To generate the full neural network predictions, train the models locally on your machine. The models will learn from the `data/dataset.json` file.

Run the following commands from the root of the project:

```bash
# Train the Difficulty model (~3-5 mins)
python -m model.train_difficulty

# Train the Intent model (~3-5 mins)
python -m model.train_intent

# Train the Topic model (Multi-label) (~3-5 mins)
python -m model.train_topic
```

Once training is complete, the weights will be saved automatically in the `model/saved_models/` directory.

### 3. Running the Application

You can interactively test the model by running the main entry script:

```bash
python main.py
```

**Main Menu Options:**
1. **Classify a Single Question** → Analyze a specific interview question
2. **Start Adaptive Learning Session** → Interactive practice with personalization
3. **Exit**

---

## 🎓 Adaptive Learning System

The system now includes an intelligent adaptive engine that:

✅ **Tracks User Performance** - Maintains detailed statistics on accuracy, topic strengths, and intent mastery  
✅ **Detects Skill Level** - Automatically classifies users as Beginner, Intermediate, or Advanced  
✅ **Identifies Weak Areas** - Focuses practice on topics and question types where improvement is needed  
✅ **Adapts Difficulty** - Questions automatically get harder or easier based on performance  
✅ **Selects Questions Intelligently** - 60% from weak topics, 30% from weak intents, 10% exploration  
✅ **Provides Recommendations** - Personalized guidance on what to study next  
✅ **Persists Profiles** - Saves progress so learning continues across sessions  

### Example Adaptive Session

```
User starts with beginner level → Easy questions
After 5 correct in a row → Medium difficulty
Struggles with DSA → More DSA questions
Weak at explanations → More explanation-type questions
90% accuracy on OS → Focuses on weaker topics
```

### For Detailed Adaptive Features Guide
See [ADAPTIVE_FEATURES.md](ADAPTIVE_FEATURES.md) for comprehensive documentation.

---

## 📊 How the Adaptive System Works

1. **User Profile Creation** - Starts with a new profile when they first use the system
2. **Question Selection** - System picks questions based on their current level and weak areas
3. **Answer Evaluation** - Uses RoBERTa classifiers and heuristics to evaluate responses
4. **Profile Update** - Records performance by topic, intent, and difficulty
5. **Level Adjustment** - Continuously updates user level (Beginner → Intermediate → Advanced)
6. **Personalization** - Next questions are selected based on updated profile

---

## 📁 Project Structure

```
roberta-multitask-model/
├── adaptive/                      # Adaptive engine
│   ├── __init__.py
│   ├── user_profile.py           # User profile and stats tracking
│   ├── adaptive_selector.py       # Intelligent question selection
│   └── session_manager.py         # Interactive session management
├── model/                        # Model training and utilities
│   ├── train_difficulty.py
│   ├── train_intent.py
│   ├── train_topic.py
│   ├── multitask_utils.py
│   └── saved_models/             # Trained model weights
├── inference/                    # Prediction modules
│   ├── predict_difficulty.py
│   ├── predict_intent.py
│   ├── predict_topic.py
│   ├── predict_profile.py
│   ├── input_validation.py
│   └── rule_based.py
├── eval/                         # Evaluation scripts
├── data/                         # Dataset
│   └── dataset.json
├── user_profiles/                # (Auto-created) User data
├── main.py                       # Updated entry point with adaptive menu
├── requirements.txt
├── README.md
├── ADAPTIVE_FEATURES.md          # Adaptive system guide
└── test_adaptive_system.py        # Integration tests
```

---

## 🔍 Single Question Classification

To classify a single question:

```
python main.py
Select: 1
Enter a question: "What is a deadlock?"

Output:
Intent: definition (0.95 confidence)
Difficulty: medium (0.87 confidence)
Topics: OS
```

---

## 🎮 Interactive Adaptive Session

To start an adaptive practice session:

```
python main.py
Select: 2
Enter username: john_doe

Session Options:
1. View Your Profile      → See stats and accuracy
2. Start Practice         → Answer questions
3. Get Recommendation    → Personalized advice
```

During practice:
- System shows a question with topic, type, and difficulty
- You provide your answer
- System evaluates and provides feedback
- Profile updates automatically
- Next question adapts to your performance

---

## 📈 Performance Metrics

The system tracks:
- **Overall Accuracy**: Percentage of correct answers across all questions
- **Topic Accuracy**: Performance in each topic (OS, DBMS, CN, OOP, DSA, General)
- **Intent Performance**: How well you handle different question types
- **Difficulty Distribution**: Accuracy on easy/medium/hard questions
- **Strength Levels**: Strong (≥80%), Moderate (60-80%), Weak (<60%)

---

## 🧪 Running Tests

To verify the adaptive system is working correctly:

```bash
python test_adaptive_system.py
```

Expected output:
```
✓ User profile tests passed!
✓ Topic stats tests passed!
✓ Dataset tests passed! (Loaded 172 questions)
✓ Adaptive selector tests passed!
✓ Profile persistence tests passed!

All tests passed! ✓
```

---

## 📚 Usage Examples

### Example 1: New User Starting
```python
from adaptive.session_manager import SessionManager

session = SessionManager("alex_smith")
session.display_profile_summary()  # Shows beginner level
session.start_session(num_questions=5)
```

### Example 2: Checking User Progress
```python
from adaptive.user_profile import UserProfileManager

manager = UserProfileManager()
profile = manager.load_profile("alex_smith")
print(f"Level: {profile.current_level}")
print(f"Accuracy: {profile.overall_accuracy:.1f}%")
print(f"Weak Topics: {profile.get_weak_topics()}")
```

### Example 3: Getting Recommendations
```python
weak_topics = profile.get_weak_topics()
strong_topics = profile.get_strong_topics()
print(f"Focus on: {weak_topics}")
print(f"You're strong in: {strong_topics}")
```

---

## 🔧 Configuration

### Adaptive Question Weights
Edit `adaptive/adaptive_selector.py`:
```python
# Adjust the distribution of question sources
strategy = random.choices(
    ["weak_topic", "weak_intent", "random"],
    weights=[60, 30, 10],  # Change these values
    k=1
)
```

### Difficulty Thresholds
Edit `adaptive/user_profile.py`:
```python
# Modify what constitutes "strong", "moderate", "weak"
if self.accuracy >= 80:      # Strong threshold
    return "strong"
elif self.accuracy >= 60:    # Moderate threshold
    return "moderate"
```

---

## 🚀 Future Enhancements

Potential improvements planned:
- [ ] Semantic similarity scoring for better answer evaluation
- [ ] Time-based difficulty adjustment
- [ ] Spaced repetition scheduling
- [ ] AI-generated personalized learning paths
- [ ] Collaborative filtering across users
- [ ] Detailed answer explanations
- [ ] Achievement badges and streaks
- [ ] Export performance reports

---

## 📝 License & Credits

This project combines question classification with adaptive learning for interview preparation.

**Core Features:**
- RoBERTa transformer for classification
- Hybrid rule-based fallback system
- Adaptive personalized learning engine

---

## 🎯 Next Steps

1. **Install & Setup**: Follow the Quick Start Guide
2. **Train Models** (optional): Run the training scripts
3. **Start Practicing**: `python main.py → Option 2`
4. **Track Progress**: View your profile and recommendations
5. **Focus Areas**: Improve weak topics with targeted practice

Good luck with your interview prep! 🚀


