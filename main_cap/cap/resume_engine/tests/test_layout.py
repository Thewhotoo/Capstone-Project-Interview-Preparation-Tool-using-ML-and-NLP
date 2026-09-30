from resume_engine.layout import ColumnAwareLayoutReconstructor


def _line_spans(make_text_span, x0, y0, width=150.0, height=10.0, page_num=0, text="line"):
    return [make_text_span(text=text, bbox=(x0, y0, x0 + width, y0 + height), page_num=page_num)]


def test_single_column_document_stays_single_column_and_keeps_order(make_document_model, make_text_span):
    spans = []
    for i in range(10):
        y = 72.0 + i * 14.0
        spans.extend(_line_spans(make_text_span, x0=72.0, y0=y, text=f"line-{i}"))
    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode == "single_column"
    assert result.layout_confidence >= 0.9
    assert [s.text for s in result.spans] == [f"line-{i}" for i in range(10)]
    assert all(s.column_index == 0 for s in result.spans)


def test_single_column_with_bullet_indentation_is_not_misread_as_two_column(
    make_document_model, make_text_span
):
    spans = []
    for i in range(10):
        y = 72.0 + i * 14.0
        # Every third line is an indented bullet -- a small, realistic
        # indentation delta, not a real column gap.
        x0 = 90.0 if i % 3 == 0 else 72.0
        spans.extend(_line_spans(make_text_span, x0=x0, y0=y, text=f"line-{i}"))
    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode == "single_column"
    assert [s.text for s in result.spans] == [f"line-{i}" for i in range(10)]


def test_stray_far_right_fragment_does_not_trigger_two_column_false_positive(
    make_document_model, make_text_span
):
    spans = []
    for i in range(9):
        y = 72.0 + i * 14.0
        spans.extend(_line_spans(make_text_span, x0=72.0, y0=y, text=f"line-{i}"))
    # A single stray far-right fragment (e.g. a lone date or page number on
    # its own line) -- exactly the false-positive risk the architecture doc
    # names (Section 4.2): must not corroborate into a second column on its
    # own (only 1 line, below MIN_CORROBORATING_LINES).
    spans.extend(_line_spans(make_text_span, x0=560.0, y0=750.0, text="stray"))
    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode != "two_column"
    # Reading order must stay chronological (top-to-bottom), never split
    # into "everything, then the stray fragment" as if it were a real column.
    ordered_texts = [s.text for s in result.spans]
    assert ordered_texts.index("line-0") < ordered_texts.index("stray")
    assert ordered_texts.index("stray") == len(ordered_texts) - 1


def test_two_column_sidebar_and_main_are_corroborated_and_column_major_ordered(
    make_document_model, make_text_span
):
    spans = []
    # Left sidebar column: 5 lines, x0=72, narrower.
    for i in range(5):
        y = 100.0 + i * 14.0
        spans.extend(
            _line_spans(make_text_span, x0=72.0, y0=y, width=100.0, text=f"sidebar-{i}")
        )
    # Right main column: 5 lines, x0=300, overlapping the same y-range.
    for i in range(5):
        y = 100.0 + i * 14.0
        spans.extend(
            _line_spans(make_text_span, x0=300.0, y0=y, width=150.0, text=f"main-{i}")
        )
    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode == "two_column"
    assert result.layout_confidence >= 0.6

    ordered_texts = [s.text for s in result.spans]
    # Column-major: all sidebar lines (column 0) before all main lines (column 1).
    last_sidebar_index = max(ordered_texts.index(f"sidebar-{i}") for i in range(5))
    first_main_index = min(ordered_texts.index(f"main-{i}") for i in range(5))
    assert last_sidebar_index < first_main_index

    by_text = {s.text: s for s in result.spans}
    for i in range(5):
        assert by_text[f"sidebar-{i}"].column_index == 0
        assert by_text[f"main-{i}"].column_index == 1


def test_multi_page_document_reorders_each_page_independently(make_document_model, make_text_span):
    spans = []
    # Page 0: single column.
    for i in range(4):
        spans.extend(
            _line_spans(make_text_span, x0=72.0, y0=72.0 + i * 14.0, page_num=0, text=f"p0-{i}")
        )
    # Page 1: clean two-column.
    for i in range(5):
        y = 100.0 + i * 14.0
        spans.extend(
            _line_spans(make_text_span, x0=72.0, y0=y, width=100.0, page_num=1, text=f"p1-left-{i}")
        )
    for i in range(5):
        y = 100.0 + i * 14.0
        spans.extend(
            _line_spans(make_text_span, x0=300.0, y0=y, width=150.0, page_num=1, text=f"p1-right-{i}")
        )
    doc = make_document_model(spans=spans, page_count=2)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    page0_spans = [s for s in result.spans if s.page_num == 0]
    page1_spans = [s for s in result.spans if s.page_num == 1]
    assert [s.text for s in page0_spans] == [f"p0-{i}" for i in range(4)]
    assert all(s.column_index == 0 for s in page0_spans)

    page1_texts = [s.text for s in page1_spans]
    last_left = max(page1_texts.index(f"p1-left-{i}") for i in range(5))
    first_right = min(page1_texts.index(f"p1-right-{i}") for i in range(5))
    assert last_left < first_right


