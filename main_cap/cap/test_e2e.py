"""End-to-end integration test for the redesigned Resume Discussion engine."""
import sys
sys.path.insert(0, ".")

import discussion_engine as de
from discussion_engine import (
    DiscussionMemory, _evaluate_discussion_answer_local,
    _semantic_similarity, TopicPool, _phrase_topic, _decide_action,
    start_session, reply, end_session, EvaluationWeights,
)

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


# ── Profile fixture ───────────────────────────────────────────────────
profile = {
    "projects": [
        {"title": "My Web App", "technologies": ["React", "Node.js"],
         "concepts": ["REST API", "authentication", "component-based architecture"],
         "summary": "A full-stack web application for task management with real-time updates.",
         "interview_seeds": ["Why did you choose REST over GraphQL?"]},
        {"title": "Data Pipeline", "technologies": ["Python", "Spark"],
         "concepts": ["ETL", "data modeling", "distributed processing"],
         "summary": "An ETL pipeline processing terabytes of log data.",
         "interview_seeds": ["How did you handle schema evolution?"]},
    ],
    "experience": [
        {"role": "Software Engineer", "company": "Acme Corp",
         "description": "Built microservices and REST APIs."},
    ],
    "certifications": [{"name": "AWS Solutions Architect"}],
    "skills": ["Python", "JavaScript", "React", "SQL", "Docker"],
    "education": [{"degree": "B.S. Computer Science", "institution": "State University"}],
    "interview_blueprint": {
        "technical_topics": [
            {"topic": "JWT-based authentication", "originating_project": "My Web App",
             "originating_experience": "", "evidence": "REST API for authentication"},
            {"topic": "distributed systems", "originating_project": "", "originating_experience": "",
             "evidence": ""},  # untraceable — must be rejected, no matching project/experience
        ],
        "resume_verification_topics": ["AWS Solutions Architect certification"],
        "estimated_strengths": ["React", "REST APIs"],
        "estimated_weaknesses": ["Data Pipeline"],
        "starting_difficulty": "intermediate",
    },
}

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 1: DiscussionMemory basic dedup ===")
mem = DiscussionMemory()
check("New memory is empty", len(mem.questions_asked) == 0)
check("Not duplicate of empty", not mem.is_duplicate("What is React?"))
check("add_question returns False (not dupe)", mem.add_question("What is React?") is False)
check("Exact duplicate detected", mem.is_duplicate("What is React?"))
check("Different question not dupe", not mem.is_duplicate("How do you deploy apps?"))
check("Questions asked list has 1 entry", len(mem.questions_asked) == 1)

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 2: DiscussionMemory concept tracking ===")
mem2 = DiscussionMemory()
mem2.mark_discussed(["react", "python", "api design"])
check("concepts_discussed updated", "react" in mem2.concepts_discussed)
mem2.mark_mastered("react")
check("react mastered", "react" in mem2.concepts_mastered)
check("react not in clarification", "react" not in mem2.concepts_needing_clarification)
mem2.mark_needs_clarification("python")
check("python needs clarification", "python" in mem2.concepts_needing_clarification)
mem2.mark_mastered("python")
check("mastered clears clarification", "python" not in mem2.concepts_needing_clarification)
uncovered = mem2.get_uncovered(["react", "python", "api design", "docker"])
check("get_uncovered returns docker", uncovered == ["docker"])
check("summary returns dict", isinstance(mem2.summary(), dict))

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 3: DiscussionMemory extended fields ===")
mem3 = DiscussionMemory()
mem3.mark_project_discussed("My Web App")
mem3.mark_project_discussed("Data Pipeline")
check("projects_discussed has 2 entries", len(mem3.projects_discussed) == 2)
mem3.mark_technologies_discussed(["React", "Node.js", "Python"])
check("technologies_discussed has 3 entries", len(mem3.technologies_discussed) == 3)
mem3.update_difficulty([0.85])
check("difficulty set to hard", mem3.current_difficulty == "hard")
check("question_count increments", mem3.question_count == 0)
mem3.add_question("Test question")
check("question_count incremented", mem3.question_count == 1)

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 4: Heuristic fallback evaluation ===")
q = {
    "id": "dq_test1",
    "text": "Tell me about My Web App.",
    "category": "project_overview",
    "context": {"project": profile["projects"][0]},
}
answer = (
    "I built a React web application with Node.js backend. "
    "It used REST API for authentication and data fetching. "
    "The project involved building a responsive UI with component-based architecture. "
    "I implemented state management using Redux and deployed it on AWS."
)
result_heuristic = _evaluate_discussion_answer_local(
    answer, q, q.get("context", {}).get("project"),
)
check(f"Score in [0,1]: {result_heuristic['overall_score']}", 0.0 <= result_heuristic["overall_score"] <= 1.0)
check(f"Evaluator is local-ml", result_heuristic["evaluator"] == "local-ml")
check(f"Grade is valid", result_heuristic["grade"] in ("excellent", "good", "adequate", "weak", "poor"))
check("concepts_demonstrated is non-empty", len(result_heuristic.get("concepts_demonstrated", [])) > 0)
check("concepts_missing is list", isinstance(result_heuristic.get("concepts_missing", []), list))
print(f"    (evaluator={result_heuristic['evaluator']}, score={result_heuristic['overall_score']:.3f}, grade={result_heuristic['grade']})")

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 5: Weak answer score < strong answer ===")
weak_answer = "I used it."
result_weak = _evaluate_discussion_answer_local(
    weak_answer, q, q.get("context", {}).get("project"),
)
check(f"Weak answer score < strong answer ({result_weak['overall_score']:.3f} < {result_heuristic['overall_score']:.3f})",
      result_weak["overall_score"] < result_heuristic["overall_score"])

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 5b: EvaluationWeights are configurable, not hardcoded ===")
default_weights = EvaluationWeights()
check("Default weights sum to 1.0",
      abs(sum([default_weights.correctness, default_weights.technical_depth,
               default_weights.completeness, default_weights.communication,
               default_weights.concept_coverage]) - 1.0) < 1e-9)
