"""
Verification script required before continuing implementation: generates a
REAL Candidate Profile from the actual uploaded resume (one real Gemini call,
matching the new technical_topics schema), builds the Topic Pool from it, and
prints Question / Source / Origin / Reason for every question the pool would
ask across a full session — plus every technical_topic entry Gemini proposed
that got rejected as untraceable.
"""
import json
import os
import sys
sys.path.insert(0, ".")

from candidate_profile_generator import extract_text_from_pdf, generate_candidate_profile
import discussion_engine as de

RESUME_PATH = sys.argv[1] if len(sys.argv) > 1 else None
if not RESUME_PATH:
    print("Usage: python _verify_traceability.py <path-to-resume.txt-or-.pdf> [--regenerate]")
    sys.exit(1)
REGENERATE = "--regenerate" in sys.argv

CACHE_PATH = "_verify_traceability_cache.json"

if not REGENERATE and os.path.exists(CACHE_PATH):
    print(f"Reusing cached profile from {CACHE_PATH} (pass --regenerate for a fresh Gemini call)")
    with open(CACHE_PATH, encoding="utf-8") as f:
        profile = json.load(f)
else:
    if RESUME_PATH.lower().endswith(".pdf"):
        text = extract_text_from_pdf(RESUME_PATH)
    else:
        with open(RESUME_PATH, encoding="utf-8") as f:
            text = f.read()

    print(f"Extracted {len(text)} chars from {RESUME_PATH}")
    print("Calling Gemini once for Candidate Profile generation...")
    profile = generate_candidate_profile(text)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

print("\n" + "=" * 70)
print("RAW interview_blueprint.technical_topics (as Gemini returned them)")
print("=" * 70)
for t in profile.get("interview_blueprint", {}).get("technical_topics", []):
    print(f"  topic={t.get('topic')!r} "
          f"originating_project={t.get('originating_project')!r} "
          f"originating_experience={t.get('originating_experience')!r} "
          f"evidence={t.get('evidence')!r}")

print("\n" + "=" * 70)
print("BUILDING TOPIC POOL")
print("=" * 70)
pool = de.TopicPool(profile)

print(f"\nProjects on profile: {[p.get('title') for p in profile.get('projects', [])]}")
print(f"Experience on profile: {[e.get('role') for e in profile.get('experience', [])]}")
print(f"Certifications on profile: {profile.get('certifications', [])}")

print("\n" + "=" * 70)
print("REJECTED technical_topics (untraceable — never asked)")
print("=" * 70)
if pool.rejected:
    for r in pool.rejected:
        print(f"  REJECTED: topic={r['topic']!r} — {r['reason']} "
              f"(originating_project={r['originating_project']!r}, "
              f"originating_experience={r['originating_experience']!r})")
else:
    print("  (none — every technical_topic Gemini proposed was traceable)")

print("\n" + "=" * 70)
print(f"FULL SESSION SIMULATION — {len(pool.units)} total units in pool")
print("=" * 70)

VALID_PROJECT_TITLES = {p.get("title", "").lower() for p in profile.get("projects", [])}
VALID_EXPERIENCE_ROLES = {e.get("role", "").lower() for e in profile.get("experience", [])}
VALID_CERT_NAMES = {
    (c.get("name", "") if isinstance(c, dict) else str(c)).lower()
    for c in profile.get("certifications", [])
}

last_category = None
question_num = 0
failures = []

while True:
    unit = pool.select_next(last_category)
    if unit is None:
        break
    question_num += 1
    unit["status"] = "covered"  # walk the whole pool for this verification pass
    last_category = unit["category"]

    question_text = de._phrase_topic(unit)

    source_type = unit.get("source_type", "")
    source_id = unit.get("source_id", "")
    source_field = unit.get("source_field", "")
    reason = unit.get("reason", "")

    # Reject-if-not-traceable, enforced here as the final check: the source_id
    # must actually match a real profile entry, and the question text itself
    # must reference it.
    traceable = False
    if source_type == "project":
        traceable = source_id.lower() in VALID_PROJECT_TITLES
    elif source_type == "experience":
        traceable = any(r and r in source_id.lower() for r in VALID_EXPERIENCE_ROLES)
    elif source_type == "certification":
        traceable = source_id.lower() in VALID_CERT_NAMES

    mentions_source = de._mentions(question_text, source_id) if source_id else False

    print(f"\nQuestion {question_num}:")
    print(f"  Question: {question_text}")
    print(f"  Source:   {source_type}")
    print(f"  Origin:   {source_id}")
    print(f"  Reason:   {reason}")
    print(f"  [traceable={traceable}, mentions_source_in_text={mentions_source}]")

    if not (source_type and source_id and source_field and reason):
        failures.append((question_num, question_text, "missing required metadata"))
        print("  ** REJECTED: missing required traceability metadata **")
    elif not traceable:
        failures.append((question_num, question_text, "source_id does not match a real profile entry"))
        print("  ** REJECTED: source_id not found in Candidate Profile **")
    elif not mentions_source:
        failures.append((question_num, question_text, "question text does not mention its source"))
        print("  ** REJECTED: question text doesn't cite its origin **")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total questions in pool: {question_num}")
print(f"Failures: {len(failures)}")
for qn, qt, reason in failures:
    print(f"  Q{qn} FAILED ({reason}): {qt}")

if failures:
    print("\nFAIL: some questions could not produce full traceability metadata.")
    sys.exit(1)
print("\nPASS: every question in the pool is traceable to exactly one Candidate Profile entry.")
