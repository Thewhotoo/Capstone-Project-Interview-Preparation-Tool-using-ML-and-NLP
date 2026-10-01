import io, json, os, sys, time
cap, mode, out = sys.argv[1], sys.argv[2], sys.argv[3]     # mode: production | heuristic
cap, out = os.path.abspath(cap), os.path.abspath(out)
V4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "v4_diagnostic_58.jsonl")   # before chdir
sys.path.insert(0, cap); os.chdir(cap)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import logging; logging.basicConfig(level=logging.WARNING)
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from question_specification import Grounding, ProjectGrounding, QuestionCategory, QuestionSpecification, SourceType
from question_families import ReasoningType
if mode == "production":
    import deployment_evaluator; deployment_evaluator.bootstrap_production_evaluator()
    from evaluator_registry import get_active_evaluator; ev = get_active_evaluator()
else:
    from heuristic_evaluator import HeuristicEvaluator; ev = HeuristicEvaluator()
rows = [json.loads(l) for l in open(V4, encoding="utf-8")]
res, t0 = [], time.time()
for i, r in enumerate(rows):
    g = r["grounding"]
    spec = QuestionSpecification(id=f"s{i}", category=QuestionCategory(r["category"]),
        grounding=Grounding(project=ProjectGrounding(title=g["title"], summary=g.get("summary", ""), technologies=tuple(g.get("technologies", ())))),
        source_type=SourceType.PROJECT, source_id=r["source_id"], source_field="projects", reason="v4 diagnostic")
    req = EvaluationRequest(request_id=f"r{i}", requested_at="2026-09-30T00:00:00+00:00", specification=spec,
        question_text=r["question"], reasoning_type=ReasoningType(r["reasoning_type"]), answer_text=r["answer"],
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=tuple(r.get("expected_concepts", ())))
    result = ev.evaluate(req)
    res.append({"example_id": r["example_id"], "score": float(result.overall_score), "grade": str(getattr(result, "grade", "")),
                **{k: float(v) for k, v in dict(getattr(result, "raw_model_output", ()) or ()).items()}})
json.dump({"evaluator": ev.name, "seconds": round(time.time() - t0, 1), "rows": res}, open(out, "w"), indent=1)
print(ev.name, f"{time.time() - t0:.1f}s for {len(rows)}")
