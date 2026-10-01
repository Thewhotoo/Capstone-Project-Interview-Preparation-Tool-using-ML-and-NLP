"""Shared fixture builders for resume_engine's test suite."""

from __future__ import annotations

import pytest

from resume_engine.document_model import DocumentModel, TextSpan
from resume_engine.sections import Section


@pytest.fixture
def make_text_span():
    def _make(
        text="Sample",
        bbox=(0.0, 0.0, 100.0, 10.0),
        font_size=10.0,
        is_bold=False,
        page_num=0,
        column_index=0,
        style_name=None,
    ):
        return TextSpan(
            text=text,
            bbox=bbox,
            font_size=font_size,
            is_bold=is_bold,
            page_num=page_num,
            column_index=column_index,
            style_name=style_name,
        )

    return _make


@pytest.fixture
def make_document_model(make_text_span):
    def _make(spans=None, hyperlinks=None, page_count=1, source_format="pdf", body_font_size=10.0):
        return DocumentModel(
            spans=spans if spans is not None else [make_text_span()],
            hyperlinks=hyperlinks if hyperlinks is not None else [],
            page_count=page_count,
            source_format=source_format,
            body_font_size=body_font_size,
        )

    return _make


@pytest.fixture
def make_section(make_text_span):
    def _make(
        label="experience",
        raw_header_text="Experience",
        spans=None,
        header_confidence=0.9,
        header_match_reason="alias_gazetteer_exact",
    ):
        return Section(
            label=label,
            raw_header_text=raw_header_text,
            spans=spans if spans is not None else [make_text_span()],
            header_confidence=header_confidence,
            header_match_reason=header_match_reason,
        )

    return _make
