"""
Shadow Mode batch runner — Milestone 7, Phase 3/4 tooling. See
`shadow_mode.py`'s module docstring for the hard constraints this whole
package respects (never a runtime path, never treats Gemini as ground
truth).

This is the "comparison tooling" deliverable for inspecting where the
deterministic engine differs from Gemini ACROSS a batch of resumes, not
just one at a time -- the mechanism a human needs to actually validate
the engine before flipping the default backend (Phase 4). Requires a real
`GEMINI_API_KEY` and a directory of real (or realistic) resume files to
be useful; NOT runnable in an environment without Gemini access, which is
exactly why this module exists as a standalone, human-invoked script
rather than something a test suite executes automatically.

Usage (from `main_cap/cap`):
    python -m resume_engine.devtools.shadow_mode_batch --dir path/to/resumes --report out.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from resume_engine.devtools.shadow_mode import ShadowComparisonResult, run_shadow_comparison

_SUPPORTED_SUFFIXES = (".pdf", ".docx")


def _extract_text(resume_path: Path) -> str:
    """Mirrors app.py's own extraction branch (`classify_resume`) exactly,
    so the Gemini side of the comparison sees the identical input the
    live application would give it."""
    if resume_path.suffix.lower() == ".pdf":
        from candidate_profile_generator import extract_text_from_pdf
        return extract_text_from_pdf(str(resume_path))
    from src.parser import extract_text
    return extract_text(str(resume_path))


def run_batch_shadow_comparison(resume_dir: str) -> dict[str, ShadowComparisonResult]:
    """Runs `run_shadow_comparison` over every supported resume file in
    `resume_dir` (non-recursive). Returns {filename: ShadowComparisonResult}.
    A single resume's failure (e.g. a corrupt file) is recorded as an
    error entry, not allowed to abort the whole batch -- one bad fixture
    shouldn't block reviewing the other 49."""
    results: dict[str, ShadowComparisonResult] = {}
    directory = Path(resume_dir)
    for resume_path in sorted(directory.iterdir()):
        if resume_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        try:
            text = _extract_text(resume_path)
            results[resume_path.name] = run_shadow_comparison(str(resume_path), text)
        except Exception as e:  # noqa: BLE001 -- deliberately broad: one bad fixture must not abort the batch
            results[resume_path.name] = e
    return results


def aggregate_category_counts(results: dict[str, ShadowComparisonResult]) -> dict[str, int]:
    """Sums discrepancy categories across every successfully-compared
    resume in the batch -- the top-line number a human reviewer looks at
    first ("how many missing_in_engine across the whole batch")."""
    totals: dict[str, int] = {}
    for result in results.values():
        if not isinstance(result, ShadowComparisonResult):
            continue
        for category, count in result.category_counts().items():
            totals[category] = totals.get(category, 0) + count
    return totals


def write_report(results: dict[str, ShadowComparisonResult], report_path: str) -> None:
    """Writes a human-reviewable JSON report -- one entry per resume, with
    every discrepancy's field/category/gemini_value/engine_value, plus a
    batch-level category summary. Never auto-resolves anything; this is
    exclusively for a human to read and decide from."""
    report = {"summary": aggregate_category_counts(results), "resumes": {}}
    for filename, result in results.items():
        if isinstance(result, Exception):
            report["resumes"][filename] = {"error": str(result)}
        else:
            report["resumes"][filename] = {
                "category_counts": result.category_counts(),
                "discrepancies": [asdict(d) for d in result.discrepancies],
            }
    Path(report_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def main() -> None:  # pragma: no cover -- thin CLI wrapper, exercised via the functions above
    import argparse

    parser = argparse.ArgumentParser(description="Run Shadow Mode across a directory of resumes.")
    parser.add_argument("--dir", required=True, help="Directory of resume files (.pdf/.docx)")
    parser.add_argument("--report", required=True, help="Output JSON report path")
    args = parser.parse_args()

    results = run_batch_shadow_comparison(args.dir)
    write_report(results, args.report)
    print(f"Compared {len(results)} resumes. Category totals: {aggregate_category_counts(results)}")
    print(f"Full report written to {args.report}")


if __name__ == "__main__":  # pragma: no cover
    main()
