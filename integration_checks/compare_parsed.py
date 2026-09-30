"""Compare two parse_all.py outputs (ours vs theirs) field by field.

    python integration_checks/compare_parsed.py parsed_ours.json parsed_theirs.json > diff.txt

Prints list-field totals (real resumes / golden corpus), how many files are
identical, and per-file differences (names, contacts, education, experience,
projects, certifications, skills).
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
A = json.load(open(sys.argv[1], encoding="utf-8"))
B = json.load(open(sys.argv[2], encoding="utf-8"))
FIELDS = ["skills", "education", "experience", "projects", "certifications"]
KEYS = {"education": ("degree", "institution", "graduation_year"), "experience": ("role", "company", "duration"),
        "projects": ("title", "name"), "certifications": ("name", "title", "issuer")}


def count(p, f):
    v = p.get(f)
    return len(v) if isinstance(v, list) else 0


def brief(field, items):
    out = []
    for it in items or []:
        out.append(it if isinstance(it, str) else " | ".join(str(it.get(k)) for k in KEYS.get(field, ()) if it.get(k)))
    return out


print("totals        group     A     B")
for f in FIELDS:
    for grp in ("real/", "golden/"):
        a = sum(count(A[x]["profile"], f) for x in A if x.startswith(grp) and "profile" in A[x])
        b = sum(count(B[x]["profile"], f) for x in B if x.startswith(grp) and "profile" in B[x])
        print(f"{f:<14}{grp:<8}{a:5} {b:5}")
print(f"identical: {sum(A[x].get('profile') == B.get(x, {}).get('profile') for x in A)}/{len(A)}")
for x in A:
    if "profile" not in A[x] or A[x]["profile"] == B[x].get("profile"):
        continue
    a, b = A[x]["profile"], B[x]["profile"]
    print(f"\n######## {x}")
    for f in ["candidate_name", "contact_details"] + FIELDS:
        if a.get(f) == b.get(f):
            continue
        if f == "skills":
            print(f"  skills only A: {sorted(set(a[f]) - set(b[f]))}\n  skills only B: {sorted(set(b[f]) - set(a[f]))}")
        elif isinstance(a.get(f), list):
            print(f"  {f}:\n    A: {brief(f, a[f])}\n    B: {brief(f, b[f])}")
        else:
            print(f"  {f}:\n    A: {a.get(f)}\n    B: {b.get(f)}")
