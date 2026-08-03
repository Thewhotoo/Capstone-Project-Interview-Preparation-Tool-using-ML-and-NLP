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
