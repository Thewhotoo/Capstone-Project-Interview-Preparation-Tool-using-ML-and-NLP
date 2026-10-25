"""
V3 Grounding Lookup — Phase 6 wiring.

Single, shared `example_id -> grounding fragment` resolver used by the
training-time `TrainingExample` builder
(`four_dim_experiment_split._to_training_example`). Inference automatically
gets the SAME grounding because `EvaluationRequest.specification` is built
by directly reusing `TrainingExample.inputs.specification` (see
`run_four_dim_training.py`'s evaluator smoke test) — there is exactly one
place a grounding fragment is ever attached to an `example_id`, this
module, so training and inference cannot drift apart.

READ-ONLY with respect to the validated artifact
`artifacts/v3_grounding/grounding_proposals.jsonl`: this module only reads
it, never writes it, never regenerates it, never invents a fallback. If an
`example_id` has no proposal (all 18 single-example projects, plus the 178
multi-example examples with no safe cross-sibling fragment), the resolver
returns `""` — `ProjectGrounding.summary`'s own default — which is byte-for-
byte the pre-V3 baseline behavior (title + technologies only, via
`grounding_to_text`'s existing empty-string handling).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
GROUNDING_PROPOSALS_PATH = os.path.join(
    _HERE, "artifacts", "v3_grounding", "grounding_proposals.jsonl"
)


@lru_cache(maxsize=1)
def _load_proposals() -> dict:
    """Loads and caches the validated grounding-proposal artifact, keyed by
    `example_id`. Cached because it's a static, already-validated file (not
    something that changes mid-run) — re-reading it per example would be
    wasted I/O, not a correctness concern either way."""
    if not os.path.exists(GROUNDING_PROPOSALS_PATH):
        return {}
    proposals: dict = {}
    with open(GROUNDING_PROPOSALS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            proposals[rec["example_id"]] = rec
    return proposals


def grounding_summary_for(example_id: str) -> str:
    """Returns the validated, question-scoped grounding fragment text for
    `example_id`, or `""` if none exists. Never invents a fallback."""
    proposal = _load_proposals().get(example_id)
    return proposal["grounding_text"] if proposal else ""


def grounding_proposal_for(example_id: str) -> Optional[dict]:
    """Returns the full proposal record (example_id, source_id,
    grounding_text, evidence_example_ids, grounding_scope, confidence) for
    `example_id`, or `None` if it was not enriched. Exposed for tests/audits
    that need the evidence chain, not just the text."""
    return _load_proposals().get(example_id)


def reset_cache_for_tests() -> None:
    """Test-only helper to force a re-read of the artifact (e.g. after a
    test writes a temporary proposals file to a monkeypatched path)."""
    _load_proposals.cache_clear()
