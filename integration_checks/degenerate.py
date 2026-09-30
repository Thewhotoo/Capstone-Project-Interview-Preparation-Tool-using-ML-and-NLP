import os, sys, io
cap = sys.argv[1]; sys.path.insert(0, cap); os.chdir(cap); os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import logging; logging.basicConfig(level=logging.ERROR)
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from question_families import ReasoningType
import deployment_evaluator; deployment_evaluator.bootstrap_production_evaluator()
from evaluator_registry import get_active_evaluator; ev = get_active_evaluator()
spec = QuestionSpecification(id="s", category=QuestionCategory.PROJECT_DEEP_DIVE,
    grounding=Grounding(project=ProjectGrounding(title="Interview Coach", summary="A Flask app that runs mock interviews and grades answers.", technologies=("Python", "Flask", "SQLite"))),
    source_type=SourceType.PROJECT, source_id="p1", source_field="projects", reason="t")
answers = {
    "i don't know": "idk",
    "not sure": "I'm not sure, I don't remember.",
    "gibberish": "asdf qwer zxcv lorem blah blah hmm",
    "keyword dump": "Flask SQLite Python REST API JWT Docker Redis microservices scalability caching",
    "off-topic": "My favourite football team is Barcelona and I like watching matches on weekends.",
    "good": "I stored each interview session in SQLite and saved every answer as a turn, so if the server restarted nothing was lost. I added an index on user id because the history page was getting slow once there were a few hundred sessions.",
}
q = "How did you make sure interview answers weren't lost if the server restarted?"
for label, a in answers.items():
    import evaluation_engine
    r = evaluation_engine.evaluate(ev, EvaluationRequest(request_id="r", requested_at="2026-09-30T00:00:00+00:00", specification=spec, question_text=q,
        reasoning_type=ReasoningType.EXPLANATION, answer_text=a, conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False)))
    print(f"  {label:<14} {r.overall_score:.2f} {r.grade}")
