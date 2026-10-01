"""Tests for expected_concepts_registry.py — Expected Concepts revision (approved)."""

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import expected_concepts_registry as registry
from expected_concepts_registry import (
    DuplicateExpectedConceptsEntryError,
    expected_concepts_for,
    lookup,
    register_expected_concepts,
    registered_names,
)


def _unique_name(prefix="tech"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TestSeedEntries(unittest.TestCase):
    """The exact worked examples from the approved RFC."""

    def test_fastapi_seeded(self):
        self.assertEqual(
            lookup("FastAPI"),
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity"),
        )

    def test_langgraph_seeded(self):
        self.assertEqual(
            lookup("LangGraph"),
            ("graph nodes", "state transitions", "orchestration", "agents", "workflow execution"),
        )

    def test_rag_seeded(self):
        self.assertEqual(
            lookup("RAG"),
            ("retrieval", "embeddings", "vector search", "chunking", "grounding"),
        )

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(lookup("fastapi"), lookup("FastAPI"))
        self.assertEqual(lookup("FASTAPI"), lookup("FastAPI"))


class TestGracefulDegradation(unittest.TestCase):
    def test_unrecognized_name_returns_empty_tuple(self):
        self.assertEqual(lookup(_unique_name("never_registered")), ())

    def test_unrecognized_name_never_raises(self):
        expected_concepts_for((_unique_name(), _unique_name()))  # must not raise

    def test_empty_candidate_list_returns_empty(self):
        self.assertEqual(expected_concepts_for(()), ())


class TestRegistration(unittest.TestCase):
    def test_register_and_lookup(self):
        name = _unique_name()
        register_expected_concepts(name, ("concept a", "concept b"))
        self.assertEqual(lookup(name), ("concept a", "concept b"))

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(DuplicateExpectedConceptsEntryError):
            register_expected_concepts("fastapi", ("something else",))

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            register_expected_concepts("   ", ("x",))

    def test_empty_concepts_rejected(self):
        with self.assertRaises(ValueError):
            register_expected_concepts(_unique_name(), ())

    def test_registered_names_includes_seeds(self):
        names = registered_names()
        self.assertIn("fastapi", names)
        self.assertIn("langgraph", names)


class TestExpectedConceptsFor(unittest.TestCase):
    def test_multiple_candidates_deduplicated_and_ordered(self):
        result = expected_concepts_for(("FastAPI", "RAG"))
        self.assertEqual(
            result,
            ("ASGI", "async request handling", "dependency injection", "routing", "modularity",
             "retrieval", "embeddings", "vector search", "chunking", "grounding"),
        )

    def test_mix_of_recognized_and_unrecognized_names(self):
        result = expected_concepts_for(("FastAPI", _unique_name("unknown")))
        self.assertEqual(result, lookup("FastAPI"))

    def test_overlapping_concepts_across_two_technologies_deduplicated(self):
        name = _unique_name()
        register_expected_concepts(name, ("retrieval", "a brand new concept"))
        result = expected_concepts_for(("RAG", name))
        self.assertEqual(result.count("retrieval"), 1)  # not duplicated


if __name__ == "__main__":
    unittest.main()
