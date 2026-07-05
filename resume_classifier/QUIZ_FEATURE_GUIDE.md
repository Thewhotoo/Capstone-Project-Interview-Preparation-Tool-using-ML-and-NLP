# Quiz Evaluation Feature

## Overview

The Quiz Evaluation feature adds domain-specific assessment to the resume classifier. After classifying a resume, you can generate domain-specific quiz questions and evaluate answers based on domain expertise indicators.

## Features

✅ **Domain-Specific Questions**: 3 curated questions per domain
✅ **Keyword-Based Evaluation**: Scores answers based on technical keywords
✅ **Performance Analytics**: Provides feedback and performance levels
✅ **10 Domains Supported**: All domains from the classifier

## Supported Domains

1. Software Engineering
2. Data Science
3. Finance
4. Healthcare
5. Marketing
6. Law
7. Education
8. Mechanical Engineering
9. Cybersecurity
10. Product Management

## API Endpoints

### 1. Generate Quiz

**Endpoint**: `POST /quiz/generate`

**Description**: Generate 3 quiz questions for a specific domain.

**Request**:
```json
{
    "domain": "Software Engineering",
    "num_questions": 3
}
```

**Response** (200 OK):
```json
{
    "domain": "Software Engineering",
    "num_questions": 3,
    "questions": [
        {
            "id": 1,
            "question": "Explain the difference between REST and GraphQL APIs. When would you use each?",
            "difficulty": "medium"
        },
        {
            "id": 2,
            "question": "What is a microservice architecture and what are its advantages and disadvantages compared to monolithic architecture?",
            "difficulty": "medium"
        },
        {
            "id": 3,
            "question": "Describe your experience with CI/CD pipelines. What tools have you used and how do they improve development workflow?",
            "difficulty": "medium"
        }
    ]
}
```

### 2. Evaluate Quiz

**Endpoint**: `POST /quiz/evaluate`

**Description**: Evaluate quiz answers and get scores with feedback.

**Request**:
```json
{
    "domain": "Software Engineering",
    "answers": [
        {
            "question_id": 1,
            "answer": "REST uses specific endpoints and HTTP methods, while GraphQL provides a single endpoint with flexible querying. REST is better for simple APIs while GraphQL is better for complex data requirements."
        },
        {
            "question_id": 2,
            "answer": "Microservices split the application into independent services that can be scaled separately, improving flexibility and deployment speed."
        },
        {
            "question_id": 3,
            "answer": "I've used GitHub Actions and Jenkins for CI/CD. They automate testing and deployment, ensuring code quality."
        }
    ]
}
```

**Response** (200 OK):
```json
{
    "domain": "Software Engineering",
    "total_questions": 3,
    "average_score": 78,
    "performance_level": "Good",
    "individual_evaluations": [
        {
            "question_id": 1,
            "question": "Explain the difference between REST and GraphQL APIs. When would you use each?",
            "user_answer": "REST uses specific endpoints...",
            "score": 100,
            "matched_keywords": ["REST", "GraphQL", "API", "endpoints"],
            "expected_keywords": ["REST", "GraphQL", "API", "endpoints", "queries"],
            "feedback": "Excellent! Your answer demonstrates strong domain knowledge."
        },
        {
            "question_id": 2,
            "question": "What is a microservice architecture...",
            "user_answer": "Microservices split the application...",
            "score": 80,
            "matched_keywords": ["microservices", "services", "deployment"],
            "expected_keywords": ["microservice", "architecture", "scalability", "distributed", "monolithic"],
            "feedback": "Good! Your answer covers key concepts. You could elaborate more on specific techniques."
        },
        {
            "question_id": 3,
            "question": "Describe your experience with CI/CD pipelines...",
            "user_answer": "I've used GitHub Actions and Jenkins...",
            "score": 54,
            "matched_keywords": ["CI/CD", "Jenkins", "GitHub Actions", "automation"],
            "expected_keywords": ["CI/CD", "Jenkins", "GitLab", "GitHub Actions", "deployment", "automation"],
            "feedback": "Good! Your answer covers key concepts. You could elaborate more on specific techniques."
        }
    ]
}
```

## Scoring System

### Score Ranges
- **75-100**: Excellent - Strong domain knowledge
- **60-74**: Good - Solid understanding, can improve
- **45-59**: Fair - Basic understanding, needs detail
- **0-44**: Needs Improvement - Lacks technical depth

