"""
Render structured diagram data (from extraction OR synthesis) into an
actual image. Since the input is already-validated structured JSON, this
is pure deterministic rendering — no model calls, nothing to hallucinate.

Requires: pip install graphviz matplotlib
Also requires the Graphviz system binary (not just the Python wrapper):
  - Ubuntu/Colab: apt-get install -y graphviz
  - Mac: brew install graphviz
"""
from __future__ import annotations

import io
import graphviz
import matplotlib.pyplot as plt
import matplotlib.lines as mlines


# ---------------------------------------------------------------------------
# Network topology + Flowchart — both are naturally node/edge graphs
# ---------------------------------------------------------------------------

def render_network_topology(data: dict) -> bytes:
    g = graphviz.Graph(format="png")
    g.attr(bgcolor="white", rankdir="LR")
    g.attr("node", shape="box", style="rounded,filled", fillcolor="#eef4ff", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="10")

    for node in data["nodes"]:
        g.node(node, node)

    for edge in data["edges"]:
        g.edge(
            edge["from_node"], edge["to_node"],
            label=edge.get("label") or "",
        )

    return g.pipe(format="png")


def render_flowchart(data: dict) -> bytes:
    g = graphviz.Digraph(format="png")
    g.attr(bgcolor="white")
    g.attr("edge", fontname="Helvetica", fontsize="10")

    shape_by_type = {"start": "ellipse", "end": "ellipse", "decision": "diamond", "process": "box"}
    fill_by_type = {"start": "#d4f7d4", "end": "#f7d4d4", "decision": "#fff3cd", "process": "#eef4ff"}

    for step in data["steps"]:
        g.node(
            step["id"], step["label"],
            shape=shape_by_type.get(step["type"], "box"),
            style="rounded,filled",
            fillcolor=fill_by_type.get(step["type"], "#eef4ff"),
            fontname="Helvetica",
        )

    for edge in data["edges"]:
        g.edge(edge["from_step"], edge["to_step"], label=edge.get("condition") or "")

    return g.pipe(format="png")


# ---------------------------------------------------------------------------
# UML class diagram — needs class-box styling (attributes/methods sections)
# and correct arrowheads per relationship type, which plain Graphviz nodes
# don't give you for free — build the label as an HTML-like table.
# ---------------------------------------------------------------------------

ARROW_STYLE_BY_REL_TYPE = {
    "inheritance": {"arrowhead": "empty", "style": "solid"},
    "composition": {"arrowhead": "diamond", "style": "solid"},
    "aggregation": {"arrowhead": "odiamond", "style": "solid"},
    "association": {"arrowhead": "vee", "style": "solid"},
    "dependency": {"arrowhead": "vee", "style": "dashed"},
}


def _uml_class_label(cls: dict) -> str:
    attrs = "".join(f'<TR><TD ALIGN="LEFT">{a}</TD></TR>' for a in cls["attributes"]) or '<TR><TD> </TD></TR>'
    methods = "".join(f'<TR><TD ALIGN="LEFT">{m}()</TD></TR>' for m in cls["methods"]) or '<TR><TD> </TD></TR>'
    return f"""<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0">
      <TR><TD BGCOLOR="#eef4ff"><B>{cls['name']}</B></TD></TR>
      <TR><TD><TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">{attrs}</TABLE></TD></TR>
      <TR><TD><TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">{methods}</TABLE></TD></TR>
    </TABLE>>"""


def render_uml_class(data: dict) -> bytes:
    g = graphviz.Digraph(format="png")
    g.attr(bgcolor="white")
    g.attr("node", shape="plain", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="10")

    for cls in data["classes"]:
        g.node(cls["name"], label=_uml_class_label(cls))

    for rel in data["relationships"]:
        style = ARROW_STYLE_BY_REL_TYPE.get(rel["type"], {"arrowhead": "vee", "style": "solid"})
        # inheritance arrow points from child to parent, per UML convention
        g.edge(rel["from_class"], rel["to_class"], label=rel["type"], **style)

    return g.pipe(format="png")


# ---------------------------------------------------------------------------
# Sequence diagram — lifelines + time-ordered arrows. Graphviz doesn't
# model "time flows downward across parallel lifelines" naturally, so
# this uses matplotlib for direct geometric control.
# ---------------------------------------------------------------------------

def render_sequence_diagram(data: dict) -> bytes:
    participants = data["participants"]
    messages = sorted(data["messages"], key=lambda m: m["order"])

    n = len(participants)
    height = max(3, 1.2 * len(messages) + 1.5)
    fig, ax = plt.subplots(figsize=(max(6, 2 * n), height))

    x_positions = {p: i for i, p in enumerate(participants)}

    # lifelines
    for p, x in x_positions.items():
        ax.plot([x, x], [0, len(messages) + 1], color="#999999", linestyle="--", zorder=1)
        ax.text(x, len(messages) + 1.3, p, ha="center", fontsize=11, fontweight="bold")

    # messages, top to bottom in order
    for i, msg in enumerate(messages):
        y = len(messages) - i
        x_from = x_positions[msg["from_participant"]]
        x_to = x_positions[msg["to_participant"]]

        arrow = mlines.Line2D(
            [x_from, x_to], [y, y], color="#2b6cb0", linewidth=1.5,
            marker=">" if x_to > x_from else "<", markevery=[1], markersize=10,
        )
        ax.add_line(arrow)
        mid_x = (x_from + x_to) / 2
        ax.text(mid_x, y + 0.15, msg["label"], ha="center", fontsize=9)

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(0, len(messages) + 2)
    ax.axis("off")

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", dpi=150, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Binary tree — Graphviz's native tree layout handles this well; the only
# trick is drawing left/right children in consistent left-to-right order
# (Graphviz doesn't guarantee child order by default, so we add invisible
# ordering constraints).
# ---------------------------------------------------------------------------

