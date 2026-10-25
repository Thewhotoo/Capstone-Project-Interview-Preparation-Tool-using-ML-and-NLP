"""
Turns a diagram's validated structured facts into weighted concepts for
evaluate.py's existing weighted-concept-matching machinery — so diagram
questions get graded with the same rubric (semantic + concept + clarity)
as text questions, just with concepts sourced from schema fields instead
of extract_weighted_concepts()'s heuristic text parsing.
"""
from __future__ import annotations


def diagram_facts_to_weighted_concepts(diagram_type: str, structured_data: dict) -> list[tuple[str, float]]:
    """
    Returns [(concept, weight), ...] compatible with evaluate.py's
    match_weighted_concepts(). Weight reflects structural importance:
    e.g. in a sequence diagram, the specific message being asked about
    should weigh more than an unrelated participant name.
    """
    concepts: list[tuple[str, float]] = []

    if diagram_type == "network_topology":
        for node in structured_data["nodes"]:
            concepts.append((node, 1.0))
        for edge in structured_data["edges"]:
            label = edge.get("label")
            weight = 1.5 if label else 1.0
            concepts.append((f"{edge['from_node']} {edge['to_node']}", weight))
            if label:
                concepts.append((label, 1.3))

    elif diagram_type == "uml_class":
        for cls in structured_data["classes"]:
            concepts.append((cls["name"], 1.2))
            for attr in cls["attributes"]:
                concepts.append((attr, 0.6))
            for method in cls["methods"]:
                concepts.append((method, 0.6))
        for rel in structured_data["relationships"]:
            concepts.append((f"{rel['from_class']} {rel['type']} {rel['to_class']}", 1.5))

    elif diagram_type == "sequence_diagram":
        for msg in structured_data["messages"]:
            concepts.append((msg["label"], 1.5))
            concepts.append((f"{msg['from_participant']} {msg['to_participant']}", 1.0))

    elif diagram_type == "flowchart":
        for step in structured_data["steps"]:
            weight = 1.5 if step["type"] == "decision" else 1.0
            concepts.append((step["label"], weight))
        for edge in structured_data["edges"]:
            if edge.get("condition"):
                concepts.append((f"{edge['from_step']} {edge['condition']}", 1.3))

    elif diagram_type == "binary_tree":
        nodes_by_id = {n["id"]: n for n in structured_data["nodes"]}
        concepts.append((nodes_by_id[structured_data["root"]]["value"], 1.5))  # root is usually the key fact
        for node in structured_data["nodes"]:
            concepts.append((node["value"], 1.0))
            if node.get("left"):
                concepts.append((f"{node['value']} left {nodes_by_id[node['left']]['value']}", 1.2))
            if node.get("right"):
                concepts.append((f"{node['value']} right {nodes_by_id[node['right']]['value']}", 1.2))

    elif diagram_type == "linked_list":
        nodes_by_id = {n["id"]: n for n in structured_data["nodes"]}
        concepts.append((nodes_by_id[structured_data["head"]]["value"], 1.5))  # head is usually the key fact
        for node in structured_data["nodes"]:
            concepts.append((node["value"], 1.0))
            if node.get("next"):
                concepts.append((f"{node['value']} {nodes_by_id[node['next']]['value']}", 1.2))

    elif diagram_type == "ds_graph":
        for node in structured_data["nodes"]:
            concepts.append((node, 1.0))
        for edge in structured_data["edges"]:
            weight = 1.5 if edge.get("weight") is not None else 1.2
            label = f"{edge['from_node']} {edge['to_node']}"
            if edge.get("weight") is not None:
                label += f" {edge['weight']}"
            concepts.append((label, weight))

    elif diagram_type == "array_structure":
        for slot in structured_data["slots"]:
            if slot["value"] is not None:
                concepts.append((f"{slot['index']} {slot['value']}", 1.0))

    return concepts


def evaluate_diagram_answer(student_answer: str, diagram_question: dict):
    """
    Grades a diagram-question answer using the SAME rubric machinery as
    text answers, but with weighted concepts sourced from the validated
    structure instead of extract_weighted_concepts()'s text heuristics.
    """
    from evaluate import (
        get_model, match_weighted_concepts, check_input_validity,
        INPUT_ISSUE_MESSAGES, build_differentiated_feedback,
    )
    from sentence_transformers import util
    import re

    is_valid, issue = check_input_validity(student_answer)
    if not is_valid:
        return {
            "score": 0.0, "grade": "F",
            "feedback": INPUT_ISSUE_MESSAGES.get(issue, "Invalid input"),
            "input_issue": issue,
        }

    weighted_concepts = diagram_facts_to_weighted_concepts(
        diagram_question["diagram_type"], diagram_question["grounding_facts"]
    )
    concept_matches = match_weighted_concepts(student_answer, weighted_concepts)

    model = get_model()
    ref = diagram_question["reference_answer"]
    student_emb = model.encode(student_answer, convert_to_tensor=True)
    ref_emb = model.encode(ref, convert_to_tensor=True)
    semantic_score = max(0.0, min(1.0, util.cos_sim(student_emb, ref_emb).item())) * 100

    total_w = sum(c["weight"] for c in concept_matches) or 1.0
    matched_w = sum(
        c["weight"] * (1.0 if c["match_type"] == "exact" else 0.7)
        for c in concept_matches if c["hit"]
    )
    concept_score = (matched_w / total_w) * 100

    sentences = re.split(r'[.!?]+', student_answer)
    sent_count = len([s for s in sentences if s.strip()])
    clarity_score = min(1.0, sent_count / 3) * 100

    overall = round(0.45 * semantic_score + 0.35 * concept_score + 0.20 * clarity_score, 2)
    grade = "A" if overall >= 80 else "B" if overall >= 70 else "C" if overall >= 60 else "D" if overall >= 50 else "F"

    rubric = {
        "semantic_score": round(semantic_score, 2),
        "concept_score": round(concept_score, 2),
        "clarity_score": round(clarity_score, 2),
        "overall_score": overall,
        "concept_matches": concept_matches,
    }
    matched = [c["concept"] for c in concept_matches if c["hit"]]
    missing = [c["concept"] for c in concept_matches if not c["hit"]]
    strengths, weaknesses, suggestions = build_differentiated_feedback(rubric, matched, missing)

    return {
        "score": overall, "grade": grade,
        "rubric": {k: v for k, v in rubric.items() if k != "concept_matches"},
        "strengths": strengths, "weaknesses": weaknesses, "suggestions": suggestions,
        "citation": diagram_question["citation"],
        "input_issue": None,
    }