def test_inline_right_aligned_dates_are_not_misread_as_a_second_column(make_document_model, make_text_span):
    """Regression test for Milestone 1 validation Finding #1: a date printed
    on the SAME visual line as the role/company text (a very common real
    template pattern) must not corroborate into a false second column, even
    though three such dates individually clear the old line-count/balance
    guards. The date band's own row-to-row spacing (34pt, once per job
    entry) is roughly double the body band's (17pt, one row per role line
    AND one per description line) -- the row-pitch-continuity guard must
    reject this."""
    spans = []
    spans.append(make_text_span(text="Jordan Example", bbox=(72.0, 57.0, 173.0, 76.0), page_num=0))
    spans.append(make_text_span(text="EXPERIENCE", bbox=(72.0, 84.0, 136.0, 98.0), page_num=0))

    job_y_positions = [105.0, 139.0, 173.0]
    for i, y in enumerate(job_y_positions):
        spans.append(
            make_text_span(text=f"Company {i}, Senior Engineer", bbox=(72.0, y, 186.0, y + 12.0), page_num=0)
        )
        spans.append(make_text_span(text="2021 - Present", bbox=(450.0, y, 509.0, y + 12.0), page_num=0))
        spans.append(
            make_text_span(
                text=f"Led a project at company {i}.", bbox=(72.0, y + 17.0, 282.0, y + 29.0), page_num=0
            )
        )

    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode != "two_column"
    # The critical regression check: dates must NOT be pulled apart from
    # their job entries and dumped at the end of the document.
    ordered_texts = [s.text for s in result.spans]
    assert ordered_texts.index("2021 - Present") < ordered_texts.index("Led a project at company 0.")


def test_short_but_genuine_sidebar_is_recognized_as_two_column(make_document_model, make_text_span):
    """Regression test for Milestone 1 validation Finding #2: a real
    two-column resume with a short (3-line) sidebar must still be
    recognized as two_column, even against a much longer main column,
    because the sidebar's own rows are single-spaced (same pitch as main),
    not because it has a comparable line COUNT (it doesn't: 3 vs 20)."""
    spans = []
    sidebar_lines = ["Skills", "Python", "SQL"]
    for i, text in enumerate(sidebar_lines):
        spans.extend(_line_spans(make_text_span, x0=40.0, y0=100.0 + i * 16.0, width=60.0, text=text))

    main_lines = [f"Experience line {i}" for i in range(20)]
    for i, text in enumerate(main_lines):
        spans.extend(_line_spans(make_text_span, x0=150.0, y0=100.0 + i * 16.0, width=200.0, text=text))

    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode == "two_column"
    by_text = {s.text: s for s in result.spans}
    assert by_text["Skills"].column_index == 0
    assert by_text["Experience line 0"].column_index == 1


def test_balance_ratio_still_rejects_extreme_imbalance_even_with_matching_pitch(
    make_document_model, make_text_span
):
    """Confirms MIN_BAND_BALANCE_RATIO is a real, active guard, not a
    vestigial one -- per explicit direction, pitch continuity was added
    ALONGSIDE balance ratio, not as its replacement. A candidate band with
    only 3 lines against 35 (balance ~0.086, below MIN_BAND_BALANCE_RATIO's
    0.1) must still be rejected even though both bands share the exact same
    single-line pitch (16pt), which would otherwise satisfy the pitch
    continuity signal on its own."""
    spans = []
    small_band = ["Skills", "Python", "SQL"]
    for i, text in enumerate(small_band):
        spans.extend(_line_spans(make_text_span, x0=40.0, y0=100.0 + i * 16.0, width=60.0, text=text))

    large_band = [f"Experience line {i}" for i in range(35)]
    for i, text in enumerate(large_band):
        spans.extend(_line_spans(make_text_span, x0=150.0, y0=100.0 + i * 16.0, width=200.0, text=text))

    doc = make_document_model(spans=spans, page_count=1)

    result = ColumnAwareLayoutReconstructor().reconstruct(doc)

    assert result.layout_mode != "two_column"
