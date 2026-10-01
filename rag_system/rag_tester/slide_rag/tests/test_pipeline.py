"""Unit tests for the slide pipeline, on small synthetic slide PDFs.

    python -m pytest slide_rag/tests -q        (from rag_system/rag_tester)
"""
from __future__ import annotations

import numpy as np
import pymupdf
import pytest

from slide_rag.classify import classify_and_clean
from slide_rag.extract import SlideRecord, extract_pdf
from slide_rag.sections import build_sections, normalize_title, title_stem
from slide_rag.text_utils import bm25_tokenize

W, H = 960, 540


def _slide(doc, title, bullets=(), header="Database Management Systems", page_no=None,
           labels=(), diagram=False, footer=None):
    page = doc.new_page(width=W, height=H)
    if header:
        page.insert_text((37, 40), header, fontsize=24, fontname="hebo")
    if title:
        page.insert_text((38, 90), title, fontsize=22, fontname="hebo")
    y = 150
    for b in bullets:
        page.insert_text((60, y), b, fontsize=18)
        y += 30
    if diagram:
        for i in range(4):
            page.draw_rect(pymupdf.Rect(560 + i * 90, 300, 630 + i * 90, 360), color=(0, 0, 0))
        for i, lab in enumerate(labels):
            page.insert_text((570 + i * 90, 335), lab, fontsize=12)
    if page_no is not None:
        page.insert_text((900, 525), str(page_no), fontsize=10)
    if footer:
        page.insert_text((300, 525), footer, fontsize=10)
    return page


@pytest.fixture
def deck(tmp_path):
    doc = pymupdf.open()
    pdf = tmp_path / "dbms.pdf"
    page = doc.new_page(width=W, height=H)
    page.insert_text((380, 200), "Database Management Systems", fontsize=36, fontname="hebo")
    page.insert_text((380, 260), "UE23CS351A - Transactions", fontsize=36, fontname="hebo")
    page.insert_text((380, 340), "Prof. Someone", fontsize=20)
    page.insert_text((380, 380), "Department of Computer Science and Engineering", fontsize=20)
    _slide(doc, "Contents", ["1.1 ACID", "1.2 Schedules"], page_no=2)
    _slide(doc, "ACID Properties", ["-Atomicity: all or nothing", "-Consistency: valid state to valid state"], page_no=3)
    _slide(doc, "ACID Properties (contd.)", ["-Isolation: concurrent transactions do not interfere",
                                             "-Durability: committed changes survive crashes"], page_no=4)
    _slide(doc, "Schedules", ["-A schedule is an ordering of operations"], page_no=5)
    _slide(doc, "Schedules", ["-A schedule is an ordering of operations",
                              "-Serial schedules run one transaction at a time"], page_no=6)
    _slide(doc, "Precedence Graph", ["-Nodes are transactions, edges are conflicts"], page_no=7,
           diagram=True, labels=["T1", "T2", "T3", "R(A)"])
    for i in range(8, 40):
        _slide(doc, f"Filler topic {i} about recovery", [f"-Point number {i} about logging and recovery"], page_no=i)
    _slide(doc, "Thank You", [], page_no=40)
    doc.save(pdf)
    return pdf


def test_header_title_and_footer(deck):
    slides, boiler = extract_pdf(deck, "dbms")
    assert "database management systems" in boiler
    s = slides[2]
    assert s.title == "ACID Properties"
    assert "Database Management Systems" not in s.body_text()
    assert [it["text"] for it in s.items][0] == "Atomicity: all or nothing"
    assert s.items[0]["kind"] == "bullet"
    assert not any(it["text"].strip() == "3" for it in s.items), "slide number must be removed"


def test_diagram_labels_are_set_aside(deck):
    slides, _ = extract_pdf(deck, "dbms")
    s = slides[6]
    assert s.title == "Precedence Graph"
    assert set(s.labels) >= {"T1", "T2", "T3", "R(A)"}
    assert "T1" not in s.body_text()
    assert s.diagram_frac > 0


def test_classification_decks_and_incremental_builds(deck):
    slides, boiler = extract_pdf(deck, "dbms")
    classify_and_clean(slides, boiler)
    assert slides[0].type == "deck_title"
    assert slides[0].deck_title == "Transactions"
    assert slides[1].type == "contents" and slides[1].dropped == "contents"
    assert slides[4].dropped == "incremental_build"      # first "Schedules" is contained in the next
    assert not slides[5].dropped
    assert slides[-1].dropped == "admin"                  # Thank You
    assert all(s.deck == slides[2].deck for s in slides[2:])