def render_binary_tree(data: dict) -> bytes:
    g = graphviz.Digraph(format="png")
    g.attr(bgcolor="white")
    g.attr("node", shape="circle", style="filled", fillcolor="#eef4ff", fontname="Helvetica")

    nodes_by_id = {n["id"]: n for n in data["nodes"]}
    for node in data["nodes"]:
        g.node(node["id"], node["value"])

    for node in data["nodes"]:
        if node.get("left"):
            g.edge(node["id"], node["left"])
        if node.get("right"):
            g.edge(node["id"], node["right"])
        # invisible ordering edge so left always renders left of right
        if node.get("left") and node.get("right"):
            with g.subgraph() as s:
                s.attr(rank="same")
                s.node(node["left"])
                s.node(node["right"])
                s.edge(node["left"], node["right"], style="invis")

    return g.pipe(format="png")


# ---------------------------------------------------------------------------
# Linked list — rendered left-to-right as a strict chain, since Graphviz's
# default layout doesn't guarantee a straight line for a simple path.
# ---------------------------------------------------------------------------

def render_linked_list(data: dict) -> bytes:
    g = graphviz.Digraph(format="png")
    g.attr(bgcolor="white", rankdir="LR")
    g.attr("node", shape="record", style="filled", fillcolor="#eef4ff", fontname="Helvetica")

    for node in data["nodes"]:
        g.node(node["id"], f"{{ {node['value']} | <next> }}")

    for node in data["nodes"]:
        if node.get("next"):
            g.edge(f"{node['id']}:next", node["next"])
        if data.get("doubly_linked") and node.get("prev"):
            g.edge(f"{node['id']}", f"{node['prev']}", constraint="false", style="dashed")

    return g.pipe(format="png")


# ---------------------------------------------------------------------------
# General graph (algorithms context — Dijkstra/BFS/DFS) — like network
# topology, but shows edge weights prominently since that's usually the
# point of a DS/algorithms graph diagram.
# ---------------------------------------------------------------------------

def render_ds_graph(data: dict) -> bytes:
    directed_any = any(e.get("directed") for e in data["edges"])
    g = graphviz.Digraph(format="png") if directed_any else graphviz.Graph(format="png")
    g.attr(bgcolor="white")
    g.attr("node", shape="circle", style="filled", fillcolor="#eef4ff", fontname="Helvetica")
    g.attr("edge", fontname="Helvetica", fontsize="10")

    for node in data["nodes"]:
        g.node(node, node)

    for edge in data["edges"]:
        label = str(edge["weight"]) if edge.get("weight") is not None else ""
        g.edge(edge["from_node"], edge["to_node"], label=label)

    return g.pipe(format="png")


# ---------------------------------------------------------------------------
# Array / stack / queue / hash table — a row of boxes, rendered with
# matplotlib for precise control over index labels above/below each slot.
# ---------------------------------------------------------------------------

def render_array_structure(data: dict) -> bytes:
    slots = data["slots"]
    n = len(slots)
    fig, ax = plt.subplots(figsize=(max(4, 1.1 * n), 2.2))

    for i, slot in enumerate(slots):
        value = slot["value"] if slot["value"] is not None else ""
        facecolor = "#eef4ff" if slot["value"] is not None else "#f5f5f5"
        rect = plt.Rectangle((i, 0), 1, 1, facecolor=facecolor, edgecolor="#333333")
        ax.add_patch(rect)
        ax.text(i + 0.5, 0.5, value, ha="center", va="center", fontsize=11)
        ax.text(i + 0.5, -0.25, slot["index"], ha="center", va="center", fontsize=9, color="#666666")

    ax.set_xlim(0, n)
    ax.set_ylim(-0.6, 1.3)
    ax.set_title(data.get("structure_kind", "array"), fontsize=10, loc="left", color="#666666")
    ax.axis("off")

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", dpi=150, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

RENDERERS = {
    "network_topology": render_network_topology,
    "uml_class": render_uml_class,
    "sequence_diagram": render_sequence_diagram,
    "flowchart": render_flowchart,
    "binary_tree": render_binary_tree,
    "linked_list": render_linked_list,
    "ds_graph": render_ds_graph,
    "array_structure": render_array_structure,
}


def render_diagram(diagram_type: str, data: dict) -> bytes:
    renderer = RENDERERS.get(diagram_type)
    if renderer is None:
        raise ValueError(f"No renderer for diagram type: {diagram_type}")
    return renderer(data)