custom_weights = EvaluationWeights.from_dict({"correctness": 0.9, "technical_depth": 0.1,
                                               "completeness": 0.0, "communication": 0.0,
                                               "concept_coverage": 0.0})
custom_result = _evaluate_discussion_answer_local(
    answer, q, q.get("context", {}).get("project"), weights=custom_weights,
)
check("Custom weights change the resulting score",
      custom_result["overall_score"] != result_heuristic["overall_score"])
check("grade() respects custom thresholds",
      EvaluationWeights(grade_excellent=0.01).grade(0.5) == "excellent")

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 6: TopicPool construction — hierarchy, traceability, rejection ===")
pool = TopicPool(profile)
categories = {u["category"] for u in pool.units.values()}
check("Pool has project_overview units", "project_overview" in categories)
check("Pool has project_deep_dive units (from interview_seeds)", "project_deep_dive" in categories)
check("Pool has experience units", "experience" in categories)
check("Pool has certification units", "certification" in categories)
check("Pool has skill_in_context units (traceable technical_topics only)",
      "skill_in_context" in categories)
check("No independent technical_topic/verification_topic categories remain",
      "technical_topic" not in categories and "verification_topic" not in categories)

# Every unit must be traceable to exactly one Candidate Profile entry.
for u in pool.units.values():
    check(f"Unit {u['id']} ({u['category']}) has source_type", bool(u.get("source_type")))
    check(f"Unit {u['id']} ({u['category']}) has source_id", bool(u.get("source_id")))
    check(f"Unit {u['id']} ({u['category']}) has source_field", bool(u.get("source_field")))
    check(f"Unit {u['id']} ({u['category']}) has a reason", bool(u.get("reason")))

# The untraceable "distributed systems" technical_topic must be rejected, not asked.
skill_units = [u for u in pool.units.values() if u["category"] == "skill_in_context"]
check("Traceable skill_in_context (JWT auth -> My Web App) was kept",
      any(u["text_seed"] == "JWT-based authentication" for u in skill_units))
check("Untraceable technical_topic ('distributed systems') was NOT added as a unit",
      not any(u["text_seed"] == "distributed systems" for u in skill_units))
check("Untraceable technical_topic was recorded in pool.rejected",
      any(r["topic"] == "distributed systems" for r in pool.rejected))
print(f"    Rejected (untraceable): {pool.rejected}")

weak_units = [u for u in pool.units.values() if u["category"] == "project_overview"
              and u["grounding"]["project"]["title"] == "Data Pipeline"]
check("Estimated-weakness project is priority-boosted", weak_units and weak_units[0]["priority_boost"])
print(f"    Pool built {len(pool.units)} topic units across categories: {sorted(categories)}")

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 7: Adaptive selection favors priority/diversity, not FIFO order ===")
pool2 = TopicPool(profile)
seen_categories = []
picked_ids = set()
for _ in range(6):
    unit = pool2.select_next(seen_categories[-1] if seen_categories else None)
    if unit is None:
        break
    check("select_next never repeats an already-picked unit", unit["id"] not in picked_ids)
    picked_ids.add(unit["id"])
    unit["status"] = "covered"
    seen_categories.append(unit["category"])
