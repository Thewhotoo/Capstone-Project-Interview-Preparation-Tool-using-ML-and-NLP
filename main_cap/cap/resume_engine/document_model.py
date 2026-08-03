"""
Document Model — the output type of Stage 1 (Document Extraction) and the
input every later stage reads from, either directly or via the Section
objects Stage 3 carves out of it.

See docs/architecture/ResumeIntelligenceEngine.md Section 3.1 and Section
4.1. No extraction logic lives here — only the data shape extraction
produces (extractor.py, Milestone 1, is what actually populates these).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class TextSpan:
    """One styled, positioned run of text, as read off a PDF/DOCX page."""

    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    font_size: float
    is_bold: bool
    page_num: int
    column_index: int = 0  # set by Layout Reconstruction (layout.py, Milestone 1); 0 = unresolved
    style_name: str | None = None  # DOCX paragraph style name (e.g. "Heading 1"); always None for PDF


@dataclass
class ExtractionQuality:
    """Document-level signal from Stage 1 (extractor.py, Milestone 1) that
    later stages read to temper their own confidence when extraction was
    sparse or degraded, rather than each stage re-deriving this itself.
    See docs/architecture/ResumeIntelligenceEngine.md Section 4.1."""

    chars_extracted: int = 0
    span_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class DocumentModel:
    """Styled, positioned text for an entire resume document, plus
    hyperlinks PyMuPDF/python-docx expose that plain-text extraction would
    otherwise drop (e.g. a "LinkedIn" label hyperlinked to a URL with no
    visible URL text)."""

    spans: list[TextSpan] = field(default_factory=list)
    hyperlinks: list[tuple[str, tuple[float, float, float, float], int]] = field(default_factory=list)
    page_count: int = 0
    source_format: Literal["pdf", "docx"] = "pdf"
    body_font_size: float = 0.0  # modal font size across all spans; Section Detection's baseline (Milestone 2)
    extraction_quality: ExtractionQuality = field(default_factory=ExtractionQuality)
    layout_mode: Literal["single_column", "two_column", "ambiguous"] | None = None  # set by Layout Reconstruction
    layout_confidence: float = 0.0  # set by Layout Reconstruction
