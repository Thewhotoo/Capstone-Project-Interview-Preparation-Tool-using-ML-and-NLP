from resume_engine.sections import (
    MAX_HEADER_WORDS,
    MIN_HEADER_FONT_RATIO,
    HeuristicSectionDetector,
    _classify_header_line,
    _fuzzy_match_label,
    _group_into_document_lines,
    _is_candidate_header_line,
    _LazySemanticModel,
)


def test_group_into_document_lines_groups_by_y_proximity(make_text_span):
    spans = [
        make_text_span(text="Jordan", bbox=(72.0, 72.0, 100.0, 82.0), page_num=0),
        make_text_span(text="Example", bbox=(105.0, 72.0, 150.0, 82.0), page_num=0),
        make_text_span(text="Experience", bbox=(72.0, 100.0, 150.0, 110.0), page_num=0),
    ]
    lines = _group_into_document_lines(spans)
    assert len(lines) == 2
    assert lines[0].text == "Jordan Example"
    assert lines[1].text == "Experience"


def test_group_into_document_lines_never_merges_across_page_change(make_text_span):
    spans = [
        make_text_span(text="End of page one", bbox=(72.0, 700.0, 200.0, 710.0), page_num=0),
        make_text_span(text="Top of page two", bbox=(72.0, 700.0, 200.0, 710.0), page_num=1),
    ]
    lines = _group_into_document_lines(spans)
    assert len(lines) == 2
    assert lines[0].page_num == 0
    assert lines[1].page_num == 1


def test_group_into_document_lines_never_merges_across_column_change(make_text_span):
    left = make_text_span(text="Sidebar", bbox=(72.0, 100.0, 130.0, 110.0), page_num=0, column_index=0)
    right = make_text_span(text="Main", bbox=(300.0, 100.0, 340.0, 110.0), page_num=0, column_index=1)
    lines = _group_into_document_lines([left, right])
    assert len(lines) == 2
    assert lines[0].column_index == 0
    assert lines[1].column_index == 1


def test_candidate_header_line_accepts_larger_font(make_text_span):
    span = make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0)
    lines = _group_into_document_lines([span])
    assert _is_candidate_header_line(lines[0], body_font_size=10.0)


def test_candidate_header_line_accepts_bold_same_size(make_text_span):
    span = make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), font_size=10.0, is_bold=True)
    lines = _group_into_document_lines([span])
    assert _is_candidate_header_line(lines[0], body_font_size=10.0)


def test_candidate_header_line_accepts_all_caps_plain_text(make_text_span):
    """The common ATS-plain pattern: header is same size, not bold, but
    ALL CAPS -- must not be excluded just because it isn't bigger/bolder."""
    span = make_text_span(text="EXPERIENCE", bbox=(72.0, 72.0, 150.0, 82.0), font_size=10.0, is_bold=False)
    lines = _group_into_document_lines([span])
    assert _is_candidate_header_line(lines[0], body_font_size=10.0)


def test_candidate_header_line_rejects_ordinary_body_text(make_text_span):
    span = make_text_span(
        text="Led migration of the billing platform to microservices.",
        bbox=(72.0, 72.0, 300.0, 82.0),
        font_size=10.0,
        is_bold=False,
    )
    lines = _group_into_document_lines([span])
    assert not _is_candidate_header_line(lines[0], body_font_size=10.0)


def test_candidate_header_line_rejects_long_all_caps_line(make_text_span):
    """ALL CAPS alone isn't enough if the line is long -- a real header is
    short; a long all-caps sentence (e.g. a stylized pull-quote) is not."""
    span = make_text_span(
        text="THIS RESUME WAS BUILT WITH A LOT OF CARE AND ATTENTION",
        bbox=(72.0, 72.0, 400.0, 82.0),
        font_size=10.0,
        is_bold=False,
    )
    lines = _group_into_document_lines([span])
    assert len(lines[0].text.split()) > MAX_HEADER_WORDS
    assert not _is_candidate_header_line(lines[0], body_font_size=10.0)


