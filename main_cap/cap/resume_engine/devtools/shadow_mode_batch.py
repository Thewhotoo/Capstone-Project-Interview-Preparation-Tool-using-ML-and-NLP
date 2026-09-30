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

from resume_engine.devtools.shadow_mode import (
    EngineComparisonError,
    GeminiComparisonError,
    ShadowComparisonResult,
    run_shadow_comparison,
)

_SUPPORTED_SUFFIXES = (".pdf", ".docx")


class ExtractionComparisonError(RuntimeError):
    """Stored (not raised past this module) when text/file extraction
    itself fails before either pipeline runs -- distinguishes "we never
    got far enough to compare anything" (a corrupt/scanned file, most
    likely) from a Gemini-side or engine-side failure. See
    GeminiComparisonError / EngineComparisonError in shadow_mode.py."""


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
    A single resume's failure (e.g. a corrupt file, a Gemini quota error,
    or a real engine bug) is recorded as an error entry, tagged with which
    stage failed, and never allowed to abort the whole batch -- one bad
    fixture shouldn't block reviewing the other 29."""
    results: dict[str, ShadowComparisonResult] = {}
    directory = Path(resume_dir)
    for resume_path in sorted(directory.iterdir()):
        if resume_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        try:
            text = _extract_text(resume_path)
        except Exception as e:  # noqa: BLE001 -- deliberately broad: one bad fixture must not abort the batch
            results[resume_path.name] = ExtractionComparisonError(str(e))
            continue
        try:
            results[resume_path.name] = run_shadow_comparison(str(resume_path), text)
        except Exception as e:  # noqa: BLE001 -- includes GeminiComparisonError/EngineComparisonError, already tagged
            results[resume_path.name] = e
    return results


def _error_stage(exc: Exception) -> str:
    """Classifies a stored error entry by which stage produced it, for
    report grouping. Anything not one of the three tagged types (e.g. a
    plain Exception from code predating this tagging, or from a test's
    hand-built fixture) is reported as "unknown_error" rather than
    guessed at from its message text."""
    if isinstance(exc, GeminiComparisonError):
        return "gemini_error"
    if isinstance(exc, EngineComparisonError):
        return "engine_error"
    if isinstance(exc, ExtractionComparisonError):
        return "extraction_error"
    return "unknown_error"


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
    """Writes a human-reviewable JSON report structured so the top-level
    keys answer the review questions in order, before drilling into any
    one resume:

      - meta: how much of the batch actually completed vs. errored, and
        which stage each error came from (gemini/engine/extraction) --
        this is what makes a quota-starved run ("18/30 completed, 12
        gemini_error") immediately distinguishable from a run with real
        engine problems ("28/30 completed, 2 engine_error") at a glance.
      - summary: batch-level discrepancy category totals (existing).
      - critical_failure_candidates: resumes where the engine's own
        output failed the real TopicPool health check (see
        check_engine_topic_pool_health) -- a structural pointer to
        Milestone7_EvaluationGuide.md Section 5's critical-failure
        criteria, not a verdict; still needs human confirmation.
      - errors_by_stage: filenames grouped by which stage failed, so a
        reviewer can jump straight to (for example) every engine_error
        without reading every per-resume entry.
      - resumes: full per-resume detail (unchanged shape for successful
        comparisons; error entries now also carry a "stage" tag).

    Never auto-resolves or auto-declares a side "better" -- every added
    field is either a raw count or a factual/mechanical check, exactly
    like the pre-existing discrepancy categories."""
    completed = {k: v for k, v in results.items() if isinstance(v, ShadowComparisonResult)}
    errored = {k: v for k, v in results.items() if isinstance(v, Exception)}

    errors_by_stage: dict[str, list[str]] = {}
    for filename, exc in errored.items():
        errors_by_stage.setdefault(_error_stage(exc), []).append(filename)

    critical_failure_candidates = [
        filename for filename, result in completed.items()
        if not result.topic_pool_check.get("ok", True)
    ]

    report = {
        "meta": {
            "total_resumes": len(results),
            "completed": len(completed),
            "errored": len(errored),
            "errors_by_stage_count": {stage: len(files) for stage, files in errors_by_stage.items()},
        },
        "summary": aggregate_category_counts(results),
        "critical_failure_candidates": critical_failure_candidates,
        "errors_by_stage": errors_by_stage,
        "resumes": {},
    }
    for filename, result in results.items():
        if isinstance(result, Exception):
            report["resumes"][filename] = {"error": str(result), "stage": _error_stage(result)}
        else:
            report["resumes"][filename] = {
                "category_counts": result.category_counts(),
                "discrepancies": [asdict(d) for d in result.discrepancies],
                "topic_pool_check": result.topic_pool_check,
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
    completed = sum(1 for r in results.values() if isinstance(r, ShadowComparisonResult))
    print(f"Compared {len(results)} resumes: {completed} completed, {len(results) - completed} errored.")
    print(f"Category totals: {aggregate_category_counts(results)}")
    print(f"Full report written to {args.report}")


if __name__ == "__main__":  # pragma: no cover
    main()
