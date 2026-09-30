"""
Resume Discussion engine.

Local-first redesign (see architecture review + approved plan): Gemini is
gone from this module entirely — Candidate Profile generation
(candidate_profile_generator.py) is the system's only Gemini call.

    Component 1 — TopicPool: an adaptive pool of discussion topics built
        once from the Candidate Profile, selected from (not sequenced
        through) turn by turn.
    Component 2 — local NLG: style-varied, fully-conversational templates
        phrase topics/follow-ups from grounded facts (see the note above
        `_phrase_topic_template` for why this replaced an earlier
        FLAN-T5-small rewrite step).
    Component 3 — local evaluator: SBERT relevance + KeyBERT concept
        coverage, with an NLI-based contradiction flag (see the note above
        _contradiction_flag for why NLI isn't blended into the score itself).
    Component 4 — decision policy: probe deeper / clarify / move on / skip /
        finish, driven by Component 3's score, not a fixed script.
"""

from __future__ import annotations

import logging
import random
import uuid as _uuid

logger = logging.getLogger(__name__)

# ── Session storage ──────────────────────────────────────────────────────────
_discussion_sessions = {}  # session_id -> discussion state dict

# ── Semantic model (lazy singleton) ────────────────────────────────────────
_sem_model = None
_DEDUP_THRESHOLD = 0.82  # cosine similarity above this = duplicate question

# ── Topic Pool / decision policy tuning ────────────────────────────────────
_MAX_FOLLOWUPS_PER_TOPIC = 2   # cap probing on one topic so it can't loop forever
_TARGET_QUESTION_COUNT = 12    # soft ceiling on total turns per session
_MAX_QUESTION_COUNT = 20       # hard ceiling — coverage sweep can extend past the soft target, never past this
_SKIP_THRESHOLD = 0.15         # overall_score below this = candidate isn't engaging
_PROBE_THRESHOLD = 0.55        # overall_score at/above this + missing concepts = probe deeper
_CLARIFY_LOW = 0.25            # overall_score in [_CLARIFY_LOW, _PROBE_THRESHOLD) = clarify


class DiscussionMemory:
    """Tracks interview state so the conversation feels coherent, not independent prompts.

        - projects_discussed: which projects have been covered
        - technologies_discussed: which technologies have come up
        - current_difficulty: adaptive difficulty (easy/medium/hard)
        - question_count: how many questions have been asked
    """

    def __init__(self):
        self.questions_asked: list[str] = []
        self._question_embeddings: list = []
        self.concepts_discussed: set[str] = set()
        self.concepts_mastered: set[str] = set()
        self.concepts_needing_clarification: set[str] = set()
        self.projects_discussed: set[str] = set()
        self.technologies_discussed: set[str] = set()
        self.current_difficulty: str = "medium"  # easy / medium / hard
        self.question_count: int = 0

    def add_question(self, text: str) -> bool:
        """Register a question. Returns True if it was a duplicate (should skip)."""
        if self.is_duplicate(text):
            return True
        self.questions_asked.append(text)
        self.question_count += 1
        emb = _get_sem_model()
        if emb is not None:
            e = emb.encode([text])
            self._question_embeddings.append(e[0])
        return False

    def is_duplicate(self, text: str) -> bool:
        """Check if a question is semantically similar to any already asked."""
        if not self._question_embeddings:
            return False
        model = _get_sem_model()
        if model is None:
            text_lower = text.lower()
            return any(text_lower == q.lower() for q in self.questions_asked)
        import numpy as np
        new_emb = model.encode([text])[0]
        for existing_emb in self._question_embeddings:
            dot = np.dot(new_emb, existing_emb)
            norm = np.linalg.norm(new_emb) * np.linalg.norm(existing_emb)
            sim = float(dot / norm) if norm > 0 else 0.0
            if sim >= _DEDUP_THRESHOLD:
                return True
        return False

    def mark_mastered(self, concept: str):
        self.concepts_mastered.add(concept)
        self.concepts_needing_clarification.discard(concept)

    def mark_needs_clarification(self, concept: str):
        if concept not in self.concepts_mastered:
            self.concepts_needing_clarification.add(concept)

    def mark_discussed(self, concepts: list[str]):
        for c in concepts:
            self.concepts_discussed.add(c)

    def mark_project_discussed(self, title: str):
        self.projects_discussed.add(title)

    def mark_technologies_discussed(self, techs: list[str]):
        for t in techs:
            self.technologies_discussed.add(t)

    def update_difficulty(self, recent_scores: list[float]):
        """Adjust difficulty based on recent answer quality."""
        if not recent_scores:
            self.current_difficulty = "medium"
            return
        avg = sum(recent_scores[-3:]) / len(recent_scores[-3:])
        if avg >= 0.7:
            self.current_difficulty = "hard"
        elif avg >= 0.4:
            self.current_difficulty = "medium"
        else:
            self.current_difficulty = "easy"

    def get_uncovered(self, project_concepts: list[str]) -> list[str]:
        """Return concepts from the project not yet discussed."""
        return [c for c in project_concepts if c.lower() not in
                {d.lower() for d in self.concepts_discussed}]

    def summary(self) -> dict:
        return {
            "questions_asked": list(self.questions_asked),
            "concepts_discussed": sorted(self.concepts_discussed),
            "concepts_mastered": sorted(self.concepts_mastered),
            "concepts_needing_clarification": sorted(self.concepts_needing_clarification),
            "projects_discussed": sorted(self.projects_discussed),
            "technologies_discussed": sorted(self.technologies_discussed),
            "current_difficulty": self.current_difficulty,
            "question_count": self.question_count,
        }


def _get_sem_model():
    """Lazy-load SentenceTransformer for semantic similarity evaluation."""
    global _sem_model
    if _sem_model is not None:
        return _sem_model
    try:
        from sentence_transformers import SentenceTransformer
        _sem_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("SentenceTransformer loaded for discussion evaluation")
    except Exception as e:
        logger.warning("SentenceTransformer unavailable, using fallback: %s", e)
        _sem_model = False
    return _sem_model if _sem_model is not False else None


