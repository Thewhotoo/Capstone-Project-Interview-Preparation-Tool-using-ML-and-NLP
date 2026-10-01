import sys
from pathlib import Path

# make `slide_rag` importable when pytest is run from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
