import json, sys, os, glob, time, io
cap, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, cap); os.chdir(cap)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from candidate_profile_generator import generate_candidate_profile_via_engine
root = r"C:\PESU\placement prep\capstone_latest"
files = sorted(glob.glob(root + r"\parser_tests\resumes\*.pdf")) + sorted(glob.glob(root + r"\main_cap\cap\resume_engine\tests\golden_corpus\*\resume.*"))
res, t0 = {}, time.time()
for f in files:
    key = ("real/" + os.path.basename(f)) if "parser_tests" in f else ("golden/" + os.path.basename(os.path.dirname(f)))
    t = time.time()
    try:
        res[key] = {"profile": generate_candidate_profile_via_engine(f), "seconds": round(time.time() - t, 2)}
    except Exception as e:
        res[key] = {"error": f"{type(e).__name__}: {e}"[:300]}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print(f"{len(files)} files, {sum('error' in v for v in res.values())} errors, {time.time() - t0:.0f}s")