def _semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using SentenceTransformer."""
    model = _get_sem_model()
    if model is None:
        # Fallback: word overlap ratio
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / max(len(words_a | words_b), 1)
    embs = model.encode([text_a, text_b])
    import numpy as np
    dot = np.dot(embs[0], embs[1])
    norm = np.linalg.norm(embs[0]) * np.linalg.norm(embs[1])
    return float(dot / norm) if norm > 0 else 0.0


# ═════════════════════════════════════════════════════════════════════════════
# Component 1 — Topic Pool
# ═════════════════════════════════════════════════════════════════════════════
#
# Phase 1.5 migration (Integration & Hardening): this module used to contain
# its OWN independent TopicPool implementation here — its own priority
# table, its own project/experience matching, its own selection algorithm.
# That was a second, duplicated planning implementation living alongside
# the typed Phase 1 planning subsystem (question_specification.py,
# traceability.py, coverage_tracker.py, topic_pool.py, planner.py). There is
# now exactly ONE planning implementation in this project: `TopicPool`
# below is imported from `legacy_topic_pool_adapter.py`, a thin
# compatibility wrapper that translates every call the phrasing functions
# and turn loop further down this file make (dict-shaped `unit["..."]`
# reads and in-place mutations, Chapters 11-12) into calls on the new
# `topic_pool.TopicPool` — no planning logic (priority table, matching,
# scoring, selection) is reimplemented here or in the adapter.

from legacy_topic_pool_adapter import TopicPool  # noqa: F401 (re-exported for callers of this module)


# ═════════════════════════════════════════════════════════════════════════════
# Component 2 — local question/follow-up phrasing (NLG)
# ═════════════════════════════════════════════════════════════════════════════
#
# An earlier version of this component used FLAN-T5-small to rewrite a
# grounded statement into a question, template-based rendering only as a
# fallback. In practice FLAN-T5-small repeatedly produced the opposite of
# what a senior-engineer-quality interview needs — bare "What is X?"
# definitional drift, dropped entities, near-echoes of the input — even after
# several rounds of quality-gating, and the fallback templates that actually
# fired in production were themselves terse and topic-label-like ("On
# {title} — {seed}"). Given the priority is now consistently natural,
# conversational, senior-engineer-style questions, well-crafted templates are
# the primary (and only) phrasing path: fully deterministic, so they can be
# engineered directly to the target quality bar instead of hoping a 60M-
# parameter model rewrites toward it. Variety comes from a set of question
# *styles* per category (overview, architecture, design_decision,
# implementation, debugging, optimization, tradeoffs, future_improvements,
# responsibilities, teamwork, lessons_learned, motivation, application),
# rotated so the same style never fires twice in a row.

_TOPIC_STYLES = {
    "project_overview": ["overview", "architecture", "design_decision", "future_improvements"],
    "project_deep_dive": ["implementation", "design_decision", "tradeoffs", "debugging", "optimization"],
    "skill_in_context": ["design_decision", "implementation", "tradeoffs"],
    "experience": ["responsibilities", "teamwork", "challenge", "lessons_learned"],
    "certification": ["motivation", "application"],
}

_FOLLOWUP_ANGLES = ["design_decision", "tradeoffs", "implementation", "debugging", "lessons_learned"]


def _mentions(text: str, name: str) -> bool:
    """
    Loose containment check used to enforce "questions must always mention
    the originating project or experience": exact substring match, or (for
    multi-word names) at least all-but-one of the name's significant words
    present.
    """
    if not name:
        return True
    text_lower, name_lower = text.lower(), name.lower()
    if name_lower in text_lower:
        return True
    tokens = [t for t in name_lower.split() if len(t) > 2]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in text_lower)
    return hits >= max(1, len(tokens) - 1)


def _join_naturally(items: list[str]) -> str:
    """"A, B, and C" instead of "A, B, C" — a comma-joined keyword dump reads
    like a resume bullet, not something an interviewer would actually say."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _pick_style(styles: list[str], recent_styles: list[str] | None) -> str:
    """Pick a phrasing style, avoiding whatever style was used most recently
    (any category) so consecutive questions don't read the same way — the
    "avoid asking the same style repeatedly" requirement."""
    recent_styles = recent_styles or []
    last = recent_styles[-1] if recent_styles else None
    candidates = [s for s in styles if s != last] or styles
    return random.choice(candidates)


def _origin_mention(unit: dict) -> str:
    """The specific project/experience/certification name a phrased question
    is required to reference."""
    return unit.get("source_id", "")


