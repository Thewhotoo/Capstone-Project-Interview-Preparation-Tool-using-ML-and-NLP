"""
Structured diagram extraction: classify diagram type, then extract facts
into a validated schema specific to that type. This is what prevents the
pipeline from degrading into "vague VLM description of a picture" — every
extracted fact has a defined shape, and output that doesn't parse against
that shape is rejected rather than silently trusted.

The VLM call itself is abstracted behind `call_vlm()` so this can be wired
to whatever vision model you use (Qwen2-VL for local/Colab consistency
with your existing Qwen2.5 text model, or a hosted vision API) without
changing anything else in this file.
"""
from __future__ import annotations

import base64
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ValidationError, field_validator


# ---------------------------------------------------------------------------
# VLM call — WIRE THIS to your actual vision model.
# ---------------------------------------------------------------------------

def call_vlm(image_bytes: bytes, prompt: str) -> str:
    """
    Replace this with a real call to your vision-language model.

    Option A (local, consistent with your existing Qwen2.5 text model):
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        # load once at module level, not per-call
        ...

    Option B (hosted, e.g. via Anthropic API with an image content block):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                        "media_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text

    Raising here on purpose so this module fails loudly instead of silently
    returning fake data if it's imported before being wired up.
    """
    raise NotImplementedError("Wire call_vlm() to your chosen VLM before using this module.")


# ---------------------------------------------------------------------------
# Diagram type classification
# ---------------------------------------------------------------------------

class DiagramType(str, Enum):
    NETWORK_TOPOLOGY = "network_topology"
    UML_CLASS = "uml_class"
    SEQUENCE_DIAGRAM = "sequence_diagram"
    FLOWCHART = "flowchart"
    BINARY_TREE = "binary_tree"
    LINKED_LIST = "linked_list"
    DS_GRAPH = "ds_graph"
    ARRAY_STRUCTURE = "array_structure"
    OTHER = "other"


CLASSIFY_PROMPT = """Look at this diagram from a technical textbook.
Classify it into EXACTLY ONE of these categories:
- network_topology (nodes connected by network links, e.g. routers, hosts, protocol stacks)
- uml_class (classes with attributes/methods and relationships like inheritance/association)
- sequence_diagram (participants with time-ordered messages between them, e.g. TCP handshake)
- flowchart (decision/process flow with arrows between steps)
- binary_tree (a rooted tree where each node has at most a left and right child, e.g. BST, heap)
- linked_list (a linear chain of nodes connected by "next"/"prev" pointers, e.g. singly/doubly linked list)
- ds_graph (a general graph with nodes and weighted/unweighted edges, used for algorithms like Dijkstra/BFS/DFS — not a network topology)
- array_structure (an indexed sequence of slots/cells, e.g. array, stack, queue, or hash table with buckets)
- other (anything that doesn't fit the above, e.g. a photo or a bar chart)

Respond with ONLY the category name, nothing else."""


def classify_diagram(image_bytes: bytes) -> DiagramType:
    raw = call_vlm(image_bytes, CLASSIFY_PROMPT).strip().lower()
    for dtype in DiagramType:
        if dtype.value in raw:
            return dtype
    return DiagramType.OTHER


# ---------------------------------------------------------------------------
# Per-type schemas. Each has: strict Pydantic model + an extraction prompt
# that forces the VLM to fill exactly that shape as JSON.
# ---------------------------------------------------------------------------

class NetworkEdge(BaseModel):
    from_node: str
    to_node: str
    label: Optional[str] = None       # e.g. protocol name, link type
    directed: bool = False

class NetworkTopology(BaseModel):
    nodes: list[str]
    edges: list[NetworkEdge]

    @field_validator("nodes")
    @classmethod
    def nodes_non_empty(cls, v):
        if not v:
            raise ValueError("nodes must be non-empty for a network_topology diagram")
        return v


class UMLRelationship(BaseModel):
    from_class: str
    to_class: str
    type: str   # "inheritance" | "association" | "composition" | "aggregation" | "dependency"

