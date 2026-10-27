"""
Grader regression benchmark (grader_eval/benchmark.py) as a test: fails if the
technical grader gets worse than grader_eval/baseline.json on any labelled set.

Slow (grades ~580 answers with the real models), so it only runs when asked:
    CAP_RUN_GRADER_BENCHMARK=1 python -m pytest test_grader_benchmark.py -q
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("CAP_RUN_GRADER_BENCHMARK"), "set CAP_RUN_GRADER_BENCHMARK=1 to run")
class TestGraderBenchmark(unittest.TestCase):
    def test_no_regression_vs_baseline(self):
        run = subprocess.run([sys.executable, str(ROOT / "grader_eval" / "benchmark.py")],
                             capture_output=True, text=True, encoding="utf-8", timeout=3600)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
