"""
Round 1 question quality after integrating the teammate's planner changes
(resumeParser_integration.md step 4): resume-specific seed questions (naming
their project, never two in a row), no repeated question wording, and a soft
cooldown so one project doesn't take several turns in a row.
"""

import unittest

import conversation_engine
from candidate_profile_generator import CandidateProfile, ProjectEntry
from question_realizer import _name_the_project, _short_project_name
from topic_pool import _RECENT_SOURCE_PENALTY

ANSWER = ("I built that part myself using Python and a small database. I chose it because it was simple "
          "to debug, and I measured the response time before and after the change.")


def _profile():
    return CandidateProfile(
        candidate_name="Test", skills=["Python", "Redis", "React", "Node.js", "Docker"],
        projects=[
            ProjectEntry(title="AI SOC Analyst — Intelligent Log Analysis", summary="Security log triage with LLMs.",
                         technologies=["Python", "Redis", "Docker"], concepts=["caching"],
                         interview_seeds=["Why did you use Redis in this project?",
                                          "How did you approach caching in this project?"]),
            ProjectEntry(title="Task Tracker", summary="A web app to track tasks.",
                         technologies=["React", "Node.js"], concepts=["authentication"],
                         interview_seeds=["Why did you use React in this project?",
                                          "How did you approach authentication in this project?"]),
        ],
    ).model_dump()


def _run_interview():
    payload, _ = conversation_engine.start_conversation(_profile())
    cid, q, qs = payload["conversation_id"], payload["question"], []
    while q and len(qs) < 20:
        qs.append(q)
        payload, _ = conversation_engine.advance_conversation(cid, ANSWER)
        q = payload.get("next_question")
    conversation_engine.end_conversation(cid)
    return qs


class TestSeedQuestions(unittest.TestCase):
    def test_short_project_name(self):
        self.assertEqual(_short_project_name("Patient OS v2 — Multi-Source Health AI Copilot"), "Patient OS v2")
        self.assertEqual(_short_project_name("Task Tracker"), "Task Tracker")
        self.assertEqual(_short_project_name("Chronos: Distributed Task System"), "Chronos")

    def test_interview_uses_named_seeds_without_back_to_back_runs(self):
        qs = _run_interview()
        seeds = [q for q in qs if q["family"] == "interview_seed"]
        self.assertTrue(seeds, [q["text"] for q in qs])
        for q in seeds:
            self.assertNotIn("this project?", q["text"])
            self.assertTrue("AI SOC Analyst" in q["text"] or "Task Tracker" in q["text"], q["text"])
        for a, b in zip(qs, qs[1:]):
            self.assertFalse(a["family"] == b["family"] == "interview_seed", (a["text"], b["text"]))

    def test_no_repeated_question_wording(self):
        cores = []
        for q in _run_interview():
            head, sep, tail = q["text"].partition(" — ")
            cores.append(tail if sep and len(head.split()) <= 9 else q["text"])
        self.assertEqual(len(cores), len(set(cores)), cores)


class TestRecentSourceCooldown(unittest.TestCase):
    def test_penalty_breaks_ties_but_never_overrides_priority(self):
        # smaller than one priority tier (10), larger than weakness (2) + diversity (1) bonuses
        self.assertTrue(3 <= _RECENT_SOURCE_PENALTY < 10)

    def test_interview_moves_between_projects(self):
        qs = _run_interview()
        runs = sum(1 for a, b in zip(qs, qs[1:]) if a["source_id"] == b["source_id"])
        self.assertLessEqual(runs, len(qs) // 2, [(q["source_id"], q["text"]) for q in qs])


if __name__ == "__main__":
    unittest.main()
