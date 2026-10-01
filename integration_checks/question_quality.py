"""Round 1 question quality across many resumes (run before/after planner changes).

    python integration_checks/question_quality.py <parsed_profiles.json> [--show N]

Runs a full Round 1 per profile with a canned answer and reports, over all
interviews:
  questions            total asked
  repeated_text        a question whose wording was already asked in the same interview
  repeated_core        same, after removing the transition opener ("Let's stay on this for a moment — ")
  family_repeat_3      same question family (style) as one of the previous 3 turns
  same_source_run      a turn on the same source (project/job/cert) as the turn before
  seed_specific        questions rendered from the resume's own interview seeds
  distinct_sources     average number of different resume items asked about per interview
--show N prints the first N interviews' questions.
"""
import io
import json
import os
import sys
from collections import Counter

CAP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main_cap", "cap"))
sys.path.insert(0, CAP)
os.chdir(CAP)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import logging
logging.disable(logging.CRITICAL)
import conversation_engine

ANSWER = ("I built that part myself using Python and a small database. I chose it because it was simple to "
          "debug, and I measured the response time before and after the change.")
profiles = {k: v["profile"] for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items() if "profile" in v}
show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0

m = Counter()
distinct = []
for n, (name, profile) in enumerate(profiles.items()):
    payload, _ = conversation_engine.start_conversation(profile)
    if "conversation_id" not in payload:
        continue
    cid, q, qs = payload["conversation_id"], payload.get("question"), []
    while q and len(qs) < 20:
        qs.append(q)
        payload, _ = conversation_engine.advance_conversation(cid, ANSWER)
        q = payload.get("next_question")
    conversation_engine.end_conversation(cid)
    seen, seen_core = set(), set()
    for i, q in enumerate(qs):
        head, sep, tail = q["text"].partition(" — ")
        core = tail if sep and len(head.split()) <= 9 and not head.rstrip().endswith("?") else q["text"]
        m["repeated_core"] += core in seen_core
        seen_core.add(core)
        m["questions"] += 1
        m["repeated_text"] += q["text"] in seen
        seen.add(q["text"])
        m["family_repeat_3"] += q["family"] in {p["family"] for p in qs[max(0, i - 3):i]}
        m["same_source_run"] += i > 0 and q["source_id"] == qs[i - 1]["source_id"]
        m["seed_specific"] += q["family"] == "interview_seed"
    distinct.append(len({q["source_id"] for q in qs}))
    if n < show:
        print(f"\n== {name}")
        for i, q in enumerate(qs, 1):
            print(f"  Q{i} [{q['family']} | {q['source_id'][:28]}] {q['text']}")
print("\n" + "  ".join(f"{k}={v}" for k, v in m.items()) + f"  distinct_sources_per_interview={sum(distinct) / max(1, len(distinct)):.2f}")
