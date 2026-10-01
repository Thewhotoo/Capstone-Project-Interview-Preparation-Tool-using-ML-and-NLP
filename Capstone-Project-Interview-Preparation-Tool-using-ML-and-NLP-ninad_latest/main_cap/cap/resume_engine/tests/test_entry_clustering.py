from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line


def test_cluster_entries_groups_bold_header_with_following_body(make_text_span):
    spans = [
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 72.0, 250.0, 82.0), is_bold=True),
        make_text_span(text="Led migration of the billing platform.", bbox=(72.0, 90.0, 280.0, 100.0)),
        make_text_span(text="Reduced latency by 40%.", bbox=(72.0, 106.0, 250.0, 116.0)),
        make_text_span(text="Beta Inc, Software Engineer", bbox=(72.0, 122.0, 250.0, 132.0), is_bold=True),
        make_text_span(text="Built the analytics dashboard.", bbox=(72.0, 140.0, 260.0, 150.0)),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 2
    assert entries[0].header_text == "Acme Corp, Senior Engineer"
    assert entries[0].body_lines == ["Led migration of the billing platform.", "Reduced latency by 40%."]
    assert entries[1].header_text == "Beta Inc, Software Engineer"
    assert entries[1].body_lines == ["Built the analytics dashboard."]


def test_cluster_entries_uses_larger_font_as_header_signal(make_text_span):
    spans = [
        make_text_span(text="Project Alpha", bbox=(72.0, 72.0, 200.0, 90.0), font_size=14.0, is_bold=False),
        make_text_span(text="A tool for tracking things.", bbox=(72.0, 92.0, 260.0, 102.0), font_size=10.0),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 1
    assert entries[0].header_text == "Project Alpha"
    assert entries[0].body_lines == ["A tool for tracking things."]


def test_cluster_entries_falls_back_to_one_entry_when_nothing_is_header_like(make_text_span):
    """No bold/larger line anywhere -- a plain ATS template with zero
    typographic variation. Must not silently produce zero entries."""
    spans = [
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 72.0, 250.0, 82.0), font_size=10.0),
        make_text_span(text="Led migration of the billing platform.", bbox=(72.0, 90.0, 280.0, 100.0), font_size=10.0),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 1
    assert entries[0].header_text == "Acme Corp, Senior Engineer"
    assert entries[0].body_lines == ["Led migration of the billing platform."]


def test_cluster_entries_returns_empty_list_for_no_spans():
    assert cluster_entries([], body_font_size=10.0) == []


def test_cluster_entries_never_merges_across_page_or_column_change(make_text_span):
    spans = [
        make_text_span(text="Acme Corp", bbox=(72.0, 700.0, 200.0, 710.0), is_bold=True, page_num=0),
        make_text_span(text="Continued work.", bbox=(72.0, 72.0, 250.0, 82.0), page_num=1),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 1
    assert entries[0].body_lines == ["Continued work."]


def test_strip_section_header_line_removes_the_header_and_keeps_the_rest(make_text_span):
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), is_bold=True),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 90.0, 250.0, 100.0), is_bold=True),
    ]
    result = strip_section_header_line(spans, "Experience")
    assert [s.text for s in result] == ["Acme Corp, Senior Engineer"]


def test_strip_section_header_line_removes_every_matching_occurrence(make_text_span):
    """A label detected more than once (cross-page continuation, or a
    repeated running header per Milestone 2's known limitation) can
    concatenate more than one header hit into one Section's spans."""
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), is_bold=True, page_num=0),
        make_text_span(text="Acme Corp", bbox=(72.0, 90.0, 250.0, 100.0), is_bold=True, page_num=0),
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), is_bold=True, page_num=1),
        make_text_span(text="Beta Inc", bbox=(72.0, 90.0, 250.0, 100.0), is_bold=True, page_num=1),
    ]
    result = strip_section_header_line(spans, "Experience")
    assert [s.text for s in result] == ["Acme Corp", "Beta Inc"]


def test_strip_section_header_line_is_a_no_op_for_empty_header_text(make_text_span):
    spans = [make_text_span(text="Some content", bbox=(72.0, 72.0, 150.0, 82.0))]
    assert strip_section_header_line(spans, "") == spans


