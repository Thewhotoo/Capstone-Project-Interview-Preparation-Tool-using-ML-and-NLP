from pydantic import BaseModel
from typing import Optional, Dict, List

class PredictRequest(BaseModel):
    text: Optional[str] = None      # raw text input (optional if file uploaded)

class ExperienceResult(BaseModel):
    years: int
    level: str                      # Junior / Mid / Senior

class PredictResponse(BaseModel):
    predicted_domain:   str
    confidence:         float
    all_scores:         Dict[str, float]
    experience:         ExperienceResult
    skills:             List[str]
    email:              Optional[str]
    phone:              Optional[str]

# ── Quiz Related Schemas ──────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    id:         int
    question:   str
    difficulty: str

class QuizGenerateResponse(BaseModel):
    domain:         str
    num_questions:  int
    questions:      List[QuizQuestion]

class QuizAnswerInput(BaseModel):
    question_id:    int
    answer:         str

class AnswerEvaluation(BaseModel):
    question_id:        int
    question:           str
    user_answer:        str
    score:              int
    matched_keywords:   List[str]
    expected_keywords:  List[str]
    feedback:           str

class QuizEvaluationResponse(BaseModel):
    domain:                     str
    total_questions:            int
    average_score:              int
    performance_level:          str
    individual_evaluations:     List[AnswerEvaluation]

class QuizSessionRequest(BaseModel):
    domain:             str
    answers:            List[QuizAnswerInput]