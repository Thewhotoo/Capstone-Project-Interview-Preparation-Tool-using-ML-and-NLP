"""
Location gazetteer — Milestone 3 (Entity Parsing). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

A small, deliberately non-exhaustive gazetteer of major cities/states/
countries for `ContactParser.location` -- a display-only field with no
downstream functional consumer (Section 1.2), so gazetteer-only fuzzy
matching is the right amount of rigor; the SBERT-corroboration fallback the
architecture doc mentions for this field is deferred past Milestone 3
rather than adding a second ML-dependent code path to the lightest-weight
parser for a cosmetic field.
"""

from __future__ import annotations

LOCATIONS: tuple[str, ...] = (
    # Major US cities/metros
    "New York", "San Francisco", "Los Angeles", "Chicago", "Seattle",
    "Austin", "Boston", "Denver", "Atlanta", "Portland", "San Diego",
    "Washington DC", "Dallas", "Houston", "Philadelphia", "Miami",
    "San Jose", "Minneapolis", "Phoenix", "Detroit",
    # States
    "California", "Texas", "Massachusetts",
    "Illinois", "Colorado", "Georgia", "Oregon", "Florida",
    # Countries / international hubs
    "United States", "USA", "Canada", "United Kingdom", "London",
    "Toronto", "Vancouver", "India", "Bangalore", "Mumbai", "Delhi",
    "Germany", "Berlin", "France", "Paris", "Singapore", "Australia",
    "Sydney", "Remote",
)