def test_sections_merge_continuations(deck):
    slides, boiler = extract_pdf(deck, "dbms")
    classify_and_clean(slides, boiler)
    emb = np.eye(len(slides), dtype=np.float32)            # unrelated content everywhere
    sections = build_sections(slides, emb, "dbms")
    acid = next(s for s in sections if s.title.startswith("ACID"))
    assert acid.pages == [3, 4]
    assert acid.title == "ACID Properties"
    assert "Durability" in acid.text and "Atomicity" in acid.text
    sched = next(s for s in sections if s.title == "Schedules")
    assert sched.pages == [6]


def test_personal_note_annotations_are_stripped(tmp_path):
    doc = pymupdf.open()
    for i in range(6):
        page = _slide(doc, f"Topic {i} heading", [f"- Real bullet number {i} about paging"], page_no=i)
    page.add_freetext_annot(pymupdf.Rect(500, 300, 900, 360), "see notebook before exam", fontsize=14)
    pdf = tmp_path / "annotated.pdf"
    doc.save(pdf)
    slides, _ = extract_pdf(pdf, "os")
    s = slides[-1]
    assert "see notebook" not in s.full_text()
    assert "Real bullet number 5 about paging" in s.full_text()
    assert any("see notebook" in n for n in s.removed_notes)


@pytest.mark.parametrize("raw,expected", [
    ("Deadlocks (contd.)", "deadlocks"),
    ("Deadlocks (Contd)", "deadlocks"),
    ("Deadlocks contd.", "deadlocks"),
    ("Paging - 2", "paging"),
    ("Normal Forms Part II", "normal forms"),
    ("IPv4 Addressing", "ipv4 addressing"),
    ("IPv4", "ipv4"),
    ("Learn more", "learn more"),
    ("Schedules (more)", "schedules"),
])
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected


def test_title_stem():
    assert title_stem("Hashing: Linear Probing") == "hashing"
    assert title_stem("Example: ER Diagram") == ""          # generic stems never join sections


def test_bm25_tokenizer_matches_query_and_corpus():
    assert bm25_tokenize("What is a deadlock?") == ["deadlock"]
    assert "deadlock" in bm25_tokenize("Deadlock: a set of blocked processes")
    assert "c++" in bm25_tokenize("Templates in C++")


def _rec(page, title, text, type_="concept", deck=1):
    r = SlideRecord(subject="x", pdf="x.pdf", page=page, width=W, height=H, title=title,
                    items=[{"text": text, "level": 0, "kind": "bullet"}] if text else [])
    r.type, r.deck = type_, deck
    return r


def test_quiz_slides_are_set_aside():
    from slide_rag.classify import classify_slide
    quiz = _rec(1, "1. What is the primary purpose of the Adapter pattern?",
                "A) Create objects B) Convert an interface into another C) Notify observers D) None")
    assert classify_slide(quiz, set()) == "quiz"
    concept = _rec(2, "Adapter: Class, Object Structural", "Converts the interface of a class into another interface")
    assert classify_slide(concept, set()) == "concept"


def test_problem_solution_slides_are_stitched_and_unsolved_flagged():
    slides = [
        _rec(1, "Example 1: Minimal Cover", "Find the minimal cover of F", "problem"),
        _rec(2, "Solution", "Step 1: decompose the right-hand sides", "problem"),
        _rec(3, "Example 2: Closure", "Find the closure of AB", "problem"),
        _rec(4, "Candidate Keys", "A candidate key is a minimal superkey"),
    ]
    emb = np.eye(4, dtype=np.float32)
    secs = build_sections(slides, emb, "x")
    assert [s.pages for s in secs] == [[1, 2], [3], [4]]
    assert not secs[0].unsolved
    assert secs[1].unsolved


def test_size_cap_splits_long_runs():
    long = " ".join(["word"] * 200)
    slides = [_rec(i, "Indexing", f"{long} {i}") for i in range(1, 5)]
    emb = np.ones((4, 4), dtype=np.float32) / 2
    secs = build_sections(slides, emb, "x")
    assert len(secs) >= 2
    assert all(s.words <= 450 for s in secs)
    assert secs[1].part == 2
