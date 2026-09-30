"""
Code evaluation module – syntax checking, compilation, execution (batch & real‑time),
unit tests, and feedback. Supports Python, Java, C++, JavaScript.
"""
import ast
import os
import json
import subprocess
import tempfile
import time
import select
from pathlib import Path
from typing import Dict, List, Tuple, Any, Generator

from sentence_transformers import SentenceTransformer

# Lazy load CodeBERT model
_codebert = None

def get_codebert():
    global _codebert
    if _codebert is None:
        print("Loading CodeBERT for code similarity...")
        _codebert = SentenceTransformer("microsoft/codebert-base")
    return _codebert

# =================================================================
# Language‑specific syntax checkers
# =================================================================

def check_python_syntax(code: str) -> Dict[str, Any]:
    result = {"errors": [], "warnings": []}
    try:
        ast.parse(code)
    except SyntaxError as e:
        result["errors"].append(f"SyntaxError: {e}")
        return result
    # Optional pylint (lightweight)
    try:
        import pylint.lint
        from pylint.reporters.text import TextReporter
        from io import StringIO
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            out = StringIO()
            reporter = TextReporter(out)
            pylint.lint.Run([f.name], reporter=reporter, exit=False)
            output = out.getvalue()
            for line in output.splitlines():
                if line.strip() and (line.startswith("E:") or line.startswith("W:")):
                    result["warnings"].append(line.strip())
            Path(f.name).unlink()
    except Exception:
        pass
    return result