def _phrase_topic(unit: dict, recent_styles: list[str] | None = None) -> str:
    """
    Render a topic unit into a full, natural, senior-engineer-style interview
    question — never a topic-label prompt like "React Component Design".
    Every branch names the originating project/experience/certification
    explicitly (Resume Discussion questions must always cite exactly one
    Candidate Profile entry) and picks a question style not used on the
    immediately preceding turn. Records the chosen style on the unit itself
    (`unit["style_used"]`) so callers can feed it back into `recent_styles`
    on the next turn.
    """
    category = unit["category"]
    grounding = unit.get("grounding") or {}
    styles = _TOPIC_STYLES.get(category, ["overview"])
    style = _pick_style(styles, recent_styles)
    unit["style_used"] = style

    if category == "project_overview":
        project = grounding.get("project", {})
        title = project.get("title", "this project")
        techs = project.get("technologies", [])[:3]
        tech_str = f" using {_join_naturally(techs)}" if techs else ""
        variants = {
            "overview": [
                f"I noticed you built {title}{tech_str}. Can you walk me through what the project does and what your role was in building it?",
                f"Tell me about {title}{tech_str} — what problem was it solving, and what did you personally build?",
            ],
            "architecture": [
                f"How did you structure {title}{tech_str} — what did the overall architecture look like?",
                f"Walk me through the overall architecture of {title}{tech_str}. How did the pieces fit together?",
            ],
            "design_decision": [
                f"What were the key design decisions behind {title}{tech_str}, and why did you make them?",
                f"Looking at {title}{tech_str}, what was the most important design decision you made, and what drove it?",
            ],
            "future_improvements": [
                f"If you were to revisit {title} today, what would you change or improve, and why?",
                f"What's the next thing you'd add to {title} if you kept working on it?",
            ],
        }
        return random.choice(variants.get(style, variants["overview"]))

    if category == "project_deep_dive":
        project = grounding.get("project", {})
        title = project.get("title", "that project")
        seed_clause = (unit.get("text_seed") or "your approach").rstrip("?.").strip()
        variants = {
            "implementation": [
                f"I noticed your {title} project involved {seed_clause}. Can you walk me through how you implemented that?",
                f"How did you go about building {seed_clause} in {title}?",
            ],
            "design_decision": [
                f"Why did you take the approach you did for {seed_clause} in {title}?",
                f"What made you settle on that approach for {seed_clause} in {title}?",
            ],
            "tradeoffs": [
                f"What tradeoffs did you weigh around {seed_clause} in {title}?",
                f"Were there other options you considered for {seed_clause} in {title}, and why didn't you go with them?",
            ],
            "debugging": [
                f"Did {seed_clause} in {title} give you any trouble? How did you work through it?",
                f"What was the trickiest bug or edge case you ran into with {seed_clause} in {title}?",
            ],
            "optimization": [
                f"How did {seed_clause} hold up at scale in {title} — did you have to optimize anything there?",
                f"Did {seed_clause} in {title} ever become a performance bottleneck, and if so, what did you do about it?",
            ],
        }
        return random.choice(variants.get(style, variants["implementation"]))

    if category == "skill_in_context":
        # Technologies are never asked about standalone — always attached to
        # the specific project/experience that actually used them.
        topic = unit.get("text_seed", "this technology")
        origin = unit.get("source_id", "that project")
        context_phrase = f"in your work as {origin}" if unit.get("source_type") == "experience" else f"in your {origin} project"
        variants = {
            "design_decision": [
                f"I noticed you used {topic} {context_phrase}. What led you to choose {topic} over other options?",
                f"Why {topic} specifically {context_phrase}? What else did you consider?",
            ],
            "implementation": [
                f"How did you integrate {topic} {context_phrase}? Walk me through the implementation.",
                f"Can you walk me through how {topic} actually fit into the system {context_phrase}?",
            ],
            "tradeoffs": [
                f"You used {topic} {context_phrase} — what tradeoffs did that bring, compared to alternatives you considered?",
                f"Looking at {topic} {context_phrase}, were there any downsides you ran into?",
            ],
        }
        return random.choice(variants.get(style, variants["design_decision"]))

    if category == "experience":
        exp = grounding.get("experience", {})
        role = exp.get("role", "that role")
        company = exp.get("company", "")
        company_str = f" at {company}" if company else ""
        variants = {
            "responsibilities": [
                f"You worked as {role}{company_str}. What were your day-to-day responsibilities there?",
                f"What did a typical day look like for you as {role}{company_str}?",
            ],
            "teamwork": [
                f"During your time as {role}{company_str}, how did you collaborate with your team on technical decisions?",
                f"As {role}{company_str}, how did you work with the rest of your team day to day?",
            ],
            "challenge": [
                f"What was the most technically challenging problem you tackled as {role}{company_str}?",
                f"What's the hardest technical problem you ran into as {role}{company_str}, and how did you solve it?",
            ],
            "lessons_learned": [
                f"Looking back at your time as {role}{company_str}, what's the biggest thing you learned?",
                f"What would you tell someone starting a role like {role}{company_str} today, based on what you learned there?",
            ],
        }
        return random.choice(variants.get(style, variants["responsibilities"]))

    if category == "certification":
        cert = grounding.get("certification", {})
        name = cert.get("name", "that certification")
        variants = {
            "motivation": [
                f"What motivated you to pursue the {name} certification?",
                f"What made you decide to go after the {name} certification?",
            ],
            "application": [
                f"Has the {name} certification influenced how you approach your projects or work?",
                f"Where have you actually applied what you learned from the {name} certification?",
            ],
        }
        return random.choice(variants.get(style, variants["motivation"]))

    return "Tell me more about your background."


def _followup_target_desc(unit: dict, concepts_missing: list[str]) -> str:
    """What the follow-up is actually about: the evaluator's own
    missing-concept output when there is one (the grounding requirement for
    follow-ups), otherwise the current topic's own seed/subject — never
    something invented outside what's already on the table for this unit."""
    if concepts_missing:
        return concepts_missing[0]
    seed = unit.get("text_seed")
    if seed:
        return seed.rstrip("?.").strip()
    return "that part of your work"


def _phrase_followup(action: str, unit: dict, concepts_missing: list[str],
                      recent_styles: list[str] | None = None) -> str:
    """
    Phrase a follow-up question. The *subject* is always grounded — either
    the evaluator's specific missing-concept output, or (if nothing specific
    is missing) the current topic's own subject — never invented. The
    *angle* varies (design decision, tradeoff, implementation detail,
    debugging, lessons learned) so follow-ups explore the conversation
    instead of repeating "explain the missing concept" verbatim every time,
    and never repeats the immediately preceding style.
    """
    target_desc = _followup_target_desc(unit, concepts_missing)
    origin = unit.get("source_id", "")
    origin_phrase = f" in your {origin} project" if unit.get("source_type") == "project" and origin else (
        f" in your work as {origin}" if unit.get("source_type") == "experience" and origin else ""
    )
    angle = _pick_style(_FOLLOWUP_ANGLES, recent_styles)
    unit["style_used"] = angle

    variants = {
        "design_decision": [
            f"What led you to design {target_desc} the way you did{origin_phrase}?",
            f"Why did you approach {target_desc} that way{origin_phrase}?",
        ],
        "tradeoffs": [
            f"What tradeoffs did you weigh when working on {target_desc}{origin_phrase}?",
            f"Were there alternatives to how you handled {target_desc}{origin_phrase}, and why didn't you go with them?",
        ],
        "implementation": [
            f"Can you walk me through how you actually approached {target_desc}{origin_phrase}?",
            f"What did building out {target_desc} actually look like in practice{origin_phrase}?",
        ],
        "debugging": [
            f"Did you hit any tricky bugs or edge cases with {target_desc}{origin_phrase}, and how did you resolve them?",
            f"What was the hardest part of getting {target_desc} working{origin_phrase}?",
        ],
        "lessons_learned": [
            f"Looking back, what would you do differently with {target_desc}{origin_phrase}?",
            f"What did you take away from working on {target_desc}{origin_phrase}?",
        ],
    }
    return random.choice(variants.get(angle, variants["design_decision"]))


# ═════════════════════════════════════════════════════════════════════════════
# Component 4 — local decision policy
# ═════════════════════════════════════════════════════════════════════════════

def _decide_action(eval_result: dict, followups_used: int) -> str:
    """
    Choose probe_deeper / clarify / move_on / skip from the local evaluator's
    own score (SBERT relevance + NLI entailment + KeyBERT concept coverage —
    see Component 3). This is a transparent threshold policy over a genuine
    ML-computed signal, not a rule-based classifier standing in for judgment.
    """
    overall = eval_result.get("overall_score", 0.0)
    concepts_missing = eval_result.get("concepts_missing", [])

    if overall < _SKIP_THRESHOLD:
        return "skip"
    if followups_used >= _MAX_FOLLOWUPS_PER_TOPIC:
        return "move_on"
    if overall >= _PROBE_THRESHOLD and concepts_missing:
        return "probe_deeper"
    if _CLARIFY_LOW <= overall < _PROBE_THRESHOLD:
        return "clarify"
    return "move_on"


