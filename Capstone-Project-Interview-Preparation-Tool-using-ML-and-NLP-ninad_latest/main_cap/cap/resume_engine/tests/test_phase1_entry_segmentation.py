"""Phase 1 robustness regression tests: plain-text / boldless / dateless /
pipeless multi-entry resumes must segment correctly, and technology
attribution must stay entry-local, title-aware, pipe-description-safe, and
guarded against common-English-word collisions.

These tests deliberately model TXT-derived geometry: uniform font size, no
bold, and blank lines expressed as a vertical gap (exactly what the TXT
extractor produces once blank-line separation is preserved). They exercise
`cluster_entries` and `ProjectParser` directly (fast, no model load) plus one
true end-to-end parse of the original three-project failure.

See docs/architecture -- Phase 1 parser robustness.
"""

from __future__ import annotations

from resume_engine.document_model import DocumentModel, TextSpan
from resume_engine.parsers._entry_clustering import cluster_entries
from resume_engine.parsers.education_parser import EducationParser
from resume_engine.parsers.experience_parser import ExperienceParser
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.sections import Section

LINE_H = 14.0  # matches extractor.DOCX_LINE_HEIGHT


def txt_spans(lines: list[str]):
    """Builds TXT-style spans (uniform 11pt, never bold). An empty string in
    `lines` is a BLANK line: it is not emitted as a span, but it advances the
    vertical cursor, so the surrounding real lines carry a genuine y-gap --
    exactly the structure a plain-text resume has between entries."""
    spans: list[TextSpan] = []
    y = 72.0
    for line in lines:
        if line == "":
            y += LINE_H
            continue
        spans.append(
            TextSpan(text=line, bbox=(72.0, y, 470.0, y + LINE_H),
                     font_size=11.0, is_bold=False, page_num=0, column_index=0)
        )
        y += LINE_H
    return spans


def projects_section(lines: list[str]) -> Section:
    return Section(label="projects", raw_header_text="", spans=txt_spans(lines),
                   header_confidence=0.9, header_match_reason="test")


def doc_for(spans) -> DocumentModel:
    return DocumentModel(spans=spans, body_font_size=11.0, source_format="txt")


def parse_projects(lines: list[str]):
    section = projects_section(lines)
    return ProjectParser().parse({"projects": section}, doc_for(section.spans)).entities


def titles(entries):
    return [e.header_text for e in entries]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Plain-text three-project resume: 3 entries, correct per-project techs
# ─────────────────────────────────────────────────────────────────────────────
def test_1_plain_text_three_projects_no_contamination():
    projs = parse_projects([
        "DriftGuard - Real-time anomaly detection service",
        "Built using Python and PostgreSQL.",
        "Implemented anomaly detection and worker retries.",
        "",
        "QuizForge - Multiplayer quiz platform",
        "Built using React and Node.js.",
        "Implemented WebSocket communication.",
        "",
        "PaperTrail - Research paper assistant",
        "Built using Go and Redis.",
        "Implemented document processing.",
    ])
    assert len(projs) == 3
    by_title = {p["title"]: set(p["technologies"]) for p in projs}
    names = list(by_title)
    assert any("DriftGuard" in n for n in names)
    assert any("QuizForge" in n for n in names)
    assert any("PaperTrail" in n for n in names)

    drift = next(t for n, t in by_title.items() if "DriftGuard" in n)
    quiz = next(t for n, t in by_title.items() if "QuizForge" in n)
    paper = next(t for n, t in by_title.items() if "PaperTrail" in n)

    assert {"Python", "PostgreSQL"} <= drift
    assert {"React", "Node.js"} <= quiz
    assert {"Go", "Redis"} <= paper
    # No cross-contamination:
    assert "React" not in drift and "Node.js" not in drift and "Go" not in drift
    assert "Python" not in quiz and "Go" not in quiz
    assert "React" not in paper and "PostgreSQL" not in paper


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Dateless + boldless + pipeless: N records -> N records
# ─────────────────────────────────────────────────────────────────────────────
def test_2_dateless_boldless_pipeless_all_survive():
    entries = cluster_entries(txt_spans([
        "Alpha Engine - task scheduler",
        "Built using Python.",
        "",
        "Beta Service - chat backend",
        "Built using Redis.",
        "",
        "Gamma Tool - report generator",
        "Built using Go.",
    ]), body_font_size=11.0)
    assert len(entries) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Project names alone (blank-separated) must not collapse
