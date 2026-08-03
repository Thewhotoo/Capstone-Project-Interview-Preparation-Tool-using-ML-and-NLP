"""
Document Extraction — Stage 1. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.1.

`PdfDocxExtractor` is the concrete `interfaces.DocumentExtractor`
implementation. PDF extraction (pymupdf dict-mode spans + hyperlinks) is
implemented here; DOCX extraction lands in a later step of this same
milestone.
"""

from __future__ import annotations

import os
from collections import Counter

from resume_engine.document_model import DocumentModel, ExtractionQuality, TextSpan
from resume_engine.pipeline_trace import PipelineTrace

# Matches the floor already used at app.py's classify-resume step, for
# continuity with today's pipeline rather than inventing a new number.
MIN_EXTRACTED_CHARS = 50

# PyMuPDF span "flags" bitfield: bit 4 (value 16) is bold.
PDF_BOLD_FLAG = 1 << 4

# python-docx exposes no real x/y coordinates, so a synthetic geometry is
# assigned that mirrors a US-Letter PDF page closely enough for Layout
# Reconstruction's gap-analysis (layout.py) to run unmodified against DOCX
# output -- these constants exist so that geometry is documented and
# reviewable in one place, not scattered magic numbers.
DOCX_PAGE_WIDTH = 612.0
DOCX_LEFT_MARGIN = 72.0
DOCX_TOP_MARGIN = 72.0
DOCX_USABLE_WIDTH = DOCX_PAGE_WIDTH - 2 * DOCX_LEFT_MARGIN
DOCX_LINE_HEIGHT = 14.0
DOCX_DEFAULT_FONT_SIZE = 11.0


class ExtractionFailure(Exception):
    """Raised when a file cannot be usefully extracted: a scanned/image-only
    PDF, a corrupt or password-protected file, or a file whose total
    extracted text falls below MIN_EXTRACTED_CHARS. Mirrors today's
    ValueError at candidate_profile_generator.py:258-262, as a purpose-built,
    catchable type rather than a bare ValueError or a raw library exception
    (see docs/architecture/ResumeIntelligenceEngine.md Section 4.1)."""