# ═════════════════════════════════════════════════════════════════════════════
# Component 3 — local ML evaluator (SBERT + KeyBERT, NLI as a contradiction
# flag rather than a scoring signal — see the note above _contradiction_flag)
# ═════════════════════════════════════════════════════════════════════════════
#
# Pretrained, off-the-shelf signals — nothing trained or fine-tuned:
#   1. SBERT bi-encoder cosine similarity: is the answer semantically on-topic?
#   2. KeyBERT keyphrase extraction: which grounding concepts/technologies did
#      the answer actually address, tolerant of rewording (unlike literal
#      substring matching).
#   3. NLI cross-encoder: NOT blended into the score (see note below) — used
#      only to flag likely contradictions between the answer and the
#      grounding facts as a red flag surfaced in `weaknesses`.
# Completeness/communication stay as plain text statistics (word/sentence
# count, first-person markers) — not something a model changes.

_nli_model = None
_keybert_model = None


def _get_nli_model():
    """Lazy-load a small pretrained NLI cross-encoder (ships with the
    already-installed sentence-transformers package — no new dependency)."""
    global _nli_model
    if _nli_model is not None:
        return _nli_model
    try:
        from sentence_transformers import CrossEncoder
        _nli_model = CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768")
        logger.info("NLI cross-encoder loaded for discussion evaluation")
    except Exception as e:
        logger.warning("NLI cross-encoder unavailable, entailment scoring disabled: %s", e)
        _nli_model = False
    return _nli_model if _nli_model is not False else None


def _get_keybert_model():
    """Lazy-load KeyBERT, reusing the shared SBERT singleton (_get_sem_model)
    rather than loading a second copy of the same embedding model."""
    global _keybert_model
    if _keybert_model is not None:
        return _keybert_model
    sem = _get_sem_model()
    if sem is None:
        _keybert_model = False
        return None
    try:
        from keybert import KeyBERT
        _keybert_model = KeyBERT(model=sem)
        logger.info("KeyBERT loaded for discussion evaluation (reusing shared SBERT model)")
    except Exception as e:
        logger.warning("KeyBERT unavailable, keyphrase extraction disabled: %s", e)
        _keybert_model = False
    return _keybert_model if _keybert_model is not False else None


_CONTRADICTION_THRESHOLD = 0.5

# NOTE on what NLI is (and isn't) used for here: an earlier version of this
# evaluator blended NLI *entailment strength* into the correctness score, on
# the theory that it would catch keyword-stuffed-but-vacuous answers that
# SBERT cosine similarity over-scores. Empirically it did the opposite: NLI
# cross-encoders (tested here at both nli-MiniLM2-L6-H768 and the larger
# nli-deberta-v3-small) pick up a well-documented lexical-overlap heuristic
# — a rambling answer that closely echoes the grounding text's wording reads
# as "entailment," while a genuinely well-explained answer that paraphrases
# scores as merely "neutral." That's backwards for grading answer quality,
# and it made the score *worse* than plain SBERT similarity, not better.
# NLI is reliable at a narrower, different job it's actually trained for:
# flagging outright *contradiction* (e.g. an answer that conflicts with a
# resume claim) — a real interview red flag — so that's what it's used for
# below (see `_contradiction_flag`), not as a correctness signal.


def _contradiction_flag(answer: str, ref_text: str) -> bool:
    """True if the NLI model finds the answer likely *contradicts* the
    grounding text — a genuine red flag (e.g. the candidate's account
    conflicts with what their resume/project description claims)."""
    model = _get_nli_model()
    if model is None or not answer.strip() or not ref_text.strip():
        return False
    import numpy as np
    logits = model.predict([(answer, ref_text)])[0]
    exp = np.exp(logits - np.max(logits))
    probs = exp / exp.sum()
    return float(probs[0]) >= _CONTRADICTION_THRESHOLD  # id2label: 0=contradiction


def _extract_keyphrases(text: str, top_n: int = 8) -> list[str]:
    model = _get_keybert_model()
    if model is None or not text.strip():
        return []
    try:
        pairs = model.extract_keywords(
            text, keyphrase_ngram_range=(1, 2), stop_words="english", top_n=top_n,
        )
        return [p[0] for p in pairs]
    except Exception as e:
        logger.warning("KeyBERT extraction failed: %s", e)
        return []


def _keyphrase_covers_term(keyphrases: list[str], term: str) -> bool:
    """True if an extracted keyphrase plausibly refers to `term` — exact
    substring match, or token overlap for paraphrase tolerance (e.g. an
    answer phrase 'in-memory cache' should still cover the grounding term
    'caching')."""
    term_lower = term.lower().strip()
    if not term_lower:
        return False
    term_tokens = set(term_lower.split())
    for kp in keyphrases:
        kp_lower = kp.lower()
        if term_lower in kp_lower or kp_lower in term_lower:
            return True
        if term_tokens & set(kp_lower.split()):
            return True
    return False


class EvaluationWeights:
    """
    Configurable weights + grade-band thresholds for the local evaluator —
    a single named place to tune scoring, not magic numbers scattered across
    functions. Defaults match the formula this codebase already used.
    Override via the constructor, `from_dict`, or `from_env`.
    """

    def __init__(self, correctness=0.30, technical_depth=0.25, completeness=0.20,
                 communication=0.15, concept_coverage=0.10,
                 grade_excellent=0.80, grade_good=0.60, grade_adequate=0.40, grade_weak=0.25):
        self.correctness = correctness
        self.technical_depth = technical_depth
        self.completeness = completeness
        self.communication = communication
        self.concept_coverage = concept_coverage
        self.grade_excellent = grade_excellent
        self.grade_good = grade_good
        self.grade_adequate = grade_adequate
        self.grade_weak = grade_weak

    @classmethod
    def from_dict(cls, d: dict) -> "EvaluationWeights":
        return cls(**{**cls().__dict__, **d})

    @classmethod
    def from_env(cls) -> "EvaluationWeights":
        import os
        defaults = cls()

        def f(name: str, default: float) -> float:
            v = os.environ.get(name)
            try:
                return float(v) if v else default
            except ValueError:
                return default

        return cls(
            correctness=f("CAP_EVAL_W_CORRECTNESS", defaults.correctness),
            technical_depth=f("CAP_EVAL_W_TECH_DEPTH", defaults.technical_depth),
            completeness=f("CAP_EVAL_W_COMPLETENESS", defaults.completeness),
            communication=f("CAP_EVAL_W_COMMUNICATION", defaults.communication),
            concept_coverage=f("CAP_EVAL_W_COVERAGE", defaults.concept_coverage),
        )

    def grade(self, overall: float) -> str:
        if overall >= self.grade_excellent: return "excellent"
        if overall >= self.grade_good: return "good"
        if overall >= self.grade_adequate: return "adequate"
        if overall >= self.grade_weak: return "weak"
        return "poor"


