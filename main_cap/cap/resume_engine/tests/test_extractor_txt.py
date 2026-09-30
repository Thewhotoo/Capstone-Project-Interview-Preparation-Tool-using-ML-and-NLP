import pytest

from resume_engine.extractor import ExtractionFailure, PdfDocxExtractor


@pytest.fixture
def plain_txt(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text(
        "Jordan Example\n"
        "jordan@example.com | 555-123-4567\n\n"
        "EXPERIENCE\n"
        "Software Engineer, Acme Corp\n"
        "Jan 2021 - Present\n"
        "Built REST APIs using Python and Redis, improving latency by 30%.\n\n"
        "PROJECTS\n"
        "Resume Parser\n"
        "Built a resume parsing pipeline using Python, spaCy, and FastAPI.\n",
        encoding="utf-8",
    )
    return path


def test_extract_txt_returns_spans_with_text_and_bbox(plain_txt):
    result = PdfDocxExtractor().extract(str(plain_txt), "txt")
    texts = [s.text for s in result.spans]
    assert "Jordan Example" in texts
    assert any("Software Engineer" in t for t in texts)
    for span in result.spans:
        assert span.page_num == 0
        assert len(span.bbox) == 4
        assert span.is_bold is False
        assert span.style_name is None


def test_extract_txt_skips_blank_lines(plain_txt):
    result = PdfDocxExtractor().extract(str(plain_txt), "txt")
    assert all(s.text.strip() for s in result.spans)


def test_extract_txt_computes_extraction_quality_and_source_format(plain_txt):
    result = PdfDocxExtractor().extract(str(plain_txt), "txt")
    assert result.source_format == "txt"
    assert result.extraction_quality.chars_extracted > 0
    assert result.extraction_quality.span_count == len(result.spans)
    assert result.body_font_size > 0


def test_extract_txt_raises_extraction_failure_for_near_empty_file(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("hi", encoding="utf-8")
    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract(str(path), "txt")


def test_extract_txt_raises_extraction_failure_for_missing_file(tmp_path):
    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract(str(tmp_path / "does_not_exist.txt"), "txt")
