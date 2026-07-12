"""Test: Experience extraction for pipe-delimited resume format."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resume_classifier"))

from src.features import calculate_total_experience, extract_job_experiences

PIPE_DELIMITED_RESUME = """
MAYUR PATIL
Email: mayur.patil@email.com

WORK EXPERIENCE

Software Engineer | TCS | Pune, India | Jan 2022 - Present
- Developed and maintained microservices using Python Flask and FastAPI
- Built RESTful APIs serving 10,000+ daily active users

Junior Developer | Infosys | Bangalore, India | Jun 2020 - Dec 2021
- Developed backend services using Python Django and Flask
- Created REST APIs for mobile application integration
"""

jobs = extract_job_experiences(PIPE_DELIMITED_RESUME)
exp = calculate_total_experience(PIPE_DELIMITED_RESUME)

print(f"Jobs found: {len(jobs)}")
for j in jobs:
    print(f"  - {j['title']} @ {j['company']}: {j['date_range']} ({j['duration_years']}yr)")
print(f"Total experience: {exp}")

assert len(jobs) >= 2, f"FAIL: Expected >=2 jobs, got {len(jobs)}"
assert exp["years"] >= 3, f"FAIL: Expected >=3 years, got {exp['years']}"
assert exp["level"] != "Unknown", f"FAIL: Level should not be Unknown, got {exp['level']}"
print("\nALL TESTS PASSED")