def test_cluster_entries_does_not_fragment_bullets_when_document_wide_body_font_size_is_skewed(
    make_text_span,
):
    """Regression test -- Phase 1 real-world evaluation (self_devraj.pdf):
    a resume whose Experience-section bullets are ~9pt, but whose
    document-wide `body_font_size` (computed elsewhere in the document by
    raw span-token count, e.g. a dense inline skills paragraph) was only
    7.2pt. Every 9pt bullet line then cleared the old
    `body_font_size * 1.05` bar and was wrongly treated as a new entry
    header, splitting one job into ~20 spurious entries. The section's own
    local line-font median (9.0, all bullets) must be used instead, so
    only the genuinely bold header line starts a new entry."""
    skewed_doc_wide_body_font_size = 7.2
    spans = [
        make_text_span(
            text="Acme Corp, Senior Engineer",
            bbox=(72.0, 72.0, 250.0, 82.0),
            font_size=9.33,
            is_bold=True,
        ),
        make_text_span(
            text="Working as a full-stack developer for a client project on a wealth platform.",
            bbox=(72.0, 90.0, 400.0, 100.0),
            font_size=8.58,
        ),
        make_text_span(
            text="Collaborated with client teams to rebuild legacy systems.",
            bbox=(72.0, 106.0, 400.0, 116.0),
            font_size=9.0,
        ),
        make_text_span(
            text="Reduced deployment times by 50% via an automated testing framework.",
            bbox=(72.0, 122.0, 400.0, 132.0),
            font_size=9.0,
        ),
    ]
    entries = cluster_entries(spans, body_font_size=skewed_doc_wide_body_font_size)

    assert len(entries) == 1
    assert entries[0].header_text == "Acme Corp, Senior Engineer"
    assert entries[0].body_lines == [
        "Working as a full-stack developer for a client project on a wealth platform.",
        "Collaborated with client teams to rebuild legacy systems.",
        "Reduced deployment times by 50% via an automated testing framework.",
    ]


def test_cluster_entries_does_not_treat_a_bullet_with_one_bold_word_as_a_header(make_text_span):
    """Regression test -- Phase 1 real-world evaluation (self_devraj.pdf):
    a bullet that is almost entirely plain text except for one emphasized
    word/acronym (e.g. "...reporting directly to the **CTO**.") must stay
    part of the current entry's body, not start a spurious new entry. Only
    a MAJORITY-bold line counts as a header (see `_Line.is_bold`)."""
    spans = [
        make_text_span(
            text="Acme Corp, Senior Engineer",
            bbox=(72.0, 72.0, 250.0, 82.0),
            is_bold=True,
        ),
        make_text_span(
            text="Drove the rollout of a new billing pipeline, reporting directly to the",
            bbox=(72.0, 90.0, 400.0, 100.0),
            is_bold=False,
        ),
        make_text_span(text="CTO", bbox=(400.0, 90.0, 420.0, 100.0), is_bold=True),
        make_text_span(text=".", bbox=(420.0, 90.0, 424.0, 100.0), is_bold=False),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 1
    assert entries[0].header_text == "Acme Corp, Senior Engineer"
    assert len(entries[0].body_lines) == 1
    assert "reporting directly to the CTO ." in entries[0].body_lines[0]


def test_cluster_entries_recognizes_a_bold_header_with_a_longer_non_bold_trailing_date(
    make_text_span,
):
    """Regression test -- Phase 1 real-world evaluation (self_devraj.pdf):
    a header line where the bold role/company text is SHORTER, by
    character count, than its own non-bold trailing date/location (e.g.
    "**Care Fi, Software Developer Intern** Oct 2022 - May 2023 (Remote)")
    must still be recognized as a header. A naive >=50% bold-character
    majority over the WHOLE line fails this common template shape; the
    threshold must have enough margin below the ~45-50% these real
    headers land at, while staying well above the ~2-14% a bulleted line
    with one bold word/phrase measures at."""
    spans = [
        make_text_span(text="Care Fi, Software Developer Intern", bbox=(72.0, 72.0, 260.0, 82.0), is_bold=True),
        make_text_span(
            text="Oct 2022 - May 2023 (Gurugram, India)",
            bbox=(262.0, 72.0, 420.0, 82.0),
            is_bold=False,
        ),
        make_text_span(
            text="Designed and implemented a healthcare fintech app.",
            bbox=(72.0, 90.0, 350.0, 100.0),
            is_bold=False,
        ),
    ]
    entries = cluster_entries(spans, body_font_size=10.0)

    assert len(entries) == 1
    assert entries[0].header_text == "Care Fi, Software Developer Intern Oct 2022 - May 2023 (Gurugram, India)"
    assert entries[0].body_lines == ["Designed and implemented a healthcare fintech app."]
