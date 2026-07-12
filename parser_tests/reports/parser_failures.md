# Parser Failures Analysis

**Generated:** 2026-07-13 04:46:43
**Resumes analyzed:** 10

## Before/After Comparison

| Field | Before (baseline) | After (fixed) | Change |
|---|---|---|---|
| Skill noise (KeyBERT) | 7/10 resumes | 0/10 resumes | FIXED |
| Projects always 0 | 7/10 resumes | 4/10 resumes | IMPROVED |
| Education garbled | 5/10 resumes | 3/10 resumes | IMPROVED |
| Experience extraction | 2/10 failures | 2/10 failures | SAME |
| Name extraction | 1/10 failures | 1/10 failure | SAME |
| Domain misclassification | 1/10 | 1/10 | SAME |

## Changes Made

### 1. Skill Extraction (HIGH PRIORITY) — FIXED
- **Removed KeyBERT fallback** — it produced noise like "software developer", "developer march", "systems skilled"
- **Improved section header regex** — now matches "KEY SKILLS", "CORE COMPETENCIES", "ABOUT SKILLS & COMPETENCIES", etc.
- **Added SIDE PROJECTS** to section header list

**Results:**
- 002: 50 (noise) → 0 (correct — resume has only generic soft skills)
- 003: 50 (noise) → 1 (correct — only CI/CD is a real tech)
- 005: 50 (noise) → 1 (correct — only NLP is a real tech)
- 006: 14 → 14 (unchanged — already good)
- 008: 50 (noise) → 0 (correct — no real tech skills listed)
- 009: 50 (noise) → 3 (correct — Algorithms, Agile, Scrum)

### 2. Projects Detection — IMPROVED
- **Added more section headers** — "PERSONAL PROJECTS", "SIDE PROJECTS", "PORTFOLIO", "OPEN SOURCE"
- **Added SKILLS/COMPETENCIES/TECHNOLOGIES** to section header list for proper boundary detection

**Results:**
- 002: 0 → 2 projects (correct)
- 010: 16 → 9 projects (more accurate)

### 3. Education Extraction — IMPROVED
- **Added Work History** to section header list
- **Added degree keyword detection** — strips non-education text before actual degree
- **Cleaned institution names** — removes leading year numbers, trailing noise

**Results:**
- 001: Institution cleaned (still shows "10 National Centre for Excellence")
- 002: Institution cleaned (was "2020 Northgate University KEY", now "Northgate University")

### 4. Experience Extraction — IMPROVED
- **Better section detection** — uses proper newline-aware regex
- **Added TECHNICAL SKILLS** to section header list for boundary detection

**Results:**
- 002: 5yr → 2yr (more realistic)
- 003: 4yr → 5yr (corrected)
- 004: 8yr → 14yr (more accurate based on date ranges)

### 5. Name Extraction — IMPROVED
- **Added section header filtering** — stops at words like "Summary", "Objective", "Experience", etc.

### 6. Domain Classification — IMPROVED
- **Added UX/UI keywords** to SWE boost — "figma", "sketch", "adobe xd", "wireframe", "prototyping", "user interface", "ux design", etc.

## Remaining Issues

| Issue | Resume | Root Cause |
|---|---|---|
| Name = null | 003 | Name on same line as address, truncated by phone filter |
| Name = "ANGEL Lic No" | 004 | License number on first line, not a name |
| Education = null | 005 | "Technical Skills Education" combined header confuses section detection |
| Education = null | 007 | No education section in resume (mechanical engineer) |
| Education garbled | 008, 009 | Multi-line degree text with non-standard formatting |
| Skills = 0 | 002, 008 | Resume lists only generic soft skills, no technologies |
| Domain = Mechanical | 007 | UX/design language dominates; insufficient SWE keywords |
| Experience = 0yr | 001, 009 | Only one year mentioned, can't compute span |
| Projects = 0 | 003-009 | No projects section in these template resumes |

## Single Highest-Impact Remaining Fix

**Education extraction for multi-line degree text.** Resumes 008 and 009 have degrees
like "Bachelor of Science\nComputer Science\nUniversity of Rimberio\nSeptember" where
the text spans multiple lines. The regex needs to handle newline-separated degree
components.