# ─────────────────────────────────────────────────────────────────────────────
def test_3_project_names_alone_do_not_collapse():
    entries = cluster_entries(txt_spans([
        "Chronos",
        "A distributed workflow orchestrator.",
        "",
        "QuizForge",
        "A multiplayer quiz platform.",
        "",
        "PaperTrail",
        "A research paper assistant.",
    ]), body_font_size=11.0)
    assert len(entries) == 3
    assert titles(entries) == ["Chronos", "QuizForge", "PaperTrail"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 / 5 / 6 — em dash, hyphen, pipe title shapes are entry titles
# ─────────────────────────────────────────────────────────────────────────────
def test_4_em_dash_title_recognized():
    entries = cluster_entries(txt_spans([
        "Chronos — Distributed workflow orchestrator",
        "Built using FastAPI.",
        "",
        "Helios — Solar telemetry dashboard",
        "Built using React.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_5_hyphen_title_recognized():
    entries = cluster_entries(txt_spans([
        "Chronos - Distributed workflow orchestrator",
        "Built using FastAPI.",
        "",
        "Helios - Solar telemetry dashboard",
        "Built using React.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_6_pipe_title_still_works():
    entries = cluster_entries(txt_spans([
        "Chronos | Distributed workflow orchestrator",
        "Built using FastAPI.",
        "",
        "Helios | Solar telemetry dashboard",
        "Built using React.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Date-based project parsing still works (bold PDF-style unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def test_7_dated_entries_still_segment():
    spans = [
        TextSpan(text="Chronos (2025)", bbox=(72.0, 72.0, 200.0, 86.0), font_size=11.0, is_bold=False, page_num=0),
        TextSpan(text="Built using Python.", bbox=(72.0, 88.0, 260.0, 102.0), font_size=11.0, is_bold=False, page_num=0),
        TextSpan(text="Helios (2024)", bbox=(72.0, 104.0, 200.0, 118.0), font_size=11.0, is_bold=False, page_num=0),
        TextSpan(text="Built using Redis.", bbox=(72.0, 120.0, 260.0, 134.0), font_size=11.0, is_bold=False, page_num=0),
    ]
    entries = cluster_entries(spans, body_font_size=11.0)
    assert len(entries) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Title + description + content stays ONE project (no over-seg)
# ─────────────────────────────────────────────────────────────────────────────
def test_8_entry_continuation_stays_one_project():
    entries = cluster_entries(txt_spans([
        "Chronos",
        "Distributed workflow orchestrator",
        "Built using FastAPI and PostgreSQL.",
        "Implemented retries and leases.",
    ]), body_font_size=11.0)
    assert len(entries) == 1
    assert entries[0].header_text == "Chronos"


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — Bullet continuation stays ONE project
# ─────────────────────────────────────────────────────────────────────────────
def test_9_bullet_continuation_stays_one_project():
    entries = cluster_entries(txt_spans([
        "Chronos",
        "• Built using FastAPI",
        "• Used PostgreSQL",
        "• Implemented retries",
    ]), body_font_size=11.0)
    assert len(entries) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 — Cross-attribution invariant (disjoint stacks stay disjoint)
# ─────────────────────────────────────────────────────────────────────────────
def test_10_cross_attribution_invariant():
    projs = parse_projects([
        "Alpha - ingestion pipeline",
        "Built using Python and Kafka.",
        "",
        "Beta - web client",
        "Built using React and TypeScript.",
        "",
        "Gamma - systems daemon",
        "Built using Rust and SQLite.",
    ])
    assert len(projs) == 3
    tech = {p["title"]: set(p["technologies"]) for p in projs}
    sets = list(tech.values())
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert sets[i] & sets[j] == set(), f"contamination: {sets[i]} ∩ {sets[j]}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 11 — Every project survives (5 projects -> 5 entries)
# ─────────────────────────────────────────────────────────────────────────────
def test_11_every_project_survives_five():
    lines = []
    for name in ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]:
        lines += [f"{name} - a useful service", "Built using Python.", ""]
    entries = cluster_entries(txt_spans(lines), body_font_size=11.0)
    assert len(entries) == 5


# ─────────────────────────────────────────────────────────────────────────────
# Test 12 — Technology mentioned in the title is captured
# ─────────────────────────────────────────────────────────────────────────────
def test_12_title_line_technology_captured():
    projs = parse_projects([
        "Chronos - Python workflow orchestrator",
        "Handles scheduling and retries.",
    ])
    assert len(projs) == 1
    assert "Python" in projs[0]["technologies"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 13 — Pipe description is NOT a technology
# ─────────────────────────────────────────────────────────────────────────────
def test_13_pipe_description_is_not_a_technology():
    projs = parse_projects([
        "Chronos | Distributed workflow orchestrator",
        "Handles scheduling.",
    ])
    assert len(projs) == 1
    assert projs[0]["title"] == "Chronos"
    assert "Distributed workflow orchestrator" not in projs[0]["technologies"]
    assert projs[0]["technologies"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 14 — Common English words are NOT technologies
# ─────────────────────────────────────────────────────────────────────────────
def test_14_common_english_words_are_not_technologies():
    projs = parse_projects([
        "Community Garden Planner - neighborhood tool",
        "We wanted the system to react to changing demand.",
        "We used an express delivery workflow for updates.",
        "The service should go back to a healthy state after failures.",
        "We spring into action when the queue grows.",
        "Rust never sleeps was our reliability motto.",
        "Users could rest assured the data was safe.",
    ])
    assert len(projs) == 1
    got = set(projs[0]["technologies"])
    for fp in {"React", "Express", "Go", "Spring", "Rust", "REST"}:
        assert fp not in got, f"false-positive technology: {fp} in {got}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 15 — Genuine ambiguous technologies ARE detected (with context)
# ─────────────────────────────────────────────────────────────────────────────
def test_15_genuine_ambiguous_technologies_detected():
    projs = parse_projects([
        "Trailhead - API platform",
        "Built a REST API using Express and React.",
        "Implemented the pricing service in Rust.",
    ])
    assert len(projs) == 1
    got = set(projs[0]["technologies"])
    assert {"REST", "Express", "React", "Rust"} <= got, f"missing genuine techs: {got}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 16 — Experience analogue: dateless jobs do not merge
# ─────────────────────────────────────────────────────────────────────────────
def test_16_experience_without_dates_does_not_merge():
    section = Section(label="experience", raw_header_text="", spans=txt_spans([
        "Software Engineer, Acme Corp",
        "Built the billing service in Python.",
        "",
        "Backend Intern, Globex Inc",
        "Built the ingestion pipeline in Go.",
    ]), header_confidence=0.9, header_match_reason="test")
    result = ExperienceParser().parse({"experience": section}, doc_for(section.spans))
    assert len(result.entities) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 17 — Education analogue: two dateless degrees do not merge into one
# ─────────────────────────────────────────────────────────────────────────────
def test_17_education_two_degrees_do_not_merge():
    section = Section(label="education", raw_header_text="", spans=txt_spans([
        "Master of Science in Computer Science",
        "Stanford University",
        "",
        "Bachelor of Engineering in Information Technology",
        "University of Mumbai",
    ]), header_confidence=0.9, header_match_reason="test")
    result = EducationParser().parse({"education": section}, doc_for(section.spans))
    assert len(result.entities) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 18 — Single-project resume still produces exactly one project
# ─────────────────────────────────────────────────────────────────────────────
def test_18_single_project_stays_one():
    projs = parse_projects([
        "Chronos - Distributed workflow orchestrator",
        "Built using FastAPI and PostgreSQL.",
        "Implemented retries and leases.",
    ])
    assert len(projs) == 1
    assert "FastAPI" in projs[0]["technologies"]
    assert "PostgreSQL" in projs[0]["technologies"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 19 — Multiple projects sharing a technology (shared tech allowed)
# ─────────────────────────────────────────────────────────────────────────────
def test_19_shared_technology_allowed():
    projs = parse_projects([
        "Alpha - data api",
        "Built using Python and PostgreSQL.",
        "",
        "Beta - cache layer",
        "Built using Python and Redis.",
    ])
    assert len(projs) == 2
    tech = {p["title"]: set(p["technologies"]) for p in projs}
    alpha = next(t for n, t in tech.items() if "Alpha" in n)
    beta = next(t for n, t in tech.items() if "Beta" in n)
    assert "Python" in alpha and "Python" in beta  # shared, genuinely present
    assert "PostgreSQL" in alpha and "PostgreSQL" not in beta
    assert "Redis" in beta and "Redis" not in alpha


# ─────────────────────────────────────────────────────────────────────────────
# Test 20 — Skills-only technologies do not bleed into projects
# ─────────────────────────────────────────────────────────────────────────────
def test_20_skills_do_not_bleed_into_projects():
    # A project whose body mentions no gazetteer technology; a Skills section
    # (parsed separately) is not visible to ProjectParser at all.
    projs = parse_projects([
        "Chronos - workflow orchestrator",
        "Coordinated background jobs and scheduling.",
    ])
    assert len(projs) == 1
    assert projs[0]["technologies"] == []


# ═════════════════════════════════════════════════════════════════════════════
# Blank-line GEOMETRY regression tests (from the Phase 1 geometry QA pass).
#
# The entry boundary uses a blank-line gap as ONE signal (`_gap_flags`), so
# these pin the two directions that must never drift:
#   - internal whitespace (a blank between prose paragraphs / bullet groups /
#     under a title) must NOT split an entry, and
#   - real between-entry blank lines (one, two, three+, plus leading/trailing
#     blanks) must still separate entries.
# ═════════════════════════════════════════════════════════════════════════════

def test_geo_internal_blank_in_description_does_not_split():
    """A blank line inside a project's prose description must stay ONE
    project -- the paragraph after the blank is prose (content), never an
    entry start, regardless of the gap it creates."""
    projs = parse_projects([
        "Alpha - task scheduler",
        "Built using Python and PostgreSQL.",
        "",
        "Improved throughput and reduced latency substantially over time.",
        "",
        "Beta - chat service",
        "Built using Redis.",
    ])
    assert len(projs) == 2
    alpha = next(set(p["technologies"]) for p in projs if "Alpha" in p["title"])
    assert alpha == {"Python", "PostgreSQL"}  # no contamination from the split


def test_geo_multiple_prose_paragraphs_stay_one_project():
    """Several blank-separated prose paragraphs under one title remain a
    single project."""
    entries = cluster_entries(txt_spans([
        "Alpha - task scheduler",
        "Built using Python and PostgreSQL.",
        "",
        "Scaled to thousands of concurrent jobs with a leasing protocol.",
        "",
        "Added observability with structured logging and metrics.",
    ]), body_font_size=11.0)
    assert len(entries) == 1


def test_geo_bullet_groups_separated_by_blanks_stay_one_project():
    """Bullet groups separated by a blank line remain one project -- bullets
    are content, never an entry start, gap or not."""
    entries = cluster_entries(txt_spans([
        "Alpha - task scheduler",
        "• Built using Python",
        "• Used PostgreSQL",
        "",
        "• Implemented retries",
        "• Added backpressure",
    ]), body_font_size=11.0)
    assert len(entries) == 1


def test_geo_two_blank_lines_between_projects_still_separate():
    entries = cluster_entries(txt_spans([
        "Alpha - task scheduler",
        "Built using Python.",
        "",
        "",
        "Beta - chat service",
        "Built using Redis.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_geo_three_plus_blank_lines_between_projects_still_separate():
    entries = cluster_entries(txt_spans([
        "Alpha - task scheduler",
        "Built using Python.",
        "",
        "",
        "",
        "Beta - chat service",
        "Built using Redis.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_geo_leading_blank_lines_do_not_affect_segmentation():
    """Blank lines before the first entry (e.g. right under the section
    header) must not change the outcome."""
    entries = cluster_entries(txt_spans([
        "",
        "",
        "Alpha - task scheduler",
        "Built using Python.",
        "",
        "Beta - chat service",
        "Built using Redis.",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_geo_trailing_blank_lines_do_not_affect_segmentation():
    entries = cluster_entries(txt_spans([
        "Alpha - task scheduler",
        "Built using Python.",
        "",
        "Beta - chat service",
        "Built using Redis.",
        "",
        "",
    ]), body_font_size=11.0)
    assert len(entries) == 2


def test_geo_KNOWN_LIMITATION_blank_separated_titlelike_subheading_oversplits():
    """KNOWN LIMITATION (documented, intentionally NOT fixed in Phase 1): a
    blank-separated, title-like SUBHEADING inside a project (e.g. "Key
    Features") is over-segmented into its own entry, because a blank gap
    before a title-like line reads as an entry boundary and there is no
    signal here that distinguishes a within-entry heading from a sibling
    entry.

    This test pins the CURRENT behavior so the limitation is visible and any
    future change to it is deliberate. Crucially it also asserts the CORE
    INVARIANT still holds: the over-split does NOT contaminate technologies
    across entries -- the real project keeps its own tech and the phantom
    'Key Features' entry carries none. (A future refinement could suppress a
    gap-start on a line lacking the section's established entry-separator
    shape; out of scope for this cleanup.)"""
    projs = parse_projects([
        "Alpha - task scheduler",
        "Built using Python.",
        "",
        "Key Features",
        "",
        "Implemented retries and backpressure.",
    ])
    # Documented current behavior: over-segmented into 2.
    assert len(projs) == 2
    # But the invariant that matters is preserved -- no tech contamination:
    alpha = next(set(p["technologies"]) for p in projs if "Alpha" in p["title"])
    phantom = next(set(p["technologies"]) for p in projs if "Alpha" not in p["title"])
    assert alpha == {"Python"}
    assert phantom == set()


def test_geo_UNSUPPORTED_bare_names_no_structure_are_not_invented_as_boundaries():
    """INTENTIONALLY UNSUPPORTED / ambiguous: bare project names with no
    descriptions, dates, separators, bullets, or any other structural
    evidence -- even with blank lines, the spacing is uniform so no line
    stands out as a boundary. The parser must NOT invent boundaries here; it
    conservatively yields a single entry rather than fabricating three. (Any
    real structural evidence -- a description, a bullet, a dash/pipe
    separator, or a date -- resolves this, as the other tests show.)"""
    entries = cluster_entries(txt_spans([
        "Project Alpha",
        "",
        "Project Beta",
        "",
        "Project Gamma",
    ]), body_font_size=11.0)
    # Not invented as 3 separate boundaries; conservatively one entry.
    assert len(entries) == 1