check("Selection order isn't a fixed single-category run",
      len(set(seen_categories)) > 1)
print(f"    Selection order: {seen_categories}")

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 8: _decide_action policy thresholds ===")
check("Near-empty/irrelevant answer -> skip",
      _decide_action({"overall_score": 0.05, "concepts_missing": []}, 0) == "skip")
check("Strong score + missing concepts -> probe_deeper",
      _decide_action({"overall_score": 0.7, "concepts_missing": ["caching"]}, 0) == "probe_deeper")
check("Mixed score -> clarify",
      _decide_action({"overall_score": 0.35, "concepts_missing": ["caching"]}, 0) == "clarify")
check("Follow-up budget spent -> move_on regardless of score",
      _decide_action({"overall_score": 0.9, "concepts_missing": ["x"]}, de._MAX_FOLLOWUPS_PER_TOPIC) == "move_on")

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 9: _phrase_topic renders every category to a non-empty, source-anchored question ===")
for category in ("project_overview", "project_deep_dive", "skill_in_context",
                  "experience", "certification"):
    units = [u for u in pool.units.values() if u["category"] == category]
    check(f"At least one '{category}' unit exists in fixture pool", len(units) > 0)
    if units:
        unit = units[0]
        text = _phrase_topic(unit)
        check(f"'{category}' phrases to a non-empty question", isinstance(text, str) and len(text) > 5)
        if unit.get("source_id"):
            check(f"'{category}' question mentions its source ({unit['source_id']!r})",
                  de._mentions(text, unit["source_id"]))

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 10: Semantic similarity correctness ===")
sim_same = _semantic_similarity(
    "What is machine learning?",
    "Explain the concept of machine learning"
)
sim_diff = _semantic_similarity(
    "What is machine learning?",
    "How do you deploy applications to production?"
)
check(f"Same-topic sim > diff-topic sim ({sim_same:.3f} > {sim_diff:.3f})", sim_same > sim_diff)
check(f"Same-topic sim > 0.5 ({sim_same:.3f})", sim_same > 0.5)

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 11: DiscussionMemory semantic dedup ===")
mem7 = DiscussionMemory()
mem7.add_question("What is machine learning?")
check("Exact duplicate detected", mem7.is_duplicate("What is machine learning?"))
check("Semantic duplicate detected", mem7.is_duplicate("Explain the concept of machine learning"))
check("Different question not duplicate", not mem7.is_duplicate("How do you deploy applications?"))

# ═══════════════════════════════════════════════════════════════════════
print("\n=== Test 12: Full local session flow via start_session/reply/end_session ===")
strong_answers = [
    "I built a React web application with Node.js backend, using REST APIs for "
    "authentication and a component-based architecture on the frontend.",
    "For the ETL pipeline I used Spark to process terabytes of log data, handling "
    "schema evolution by versioning the Avro schemas and validating on ingest.",
    "As a Software Engineer at Acme Corp I designed and built several internal "
    "microservices exposing REST APIs consumed by other teams.",
    "I earned the AWS Solutions Architect certification and used that knowledge "
    "to design our multi-AZ deployment for the caching layer.",
]

result, status = start_session(profile, "profile_test_e2e")
check("start_session returns 200", status == 200)
disc_id = result.get("session_id")
check("start_session returns a session_id", bool(disc_id))
check("start_session's question is non-empty", len(result.get("question", {}).get("text", "")) > 5)

turns = 0
completed = False
for ans in strong_answers * 3:  # enough turns to either complete or hit the ceiling
    r, status = reply(disc_id, ans)
    check(f"reply() call {turns} returns 200", status == 200)
    turns += 1
    if r.get("is_completed"):
        completed = True
        break
    if turns >= de._TARGET_QUESTION_COUNT + 2:
        break

check("Session reaches completion or the question-count ceiling", completed or turns >= de._TARGET_QUESTION_COUNT)

end_result, end_status = end_session(disc_id)
check("end_session returns 200", end_status == 200)
check("end_session does not crash on projects_discussed (regression check)",
      isinstance(end_result.get("projects_discussed"), list))
check("end_session reports at least one project discussed",
      len(end_result.get("projects_discussed", [])) > 0)
check("end_session reports technologies_demonstrated as a list",
      isinstance(end_result.get("technologies_demonstrated"), list))
print(f"    turns={turns} completed={completed} projects_discussed={end_result.get('projects_discussed')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
print("ALL TESTS PASSED")