DEFAULT_EVAL_WEIGHTS = EvaluationWeights.from_env()


def _relevant_terms(question_text: str, terms: list[str], max_terms: int = 3) -> list[str]:
    """
    Scope a project's full technology/concept list down to what THIS
    question is actually about. A project can list many concepts (e.g. a
    security platform might demonstrate log analysis, attack detection, web
    development, and data visualization); a single question only ever probes
    one of those. Checking coverage against the *whole* list every turn made
    concepts_missing non-empty almost regardless of answer quality, which
    over-triggered follow-ups (see discussion_engine's decision policy).
    """
    if not terms or not question_text:
        return terms
    scored = sorted(
        ((t, _semantic_similarity(question_text, t)) for t in terms),
        key=lambda x: x[1], reverse=True,
    )
    relevant = [t for t, s in scored if s >= 0.15][:max_terms]
    return relevant or [scored[0][0]]  # never empty — always at least the closest match


def _evaluate_discussion_answer_local(
    answer: str,
    question: dict,
    project_context: dict | None = None,
    weights: EvaluationWeights = DEFAULT_EVAL_WEIGHTS,
) -> dict:
    """Local ML evaluation: SBERT relevance + KeyBERT concept coverage,
    combined via `weights`, plus an NLI-based contradiction flag (not scored
    numerically — see the note above _contradiction_flag). Replaces both the
    old Gemini rubric and the old heuristic fallback — one evaluator, one
    schema, one grade scale."""
    text = answer.strip()
    word_count = len(text.split())
    answer_lower = text.lower()

    ref_parts = []
    if project_context:
        ref_parts.append(project_context.get("title", ""))
        ref_parts.append(project_context.get("summary", ""))
        ref_parts.extend(project_context.get("technologies", []))
        ref_parts.extend(project_context.get("concepts", []))
    ref_text = " ".join(p for p in ref_parts if p)
    question_text = question.get("text", "")

    # ── 1. CORRECTNESS: SBERT relevance ─────────────────────────────────
    # (NLI is used below only to flag outright contradictions — see the
    # note above _contradiction_flag for why it isn't blended in here.)
    if ref_text:
        correctness = _semantic_similarity(text, ref_text)
    else:
        correctness = _semantic_similarity(text, question_text)
    correctness = max(0.0, min(1.0, correctness))
    contradiction = _contradiction_flag(text, ref_text) if ref_text else False

    # ── 2. TECHNICAL DEPTH / CONCEPT COVERAGE: KeyBERT ──────────────────
    answer_keyphrases = _extract_keyphrases(text) if word_count >= 4 else []
    mentioned_techs: list[str] = []
    mentioned_concepts: list[str] = []
    missing_concepts: list[str] = []
    if project_context:
        # Scoped to what THIS question is actually about, not the whole
        # project's full technology/concept list — a project with 6 concepts
        # gets asked about one at a time, so checking coverage against all 6
        # every turn made concepts_missing non-empty almost every turn
        # regardless of answer quality, over-triggering follow-ups.
        proj_techs = _relevant_terms(question_text, project_context.get("technologies", []))
        proj_concepts = _relevant_terms(question_text, project_context.get("concepts", []))
        for t in proj_techs:
            if t.lower() in answer_lower or _keyphrase_covers_term(answer_keyphrases, t):
                mentioned_techs.append(t)
        for c in proj_concepts:
            if c.lower() in answer_lower or _keyphrase_covers_term(answer_keyphrases, c):
                mentioned_concepts.append(c)
            else:
                missing_concepts.append(c)
        all_expected = proj_techs + proj_concepts
        covered = len(mentioned_techs) + len(mentioned_concepts)
        coverage = covered / len(all_expected) if all_expected else 0.5
    else:
        coverage = 0.5

    general_tech = {"api", "database", "algorithm", "architecture", "framework",
                    "server", "deployment", "testing", "optimization", "caching",
                    "security", "authentication", "encryption", "pipeline",
                    "docker", "kubernetes", "cloud", "rest", "graphql",
                    "sql", "nosql", "frontend", "backend", "performance"}
    general_hits = sum(1 for t in general_tech if t in answer_lower)
    tech_score = min(1.0, coverage + general_hits * 0.03)

    # ── 3. COMPLETENESS (plain text statistics) ─────────────────────────
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    completeness = 0.0
    if word_count < 8: completeness = 0.1
    elif word_count < 25: completeness = 0.3
    elif word_count < 60: completeness = 0.5
    elif word_count < 120: completeness = 0.7
    else: completeness = 0.85
    if len(sentences) >= 3: completeness = min(1.0, completeness + 0.1)
    if len(sentences) >= 5: completeness = min(1.0, completeness + 0.05)

    # ── 4. COMMUNICATION (plain text statistics) ────────────────────────
    has_perspective = any(w in answer_lower for w in [
        "i designed", "i built", "i implemented", "i developed",
        "i chose", "i decided", "my approach", "i was responsible",
        "i led", "i managed", "i created", "i configured", "i set up", "i integrated",
    ])
    communication = 0.35
    if len(sentences) >= 2: communication += 0.2
    if any(w in answer_lower for w in ["first", "then", "also", "because", "therefore", "however"]):
        communication += 0.15
    if has_perspective: communication += 0.15
    if word_count > 40: communication += 0.1
    communication = min(1.0, communication)

    # ── OVERALL (configurable weights) ──────────────────────────────────
    overall = (
        correctness * weights.correctness +
        tech_score * weights.technical_depth +
        completeness * weights.completeness +
        communication * weights.communication +
        coverage * weights.concept_coverage
    )
    overall = max(0.0, min(1.0, overall))
    grade = weights.grade(overall)

    strengths = []
    if correctness >= 0.65: strengths.append("Strong alignment with project context")
    elif correctness >= 0.45: strengths.append("Relevant response")
    if tech_score >= 0.5: strengths.append("Good technical terminology")
    if completeness >= 0.65: strengths.append("Detailed response")
    if communication >= 0.65: strengths.append("Well-structured communication")
    if has_perspective: strengths.append("Demonstrates personal ownership")
    if not strengths: strengths.append("Attempted to address the question")

    weaknesses = []
    if contradiction: weaknesses.append("This answer may conflict with what your resume/project description states")
    if correctness < 0.35: weaknesses.append("Does not strongly connect to project context")
    if tech_score < 0.25: weaknesses.append("Lacks specific technology mentions")
    if completeness < 0.35: weaknesses.append("Too brief — provide more detail")
    if communication < 0.45: weaknesses.append("Could improve structure and transitions")
    if not has_perspective: weaknesses.append("Use first-person to describe your contributions")
    if not weaknesses: weaknesses.append("Minor areas for deeper elaboration")

    suggested = _generate_suggested_answer(question, project_context)
    feedback = f"{'Excellent' if overall >= 0.8 else 'Good' if overall >= 0.6 else 'Adequate' if overall >= 0.4 else 'Needs improvement'} response. Strengths: {'; '.join(strengths[:2])}. Areas to improve: {'; '.join(weaknesses[:2])}."
    reasoning = f"Correctness: {correctness:.0%}\nTechnical Depth: {tech_score:.0%}\nCompleteness: {completeness:.0%}\nCommunication: {communication:.0%}\nConcept Coverage: {coverage:.0%}"

    return {
        "correctness": round(correctness, 3),
        "technical_depth": round(tech_score, 3),
        "completeness": round(completeness, 3),
        "communication": round(communication, 3),
        "confidence": round(communication, 3),  # proxy, consistent with the prior evaluator
        "concept_coverage": round(coverage, 3),
        "overall_score": round(overall, 3),
        "feedback": feedback,
        "reasoning": reasoning,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggested_answer": suggested,
        "grade": grade,
        "concepts_demonstrated": mentioned_techs + mentioned_concepts,
        "concepts_missing": missing_concepts,
        "follow_up_recommendation": "move on",
        "evaluator": "local-ml",
        "contradiction": contradiction,
    }


