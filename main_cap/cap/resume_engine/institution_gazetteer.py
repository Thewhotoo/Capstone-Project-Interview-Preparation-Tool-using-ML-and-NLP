"""
Institution gazetteer — Milestone 5 (Entity Parsing continued). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

A small, deliberately non-exhaustive confidence booster for
`EducationParser.institution` -- an unrecognized institution name is still
accepted at lower confidence (a closed-world list would be actively wrong
for a global user base, same reasoning as `location_gazetteer.py`). The
generic `_INSTITUTION_KEYWORDS` regex in `education_parser.py` (not here)
is what actually finds the institution *line*; this gazetteer only decides
whether that line earns the higher, gazetteer-matched confidence tier.
"""

from __future__ import annotations

INSTITUTIONS: tuple[str, ...] = (
    "Massachusetts Institute of Technology", "Stanford University",
    "Harvard University", "University of California, Berkeley",
    "Carnegie Mellon University", "California Institute of Technology",
    "University of Michigan", "University of Illinois",
    "Georgia Institute of Technology", "University of Texas at Austin",
    "University of Washington", "Cornell University", "Princeton University",
    "Columbia University", "University of Pennsylvania", "Yale University",
    "University of Toronto", "University of Waterloo", "McGill University",
    "Indian Institute of Technology", "IIT Bombay", "IIT Delhi",
    "Indian Institute of Science", "National University of Singapore",
    "University of Oxford", "University of Cambridge", "Imperial College London",
    "ETH Zurich", "University of Melbourne", "University of Sydney",
)