def test_candidate_header_line_font_ratio_boundary(make_text_span):
    body_font_size = 10.0
    just_below = make_text_span(
        text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), font_size=body_font_size * (MIN_HEADER_FONT_RATIO - 0.01)
    )
    just_above = make_text_span(
        text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), font_size=body_font_size * (MIN_HEADER_FONT_RATIO + 0.01)
    )
    lines_below = _group_into_document_lines([just_below])
    lines_above = _group_into_document_lines([just_above])
    assert not _is_candidate_header_line(lines_below[0], body_font_size)
    assert _is_candidate_header_line(lines_above[0], body_font_size)


def test_fuzzy_match_label_exact_alias():
    label, score = _fuzzy_match_label("Experience")
    assert label == "experience"
    assert score >= 95


def test_fuzzy_match_label_nonstandard_but_known_phrasing():
    label, score = _fuzzy_match_label("Employment History")
    assert label == "experience"
    assert score >= 85


def test_fuzzy_match_label_weak_for_unrelated_text():
    label, score = _fuzzy_match_label("Volunteer Work Abroad")
    assert score < 85


def test_classify_header_line_confident_gazetteer_match(make_text_span):
    span = make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0)
    line = _group_into_document_lines([span])[0]
    label, confidence, reason = _classify_header_line(line)
    assert label == "experience"
    assert confidence == 0.9
    assert "alias_gazetteer_fuzzy" in reason


def test_classify_header_line_docx_style_boosts_confidence(make_text_span):
    span = make_text_span(
        text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0, style_name="Heading 1"
    )
    line = _group_into_document_lines([span])[0]
    label, confidence, reason = _classify_header_line(line)
    assert label == "experience"
    assert confidence == 0.98
    assert "docx_style_match:Heading 1" in reason


def test_classify_header_line_unrecognized_text_becomes_unknown(make_text_span):
    span = make_text_span(text="Hobbies And Interests", bbox=(72.0, 72.0, 200.0, 90.0), font_size=14.0)
    line = _group_into_document_lines([span])[0]
    label, confidence, reason = _classify_header_line(line)
    assert label == "unknown"
    assert confidence < 0.5


