import pymupdf
import pytest

from resume_engine.extractor import ExtractionFailure, PdfDocxExtractor


@pytest.fixture
def simple_pdf(tmp_path):
    path = tmp_path / "resume.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Jordan Example", fontsize=16, fontname="hebo")
    page.insert_text(
        (72, 100),
        "Software Engineer with several years of experience building things.",
        fontsize=10,
        fontname="helv",
    )
    rect = pymupdf.Rect(72, 120, 200, 135)
    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": "https://linkedin.com/in/jordan"})
    doc.save(str(path))
    doc.close()
    return path


def test_extract_pdf_returns_spans_with_text_and_bbox(simple_pdf):
    result = PdfDocxExtractor().extract(str(simple_pdf), "pdf")
    texts = [s.text for s in result.spans]
    assert "Jordan Example" in texts
    assert any("Software Engineer" in t for t in texts)
    for span in result.spans:
        assert span.page_num == 0
        assert len(span.bbox) == 4


def test_extract_pdf_detects_bold_vs_non_bold(simple_pdf):
    result = PdfDocxExtractor().extract(str(simple_pdf), "pdf")
    by_text = {s.text: s for s in result.spans}
    assert by_text["Jordan Example"].is_bold is True
    assert by_text["Software Engineer with several years of experience building things."].is_bold is False


def test_extract_pdf_captures_hyperlinks(simple_pdf):
    result = PdfDocxExtractor().extract(str(simple_pdf), "pdf")
    assert len(result.hyperlinks) == 1
    url, bbox, page_num = result.hyperlinks[0]
    assert url == "https://linkedin.com/in/jordan"
    assert page_num == 0
    assert len(bbox) == 4


def test_extract_pdf_computes_extraction_quality_and_body_font_size(simple_pdf):
    result = PdfDocxExtractor().extract(str(simple_pdf), "pdf")
    assert result.extraction_quality.span_count == 2
    assert result.extraction_quality.chars_extracted == len("Jordan Example") + len(
        "Software Engineer with several years of experience building things."
    )
    # Only one span at 10.0 and one at 16.0 -- both equally "most common";
    # Counter.most_common picks insertion order on ties, so just assert it's
    # one of the two real font sizes present, not a made-up default.
    assert result.body_font_size in (10.0, 16.0)


def test_extract_pdf_sets_page_count_and_source_format(simple_pdf):
    result = PdfDocxExtractor().extract(str(simple_pdf), "pdf")
    assert result.page_count == 1
    assert result.source_format == "pdf"


def test_extract_raises_extraction_failure_for_missing_file():
    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract("does-not-exist.pdf", "pdf")


def test_extract_raises_extraction_failure_for_near_empty_pdf(tmp_path):
    path = tmp_path / "sparse.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Hi", fontsize=10, fontname="helv")
    doc.save(str(path))
    doc.close()

    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract(str(path), "pdf")


def test_extract_raises_extraction_failure_for_corrupt_pdf(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a real pdf file")

    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract(str(path), "pdf")


def test_extract_raises_extraction_failure_for_unsupported_format(simple_pdf):
    # "txt" became a supported source_format alongside the production
    # cutover -- "doc" (legacy binary Word format) remains genuinely
    # unsupported, so it's the unsupported-format case now.
    with pytest.raises(ExtractionFailure):
        PdfDocxExtractor().extract(str(simple_pdf), "doc")
