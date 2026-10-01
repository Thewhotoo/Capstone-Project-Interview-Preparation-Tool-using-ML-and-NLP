"""Non-answer gate: false positives on real answers vs catches on junk; ours vs the teammate's original.

    python integration_checks/gate_check.py
"""
import io, json, os, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "main_cap", "cap"))
from answer_gate import check_answer
# The teammate's original gate (two files copied from his branch) for comparison.
THEIRS = os.path.join(ROOT, "integration_checks", "data", "teammate_gate")
theirs = None
if os.path.isdir(THEIRS):
    import importlib.util
    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m; spec.loader.exec_module(m); return m
    try:
        src = open(os.path.join(THEIRS, "overall_single_evaluator.py"), encoding="utf-8").read()
        ns = {}
        exec(src[src.index("_NON_ANSWER_MARKERS"):src.index("def _grade_from_score")], ns)
        sys.path.insert(0, THEIRS)
        deg = _load("their_scorer", os.path.join(THEIRS, "correctness_nli_scorer.py")).degeneracy
        theirs = lambda t: ns["_is_non_answer"](t) or deg(t).is_degenerate
    except Exception as exc:
        print("teammate's gate not loadable:", exc)

real = []   # (source, style, text): answers that are genuine attempts
for a in json.load(open(os.path.join(ROOT, "grader_eval", "output_questions.json"), encoding="utf-8-sig")):
    real.append(("llm-400", a["style"], a["answer"]))
for a in json.load(open(os.path.join(ROOT, "grader_eval", "tuning_set", "answers.json"), encoding="utf-8-sig")):
    real.append(("llm-100", a["style"], a["answer"]))
for a in json.load(open(os.path.join(ROOT, "grader_eval", "my_answers.json"), encoding="utf-8-sig")):
    real.append(("yours", "main", a["answer"]))
    if a["followup"]["answer"].strip():
        real.append(("yours", "followup", a["followup"]["answer"]))
v4 = os.path.join(ROOT, "integration_checks", "data", "v4_diagnostic_58.jsonl")
if os.path.exists(v4):
    for l in open(v4, encoding="utf-8"):
        real.append(("round1-58", "diagnostic", json.loads(l)["answer"]))

JUNK = ["I don't really remember the difference between TCP and UDP, sorry.",
        "I haven't studied that pattern properly, so I don't know how to answer this.",
        "I don't remember the cases, sorry. I'd have to look them up.",
        "idk", "I don't know.", "I'm not sure, I don't remember.", "no idea honestly", "pass",
        "Flask SQLite Python REST API JWT Docker Redis microservices scalability caching",
        "python, flask, sql, docker, redis, aws, kubernetes, react",
        "asdf qwer zxcv lorem blah blah hmm", "yes yes yes yes yes yes yes yes yes yes",
        "<script>alert('x')</script>", "def f(x): return x + 1", "12345 67890 !!!! ???? 111",
        "caching caching caching caching caching caching redis redis redis redis"]
SHOULD_PASS = ["I don't know the exact number, but it cut latency by about 40% after I added the index.",
               "List<String> list = new ArrayList<>(); here List is the interface and ArrayList is the implementation",
               "I passed all the integration tests after fixing the retry bug.",
               "We weren't sure about the load, so I benchmarked three databases and picked Postgres.",
               "The function should return the cached value if it is still fresh, otherwise it refetches.",
               "I select the rows from the cache first and only hit the database on a miss.",
               "I didn't know React well at first, so I built a small prototype to learn it before the real UI.",
               "Redis, because it was fast.", "nope"]

def run(fn, label):
    flagged = Counter(); total = Counter(); examples = []
    for src, style, text in real:
        key = f"{src}:{style}"
        total[key] += 1
        if fn(text):
            flagged[key] += 1
            if style not in ("dont_know",) and "not sure" not in text.lower() and len(examples) < 8: examples.append((key, text[:110]))
    fp = sum(v for k, v in flagged.items() if not k.endswith("dont_know"))
    n = sum(v for k, v in total.items() if not k.endswith("dont_know"))
    dk = sum(v for k, v in flagged.items() if k.endswith("dont_know")); dkn = sum(v for k, v in total.items() if k.endswith("dont_know"))
    print(f"\n== {label}")
    fp -= sum(1 for src, style, t in real if style != "dont_know" and fn(t) and t.strip().lower() in ("im not sure", "i'm not sure", "nope"))
    print("  (the user's own 'im not sure' / 'nope' replies are real non-answers, not counted)")
    print(f"  real attempts wrongly flagged: {fp}/{n}   |   'I don't know' answers flagged: {dk}/{dkn}")
    print(f"  junk replies caught: {sum(bool(fn(t)) for t in JUNK)}/{len(JUNK)}   |   tricky real sentences wrongly flagged: {sum(bool(fn(t)) for t in SHOULD_PASS)}/{len(SHOULD_PASS)}")
    for k, t in examples: print(f"    e.g. [{k}] {t}")
    for t in SHOULD_PASS:
        if fn(t): print(f"    tricky flagged: {t}")
    for t in JUNK:
        if not fn(t): print(f"    junk missed: {t}")

run(lambda t: check_answer(t).gated, "OUR gate (answer_gate.py)")
if theirs: run(theirs, "teammate's original gate")