def test_detect_labels_standard_headers(make_document_model, make_text_span):
    spans = [
        make_text_span(text="Jordan Example", bbox=(72.0, 72.0, 170.0, 90.0), font_size=16.0),
        make_text_span(text="Experience", bbox=(72.0, 100.0, 150.0, 118.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 122.0, 250.0, 132.0)),
        make_text_span(text="Education", bbox=(72.0, 150.0, 150.0, 168.0), font_size=14.0),
        make_text_span(text="State University, B.S. 2020", bbox=(72.0, 172.0, 250.0, 182.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    by_label = {s.label: s for s in sections}
    assert "experience" in by_label
    assert "education" in by_label
    experience_texts = [s.text for s in by_label["experience"].spans]
    assert "Acme Corp, Senior Engineer" in experience_texts
    education_texts = [s.text for s in by_label["education"].spans]
    assert "State University, B.S. 2020" in education_texts


def test_detect_assigns_body_text_to_the_currently_open_section(make_document_model, make_text_span):
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 100.0, 150.0, 118.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 122.0, 250.0, 132.0)),
        make_text_span(text="Led migration of the billing platform.", bbox=(72.0, 138.0, 280.0, 148.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert len(sections) == 1
    assert sections[0].label == "experience"
    texts = [s.text for s in sections[0].spans]
    assert "Acme Corp, Senior Engineer" in texts
    assert "Led migration of the billing platform." in texts


def test_detect_handles_missing_sections_gracefully(make_document_model, make_text_span):
    """No Education header anywhere -- must simply be absent, never a crash
    or a fabricated empty entry."""
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 100.0, 150.0, 118.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 122.0, 250.0, 132.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    labels = {s.label for s in sections}
    assert "education" not in labels
    assert "experience" in labels


def test_detect_content_before_first_header_becomes_leading_contact_section(
    make_document_model, make_text_span
):
    """Contact special case, part 1 (architecture doc Section 4.3): plain
    pre-header content defaults to "contact", not "unknown"."""
    spans = [
        make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 72.0, 220.0, 82.0)),
        make_text_span(text="(555) 010-1234", bbox=(72.0, 92.0, 220.0, 102.0)),
        make_text_span(text="Experience", bbox=(72.0, 120.0, 150.0, 138.0), font_size=14.0),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert sections[0].label == "contact"
    assert sections[0].header_match_reason == "pre_first_header_block"
    leading_texts = [s.text for s in sections[0].spans]
    assert "jordan.example@test.invalid" in leading_texts
    assert "(555) 010-1234" in leading_texts
    assert sections[1].label == "experience"


def test_detect_name_banner_before_first_real_section_folds_into_contact(
    make_document_model, make_text_span
):
    """A large-font NAME BANNER before the first real section is
    structurally header-like (large font) but shouldn't become its own
    stray "unknown" section -- it's almost always part of the name/contact
    block. Folded into the leading contact bucket instead."""
    spans = [
        make_text_span(text="Jordan Example", bbox=(72.0, 72.0, 170.0, 90.0), font_size=16.0),
        make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 92.0, 220.0, 102.0)),
        make_text_span(text="Experience", bbox=(72.0, 120.0, 150.0, 138.0), font_size=14.0),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert sections[0].label == "contact"
    leading_texts = [s.text for s in sections[0].spans]
    assert "Jordan Example" in leading_texts
    assert "jordan.example@test.invalid" in leading_texts
    assert sections[1].label == "experience"
    assert len(sections) == 2


def test_detect_ambiguous_header_after_a_real_section_stays_unknown(make_document_model, make_text_span):
    """The leading-block fold (previous test) only applies before the
    first real section -- an ambiguous header appearing AFTER one is still
    its own "unknown" section, not swept into contact."""
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 92.0, 250.0, 102.0)),
        make_text_span(text="Languages", bbox=(72.0, 120.0, 200.0, 138.0), font_size=14.0),
        make_text_span(text="Fluent in Spanish and English.", bbox=(72.0, 140.0, 260.0, 150.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    by_label = [s.label for s in sections]
    assert by_label == ["experience", "unknown"]


def test_detect_weakly_matched_header_gets_closest_label_at_low_confidence(
    make_document_model, make_text_span
):
    """Tier 3 (architecture doc Section 4.3): a structurally header-like
    line with only a weak gazetteer match is assigned the CLOSEST label,
    not "unknown" -- low confidence is the signal that it's uncertain, not
    an outright rejection. "unknown" is reserved for a match too weak to
    trust at all (see the next test)."""
    spans = [
        make_text_span(text="Career Highlights", bbox=(72.0, 72.0, 200.0, 90.0), font_size=14.0),
        make_text_span(text="Some highlight text.", bbox=(72.0, 92.0, 220.0, 102.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert len(sections) == 1
    assert sections[0].label != "unknown"
    assert sections[0].header_confidence == 0.4
    assert "alias_gazetteer_weak" in sections[0].header_match_reason


def test_detect_genuinely_unrecognized_header_becomes_unknown(make_document_model, make_text_span):
    """A real section must already exist first (see the leading-block-fold
    tests above) -- an unrecognized header before any real section folds
    into contact instead of becoming its own "unknown" section."""
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 92.0, 250.0, 102.0)),
        make_text_span(text="Languages", bbox=(72.0, 120.0, 200.0, 138.0), font_size=14.0),
        make_text_span(text="Fluent in Spanish and English.", bbox=(72.0, 140.0, 220.0, 150.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert len(sections) == 2
    assert sections[1].label == "unknown"
    assert sections[1].header_confidence < 0.5
    assert sections[1].header_match_reason == "no_confident_match"


def test_contact_safety_net_tags_misplaced_email_regardless_of_section(
    make_document_model, make_text_span
):
    """Part 2 of the contact special case: an email mentioned inside an
    unrelated section (e.g. a sidebar footer under Skills) is ALSO tagged
    into "contact" -- Section.spans is a non-exclusive list of references,
    so the span still belongs to its structural home section too."""
    spans = [
        make_text_span(text="Skills", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0),
        make_text_span(text="Python, SQL", bbox=(72.0, 92.0, 220.0, 102.0)),
        make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 112.0, 260.0, 122.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    skills_section = next(s for s in sections if s.label == "skills")
    contact_section = next(s for s in sections if s.label == "contact")
    assert "jordan.example@test.invalid" in [s.text for s in skills_section.spans]
    assert "jordan.example@test.invalid" in [s.text for s in contact_section.spans]


def test_contact_safety_net_is_a_no_op_when_nothing_matches(make_document_model, make_text_span):
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 92.0, 250.0, 102.0)),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert all(s.label != "contact" for s in sections)


def test_embedding_fallback_resolves_a_creative_header_gazetteer_fuzzy_match_cannot(make_text_span):
    """Tier 4: 'Where I have Worked' scores below FUZZY_WEAK_THRESHOLD on
    gazetteer fuzzy match (no shared vocabulary with any alias) but is
    semantically close to "experience" -- exactly the case Tier 4 exists
    for, per the architecture doc's Section 4.3."""
    span = make_text_span(text="Where I have Worked", bbox=(72.0, 72.0, 220.0, 90.0), font_size=14.0)
    line = _group_into_document_lines([span])[0]

    label, confidence, reason = _classify_header_line(line)

    assert label == "experience"
    assert confidence == 0.4
    assert reason.startswith("embedding_fallback:")


def test_embedding_fallback_degrades_gracefully_when_sbert_unavailable(make_text_span, monkeypatch):
    """Section 7's graceful-degradation requirement: if SBERT can't load,
    Tier 4 is skipped -- classification falls back to "unknown" rather than
    raising."""
    monkeypatch.setattr(_LazySemanticModel, "get", classmethod(lambda cls: None))

    span = make_text_span(text="Where I have Worked", bbox=(72.0, 72.0, 220.0, 90.0), font_size=14.0)
    line = _group_into_document_lines([span])[0]

    label, confidence, reason = _classify_header_line(line)

    assert label == "unknown"
    assert reason == "no_confident_match"


def test_detect_section_continues_across_a_page_break_with_no_new_header(
    make_document_model, make_text_span
):
    """Continuation across pages (architecture doc Section 4.3): a section
    with no new header on page 2 just keeps collecting page-2 content,
    since detection walks the already-linearized doc.spans directly with
    no page-boundary special-casing."""
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=14.0, page_num=0),
        make_text_span(
            text="Acme Corp, Senior Engineer", bbox=(72.0, 92.0, 250.0, 102.0), page_num=0
        ),
        # Page break -- no new header, content continues under "experience".
        make_text_span(
            text="Continued: led the Q3 migration project.", bbox=(72.0, 72.0, 280.0, 82.0), page_num=1
        ),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    assert len(sections) == 1
    assert sections[0].label == "experience"
    texts = [s.text for s in sections[0].spans]
    assert "Acme Corp, Senior Engineer" in texts
    assert "Continued: led the Q3 migration project." in texts


def test_detect_handles_two_column_layout_after_layout_reconstruction(
    make_document_model, make_text_span
):
    """Milestone 1's reading order groups an entire column before moving to
    the next (column-major order) -- Section Detection relies on exactly
    that ordering and needs no column-aware special-casing of its own
    beyond the line-grouping helper's page/column boundaries."""
    spans = [
        # Column 0 (sidebar), fully, as M1's layout reconstruction would order it.
        make_text_span(
            text="Skills", bbox=(72.0, 100.0, 130.0, 118.0), font_size=14.0, column_index=0
        ),
        make_text_span(
            text="Python, SQL", bbox=(72.0, 120.0, 200.0, 130.0), column_index=0
        ),
        # Column 1 (main), fully.
        make_text_span(
            text="Experience", bbox=(300.0, 100.0, 380.0, 118.0), font_size=14.0, column_index=1
        ),
        make_text_span(
            text="Acme Corp, Senior Engineer", bbox=(300.0, 120.0, 500.0, 130.0), column_index=1
        ),
    ]
    doc = make_document_model(spans=spans, body_font_size=10.0)

    sections = HeuristicSectionDetector().detect(doc)

    by_label = {s.label: s for s in sections}
    assert "Python, SQL" in [s.text for s in by_label["skills"].spans]
    assert "Acme Corp, Senior Engineer" in [s.text for s in by_label["experience"].spans]
