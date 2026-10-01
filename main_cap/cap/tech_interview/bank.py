"""The question bank, as the app sees it: active questions only.

The bank is generated offline (rag_system/rag_tester/slide_rag/qbank.py) and
ranked by rank_bank.py; each question's "active" flag decides whether the app
may use it. Held-back questions are never served.

Location: CAP_QUESTION_BANK_DIR, or rag_system/rag_tester/question_bank.

CAP_GRADER_ENRICHMENT picks how much of the offline enrichment
(slide_rag/enrich_bank.py) the grader uses: off | replies (short correct
follow-up replies; the default) | all (also informal variants of each key
point and the question's main idea -- measured to pass wrong answers, so off).

CAP_CURATED_ONLY (default on): new interviews draw only from the hand-reviewed
best questions ("curated": true in the bank JSON; "quality_score" >= 8 out of 10,
or 7+ for a most-asked topic; with a "quality_note", reviewed 2026-09-30). Each bank file
lists them first, most-asked topics first ("interview_priority"), then by score. "0" serves
every active question again. Looking a question up by id
(question_by_id) always sees every active question, so older sessions still resolve.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "rag_system" / "rag_tester" / "question_bank"
# Measured 2026-09-30 (PROJECT_DOCUMENTATION.md §4.25): follow-up replies help (your 40 follow-ups judged
# right 30 -> 35, wrong replies accepted 8% -> 9%); key-point variants + main idea let wrong answers
# through (confidently wrong 0.21 -> 0.53, move-on agreement 357 -> 294 / 400), so they stay off.
DEFAULT_ENRICHMENT = "replies"
SUBJECT_LABELS = {"cn": "Computer Networks", "dbms": "DBMS", "dsa": "Data Structures & Algorithms",
                  "ooad": "Object-Oriented Analysis & Design", "os": "Operating Systems"}


@dataclass(frozen=True)
class KeyPoint:
    point: str
    followup: str            # "" -> no prepared follow-up for this point
    followup_answer: str
    # From slide_rag/enrich_bank.py (may be empty): informal ways students say
    # the point, and short correct replies to its follow-up.
    variants: tuple[str, ...] = ()
    followup_replies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Question:
    id: str
    subject: str
    topic_id: str
    topic: str
    difficulty: str          # easy | medium | hard
    text: str
    reference_answer: str
    key_points: tuple[KeyPoint, ...]
    confidence: float
    source_pages: tuple[int, ...] = field(default=())
    # The question's main idea in one short sentence (enrich_bank.py, written
    # without seeing the key points). An extra route to credit, never a penalty.
    core_point: str = ""
    core_variants: tuple[str, ...] = ()
    curated: bool = False    # hand-reviewed as one of the best questions (see CAP_CURATED_ONLY)
    # How often the topic comes up in placement interviews: 3 very often, 2 regularly,
    # 1 rarely (slide_rag/interview_priority.py). The selector favours higher tiers.
    interview_priority: int = 2

    @property
    def subject_label(self) -> str:
        return SUBJECT_LABELS.get(self.subject, self.subject.upper())


def bank_dir() -> Path:
    return Path(os.environ.get("CAP_QUESTION_BANK_DIR", _DEFAULT_DIR))


ENRICHMENT_MODES = ("off", "replies", "all")


def enrichment_mode() -> str:
    """CAP_GRADER_ENRICHMENT: off | replies (follow-up replies only) | all (also key-point
    variants and the main idea). "1"/"on" mean all."""
    raw = os.environ.get("CAP_GRADER_ENRICHMENT", DEFAULT_ENRICHMENT).strip().lower()
    aliases = {"0": "off", "false": "off", "no": "off", "1": "all", "true": "all", "on": "all", "yes": "all"}
    return aliases.get(raw, raw)


def _parse(item: dict, mode: str = "off") -> Question | None:
    use_replies, use_all = mode in ("replies", "all"), mode == "all"
    try:
        points = tuple(KeyPoint(str(p["point"]), str(p.get("followup") or ""), str(p.get("followup_answer") or ""),
                                tuple(str(v) for v in p.get("variants") or ()) if use_all else (),
                                tuple(str(r) for r in p.get("followup_replies") or ()) if use_replies else ())
                       for p in item["key_points"] if str(p.get("point", "")).strip())
        if not points or not str(item.get("question", "")).strip():
            return None
        core = (item.get("core_point") or {}) if use_all else {}
        return Question(
            id=str(item["id"]), subject=str(item["subject"]), topic_id=str(item["topic_id"]),
            topic=str(item["topic"]), difficulty=str(item.get("difficulty", "medium")),
            text=str(item["question"]).strip(), reference_answer=str(item.get("reference_answer", "")).strip(),
            key_points=points, confidence=float(item.get("confidence", 0.0)),
            source_pages=tuple(int(p) for p in item.get("source_pages", [])),
            core_point=str(core.get("point", "")).strip(),
            core_variants=tuple(str(v) for v in core.get("variants") or ()),
            curated=item.get("curated") is True,
            interview_priority=int(item.get("interview_priority", 2)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Skipping malformed bank question %s: %s", item.get("id"), exc)
        return None


def curated_only() -> bool:
    return os.environ.get("CAP_CURATED_ONLY", "1").strip().lower() not in ("0", "false", "no", "off")


def load_bank(directory: str | None = None, enriched: bool | str | None = None,
              curated: bool | None = None) -> tuple[Question, ...]:
    """The questions new interviews may use: the curated ones (or every ACTIVE
    question when curation is off or nothing is curated). `enriched`: a mode
    (off | replies | all), True/False for all/off, or None for CAP_GRADER_ENRICHMENT.
    `curated`: None follows CAP_CURATED_ONLY."""
    mode = enrichment_mode() if enriched is None else "all" if enriched is True else "off" if enriched is False else enriched
    if mode not in ENRICHMENT_MODES:
        logger.warning("Unknown CAP_GRADER_ENRICHMENT %r; using 'off'", mode)
        mode = "off"
    questions = _load_bank(directory, mode)
    if curated_only() if curated is None else curated:
        picked = tuple(q for q in questions if q.curated)
        if picked:
            return picked
    return questions


@lru_cache(maxsize=8)
def _load_bank(directory: str | None, enriched: str) -> tuple[Question, ...]:
    d = Path(directory) if directory else bank_dir()
    questions = []
    for path in sorted(d.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read question bank file %s: %s", path, exc)
            continue
        for item in items if isinstance(items, list) else []:
            if item.get("active", True) is not True:
                continue
            q = _parse(item, enriched)
            if q is not None:
                questions.append(q)
    logger.info("Question bank: %d active questions (%d curated) from %s (enrichment: %s)",
                len(questions), sum(q.curated for q in questions), d, enriched)
    return tuple(questions)


def question_by_id(question_id: str, directory: str | None = None) -> Question | None:
    return next((q for q in load_bank(directory, curated=False) if q.id == question_id), None)