def _generate_suggested_answer(question: dict, project_context: dict | None) -> str:
    """Generate a suggested stronger answer based on the question and project context."""
    cat = question.get("category", "")

    if cat in ("project_overview", "project_deep_dive") and project_context:
        title = project_context.get("title", "the project")
        techs = project_context.get("technologies", [])
        concepts = project_context.get("concepts", [])
        summary = project_context.get("summary", "")

        parts = [f"In {title}, I was responsible for "]
        if summary:
            parts.append(f"building the core functionality. {summary[:150]}")
        if techs:
            parts.append(f" I primarily worked with {', '.join(techs[:4])}")
        if concepts:
            parts.append(f", applying concepts like {', '.join(concepts[:3])}")
        parts.append(".")
        return "".join(parts)

    if cat == "experience":
        exp = question.get("context", {}).get("experience", {})
        role = exp.get("role", "that role")
        company = exp.get("company", "the company")
        return (
            f"As {role} at {company}, I focused on [specific responsibility]. "
            "For example, I [specific action] which resulted in [measurable outcome]. "
            "The main technical challenge was [challenge], and I solved it by [approach]."
        )

    return (
        "A strong answer would include: (1) the specific problem you addressed, "
        "(2) the technical approach you took, (3) technologies and concepts involved, "
        "(4) the outcome or result, and (5) what you learned or would do differently."
    )


# ═════════════════════════════════════════════════════════════════════════════
# Route-facing API — thin wrappers app.py's Flask routes delegate to
# ═════════════════════════════════════════════════════════════════════════════

def _unit_context(unit: dict) -> dict:
    """Grounding context in the shape evaluation/rendering code expects."""
    return unit.get("grounding") or {}


def start_session(profile: dict, profile_session_id: str) -> tuple[dict, int]:
    """
    Start a conversational Resume Discussion session.

    Local only: builds a Topic Pool from the Candidate Profile (Component 1)
    and phrases the first question (Component 2, local templates). No Gemini
    call happens here or anywhere else in this module.
    """
    pool = TopicPool(profile)
    memory = DiscussionMemory()
    disc_session_id = f"disc_{_uuid.uuid4().hex[:12]}"

    unit = pool.select_next(last_category=None)
    if unit is None:
        return {"error": "No discussion questions could be generated from the profile."}, 400

    q_text = _phrase_topic(unit, recent_styles=pool.recent_styles)
    pool.recent_styles.append(unit.get("style_used", ""))
    logger.info("[Discussion] QUESTION 1: %r", q_text)
    memory.add_question(q_text)
    unit["status"] = "active"

    first_q = {
        "id": f"dq_{_uuid.uuid4().hex[:8]}",
        "text": q_text,
        "category": unit["category"],
        "context": _unit_context(unit),
        "topic_unit_id": unit["id"],
    }

    # `history` is a log of *completed* Q&A turns only; `current_question`
    # is the one turn awaiting an answer — explicit state, not inferred
    # from history[-1] (which is empty before the first answer).
    _discussion_sessions[disc_session_id] = {
        "profile_session_id": profile_session_id,
        "profile": profile,
        "history": [],
        "current_question": first_q,
        "pool": pool,
        "last_category": unit["category"],
        "discussion_ended": False,
        "memory": memory,
    }

    return {
        "status": "success",
        "session_id": disc_session_id,
        "question": {
            "id": first_q["id"],
            "text": first_q["text"],
            "category": first_q["category"],
        },
        "question_num": 1,
        "total_questions": _TARGET_QUESTION_COUNT,
    }, 200


def _select_and_phrase_next(pool: "TopicPool", memory: "DiscussionMemory", last_category: str | None) -> dict | None:
    """
    Pick the next pool unit and phrase it, skipping duplicate-phrasing
    collisions by trying the next-best remaining candidate. Each collision
    marks that one unit "covered" and tries again — bounded naturally by the
    pool's finite size, not by an arbitrary attempt count. A previous version
    capped this at 2 tries, which ended sessions early (e.g. one real run
    stopped after 6 questions with an entire experience entry and several
    skill_in_context units still unasked) whenever two unlucky collisions
    happened to land in a row, well before the pool was actually exhausted.
    """
    while True:
        unit = pool.select_next(last_category)
        if unit is None:
            return None
        q_text = _phrase_topic(unit, recent_styles=pool.recent_styles)
        if memory.is_duplicate(q_text):
            logger.info("[Discussion] Phrased question was a near-duplicate, discarding and re-selecting: %r", q_text)
            unit["status"] = "covered"
            continue
        pool.recent_styles.append(unit.get("style_used", ""))
        logger.info("[Discussion] QUESTION: %r", q_text)
        memory.add_question(q_text)
        unit["status"] = "active"
        return {
            "id": f"nq_{_uuid.uuid4().hex[:8]}",
            "text": q_text,
            "category": unit["category"],
            "context": _unit_context(unit),
            "topic_unit_id": unit["id"],
        }


