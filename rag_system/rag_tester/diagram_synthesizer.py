"""
Synthesize NEW diagrams from scratch, grounded in retrieved course context.
Unlike diagram_schemas.py (which extracts structure FROM an existing image
via a VLM), this generates structure directly as text/JSON via your
existing Qwen pipeline, then validates it with the SAME Pydantic schemas.

Why this sidesteps the hard part of the original idea: there's no vision
step here, so there's no "VLM inconsistently reads arrow directions"
failure mode. The JSON produced here IS the diagram's ground truth by
construction — it gets rendered from this JSON and graded against this
JSON, so image/question/rubric are guaranteed consistent with each other.
"""
from __future__ import annotations

import json
from pydantic import ValidationError

from generate import get_llm_response
from diagram_schemas import (
    DiagramType, NetworkTopology, UMLClassDiagram, SequenceDiagram, Flowchart,
    BinaryTree, LinkedList, DSGraph, ArrayStructure,
    _strip_code_fences,
)

SCHEMA_BY_TYPE = {
    DiagramType.NETWORK_TOPOLOGY: NetworkTopology,
    DiagramType.UML_CLASS: UMLClassDiagram,
    DiagramType.SEQUENCE_DIAGRAM: SequenceDiagram,
    DiagramType.FLOWCHART: Flowchart,
    DiagramType.BINARY_TREE: BinaryTree,
    DiagramType.LINKED_LIST: LinkedList,
    DiagramType.DS_GRAPH: DSGraph,
    DiagramType.ARRAY_STRUCTURE: ArrayStructure,
}

SYNTHESIS_PROMPTS = {
    DiagramType.NETWORK_TOPOLOGY: """Based ONLY on this reference material:
{context}

Design a network topology diagram (4-7 nodes) that illustrates a concept from
this material (e.g. a specific protocol interaction, routing scenario, or
network layer). Return JSON matching EXACTLY:
{{"nodes": ["Host A", "Router 1", ...], "edges": [{{"from_node": "...", "to_node": "...", "label": "...", "directed": true}}]}}
Every node and edge label must be grounded in the reference material — do not invent protocols or devices not mentioned.
Respond with ONLY the JSON.""",

    DiagramType.UML_CLASS: """Based ONLY on this reference material:
{context}

Design a UML class diagram (3-5 classes) that illustrates a design pattern
or object model from this material. Return JSON matching EXACTLY:
{{"classes": [{{"name": "...", "attributes": ["..."], "methods": ["..."]}}], "relationships": [{{"from_class": "...", "to_class": "...", "type": "inheritance|association|composition|aggregation|dependency"}}]}}
Every class, attribute, method, and relationship must be grounded in the reference material.
Respond with ONLY the JSON.""",

    DiagramType.SEQUENCE_DIAGRAM: """Based ONLY on this reference material:
{context}

Design a sequence diagram (2-4 participants, 4-8 messages) that illustrates
a process from this material (e.g. a handshake, request/response flow).
Return JSON matching EXACTLY:
{{"participants": ["Client", "Server", ...], "messages": [{{"order": 1, "from_participant": "...", "to_participant": "...", "label": "..."}}]}}
Every message must be grounded in the reference material's description of this process.
Respond with ONLY the JSON.""",

    DiagramType.FLOWCHART: """Based ONLY on this reference material:
{context}

Design a flowchart (4-8 steps, at least one decision) that illustrates a
process or algorithm from this material. Return JSON matching EXACTLY:
{{"steps": [{{"id": "1", "label": "...", "type": "start|process|decision|end"}}], "edges": [{{"from_step": "1", "to_step": "2", "condition": null}}]}}
Every step must be grounded in the reference material.
Respond with ONLY the JSON.""",

    DiagramType.BINARY_TREE: """Based ONLY on this reference material:
{context}

Design a binary tree (5-9 nodes) that illustrates a concept from this
material (e.g. a BST after a sequence of insertions, a heap, a traversal
example). Return JSON matching EXACTLY:
{{"root": "n1", "nodes": [{{"id": "n1", "value": "...", "left": "id_or_null", "right": "id_or_null"}}]}}
Values must be grounded in the reference material's example (e.g. the exact numbers/keys it uses),
and the tree shape must be a VALID binary tree consistent with that material (e.g. if it's a BST,
left < parent < right must hold). Respond with ONLY the JSON.""",

    DiagramType.LINKED_LIST: """Based ONLY on this reference material:
{context}

Design a linked list (4-6 nodes) that illustrates a concept from this
material (e.g. list after an insertion/deletion operation). Return JSON matching EXACTLY:
{{"head": "n1", "nodes": [{{"id": "n1", "value": "...", "next": "id_or_null", "prev": null}}], "doubly_linked": false}}
Set "doubly_linked" true only if the material specifically discusses a doubly-linked list.
Respond with ONLY the JSON.""",

    DiagramType.DS_GRAPH: """Based ONLY on this reference material:
{context}

Design a graph (5-7 vertices) that illustrates an algorithm from this
material (e.g. for Dijkstra, BFS, DFS, or MST). Return JSON matching EXACTLY:
{{"nodes": ["A", "B", ...], "edges": [{{"from_node": "...", "to_node": "...", "weight": 4, "directed": false}}]}}
Include edge weights only if the material's algorithm requires them (e.g. Dijkstra/MST need weights;
BFS/DFS typically don't — use null in that case). Respond with ONLY the JSON.""",

    DiagramType.ARRAY_STRUCTURE: """Based ONLY on this reference material:
{context}

Design an array/stack/queue/hash-table state (5-8 slots) that illustrates
an operation from this material (e.g. array after a sort pass, stack after
pushes, hash table after insertions with a specific collision policy).
Return JSON matching EXACTLY:
{{"structure_kind": "array|stack|queue|hash_table", "slots": [{{"index": "0", "value": "..."}}]}}
Use null for "value" on slots that should be empty. Respond with ONLY the JSON.""",
}


def synthesize_diagram(diagram_type: DiagramType, context: str, max_retries: int = 2) -> dict | None:
    """
    Returns {"type": diagram_type, "data": <validated dict>} or None if
    the LLM can't produce valid JSON after retries. Fails closed, same
    policy as the extraction path — no diagram data beats fabricated
    diagram data flowing into a question.
    """
    schema = SCHEMA_BY_TYPE[diagram_type]
    prompt = SYNTHESIS_PROMPTS[diagram_type].format(context=context)

    last_error = None
    for attempt in range(max_retries + 1):
        raw = get_llm_response(prompt)
        try:
            parsed = json.loads(_strip_code_fences(raw))
            validated = schema(**parsed)
            return {"type": diagram_type.value, "data": validated.model_dump()}
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            last_error = e
            prompt += f"\n\nYour previous response was invalid ({e}). Return ONLY valid JSON matching the exact shape."

    print(f"[diagram synthesis] failed validation after {max_retries + 1} attempts: {last_error}")
    return None
