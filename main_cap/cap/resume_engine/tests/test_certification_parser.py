from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.certification_parser import CertificationParser


def _certifications_section(make_section, make_text_span):
    spans = [
        make_text_span(text="Certifications", bbox=(72.0, 72.0, 200.0, 90.0), font_size=13.0, is_bold=True),
        make_text_span(text="AWS Certified Solutions Architect", bbox=(72.0, 100.0, 300.0, 110.0)),
        make_text_span(text="PMP", bbox=(72.0, 117.0, 150.0, 127.0)),
    ]
    return make_section(
        label="certifications", raw_header_text="Certifications", spans=spans, header_confidence=0.9
    )


def test_certification_parser_extracts_one_entity_per_line(make_section, make_text_span, make_document_model):
    section = _certifications_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = CertificationParser().parse({"certifications": section}, doc)

    assert result.entities == ["AWS Certified Solutions Architect", "PMP"]
    assert len(result.confidences) == 2


def test_certification_parser_normalizes_near_variant_via_gazetteer(
    make_section, make_text_span, make_document_model
):
    header = make_text_span(text="Certifications", bbox=(72.0, 72.0, 200.0, 90.0), is_bold=True)
    body = make_text_span(
        text="AWS Certified Solutions Architect - Associate", bbox=(72.0, 100.0, 350.0, 110.0)
    )
    section = make_section(
        label="certifications", raw_header_text="Certifications", spans=[header, body], header_confidence=0.9
    )
    doc = make_document_model(spans=[header, body], body_font_size=10.0)

    result = CertificationParser().parse({"certifications": section}, doc)

    assert result.entities == ["AWS Certified Solutions Architect Associate"]
    assert "certification_gazetteer_match" in result.confidences[0].reasons[1]


def test_certification_parser_dedupes_case_insensitively(make_section, make_text_span, make_document_model):
    header = make_text_span(text="Certifications", bbox=(72.0, 72.0, 200.0, 90.0), is_bold=True)
    body1 = make_text_span(text="PMP", bbox=(72.0, 100.0, 150.0, 110.0))
    body2 = make_text_span(text="pmp", bbox=(72.0, 117.0, 150.0, 127.0))
    section = make_section(
        label="certifications", raw_header_text="Certifications", spans=[header, body1, body2],
        header_confidence=0.9,
    )
    doc = make_document_model(spans=[header, body1, body2], body_font_size=10.0)

    result = CertificationParser().parse({"certifications": section}, doc)

    assert result.entities == ["PMP"]


def test_certification_parser_sweeps_skills_section_for_stray_mentions(
    make_section, make_text_span, make_document_model
):
    skills_spans = [make_text_span(text="AWS Certified Solutions Architect, Python", bbox=(72.0, 72.0, 400.0, 82.0))]
    skills_section = make_section(label="skills", raw_header_text="Skills", spans=skills_spans, header_confidence=0.9)
    doc = make_document_model(spans=skills_spans, body_font_size=10.0)

    result = CertificationParser().parse({"skills": skills_section}, doc)

    assert "AWS Certified Solutions Architect" in result.entities
    reasons = result.confidences[result.entities.index("AWS Certified Solutions Architect")].reasons
    assert any("stray_mention_sweep" in r for r in reasons)


def test_certification_parser_stray_sweep_does_not_duplicate_explicit_section_entry(
    make_section, make_text_span, make_document_model
):
    cert_spans = [
        make_text_span(text="Certifications", bbox=(72.0, 72.0, 200.0, 90.0), is_bold=True),
        make_text_span(text="PMP", bbox=(72.0, 100.0, 150.0, 110.0)),
    ]
    cert_section = make_section(
        label="certifications", raw_header_text="Certifications", spans=cert_spans, header_confidence=0.9
    )
    skills_spans = [make_text_span(text="PMP certified, Python", bbox=(72.0, 200.0, 400.0, 210.0))]
    skills_section = make_section(label="skills", raw_header_text="Skills", spans=skills_spans, header_confidence=0.9)
    doc = make_document_model(spans=cert_spans + skills_spans, body_font_size=10.0)

    result = CertificationParser().parse({"certifications": cert_section, "skills": skills_section}, doc)

    assert result.entities.count("PMP") == 1


def test_certification_parser_returns_empty_when_no_section_and_no_stray_mentions(make_document_model):
    doc = make_document_model(spans=[])
    result = CertificationParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_certification_parser_conforms_to_entity_parser_protocol(
    make_section, make_text_span, make_document_model
):
    section = _certifications_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)
    check_parser_conformance(CertificationParser(), {"certifications": section}, doc)
