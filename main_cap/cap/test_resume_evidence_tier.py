"""Tests for deployment_evaluator.py's Tier 0 (resume-evidence evaluator) --
that it activates by default, can be switched off, and that bootstrap falls
through to the next tier (never raises) if it fails."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deployment_evaluator
import evaluator_registry
from resume_evidence_evaluator import ResumeEvidenceEvaluator


class TestResumeEvidenceTier(unittest.TestCase):
    def setUp(self):
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None

    def test_active_by_default(self):
        self.assertTrue(deployment_evaluator._try_activate_resume_evidence())
        active = evaluator_registry.get_active_evaluator()
        self.assertIsInstance(active, ResumeEvidenceEvaluator)
        self.assertEqual(evaluator_registry.active_evaluator_name(), "resume-evidence-evaluator-v2")

    def test_scoring_can_be_rolled_back_to_v1(self):
        with mock.patch.dict(os.environ, {"CAP_EVIDENCE_SCORING": "v1"}):
            self.assertTrue(deployment_evaluator._try_activate_resume_evidence())
        self.assertEqual(evaluator_registry.active_evaluator_name(), "resume-evidence-evaluator-v1")

    def test_can_be_switched_off(self):
        with mock.patch.dict(os.environ, {"CAP_RESUME_EVIDENCE_EVALUATOR": "0"}):
            self.assertFalse(deployment_evaluator._try_activate_resume_evidence())
        self.assertEqual(evaluator_registry._registry, {})

    def test_switched_off_falls_through_to_next_tier_in_bootstrap(self):
        with mock.patch.dict(os.environ, {"CAP_RESUME_EVIDENCE_EVALUATOR": "0", "CAP_TRAINED_EVALUATOR": "0"}), \
                mock.patch.object(deployment_evaluator, "_try_activate_averaged_v5", lambda: False), \
                mock.patch.object(deployment_evaluator, "DEPLOYED_WEIGHTS_PATH", "nonexistent.pt"):
            deployment_evaluator.bootstrap_production_evaluator()
        self.assertEqual(evaluator_registry.active_evaluator_name(), "heuristic-v1")

    def test_bootstrap_activates_resume_evidence_by_default(self):
        with mock.patch.object(deployment_evaluator, "_try_activate_averaged_v5", lambda: False):
            deployment_evaluator.bootstrap_production_evaluator()
        self.assertEqual(evaluator_registry.active_evaluator_name(), "resume-evidence-evaluator-v2")

    def test_never_raises_on_internal_failure(self):
        with mock.patch("resume_evidence_evaluator.ResumeEvidenceEvaluator", side_effect=RuntimeError("boom")):
            self.assertFalse(deployment_evaluator._try_activate_resume_evidence())
        self.assertEqual(evaluator_registry._registry, {})


if __name__ == "__main__":
    unittest.main()
