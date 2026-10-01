"""
Diagram ingestion: turns extracted+structured diagrams into knowledge_base
chunks that retrieval.py and generate.py can treat uniformly alongside text
chunks — same citation convention (page number), same retrieval path, but
tagged so downstream code can tell "this chunk is grounded in a diagram's
structured facts" from "this chunk is prose."

Call this from dynamic_ingestor.py after your existing text-chunking step,
pointed at the same knowledge_base/<subject>/ folder.
"""
from __future__ import annotations

import json
from pathlib import Path

from diagram_extractor import extract_diagrams_from_pdf
from diagram_schemas import extract_structured_diagram, DiagramType


def diagram_to_searchable_text(diagram_record: dict) -> str:
    """
    Render the structured facts into a text form for embedding — this is
    what lets your EXISTING FAISS/BM25 hybrid retrieval find diagram
    content via normal semantic/keyword search, no retrieval.py changes
    needed for basic lookup. The structured JSON is kept alongside for
    generation/evaluation to use precisely.
    """
    dtype = diagram_record["type"]
    data = diagram_record["data"]

    if dtype == DiagramType.NETWORK_TOPOLOGY.value:
        nodes = ", ".join(data["nodes"])
        edges = "; ".join(
            f"{e['from_node']} {'->' if e['directed'] else '--'} {e['to_node']}"
            + (f" ({e['label']})" if e.get("label") else "")
            for e in data["edges"]
        )
        return f"Network diagram with nodes: {nodes}. Connections: {edges}."

    if dtype == DiagramType.UML_CLASS.value:
        classes = "; ".join(
            f"{c['name']} (attributes: {', '.join(c['attributes']) or 'none'}; "
            f"methods: {', '.join(c['methods']) or 'none'})"
            for c in data["classes"]
        )
        rels = "; ".join(
            f"{r['from_class']} {r['type']} {r['to_class']}" for r in data["relationships"]
        )
        return f"UML class diagram with classes: {classes}. Relationships: {rels}."

    if dtype == DiagramType.SEQUENCE_DIAGRAM.value:
        participants = ", ".join(data["participants"])
        messages = "; ".join(
            f"{m['order']}. {m['from_participant']} -> {m['to_participant']}: {m['label']}"
            for m in sorted(data["messages"], key=lambda m: m["order"])
        )
        return f"Sequence diagram with participants: {participants}. Message flow: {messages}."

    if dtype == DiagramType.FLOWCHART.value:
        steps = "; ".join(f"{s['id']} ({s['type']}): {s['label']}" for s in data["steps"])
        edges = "; ".join(
            f"{e['from_step']} -> {e['to_step']}" + (f" [{e['condition']}]" if e.get("condition") else "")
            for e in data["edges"]
        )
        return f"Flowchart with steps: {steps}. Flow: {edges}."

    return ""


def ingest_diagrams_for_subject(pdf_paths: list[str] | str, subject_kb_dir: str) -> list[dict]:
    """
    Extract, classify, and structure all diagrams across one or more PDFs
    for a subject, writing them into <subject_kb_dir>/diagram_chunks.json
    in the same chunk shape your existing chunks.json uses.

    Fails soft per-diagram and per-PDF: a VLM error or an unwired call_vlm()
    logs a warning and skips that diagram rather than aborting the whole
    subject's ingestion (text chunking should never be blocked by the
    diagram pipeline not being fully configured yet).
    """
    if isinstance(pdf_paths, str):
        pdf_paths = [pdf_paths]

    all_chunks = []
    for pdf_path in pdf_paths:
        try:
            diagrams = extract_diagrams_from_pdf(pdf_path)
        except Exception as e:
            print(f"[diagram ingestion] could not extract diagrams from {pdf_path}: {e}")
            continue

        for d in diagrams:
            try:
                structured = extract_structured_diagram(d.image_bytes)
            except NotImplementedError:
                print(f"[diagram ingestion] call_vlm() not wired yet — skipping diagram extraction for {pdf_path}")
                break  # no point retrying every diagram in this PDF
            except Exception as e:
                print(f"[diagram ingestion] extraction error on page {d.page_number} of {pdf_path}: {e}")
                continue

            if structured is None:
                continue  # classified as "other" or failed schema validation — skip, don't guess

            searchable_text = diagram_to_searchable_text(structured)
            all_chunks.append({
                "id": f"diagram_{len(all_chunks)}",
                "chunk_type": "diagram",
                "diagram_type": structured["type"],
                "text": searchable_text,
                "structured_data": structured["data"],
                "page": d.page_number,
                "source_pdf": Path(pdf_path).name,
                "nearby_text": d.nearby_text[:500],
            })

    out_path = Path(subject_kb_dir) / "diagram_chunks.json"
    out_path.write_text(json.dumps(all_chunks, indent=2))
    return all_chunks