def check_java_syntax(code: str) -> Dict[str, Any]:
    result = {"errors": [], "warnings": []}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        if "class Solution" not in code:
            code = "public class Solution {\n" + code + "\n}"
        f.write(code)
        fname = f.name
    try:
        proc = subprocess.run(
            ["javac", "-Xlint", fname],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            for line in proc.stderr.splitlines():
                if "error" in line.lower():
                    result["errors"].append(line.strip())
                elif "warning" in line.lower():
                    result["warnings"].append(line.strip())
        else:
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    if "warning" in line.lower():
                        result["warnings"].append(line.strip())
    except subprocess.TimeoutExpired:
        result["errors"].append("Compilation timed out.")
    except FileNotFoundError:
        result["errors"].append("Java compiler (javac) not found. Please install JDK.")
    finally:
        Path(fname).unlink(missing_ok=True)
        class_file = Path(fname).with_suffix(".class")
        if class_file.exists():
            class_file.unlink()
    return result

def check_cpp_syntax(code: str) -> Dict[str, Any]:
    result = {"errors": [], "warnings": []}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        proc = subprocess.run(
            ["g++", "-fsyntax-only", fname],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            for line in proc.stderr.splitlines():
                if "error" in line.lower():
                    result["errors"].append(line.strip())
                elif "warning" in line.lower():
                    result["warnings"].append(line.strip())
        else:
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    if "warning" in line.lower():
                        result["warnings"].append(line.strip())
    except subprocess.TimeoutExpired:
        result["errors"].append("Syntax check timed out.")
    except FileNotFoundError:
        result["errors"].append("G++ compiler not found. Please install g++.")
    finally:
        Path(fname).unlink(missing_ok=True)
    return result

def check_javascript_syntax(code: str) -> Dict[str, Any]:
    result = {"errors": [], "warnings": []}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        proc = subprocess.run(
            ["node", "--check", fname],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode != 0:
            for line in proc.stderr.splitlines():
                if "error" in line.lower():
                    result["errors"].append(line.strip())
                elif "warning" in line.lower():
                    result["warnings"].append(line.strip())
    except subprocess.TimeoutExpired:
        result["errors"].append("Syntax check timed out.")
    except FileNotFoundError:
        result["errors"].append("Node.js not found. Please install Node.js.")
    finally:
        Path(fname).unlink(missing_ok=True)
    return result

# =================================================================
# Compilation functions
# =================================================================

def compile_java(code: str, workdir: str) -> Tuple[bool, str]:
    fname = os.path.join(workdir, "Solution.java")
    with open(fname, "w") as f:
        if "class Solution" not in code:
            code = "public class Solution {\n" + code + "\n}"
        f.write(code)
    try:
        proc = subprocess.run(["javac", fname], capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return False, proc.stderr
        return True, ""
    except Exception as e:
        return False, str(e)

def compile_cpp(code: str, workdir: str) -> Tuple[bool, str]:
    fname = os.path.join(workdir, "solution.cpp")
    with open(fname, "w") as f:
        f.write(code)
    try:
        proc = subprocess.run(["g++", fname, "-o", "solution"], capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return False, proc.stderr
        return True, ""
    except Exception as e:
        return False, str(e)

# =================================================================
# Batch execution (for unit tests)
# =================================================================

def run_python_batch(code: str, test_inputs: List[Any], timeout: int = 5) -> Tuple[List[Any], List[str]]:
    """Run Python code in batch mode (using exec)."""
    outputs = []
    errors = []
    safe_globals = {"__builtins__": __builtins__}
    try:
        exec(code, safe_globals)
    except Exception as e:
        errors.append(f"Execution failed: {e}")
        return [], errors
    if "solution" not in safe_globals or not callable(safe_globals["solution"]):
        errors.append("No callable 'solution' found.")
        return [], errors
    solution = safe_globals["solution"]
    import signal
    def handler(signum, frame):
        raise TimeoutError("Timeout")
    signal.signal(signal.SIGALRM, handler)
    for inp in test_inputs:
        try:
            signal.alarm(timeout)
            if isinstance(inp, (list, tuple)):
                result = solution(*inp)
            else:
                result = solution(inp)
            signal.alarm(0)
            outputs.append(result)
        except Exception as e:
            outputs.append(None)
            errors.append(f"Test input {inp} failed: {e}")
            signal.alarm(0)
    return outputs, errors

def run_java_batch(workdir: str, test_inputs: List[Any], timeout: int = 5) -> Tuple[List[Any], List[str]]:
    outputs = []
    errors = []
    for inp in test_inputs:
        input_str = json.dumps(inp) + "\n"
        try:
            proc = subprocess.run(
                ["java", "-cp", workdir, "Solution"],
                input=input_str,
                capture_output=True, text=True, timeout=timeout
            )
            if proc.returncode != 0:
                errors.append(proc.stderr.strip())
                outputs.append(None)
            else:
                try:
                    out = json.loads(proc.stdout.strip())
                except:
                    out = proc.stdout.strip()
                outputs.append(out)
        except subprocess.TimeoutExpired:
            errors.append(f"Timeout for input {inp}")
            outputs.append(None)
        except Exception as e:
            errors.append(str(e))
            outputs.append(None)
    return outputs, errors

def run_cpp_batch(workdir: str, test_inputs: List[Any], timeout: int = 5) -> Tuple[List[Any], List[str]]:
    exe = os.path.join(workdir, "solution")
    outputs = []
    errors = []
    for inp in test_inputs:
        input_str = json.dumps(inp) + "\n"
        try:
            proc = subprocess.run(
                [exe],
                input=input_str,
                capture_output=True, text=True, timeout=timeout
            )
            if proc.returncode != 0:
                errors.append(proc.stderr.strip())
                outputs.append(None)
            else:
                try:
                    out = json.loads(proc.stdout.strip())
                except:
                    out = proc.stdout.strip()
                outputs.append(out)
        except subprocess.TimeoutExpired:
            errors.append(f"Timeout for input {inp}")
            outputs.append(None)
        except Exception as e:
            errors.append(str(e))
            outputs.append(None)
    return outputs, errors

def run_javascript_batch(workdir: str, test_inputs: List[Any], timeout: int = 5) -> Tuple[List[Any], List[str]]:
    fname = os.path.join(workdir, "solution.js")
    outputs = []
    errors = []
    for inp in test_inputs:
        input_str = json.dumps(inp) + "\n"
        try:
            proc = subprocess.run(
                ["node", fname],
                input=input_str,
                capture_output=True, text=True, timeout=timeout
            )
            if proc.returncode != 0:
                errors.append(proc.stderr.strip())
                outputs.append(None)
            else:
                try:
                    out = json.loads(proc.stdout.strip())
                except:
                    out = proc.stdout.strip()
                outputs.append(out)
        except subprocess.TimeoutExpired:
            errors.append(f"Timeout for input {inp}")
            outputs.append(None)
        except Exception as e:
            errors.append(str(e))
            outputs.append(None)
    return outputs, errors

# =================================================================
# Real‑time execution (streaming output)
# =================================================================

def run_python_real_time(code: str, timeout: int = 10) -> Generator[Tuple[str, str], None, None]:
    """Execute Python code and stream stdout/stderr line by line."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        proc = subprocess.Popen(
            ['python3', fname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.kill()
                yield ('stderr', f'[Timeout after {timeout}s]')
                break
            # Check stdout
            if select.select([proc.stdout], [], [], 0.1)[0]:
                line = proc.stdout.readline()
                if line:
                    yield ('stdout', line.rstrip())
            if select.select([proc.stderr], [], [], 0.1)[0]:
                line = proc.stderr.readline()
                if line:
                    yield ('stderr', line.rstrip())
            time.sleep(0.05)
        # Read remaining
        for line in proc.stdout:
            yield ('stdout', line.rstrip())
        for line in proc.stderr:
            yield ('stderr', line.rstrip())
    finally:
        os.unlink(fname)

def run_java_real_time(code: str, timeout: int = 10) -> Generator[Tuple[str, str], None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        fname = os.path.join(tmpdir, 'Solution.java')
        with open(fname, 'w') as f:
            if 'class Solution' not in code:
                code = 'public class Solution {\n' + code + '\n}'
            f.write(code)
        # Compile
        proc = subprocess.Popen(
            ['javac', fname],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        if proc.returncode != 0:
            yield ('stderr', 'Compilation failed:')
            for line in stderr.splitlines():
                yield ('stderr', line)
            return
        # Run
        proc = subprocess.Popen(
            ['java', '-cp', tmpdir, 'Solution'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.kill()
                yield ('stderr', f'[Timeout after {timeout}s]')
                break
            if select.select([proc.stdout], [], [], 0.1)[0]:
                line = proc.stdout.readline()
                if line:
                    yield ('stdout', line.rstrip())
            if select.select([proc.stderr], [], [], 0.1)[0]:
                line = proc.stderr.readline()
                if line:
                    yield ('stderr', line.rstrip())
            time.sleep(0.05)
        for line in proc.stdout:
            yield ('stdout', line.rstrip())
        for line in proc.stderr:
            yield ('stderr', line.rstrip())

def run_cpp_real_time(code: str, timeout: int = 10) -> Generator[Tuple[str, str], None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        fname = os.path.join(tmpdir, 'solution.cpp')
        with open(fname, 'w') as f:
            f.write(code)
        # Compile
        proc = subprocess.Popen(
            ['g++', fname, '-o', 'solution'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        if proc.returncode != 0:
            yield ('stderr', 'Compilation failed:')
            for line in stderr.splitlines():
                yield ('stderr', line)
            return
        # Run
        exe = os.path.join(tmpdir, 'solution')
        proc = subprocess.Popen(
            [exe],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.kill()
                yield ('stderr', f'[Timeout after {timeout}s]')
                break
            if select.select([proc.stdout], [], [], 0.1)[0]:
                line = proc.stdout.readline()
                if line:
                    yield ('stdout', line.rstrip())
            if select.select([proc.stderr], [], [], 0.1)[0]:
                line = proc.stderr.readline()
                if line:
                    yield ('stderr', line.rstrip())
            time.sleep(0.05)
        for line in proc.stdout:
            yield ('stdout', line.rstrip())
        for line in proc.stderr:
            yield ('stderr', line.rstrip())

def run_javascript_real_time(code: str, timeout: int = 10) -> Generator[Tuple[str, str], None, None]:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        proc = subprocess.Popen(
            ['node', fname],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.kill()
                yield ('stderr', f'[Timeout after {timeout}s]')
                break
            if select.select([proc.stdout], [], [], 0.1)[0]:
                line = proc.stdout.readline()
                if line:
                    yield ('stdout', line.rstrip())
            if select.select([proc.stderr], [], [], 0.1)[0]:
                line = proc.stderr.readline()
                if line:
                    yield ('stderr', line.rstrip())
            time.sleep(0.05)
        for line in proc.stdout:
            yield ('stdout', line.rstrip())
        for line in proc.stderr:
            yield ('stderr', line.rstrip())
    finally:
        os.unlink(fname)

# =================================================================
# Language configuration
# =================================================================

LANG_CONFIG = {
    "python": {
        "syntax": check_python_syntax,
        "compile": None,
        "batch": run_python_batch,
        "real_time": run_python_real_time,
        "extension": ".py"
    },
    "java": {
        "syntax": check_java_syntax,
        "compile": compile_java,
        "batch": run_java_batch,
        "real_time": run_java_real_time,
        "extension": ".java"
    },
    "cpp": {
        "syntax": check_cpp_syntax,
        "compile": compile_cpp,
        "batch": run_cpp_batch,
        "real_time": run_cpp_real_time,
        "extension": ".cpp"
    },
    "javascript": {
        "syntax": check_javascript_syntax,
        "compile": None,
        "batch": run_javascript_batch,
        "real_time": run_javascript_real_time,
        "extension": ".js"
    }
}

# =================================================================
# Main evaluation (batch mode)
# =================================================================

def evaluate_code(
    student_code: str,
    reference_code: str,
    test_cases: List[Dict[str, Any]] = None,
    language: str = "python",
    stream_output: bool = False
) -> Dict[str, Any]:
    """
    Comprehensive code evaluation.
    If stream_output=True, prints output in real‑time (but still returns the result dict).
    """
    config = LANG_CONFIG.get(language, LANG_CONFIG["python"])
    result = {
        "syntax_errors": [],
        "syntax_warnings": [],
        "execution_errors": [],
        "test_results": [],
        "passed_tests": 0,
        "total_tests": 0,
        "semantic_similarity": 0.0,
        "overall_score": 0.0,
        "feedback": ""
    }

    # 1. Syntax checking
    syntax = config["syntax"](student_code)
    result["syntax_errors"] = syntax["errors"]
    result["syntax_warnings"] = syntax["warnings"]
    if syntax["errors"]:
        result["overall_score"] = 0
        result["feedback"] = "Code has syntax errors; cannot execute."
        return result

    # 2. Compile if needed
    if config["compile"]:
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, err = config["compile"](student_code, tmpdir)
            if not ok:
                result["execution_errors"].append(err)
                result["overall_score"] = 0
                result["feedback"] = "Compilation failed."
                return result
            workdir = tmpdir
    else:
        # Interpreted: we need a workdir for batch/real‑time (Python uses code directly, but we can use tempdir for consistency)
        workdir = None

    # 3. Execute tests (batch mode)
    if test_cases:
        inputs_list = [tc["inputs"] for tc in test_cases]
        expected_list = [tc["expected"] for tc in test_cases]

        # If streaming is requested, we run real‑time and capture output
        if stream_output:
            print("\n🚀 Real‑time output:\n" + "-"*40)
            if language == "python":
                # Python real‑time uses code string
                gen = config["real_time"](student_code)
                # We'll capture output but also print it
                captured = []
                for stream, line in gen:
                    if stream == 'stdout':
                        print(f"> {line}")
                    else:
                        print(f"⚠️ {line}")
                    captured.append((stream, line))
                # We need to run tests separately because real‑time is interactive
                # For batch test evaluation, we still run the batch mode.
                # So we'll run batch now.
                outputs, exec_errors = config["batch"](student_code, inputs_list)
            elif workdir:
                # For Java/C++/JS, we need to write the code to a file first
                # But real‑time functions already do that. We'll just run batch separately.
                if language == "java":
                    # We need to write code to workdir/Solution.java
                    with open(os.path.join(workdir, "Solution.java"), "w") as f:
                        if "class Solution" not in student_code:
                            student_code = "public class Solution {\n" + student_code + "\n}"
                        f.write(student_code)
                    outputs, exec_errors = config["batch"](workdir, inputs_list)
                elif language == "cpp":
                    with open(os.path.join(workdir, "solution.cpp"), "w") as f:
                        f.write(student_code)
                    outputs, exec_errors = config["batch"](workdir, inputs_list)
                elif language == "javascript":
                    with open(os.path.join(workdir, "solution.js"), "w") as f:
                        f.write(student_code)
                    outputs, exec_errors = config["batch"](workdir, inputs_list)
            else:
                outputs, exec_errors = [], ["No workdir for batch"]
        else:
            # Normal batch (no streaming)
            if language == "python":
                outputs, exec_errors = config["batch"](student_code, inputs_list)
            elif workdir:
                # Ensure code is written to workdir
                if language == "java":
                    with open(os.path.join(workdir, "Solution.java"), "w") as f:
                        if "class Solution" not in student_code:
                            student_code = "public class Solution {\n" + student_code + "\n}"
                        f.write(student_code)
                elif language == "cpp":
                    with open(os.path.join(workdir, "solution.cpp"), "w") as f:
                        f.write(student_code)
                elif language == "javascript":
                    with open(os.path.join(workdir, "solution.js"), "w") as f:
                        f.write(student_code)
                outputs, exec_errors = config["batch"](workdir, inputs_list)
            else:
                outputs, exec_errors = [], ["Unknown language for batch"]

        result["execution_errors"] = exec_errors
        result["total_tests"] = len(test_cases)
        passed = 0
        for i, (inp, exp, out) in enumerate(zip(inputs_list, expected_list, outputs)):
            if out is None:
                result["test_results"].append({"input": inp, "expected": exp, "actual": None, "passed": False})
            else:
                if out == exp:
                    passed += 1
                    result["test_results"].append({"input": inp, "expected": exp, "actual": out, "passed": True})
                else:
                    result["test_results"].append({"input": inp, "expected": exp, "actual": out, "passed": False})
        result["passed_tests"] = passed
        test_score = (passed / len(test_cases)) * 100 if test_cases else 0
    else:
        test_score = 0

    # 4. Semantic similarity (CodeBERT)
    if reference_code and student_code:
        try:
            codebert = get_codebert()
            emb_student = codebert.encode(student_code, convert_to_tensor=True)
            emb_ref = codebert.encode(reference_code, convert_to_tensor=True)
            from sentence_transformers import util
            similarity = util.cos_sim(emb_student, emb_ref).item()
            similarity = max(0.0, min(1.0, similarity))
            semantic_score = similarity * 100
            result["semantic_similarity"] = round(similarity, 4)
        except:
            semantic_score = 0
    else:
        semantic_score = 0

    # 5. Style score
    style_score = 100 if not syntax["warnings"] else max(0, 100 - len(syntax["warnings"]) * 5)

    # 6. Overall score
    if test_cases and result["total_tests"] > 0:
        overall = 0.5 * test_score + 0.3 * semantic_score + 0.2 * style_score
    else:
        overall = 0.6 * semantic_score + 0.4 * style_score

    result["overall_score"] = round(overall, 2)
    return result

# =================================================================
# Detailed feedback generation (Qwen)
# =================================================================

def generate_detailed_feedback(
    student_code: str,
    reference_code: str,
    evaluation_result: Dict[str, Any],
    question: str,
    context: str
) -> str:
    from generate import _llm_generate
    prompt = f"""
You are an expert code reviewer. Analyze the student's code and provide constructive feedback.

Question: {question}

Student Code:
```python
{student_code}