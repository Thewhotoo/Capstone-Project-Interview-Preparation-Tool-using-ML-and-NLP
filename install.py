"""
One-time setup: installs everything the app needs, then checks it's ready.

    python install.py

1. Python packages from Requirements_Global.txt (same as pip install -r).
2. Ollama, the local LLM server (it isn't a Python package, so pip can't install it):
   winget on Windows, Ollama's official script on Linux, Homebrew on macOS.
3. Starts Ollama and downloads the grading model: qwen3:8b (~5.2 GB) on an NVIDIA GPU with
   about 8 GB or more, otherwise qwen3:4b (~2.5 GB). CAP_FACT_CHECK_MODEL picks one explicitly.
4. Checks the evaluator weights came down with git-LFS, and that the LLM answers.

Safe to run again: anything already installed is skipped. Uses only the
standard library, because it runs before the requirements are installed.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "main_cap", "cap")
REQUIREMENTS = os.path.join(ROOT, "Requirements_Global.txt")
WEIGHTS = os.path.join(APP_DIR, "deployed_model_overall_single_v5_1088", "best_checkpoint_weights.pt")
OLLAMA_URL = "http://localhost:11434"
BIG_MODEL, SMALL_MODEL = "qwen3:8b", "qwen3:4b"
BIG_MODEL_MIN_GPU_MB = 7500      # qwen3:8b needs ~5.2 GB plus the app's own models (~1 GB) on the GPU


def gpu_memory_mb() -> int | None:
    """Total memory of the first NVIDIA GPU in MB, or None without one (or without nvidia-smi)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15)
        return int(out.stdout.split()[0]) if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def choose_model() -> str:
    """qwen3:8b grades both rounds best (see main_cap/cap/fact_checker.py); qwen3:4b fits smaller GPUs."""
    explicit = os.environ.get("CAP_FACT_CHECK_MODEL")
    if explicit:
        return explicit
    gpu = gpu_memory_mb()
    return BIG_MODEL if gpu is not None and gpu >= BIG_MODEL_MIN_GPU_MB else SMALL_MODEL


MODEL = choose_model()


def step(n: int, text: str) -> None:
    print(f"\n[{n}/4] {text}", flush=True)


def fail(text: str) -> None:
    print(f"\nSetup stopped: {text}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> int:
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, **kwargs)


def find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidate = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    return candidate if os.path.isfile(candidate) else None


def server_up() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=3)
        return True
    except OSError:
        return False


def install_python_packages() -> None:
    step(1, "Python packages (Requirements_Global.txt)")
    if run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS]) != 0:
        fail("pip couldn't install the requirements (see the error above). "
             "On a machine without an NVIDIA GPU, see the PyTorch note at the top of Requirements_Global.txt.")


def install_ollama() -> str:
    step(2, "Ollama (local LLM server)")
    binary = find_ollama()
    if binary:
        print(f"  already installed: {binary}")
        return binary
    system = platform.system()
    if system == "Windows":
        code = run(["winget", "install", "--id", "Ollama.Ollama", "-e",
                    "--accept-source-agreements", "--accept-package-agreements"])
    elif system == "Linux":
        code = run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
    elif system == "Darwin" and shutil.which("brew"):
        code = run(["brew", "install", "ollama"])
    else:
        code = 1
    binary = find_ollama()
    if code != 0 or binary is None:
        fail("couldn't install Ollama automatically. Install it from https://ollama.com/download, "
             "then run this script again.")
    return binary


def pull_model(binary: str) -> None:
    gpu = gpu_memory_mb()
    why = f"GPU with {gpu} MB" if gpu is not None else "no NVIDIA GPU found"
    size = "~5.2 GB" if MODEL == BIG_MODEL else "~2.5 GB"
    step(3, f"Model {MODEL} ({size} the first time; {why})")
    if not server_up():
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        print("  starting the Ollama server...", flush=True)
        deadline = time.monotonic() + 60
        while not server_up() and time.monotonic() < deadline:
            time.sleep(1)
        if not server_up():
            fail("the Ollama server didn't start. Open the Ollama app (or run `ollama serve`), "
                 "then run this script again.")
    if run([binary, "pull", MODEL]) != 0:
        fail(f"couldn't download {MODEL} (check your internet connection), then run this script again.")


def verify() -> None:
    step(4, "Checking everything is ready")
    if not os.path.isfile(WEIGHTS) or os.path.getsize(WEIGHTS) < 1_000_000:
        print("  WARNING: the evaluator weights are missing or only a git-LFS pointer. Run:\n"
              "    git lfs install && git lfs pull")
    sys.path.insert(0, APP_DIR)
    from llm_requirement import LLMNotReady, ensure_llm_ready
    try:
        model = ensure_llm_ready(warm_up=lambda checker: None)
    except LLMNotReady as e:
        fail(str(e))
    print(f"  local LLM ready: {model}" if model else "  starting without the local LLM (CAP_ALLOW_NO_LLM=1)")
    print("\nSetup complete. Start the app with:\n    cd main_cap/cap\n    python app.py")


if __name__ == "__main__":
    skip_pip = "--skip-pip" in sys.argv          # e.g. when packages are managed another way
    if not skip_pip:
        install_python_packages()
    pull_model(install_ollama())
    verify()
