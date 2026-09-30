from resume_engine.document_model import DocumentModel, ExtractionQuality, TextSpan


def test_text_span_defaults_column_index_to_unresolved():
    span = TextSpan(text="Hi", bbox=(0.0, 0.0, 1.0, 1.0), font_size=10.0, is_bold=False, page_num=0)
    assert span.column_index == 0


def test_text_span_defaults_style_name_to_none():
    span = TextSpan(text="Hi", bbox=(0.0, 0.0, 1.0, 1.0), font_size=10.0, is_bold=False, page_num=0)
    assert span.style_name is None


def test_text_span_carries_docx_style_name():
    span = TextSpan(
        text="Experience",
        bbox=(0.0, 0.0, 1.0, 1.0),
        font_size=14.0,
        is_bold=True,
        page_num=0,
        style_name="Heading 1",
    )
    assert span.style_name == "Heading 1"


def test_text_span_is_frozen():
    span = TextSpan(text="Hi", bbox=(0.0, 0.0, 1.0, 1.0), font_size=10.0, is_bold=False, page_num=0)
    try:
        span.text = "changed"
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass


def test_document_model_defaults():
    doc = DocumentModel()
    assert doc.spans == []
    assert doc.hyperlinks == []
    assert doc.page_count == 0
    assert doc.source_format == "pdf"
    assert doc.body_font_size == 0.0
    assert doc.extraction_quality == ExtractionQuality()
    assert doc.layout_mode is None
    assert doc.layout_confidence == 0.0


def test_extraction_quality_defaults():
    quality = ExtractionQuality()
    assert quality.chars_extracted == 0
    assert quality.span_count == 0
    assert quality.notes == []


def test_document_model_holds_extraction_quality_and_layout_signals():
    doc = DocumentModel(
        body_font_size=10.0,
        extraction_quality=ExtractionQuality(chars_extracted=1200, span_count=54, notes=["low_span_density"]),
        layout_mode="two_column",
        layout_confidence=0.82,
    )
    assert doc.body_font_size == 10.0
    assert doc.extraction_quality.chars_extracted == 1200
    assert doc.layout_mode == "two_column"
    assert doc.layout_confidence == 0.82


def test_document_model_holds_spans_and_hyperlinks(make_text_span):
    doc = DocumentModel(
        spans=[make_text_span(text="Jordan Example")],
        hyperlinks=[("https://linkedin.com/in/example", (0.0, 0.0, 10.0, 10.0), 0)],
        page_count=1,
        source_format="pdf",
    )
    assert doc.spans[0].text == "Jordan Example"
    assert doc.hyperlinks[0][0] == "https://linkedin.com/in/example"
