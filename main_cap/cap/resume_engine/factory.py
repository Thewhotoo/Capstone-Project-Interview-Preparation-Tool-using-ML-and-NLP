"""
Composition root — the ONLY module in resume_engine allowed to import
concrete stage implementations and wire them together. `pipeline.py`
depends solely on interfaces (design-review item 1); this module is where
those interfaces get bound to real objects.

Milestone 0: every concrete implementation wired here started as a
structural stub whose methods raise NotImplementedError (see each stage
module's docstring for which milestone implements it for real). As of
Milestone 6, all eight stages are real: the six entity parsers (Milestone
3: `ContactParser`/`ExperienceParser`/`ProjectParser`; Milestone 5:
`EducationParser`/`SkillsParser`/`CertificationParser`), Cross-Reference
(Milestone 4: interview-seed synthesis; Milestone 5: demonstrated-skills
tagging), Normalization, Validation, and Confidence Scoring (all three
Milestone 6). `default_pipeline().run(...)` now completes end-to-end
without raising -- see `resume_engine/tests/test_pipeline_end_to_end.py`.
Not yet wired into the live application (`app.py` still calls Gemini) --
that cutover is Milestone 7.
"""

from __future__ import annotations

from resume_engine.confidence import DefaultConfidenceEngine
from resume_engine.cross_reference import DefaultCrossReferenceEngine
from resume_engine.document_model import DocumentModel
from resume_engine.extractor import PdfDocxExtractor
from resume_engine.layout import ColumnAwareLayoutReconstructor
from resume_engine.normalization import DefaultNormalizer
from resume_engine.parsers.certification_parser import CertificationParser
from resume_engine.parsers.contact_parser import ContactParser
from resume_engine.parsers.education_parser import EducationParser
from resume_engine.parsers.experience_parser import ExperienceParser
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.parsers.skills_parser import SkillsParser
from resume_engine.pipeline import ResumePipeline
from resume_engine.registry import ParserRegistry
from resume_engine.sections import HeuristicSectionDetector
from resume_engine.validation import DefaultValidationEngine


def default_parser_registry() -> ParserRegistry:
    """Builds a ParserRegistry with all six entity parsers registered.

    The three real Milestone 3 parsers (`ContactParser`, `ExperienceParser`,
    `ProjectParser`) are registered WITH conformance checking (an empty
    `sample_sections={}` + a spans-less `DocumentModel`) so a non-conformant
    parser is caught here, at registration, rather than silently reaching
    production. The sample input is deliberately trivial/empty, not a
    realistic resume -- `check_parser_conformance` only verifies the SHAPE
    contract (right attributes, a real `ParserResult`, matching
    entities/confidences counts, non-empty reasons), the same lightweight
    scope `evaluator.py`'s `check_conformance` has for evaluators; it is
    not, and was never meant to be, an extraction-correctness test (that's
    resume_engine/tests/test_contact_parser.py and friends). Using each
    parser's own fast "missing section" path for this also avoids eagerly
    loading ProjectParser's KeyBERT/SBERT models on every call to this
    function -- a real cost that a richer sample input would have paid on
    every pipeline construction, not just once.

    `EducationParser`/`SkillsParser`/`CertificationParser` are real as of
    Milestone 5 and are registered the same way, with the same empty-
    sample rationale."""
    registry = ParserRegistry()

    empty_sections: dict = {}
    empty_doc = DocumentModel(spans=[], body_font_size=10.0)
    for parser in (
        ContactParser(),
        ExperienceParser(),
        ProjectParser(),
        EducationParser(),
        SkillsParser(),
        CertificationParser(),
    ):
        registry.register_parser(parser, sample_sections=empty_sections, sample_doc=empty_doc)

    return registry


def default_pipeline() -> ResumePipeline:
    """Wires the current (Milestone 0: all-stub) concrete implementations
    into a ResumePipeline. This is the only place production code should
    construct a ResumePipeline from — everywhere else depends on the
    interfaces only (resume_engine.interfaces)."""
    return ResumePipeline(
        extractor=PdfDocxExtractor(),
        layout_reconstructor=ColumnAwareLayoutReconstructor(),
        section_detector=HeuristicSectionDetector(),
        parser_runner=default_parser_registry(),
        cross_reference_engine=DefaultCrossReferenceEngine(),
        normalizer=DefaultNormalizer(),
        validation_engine=DefaultValidationEngine(),
        confidence_engine=DefaultConfidenceEngine(),
    )
