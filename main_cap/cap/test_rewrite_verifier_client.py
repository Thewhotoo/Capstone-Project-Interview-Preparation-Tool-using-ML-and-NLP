"""Tests for rewrite_verifier_client.py — Experiment 4 (Rewrite Augmentation) Stage."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rewrite_verifier_client import FakeSemanticVerifierClient, GeminiSemanticVerifierClient, SemanticDriftVerdict


class TestFakeSemanticVerifierClient(unittest.TestCase):
    def test_reports_no_drift_by_default(self):
        client = FakeSemanticVerifierClient()
        verdict = client.verify("I used Redis for caching.", "I made use of Redis to cache things.")
        self.assertIsInstance(verdict, SemanticDriftVerdict)
        self.assertFalse(verdict.meaning_changed)

    def test_reports_drift_when_marker_present(self):
        client = FakeSemanticVerifierClient()
        verdict = client.verify("I used Redis for caching.", "I used PostgreSQL, DRIFT_TEST_TRIGGER for caching.")
        self.assertTrue(verdict.meaning_changed)

    def test_explanation_is_never_empty(self):
        client = FakeSemanticVerifierClient()
        for rewritten in ("normal text", "text with DRIFT_TEST_TRIGGER"):
            verdict = client.verify("original", rewritten)
            self.assertTrue(verdict.explanation.strip())

    def test_deterministic_across_calls(self):
        client = FakeSemanticVerifierClient()
        v1 = client.verify("original text", "rewritten text")
        v2 = client.verify("original text", "rewritten text")
        self.assertEqual(v1.meaning_changed, v2.meaning_changed)

    def test_model_name_set(self):
        client = FakeSemanticVerifierClient()
        self.assertTrue(client.model_name)


class TestSemanticDriftVerdictSchema(unittest.TestCase):
    def test_defaults(self):
        verdict = SemanticDriftVerdict()
        self.assertFalse(verdict.meaning_changed)
        self.assertEqual(verdict.explanation, "")


class TestGeminiSemanticVerifierClientRetriesOnUnparsedResponse(unittest.TestCase):
    """Regression test for a real failure hit running the Experiment 4
    pilot: a successful HTTP call whose body doesn't parse into
    SemanticDriftVerdict (response.parsed is None) is NOT an exception --
    it must be retried like any other transient failure, not raised
    immediately and left to crash the entire calling batch."""

    def test_retries_then_succeeds_on_second_attempt(self):
        unparsed_response = MagicMock(parsed=None)
        good_verdict = SemanticDriftVerdict(meaning_changed=False, explanation="fine")
        parsed_response = MagicMock(parsed=good_verdict)

        fake_genai_client = MagicMock()
        fake_genai_client.models.generate_content.side_effect = [unparsed_response, parsed_response]

        with patch("rewrite_verifier_client._get_genai_client", return_value=fake_genai_client), \
             patch("rewrite_verifier_client.time.sleep"):
            client = GeminiSemanticVerifierClient()
            verdict = client.verify("original", "rewritten")

        self.assertEqual(verdict, good_verdict)
        self.assertEqual(fake_genai_client.models.generate_content.call_count, 2)

    def test_raises_after_exhausting_retries_all_unparsed(self):
        unparsed_response = MagicMock(parsed=None)
        fake_genai_client = MagicMock()
        fake_genai_client.models.generate_content.return_value = unparsed_response

        with patch("rewrite_verifier_client._get_genai_client", return_value=fake_genai_client), \
             patch("rewrite_verifier_client.time.sleep"):
            client = GeminiSemanticVerifierClient()
            with self.assertRaises(RuntimeError):
                client.verify("original", "rewritten")

        self.assertEqual(fake_genai_client.models.generate_content.call_count, 3)  # _RETRY_MAX_ATTEMPTS


if __name__ == "__main__":
    unittest.main()