class UMLClass(BaseModel):
    name: str
    attributes: list[str] = []
    methods: list[str] = []

class UMLClassDiagram(BaseModel):
    classes: list[UMLClass]
    relationships: list[UMLRelationship]

    @field_validator("classes")
    @classmethod
    def classes_non_empty(cls, v):
        if not v:
            raise ValueError("classes must be non-empty for a uml_class diagram")
        return v


class SequenceMessage(BaseModel):
    order: int
    from_participant: str
    to_participant: str
    label: str

class SequenceDiagram(BaseModel):
    participants: list[str]
    messages: list[SequenceMessage]

    @field_validator("messages")
    @classmethod
    def messages_ordered(cls, v):
        orders = [m.order for m in v]
        if orders != sorted(orders):
            raise ValueError("messages must be extracted in time order")
        return v


class FlowchartStep(BaseModel):
    id: str
    label: str
    type: str = "process"  # "start" | "process" | "decision" | "end"

class FlowchartEdge(BaseModel):
    from_step: str
    to_step: str
    condition: Optional[str] = None   # e.g. "yes" / "no" branch label

class Flowchart(BaseModel):
    steps: list[FlowchartStep]
    edges: list[FlowchartEdge]


class TreeNode(BaseModel):
    id: str
    value: str
    left: Optional[str] = None    # id of left child, or null
    right: Optional[str] = None   # id of right child, or null

class BinaryTree(BaseModel):
    root: str          # id of the root node
    nodes: list[TreeNode]

    @field_validator("nodes")
    @classmethod
    def nodes_non_empty(cls, v):
        if not v:
            raise ValueError("nodes must be non-empty for a binary_tree diagram")
        return v


class ListNode(BaseModel):
    id: str
    value: str
    next: Optional[str] = None    # id of next node, or null at tail
    prev: Optional[str] = None    # id of prev node, only for doubly-linked lists

class LinkedList(BaseModel):
    head: str
    nodes: list[ListNode]
    doubly_linked: bool = False

    @field_validator("nodes")
    @classmethod
    def nodes_non_empty(cls, v):
        if not v:
            raise ValueError("nodes must be non-empty for a linked_list diagram")
        return v


class DSGraphEdge(BaseModel):
    from_node: str
    to_node: str
    weight: Optional[float] = None
    directed: bool = False

class DSGraph(BaseModel):
    nodes: list[str]
    edges: list[DSGraphEdge]

    @field_validator("nodes")
    @classmethod
    def nodes_non_empty(cls, v):
        if not v:
            raise ValueError("nodes must be non-empty for a ds_graph diagram")
        return v


class ArraySlot(BaseModel):
    index: str          # array index, or hash bucket key
    value: Optional[str] = None   # null represents an empty slot

class ArrayStructure(BaseModel):
    structure_kind: str = "array"   # "array" | "stack" | "queue" | "hash_table"
    slots: list[ArraySlot]

    @field_validator("slots")
    @classmethod
    def slots_non_empty(cls, v):
        if not v:
            raise ValueError("slots must be non-empty for an array_structure diagram")
        return v