def reply(disc_session_id: str, answer: str) -> tuple[dict, int]:
    """
    Submit an answer and receive evaluation + next question.

    Evaluates locally (Component 3 — heuristic in Phase 2, ML-based from
    Phase 3), then applies the local decision policy (Component 4) to decide
    probe deeper / clarify / move on / skip / finish and to pick the next
    topic from the pool.
    """
    session = _discussion_sessions.get(disc_session_id)
    if not session:
        return {"error": "Invalid or expired discussion session"}, 404

    if session.get("discussion_ended"):
        return {"status": "completed"}, 200

    memory: DiscussionMemory = session.get("memory", DiscussionMemory())
    history = session["history"]
    pool: TopicPool = session["pool"]

    current_q = session.get("current_question")
    if not current_q:
        return {"error": "No question to answer"}, 400
    project_ctx = current_q.get("context", {}).get("project", None)

    eval_result = _evaluate_discussion_answer_local(answer, current_q, project_ctx)
    logger.info(
        "[Discussion] EVALUATED %r -> overall=%.2f grade=%s concepts_demonstrated=%s concepts_missing=%s",
        current_q.get("text", ""), eval_result.get("overall_score", 0.0), eval_result.get("grade", ""),
        eval_result.get("concepts_demonstrated", []), eval_result.get("concepts_missing", []),
    )

    session["history"].append({
        "question_id": current_q["id"],
        "question_text": current_q["text"],
        "answer": answer,
        "score": eval_result,
        "category": current_q["category"],
        "is_followup": current_q.get("is_followup", False),
        "context": current_q.get("context", {}),
    })
    total_answered = len(session["history"])

    # ── Update memory from the local evaluation ─────────────────────────
    if project_ctx:
        memory.mark_project_discussed(project_ctx.get("title", ""))
        memory.mark_technologies_discussed(project_ctx.get("technologies", []))
    concepts_demonstrated = eval_result.get("concepts_demonstrated", [])
    concepts_missing = eval_result.get("concepts_missing", [])
    memory.mark_discussed(concepts_demonstrated + concepts_missing)
    for c in concepts_demonstrated:
        memory.mark_mastered(c)
    for c in concepts_missing:
        memory.mark_needs_clarification(c)
    memory.update_difficulty([eval_result.get("overall_score", 0.5)])

    # ── Component 4: decide what to do next ─────────────────────────────
    unit_id = current_q.get("topic_unit_id")
    unit = pool.get(unit_id) if unit_id else None
    followups_used = unit.get("followups_used", 0) if unit else _MAX_FOLLOWUPS_PER_TOPIC
    action = _decide_action(eval_result, followups_used)
    logger.info(
        "[Discussion] DECISION: action=%s (score=%.2f, followups_used=%d/%d on this topic)",
        action, eval_result.get("overall_score", 0.0), followups_used, _MAX_FOLLOWUPS_PER_TOPIC,
    )

    is_followup = False
    next_q = None

    if action in ("probe_deeper", "clarify") and unit is not None:
        followup_text = _phrase_followup(action, unit, concepts_missing, recent_styles=pool.recent_styles)
        if followup_text and not memory.is_duplicate(followup_text):
            pool.recent_styles.append(unit.get("style_used", ""))
            unit["followups_used"] += 1
            memory.add_question(followup_text)
            is_followup = True
            next_q = {
                "id": f"nq_{_uuid.uuid4().hex[:8]}",
                "text": followup_text,
                "category": current_q["category"],
                "context": current_q.get("context", {}),
                "topic_unit_id": unit["id"],
            }
        else:
            action = "move_on"  # nothing new to ask about this topic — move on instead

    if next_q is None:
        # move_on or skip: resolve the current unit, then pull the next one
        # from the pool (adaptive selection — see TopicPool.select_next).
        if unit is not None:
            unit["status"] = "skipped" if action == "skip" else "covered"
            session["last_category"] = unit["category"]

        # The session may not end at the soft target if some resume section
        # (a project, the experience entry, certifications) hasn't been
        # touched yet — it should never end before all major resume sections
        # have had reasonable coverage. The hard cap is a safety backstop,
        # not something a normal session is expected to reach.
        reached_target = total_answered >= _TARGET_QUESTION_COUNT
        reached_hard_cap = total_answered >= _MAX_QUESTION_COUNT
        if reached_hard_cap or (reached_target and pool.all_categories_covered()):
            next_q = None
        else:
            next_q = _select_and_phrase_next(pool, memory, session.get("last_category"))

        if next_q is None:
            session["discussion_ended"] = True
            return {
                "status": "success",
                "evaluation": eval_result,
                "next_question": None,
                "is_completed": True,
                "question_num": total_answered,
                "total_questions": total_answered,
            }, 200

    session["current_question"] = next_q

    return {
        "status": "success",
        "evaluation": eval_result,
        "next_question": {
            "id": next_q["id"],
            "text": next_q["text"],
            "category": next_q["category"],
        },
        "is_followup": is_followup,
        "is_completed": False,
        "question_num": total_answered + 1,
        "total_questions": total_answered + 1,
    }, 200