### Evaluation Method
Scores are based on **keyword matching**. Each expected keyword in the answer increases the score. The formula is:

```
Score = (Matched Keywords / Total Expected Keywords) × 100
```

**Example**:
- Question has 5 expected keywords
- User mentions 4 of them
- Score = (4/5) × 100 = 80/100

## Workflow Example

### Complete Flow: Resume Classification → Quiz

```bash
# Step 1: Classify Resume
curl -X POST http://localhost:5000/predict \
  -F "file=@resume.pdf"

# Response includes predicted_domain: "Software Engineering"

# Step 2: Generate Quiz for that domain
curl -X POST http://localhost:5000/quiz/generate \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "Software Engineering",
    "num_questions": 3
  }'

# Step 3: User answers questions (locally or in UI)
# Step 4: Evaluate answers
curl -X POST http://localhost:5000/quiz/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "Software Engineering",
    "answers": [
      {
        "question_id": 1,
        "answer": "REST uses endpoints, GraphQL is flexible..."
      },
      {
        "question_id": 2,
        "answer": "Microservices are independent services..."
      },
      {
        "question_id": 3,
        "answer": "CI/CD automates testing and deployment..."
      }
    ]
  }'

# Response includes average_score and performance_level
```

## Integration with Frontend

### Suggested UI Flow

```
1. User uploads resume
   ↓
2. Display classification result
   ↓
3. "Take Quiz" button appears
   ↓
4. Fetch 3 questions via /quiz/generate
   ↓
5. Display questions one by one
   ↓
6. User answers all 3 questions
   ↓
7. Submit answers to /quiz/evaluate
   ↓
8. Display score, feedback, and performance level
```

## Python Usage Example

```python
from src.quiz_generator import get_quiz_generator

# Get generator
quiz_gen = get_quiz_generator()

# Generate quiz
quiz = quiz_gen.get_quiz("Data Science", num_questions=3)
print(quiz["questions"])

# Evaluate single answer
result = quiz_gen.evaluate_answer(
    "Data Science",
    1,
    "I handled imbalanced data using SMOTE oversampling"
)
print(f"Score: {result['score']}/100")
print(f"Feedback: {result['feedback']}")

# Evaluate complete quiz
quiz_result = quiz_gen.evaluate_quiz("Data Science", answers)
print(f"Average: {quiz_result['average_score']}")
print(f"Level: {quiz_result['performance_level']}")
```

## Testing

Run the test suite:

```bash
python eval/test_quiz.py
```

This tests:
- Quiz generation for all domains
- Answer evaluation with good and poor answers
- Complete quiz evaluation workflow

## Files Added/Modified

### New Files
- `data/domain_questions.json` - Questions database
- `src/quiz_generator.py` - Quiz logic module
- `eval/test_quiz.py` - Test suite

### Modified Files
- `api/app.py` - Added 2 new endpoints
- `api/schemas.py` - Added 5 new schemas

## Error Handling

Common errors and responses:

**1. Invalid Domain**
```json
{
    "error": "Domain 'Data Engineer' not found in available domains",
    "available_domains": ["Software Engineering", "Data Science", ...]
}
```

**2. Invalid Question ID**
```json
{
    "error": "Question 99 not found in domain 'Software Engineering'"
}
```

**3. Missing Required Fields**
```json
{
    "error": "Domain is required"
}
```

## Tips for Good Answers

To get higher scores, user answers should:
1. **Use technical keywords** - Include domain-specific terminology
2. **Show depth** - Explain not just what, but why
3. **Give examples** - Reference tools, frameworks, or specific techniques
4. **Compare alternatives** - Show understanding of trade-offs
5. **Use proper terminology** - Correct acronyms and names

### Example Good Answer vs Poor Answer

**Question**: "Explain microservices architecture"

**Poor Answer** (20/100):
> "It's when you break up your application into smaller parts"

**Good Answer** (90/100):
> "Microservices architecture breaks an application into independent services that can be deployed, scaled, and maintained separately. Each service handles a specific business capability and communicates via APIs. Advantages include better scalability and flexibility, but disadvantages include operational complexity and distributed system challenges."

## Future Enhancements

Potential improvements:
- [ ] Dynamic question generation based on resume keywords
- [ ] Answer hints/guidance system
- [ ] Spaced repetition for learning
- [ ] Certificate generation on high scores
- [ ] Leaderboard/progress tracking
- [ ] Open-ended answer analysis using NLP
- [ ] Custom question creation by admins