EXTRACTION_PROMPTS = {
    DiagramType.NETWORK_TOPOLOGY: """Extract this network diagram as JSON matching EXACTLY this shape:
{{"nodes": ["Host A", "Router 1", ...], "edges": [{{"from_node": "...", "to_node": "...", "label": "...", "directed": true}}]}}
Use the exact labels visible in the diagram for node names. If an edge has no visible label, use null.
Respond with ONLY the JSON, no other text.""",

    DiagramType.UML_CLASS: """Extract this UML class diagram as JSON matching EXACTLY this shape:
{{"classes": [{{"name": "...", "attributes": ["..."], "methods": ["..."]}}], "relationships": [{{"from_class": "...", "to_class": "...", "type": "inheritance|association|composition|aggregation|dependency"}}]}}
Use exact class/attribute/method names as shown. Only include relationships with a visible connector in the diagram.
Respond with ONLY the JSON, no other text.""",

    DiagramType.SEQUENCE_DIAGRAM: """Extract this sequence diagram as JSON matching EXACTLY this shape:
{{"participants": ["Client", "Server", ...], "messages": [{{"order": 1, "from_participant": "...", "to_participant": "...", "label": "..."}}]}}
Order messages top-to-bottom as they appear in the diagram, starting at 1.
Respond with ONLY the JSON, no other text.""",

    DiagramType.FLOWCHART: """Extract this flowchart as JSON matching EXACTLY this shape:
{{"steps": [{{"id": "1", "label": "...", "type": "start|process|decision|end"}}], "edges": [{{"from_step": "1", "to_step": "2", "condition": null}}]}}
For decision steps with branching arrows, set "condition" on each outgoing edge (e.g. "yes"/"no").
Respond with ONLY the JSON, no other text.""",

    DiagramType.BINARY_TREE: """Extract this binary tree diagram as JSON matching EXACTLY this shape:
{{"root": "node_id_of_root", "nodes": [{{"id": "...", "value": "...", "left": "id_or_null", "right": "id_or_null"}}]}}
Assign each node a short id (e.g. "n1", "n2") based on its position. "value" is the label/number shown in the node.
Use null for a missing left/right child. Respond with ONLY the JSON, no other text.""",

    DiagramType.LINKED_LIST: """Extract this linked list diagram as JSON matching EXACTLY this shape:
{{"head": "node_id_of_head", "nodes": [{{"id": "...", "value": "...", "next": "id_or_null", "prev": "id_or_null"}}], "doubly_linked": false}}
Assign each node a short id based on left-to-right position. Set "doubly_linked" true only if backward
arrows are visible. Use null for "next" at the tail node. Respond with ONLY the JSON, no other text.""",

    DiagramType.DS_GRAPH: """Extract this graph diagram as JSON matching EXACTLY this shape:
{{"nodes": ["A", "B", ...], "edges": [{{"from_node": "...", "to_node": "...", "weight": null, "directed": false}}]}}
Use the exact vertex labels shown. Set "weight" to the numeric edge weight if labeled, otherwise null.
Set "directed" true only if the edge has a visible arrowhead. Respond with ONLY the JSON, no other text.""",

    DiagramType.ARRAY_STRUCTURE: """Extract this array/stack/queue/hash-table diagram as JSON matching EXACTLY this shape:
{{"structure_kind": "array|stack|queue|hash_table", "slots": [{{"index": "0", "value": "..."}}]}}
For a hash table, "index" is the bucket key/hash value shown. Use null for "value" on empty slots.
Respond with ONLY the JSON, no other text.""",
}

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


# ---------------------------------------------------------------------------
# Extraction with validation + retry
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def extract_structured_diagram(image_bytes: bytes, max_retries: int = 2) -> dict | None:
    """
    Returns:
        {"type": DiagramType, "data": <validated pydantic model>.dict()}
        or None if classification is "other"/unsupported, or extraction
        fails validation after retries (fails CLOSED — no diagram data is
        better than silently-wrong diagram data feeding into questions
        and grading).
    """
    dtype = classify_diagram(image_bytes)
    if dtype not in SCHEMA_BY_TYPE:
        return None

    schema = SCHEMA_BY_TYPE[dtype]
    prompt = EXTRACTION_PROMPTS[dtype]

    last_error = None
    for attempt in range(max_retries + 1):
        raw = call_vlm(image_bytes, prompt)
        try:
            parsed = json.loads(_strip_code_fences(raw))
            validated = schema(**parsed)
            return {"type": dtype.value, "data": validated.model_dump()}
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            last_error = e
            # tighten the prompt on retry rather than repeating the same one verbatim
            prompt = prompt + f"\n\nYour previous response was invalid ({e}). Return ONLY valid JSON matching the exact shape."

    # exhausted retries — fail closed, log for later review rather than
    # feeding unvalidated structure into the RAG pipeline
    print(f"[diagram extraction] failed validation after {max_retries + 1} attempts: {last_error}")
    return None