class PdfDocxExtractor:
    """Concrete `interfaces.DocumentExtractor` implementation."""

    def extract(
        self, file_path: str, source_format: str, trace: PipelineTrace | None = None
    ) -> DocumentModel:
        if not os.path.isfile(file_path):
            raise ExtractionFailure(f"Resume file not found: {file_path}")

        if source_format == "pdf":
            doc = self._extract_pdf(file_path)
        elif source_format == "docx":
            doc = self._extract_docx(file_path)
        else:
            raise ExtractionFailure(f"Unsupported source_format: {source_format!r}")

        if doc.extraction_quality.chars_extracted < MIN_EXTRACTED_CHARS:
            raise ExtractionFailure(
                f"Could not extract enough text from {file_path} "
                f"({doc.extraction_quality.chars_extracted} chars extracted, "
                f"minimum {MIN_EXTRACTED_CHARS}). The file may be image-based "
                "(scanned) or otherwise unreadable."
            )
        return doc

    def _extract_pdf(self, file_path: str) -> DocumentModel:
        import pymupdf

        try:
            pdf = pymupdf.open(file_path)
        except Exception as exc:
            raise ExtractionFailure(f"Could not open PDF {file_path}: {exc}") from exc

        try:
            if pdf.needs_pass:
                raise ExtractionFailure(f"PDF {file_path} is password-protected.")

            spans: list[TextSpan] = []
            hyperlinks: list[tuple[str, tuple[float, float, float, float], int]] = []
            font_sizes: Counter = Counter()

            for page_num in range(len(pdf)):
                page = pdf[page_num]

                page_dict = page.get_text("dict")
                for block in page_dict.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "")
                            if not text:
                                continue
                            font_size = float(span.get("size", 0.0))
                            flags = span.get("flags", 0)
                            font_name = span.get("font", "")
                            is_bold = bool(flags & PDF_BOLD_FLAG) or "bold" in font_name.lower()
                            bbox = tuple(span.get("bbox", (0.0, 0.0, 0.0, 0.0)))
                            spans.append(
                                TextSpan(
                                    text=text,
                                    bbox=bbox,
                                    font_size=font_size,
                                    is_bold=is_bold,
                                    page_num=page_num,
                                )
                            )
                            font_sizes[round(font_size, 1)] += 1

                for link in page.get_links():
                    if link.get("kind") != pymupdf.LINK_URI:
                        continue
                    url = link.get("uri", "")
                    if not url:
                        continue
                    rect = link.get("from")
                    link_bbox = (rect.x0, rect.y0, rect.x1, rect.y1) if rect else (0.0, 0.0, 0.0, 0.0)
                    hyperlinks.append((url, link_bbox, page_num))

            page_count = len(pdf)
        finally:
            pdf.close()

        chars_extracted = sum(len(s.text) for s in spans)
        body_font_size = font_sizes.most_common(1)[0][0] if font_sizes else 0.0

        return DocumentModel(
            spans=spans,
            hyperlinks=hyperlinks,
            page_count=page_count,
            source_format="pdf",
            body_font_size=body_font_size,
            extraction_quality=ExtractionQuality(
                chars_extracted=chars_extracted,
                span_count=len(spans),
            ),
        )

    def _extract_docx(self, file_path: str) -> DocumentModel:
        try:
            import docx
            from docx.oxml.ns import qn
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            from docx.text.run import Run
        except ImportError as exc:
            raise RuntimeError(f"python-docx is required for DOCX extraction: {exc}") from exc

        try:
            document = docx.Document(file_path)
        except Exception as exc:
            raise ExtractionFailure(f"Could not open DOCX {file_path}: {exc}") from exc

        spans: list[TextSpan] = []
        hyperlinks: list[tuple[str, tuple[float, float, float, float], int]] = []
        font_sizes: Counter = Counter()
        notes: list[str] = []
        cursor = {"y": DOCX_TOP_MARGIN, "page_num": 0}

        def resolve_font_size(run, paragraph) -> float:
            if run.font.size is not None:
                return run.font.size.pt
            if paragraph.style is not None and paragraph.style.font.size is not None:
                return paragraph.style.font.size.pt
            return DOCX_DEFAULT_FONT_SIZE

        def has_page_break(element) -> bool:
            return any(br.get(qn("w:type")) == "page" for br in element.findall(qn("w:br")))

        def emit_run(run, paragraph, x0: float, x1: float) -> bool:
            text = run.text
            if not text:
                return False
            font_size = resolve_font_size(run, paragraph)
            style_name = paragraph.style.name if paragraph.style is not None else None
            spans.append(
                TextSpan(
                    text=text,
                    bbox=(x0, cursor["y"], x1, cursor["y"] + DOCX_LINE_HEIGHT),
                    font_size=font_size,
                    is_bold=bool(run.bold),
                    page_num=cursor["page_num"],
                    style_name=style_name,
                )
            )
            font_sizes[round(font_size, 1)] += 1
            return True

        def advance_page_if_break(element) -> None:
            if has_page_break(element):
                cursor["page_num"] += 1
                cursor["y"] = DOCX_TOP_MARGIN

        def emit_paragraph(paragraph, x0: float, x1: float) -> None:
            wrote_any = False
            for child in paragraph._p:
                if child.tag == qn("w:r"):
                    run = Run(child, paragraph)
                    wrote_any = emit_run(run, paragraph, x0, x1) or wrote_any
                    advance_page_if_break(child)
                elif child.tag == qn("w:hyperlink"):
                    r_id = child.get(qn("r:id"))
                    url = None
                    if r_id is not None:
                        try:
                            url = paragraph.part.rels[r_id].target_ref
                        except KeyError:
                            url = None
                    for run_el in child.findall(qn("w:r")):
                        run = Run(run_el, paragraph)
                        wrote_any = emit_run(run, paragraph, x0, x1) or wrote_any
                        advance_page_if_break(run_el)
                    if url:
                        hyperlinks.append(
                            (url, (x0, cursor["y"], x1, cursor["y"] + DOCX_LINE_HEIGHT), cursor["page_num"])
                        )
            if wrote_any:
                cursor["y"] += DOCX_LINE_HEIGHT

        def emit_table(table) -> None:
            # A table is treated as a layout container (a common way to hand-
            # build a two-column sidebar resume in Word), not tabular data --
            # a documented, scope-limited heuristic (architecture doc Section
            # 4.1/4.2; a genuine data table would be mis-treated the same
            # way). Each cell becomes a synthetic column; Layout
            # Reconstruction (layout.py) still does the actual column_index
            # assignment from the resulting geometry, uniformly with PDF.
            num_cols = max((len(row.cells) for row in table.rows), default=0)
            if num_cols == 0:
                return
            if num_cols > 1:
                notes.append(f"docx_table_layout_detected:{num_cols}_columns")
            cell_width = DOCX_USABLE_WIDTH / num_cols
            col_y: dict[int, float] = {}
            seen_cells: set[int] = set()
            for row in table.rows:
                for col_index, cell in enumerate(row.cells):
                    if id(cell._tc) in seen_cells:
                        continue
                    seen_cells.add(id(cell._tc))
                    x0 = DOCX_LEFT_MARGIN + col_index * cell_width
                    x1 = x0 + cell_width
                    cursor["y"] = col_y.get(col_index, DOCX_TOP_MARGIN)
                    for paragraph in cell.paragraphs:
                        emit_paragraph(paragraph, x0, x1)
                    col_y[col_index] = cursor["y"]

        body_x0 = DOCX_LEFT_MARGIN
        body_x1 = DOCX_LEFT_MARGIN + DOCX_USABLE_WIDTH
        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                emit_paragraph(Paragraph(child, document), body_x0, body_x1)
            elif child.tag == qn("w:tbl"):
                emit_table(Table(child, document))

        page_count = cursor["page_num"] + 1
        chars_extracted = sum(len(s.text) for s in spans)
        body_font_size = font_sizes.most_common(1)[0][0] if font_sizes else 0.0

        return DocumentModel(
            spans=spans,
            hyperlinks=hyperlinks,
            page_count=page_count,
            source_format="docx",
            body_font_size=body_font_size,
            extraction_quality=ExtractionQuality(
                chars_extracted=chars_extracted,
                span_count=len(spans),
                notes=notes,
            ),
        )
