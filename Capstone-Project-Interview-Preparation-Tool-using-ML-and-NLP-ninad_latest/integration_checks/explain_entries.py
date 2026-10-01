"""Show how the resume engine splits one section into entries, line by line.

    python integration_checks/explain_entries.py <resume.pdf> [section_label ...]

For every line of the chosen sections (default: experience, projects,
education, certifications): its role (content / strong_header / title), the
blank-line gap flag, and whether it starts a new entry. Run from anywhere;
uses the engine in main_cap/cap.
"""
import io
import os
import sys

CAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main_cap", "cap")
sys.path.insert(0, os.path.abspath(CAP))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from resume_engine.extractor import PdfDocxExtractor
from resume_engine.layout import ColumnAwareLayoutReconstructor
from resume_engine.parsers import _entry_clustering as ec
from resume_engine.pipeline import _absorb_repeated_unknown_entries, _group_sections_by_label
from resume_engine.sections import HeuristicSectionDetector

path = sys.argv[1]
wanted = set(sys.argv[2:]) or {"experience", "projects", "education", "certifications"}
fmt = os.path.splitext(path)[1].lstrip(".").lower()
doc = ColumnAwareLayoutReconstructor().reconstruct(PdfDocxExtractor().extract(path, fmt))
sections = _group_sections_by_label(_absorb_repeated_unknown_entries(HeuristicSectionDetector().detect(doc)))
for label, sec in sections.items():
    if label not in wanted:
        continue
    spans = ec.strip_section_header_line(sec.spans, sec.raw_header_text)
    lines = ec._group_into_lines(spans)
    body = ec._local_body_font_size(lines) or doc.body_font_size
    starts = ec._entry_start_flags(lines, body)
    gaps = ec._gap_flags(lines)
    print(f"\n===== section '{sec.label}' (header: {getattr(sec, 'raw_header_text', '')!r}, local body font {body:.1f})")
    for i, line in enumerate(lines):
        role = ec._line_role(line, body, lines[i - 1].text if i else "", lines[i + 1].text if i + 1 < len(lines) else "")
        mark = "START" if starts[i] else "     "
        print(f"{mark} {role:<13} {'gap' if gaps[i] else '   '} b={int(line.is_bold)} f={line.max_font_size:4.1f} | {line.text[:95]}")