def end_session(disc_session_id: str) -> tuple[dict, int]:
    """End a Resume Discussion session and return the full summary."""
    session = _discussion_sessions.get(disc_session_id)
    if not session:
        return {"error": "Invalid or expired discussion session"}, 404

    history = session["history"]
    memory: DiscussionMemory = session.get("memory", DiscussionMemory())

    if not history:
        return {"error": "No discussion history available"}, 400

    # Aggregate scores
    scores = [h["score"] for h in history]
    avg_quality = sum(s["overall_score"] for s in scores) / len(scores)
    avg_tech = sum(s["technical_depth"] for s in scores) / len(scores)
    avg_comm = sum(s["communication"] for s in scores) / len(scores)
    avg_conf = sum(s.get("confidence", 0) for s in scores) / len(scores)
    avg_cov = sum(s.get("concept_coverage", 0) for s in scores) / len(scores)

    # Projects discussed — from memory (tracks what was actually discussed).
    # These are sets; copy to a list rather than slicing (a `set` has no
    # slice semantics — a prior version of this code called
    # `memory.projects_discussed[:]`, which raised TypeError on every
    # session that discussed any project).
    projects_discussed = list(memory.projects_discussed)
    technologies_demonstrated = list(memory.technologies_discussed)

    # Project-level scores from history context (each entry has context.project)
    project_scores: dict[str, list[float]] = {}
    for h in history:
        # "project" may be an explicit None (e.g. a technical_topic/verification_topic
        # unit with no matching project found) rather than simply absent, so `or {}`
        # is required here — a plain `.get("project", {})` default won't catch that.
        proj = h.get("context", {}).get("project") or {}
        p_title = proj.get("title", "")
        if p_title:
            if p_title not in project_scores:
                project_scores[p_title] = []
            project_scores[p_title].append(h["score"]["overall_score"])
            if p_title not in projects_discussed:
                projects_discussed.append(p_title)

    strongest = "N/A"
    weakest = "N/A"
    if project_scores:
        strongest = max(project_scores, key=lambda k: sum(project_scores[k]) / len(project_scores[k]))
        weakest = min(project_scores, key=lambda k: sum(project_scores[k]) / len(project_scores[k]))

    # Concepts — prefer memory-tracked data, merge with per-question scores
    concepts_mastered: list[str] = sorted(memory.concepts_mastered) if memory.concepts_mastered else []
    concepts_review: list[str] = sorted(memory.concepts_needing_clarification) if memory.concepts_needing_clarification else []

    all_concepts_demo: set[str] = set()
    all_concepts_missing: set[str] = set()
    for h in history:
        sc = h["score"]
        for c in sc.get("concepts_demonstrated", []):
            all_concepts_demo.add(c)
        for c in sc.get("concepts_missing", []):
            all_concepts_missing.add(c)

    for c in all_concepts_demo:
        if c not in concepts_mastered:
            concepts_mastered.append(c)
    for c in all_concepts_missing:
        if c not in concepts_review and c not in concepts_mastered:
            concepts_review.append(c)

    # ── Resume authenticity: how often the candidate's answers appeared to
    # contradict their own resume/project claims (NLI contradiction flag,
    # see _contradiction_flag) — a real interview red flag, aggregated here
    # rather than surfaced turn-by-turn.
    contradiction_count = sum(1 for s in scores if s.get("contradiction"))
    resume_authenticity = round((1 - contradiction_count / len(scores)) * 100, 1)

    # ── Project understanding: average correctness on project-anchored
    # questions only (project_overview / project_deep_dive / a
    # skill_in_context question whose origin was a project) — separate from
    # the overall average, which also includes experience/certification turns.
    project_related_scores = [
        h["score"]["correctness"] for h in history
        if h["category"] in ("project_overview", "project_deep_dive")
        or (h["category"] == "skill_in_context" and (h.get("context") or {}).get("project"))
    ]
    project_understanding = (
        round((sum(project_related_scores) / len(project_related_scores)) * 100, 1)
        if project_related_scores else 0.0
    )

    # ── Skills demonstrated vs. not sufficiently demonstrated: compare every
    # technology actually listed against a project on the profile to what was
    # actually discussed this session — grounded in the profile, not guessed.
    profile = session.get("profile", {})
    all_project_techs: set[str] = set()
    for p in profile.get("projects", []):
        all_project_techs.update(p.get("technologies", []))
    skills_not_demonstrated = sorted(
        t for t in all_project_techs
        if t not in technologies_demonstrated and t.lower() not in {d.lower() for d in technologies_demonstrated}
    )

    # ── Strongest areas / areas to improve: the most frequently observed
    # per-answer strengths/weaknesses across the whole session.
    strength_counts: dict[str, int] = {}
    weakness_counts: dict[str, int] = {}
    for s in scores:
        for st in s.get("strengths", []):
            strength_counts[st] = strength_counts.get(st, 0) + 1
        for wk in s.get("weaknesses", []):
            weakness_counts[wk] = weakness_counts.get(wk, 0) + 1
    strongest_areas = sorted(strength_counts, key=strength_counts.get, reverse=True)[:3]
    areas_to_improve = sorted(weakness_counts, key=weakness_counts.get, reverse=True)[:3]

    # ── Personalized feedback narrative — built entirely from this
    # session's own numbers, not a generic template.
    feedback_parts = []
    if avg_quality >= 0.75:
        feedback_parts.append("You communicated your project experience clearly and with strong technical grounding.")
    elif avg_quality >= 0.55:
        feedback_parts.append("You demonstrated a solid understanding of your projects, with some areas that could use more depth.")
    else:
        feedback_parts.append("Your answers would benefit from more specific technical detail and stronger ownership language.")
    if weakest != "N/A" and weakest != strongest:
        feedback_parts.append(f"Consider revisiting how you describe {weakest} — it scored lower than your other projects in this session.")
    if concepts_review:
        feedback_parts.append(f"Be ready to speak in more depth about: {', '.join(concepts_review[:3])}.")
    if contradiction_count:
        feedback_parts.append("A couple of your answers didn't fully line up with your resume's own description — make sure your story is consistent.")
    personalized_feedback = " ".join(feedback_parts)

    # ── Recommended focus before the Technical Interview — concrete, drawn
    # from this session's actual gaps, capped so it stays actionable.
    recommended_focus = list(dict.fromkeys(concepts_review[:3] + skills_not_demonstrated[:2]))[:5]

    # Build enriched timeline
    timeline = []
    for i, h in enumerate(history):
        sc = h["score"]
        timeline.append({
            "question_num": i + 1,
            "question": h["question_text"],
            "answer": h["answer"],
            "score": sc["overall_score"],
            "grade": sc["grade"],
            "correctness": sc.get("correctness", 0),
            "technical_depth": sc.get("technical_depth", 0),
            "completeness": sc.get("completeness", 0),
            "communication": sc.get("communication", 0),
            "concept_coverage": sc.get("concept_coverage", 0),
            "strengths": sc.get("strengths", []),
            "weaknesses": sc.get("weaknesses", []),
            "suggested_answer": sc.get("suggested_answer", ""),
            "reasoning": sc.get("reasoning", ""),
            "category": h["category"],
            "is_followup": h.get("is_followup", False),
            "evaluator": sc.get("evaluator", "unknown"),
            "concepts_demonstrated": sc.get("concepts_demonstrated", []),
            "concepts_missing": sc.get("concepts_missing", []),
            "follow_up_recommendation": sc.get("follow_up_recommendation", ""),
        })

    # Cleanup session
    _discussion_sessions.pop(disc_session_id, None)

    return {
        "status": "success",
        "projects_discussed": projects_discussed,
        "average_answer_quality": round(avg_quality * 100, 1),
        "technical_depth": round(avg_tech * 100, 1),
        "communication_score": round(avg_comm * 100, 1),
        "confidence_score": round(avg_conf * 100, 1),
        "concept_coverage_avg": round(avg_cov * 100, 1),
        "strongest_project": strongest,
        "weakest_project": weakest,
        "technologies_demonstrated": technologies_demonstrated,
        "skills_not_demonstrated": skills_not_demonstrated,
        "concepts_mastered": concepts_mastered,
        "concepts_needing_review": concepts_review,
        "resume_authenticity": resume_authenticity,
        "project_understanding": project_understanding,
        "strongest_areas": strongest_areas,
        "areas_to_improve": areas_to_improve,
        "personalized_feedback": personalized_feedback,
        "recommended_focus": recommended_focus,
        "total_questions": len(history),
        "timeline": timeline,
        "memory_summary": memory.summary(),
    }, 200
