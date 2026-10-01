"""Start a full Round 1 (Resume Discussion) from every resume and answer every question.

    python integration_checks/round1_smoke.py [parsed_profiles.json]

For each parsed profile (default: re-parse parser_tests/resumes/*.pdf with the
engine in main_cap/cap): start_conversation -> answer each question with a
short canned answer until the conversation completes -> end_conversation.
Reports questions asked, what each question is grounded in, and any crash.
Proves the planner/evaluator cope with whatever the resume engine produces.
"""
import glob
import io
import json
import os
import sys
import time

CAP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main_cap", "cap"))
sys.path.insert(0, CAP)
os.chdir(CAP)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import logging
logging.basicConfig(level=logging.ERROR)

import conversation_engine
import deployment_evaluator
deployment_evaluator.bootstrap_production_evaluator()   # same evaluator the app activates at start-up
from evaluator_registry import get_active_evaluator
print("active evaluator:", get_active_evaluator().name)
from candidate_profile_generator import generate_candidate_profile_via_engine

ROOT = os.path.abspath(os.path.join(CAP, "..", ".."))
ANSWER = ("I built that part myself using Python and a small database. I chose it because it was simple to "
          "debug, and I measured the response time before and after the change.")

if len(sys.argv) > 1:
    profiles = {k: v["profile"] for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items() if "profile" in v}
else:
    profiles = {os.path.basename(f): generate_candidate_profile_via_engine(f)
                for f in sorted(glob.glob(os.path.join(ROOT, "parser_tests", "resumes", "*.pdf")))}

failures = 0
for name, profile in profiles.items():
    t0 = time.time()
    try:
        payload, status = conversation_engine.start_conversation(profile)
        cid = payload.get("conversation_id")
        asked, grounded = [], []
        while payload.get("next_question") or payload.get("question"):
            q = payload.get("next_question") or payload.get("question")
            asked.append(q.get("text", ""))
            grounded.append(q.get("project_reference") or q.get("category") or "")
            payload, status = conversation_engine.advance_conversation(cid, ANSWER)
            if payload.get("is_completed") or len(asked) > 20:
                break
        summary, _ = conversation_engine.end_conversation(cid)
        refs = sorted({g for g in grounded if g})
        print(f"OK   {name:<30} {len(asked):2} questions, {time.time() - t0:4.1f}s, grounded in: {', '.join(refs)[:120]}")
    except Exception as exc:  # report, keep going
        failures += 1
        print(f"FAIL {name:<30} {type(exc).__name__}: {exc}"[:300])
print(f"\n{len(profiles) - failures}/{len(profiles)} complete Round 1 conversations without errors")
