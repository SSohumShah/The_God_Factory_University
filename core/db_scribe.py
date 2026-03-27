"""Scribe submission persistence — one lecture transcription per course level.

Students must submit at least SCRIBE_MIN_WORDS words (≈ 1–1.5 hours of lecture
notes / transcription) once per *course level* before they can advance to the
next level.  The scribed lecture must belong to the current level — enrichment,
decomposition, and jargon courses do NOT add scribe requirements.

Extra submissions give incremental XP but do not change the gate check.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "university.db"
SCRIBE_MIN_WORDS = 10_000  # ≈ 60–90-minute lecture at ~130 wpm × 80% coverage


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    return con


def _ensure_table() -> None:
    con = _conn()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS scribe_submissions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id    TEXT NOT NULL,
                lecture_id   TEXT,
                depth_level  INTEGER DEFAULT 0,
                word_count   INTEGER NOT NULL DEFAULT 0,
                submitted_at REAL NOT NULL DEFAULT (unixepoch()),
                text_snippet TEXT
            )
        """)
        # Migration: add depth_level if table already exists without it
        cols = [r[1] for r in con.execute("PRAGMA table_info(scribe_submissions)").fetchall()]
        if "depth_level" not in cols:
            con.execute("ALTER TABLE scribe_submissions ADD COLUMN depth_level INTEGER DEFAULT 0")
        con.commit()
    finally:
        con.close()


_ensure_table()


def save_scribe(course_id: str, lecture_id: str, text: str,
                depth_level: int = 0) -> dict:
    """Persist a scribe submission. Returns summary dict."""
    words = len(text.split())
    snippet = text[:200].replace("\n", " ")
    con = _conn()
    try:
        con.execute(
            "INSERT INTO scribe_submissions "
            "(course_id, lecture_id, depth_level, word_count, submitted_at, text_snippet) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (course_id, lecture_id, depth_level, words, time.time(), snippet),
        )
        con.commit()
    finally:
        con.close()
    return {"course_id": course_id, "word_count": words,
            "depth_level": depth_level,
            "complete": words >= SCRIBE_MIN_WORDS}


def get_scribes(course_id: str) -> list[dict]:
    """Return all scribe submissions for a course, newest first."""
    _ensure_table()
    con = _conn()
    try:
        rows = con.execute(
            "SELECT * FROM scribe_submissions WHERE course_id = ? ORDER BY submitted_at DESC",
            (course_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def total_scribe_words(course_id: str) -> int:
    """Sum of all scribe word counts for this course."""
    scribes = get_scribes(course_id)
    return sum(s["word_count"] for s in scribes)


def scribe_complete(course_id: str) -> bool:
    """Return True if the student has met the minimum scribe requirement."""
    return total_scribe_words(course_id) >= SCRIBE_MIN_WORDS


# ── Per-level scribe gating ──────────────────────────────────────────────────

def level_scribe_words(course_id: str, depth_level: int) -> int:
    """Sum of scribe words submitted at a specific depth_level for a course."""
    _ensure_table()
    con = _conn()
    try:
        row = con.execute(
            "SELECT COALESCE(SUM(word_count), 0) as total "
            "FROM scribe_submissions WHERE course_id = ? AND depth_level = ?",
            (course_id, depth_level),
        ).fetchone()
        return row["total"] if row else 0
    finally:
        con.close()


def level_scribe_complete(course_id: str, depth_level: int) -> bool:
    """True if the student has a qualifying scribe at this course level.

    A qualifying scribe is a single submission of ≥ SCRIBE_MIN_WORDS from
    a lecture belonging to the given depth_level. Multiple smaller submissions
    at the same level also count if they sum to the threshold.
    """
    return level_scribe_words(course_id, depth_level) >= SCRIBE_MIN_WORDS


def get_scribe_status_for_level(course_id: str, depth_level: int) -> dict:
    """Return progress info for the scribe requirement at a given level."""
    words = level_scribe_words(course_id, depth_level)
    complete = words >= SCRIBE_MIN_WORDS
    pct = min(100, int(words / SCRIBE_MIN_WORDS * 100)) if SCRIBE_MIN_WORDS else 100
    return {
        "course_id": course_id,
        "depth_level": depth_level,
        "words_submitted": words,
        "words_required": SCRIBE_MIN_WORDS,
        "complete": complete,
        "progress_pct": pct,
    }


def verify_scribe_originality(text: str) -> dict:
    """Run a quick originality heuristic on a scribe submission.

    Checks:
    - Vocabulary diversity (unique words / total words)
    - Average sentence length variation
    - Flags if it looks like a copy-paste block (very uniform sentences)

    Returns dict with 'score' (0-100), 'passed', and 'reason'.
    """
    words = text.split()
    if not words:
        return {"score": 0, "passed": False, "reason": "Empty submission."}

    total_w = len(words)
    unique_w = len(set(w.lower() for w in words))
    diversity = unique_w / total_w

    # Sentence length variation
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if len(sentences) < 3:
        return {"score": 20, "passed": False, "reason": "Too few sentences to verify."}

    lengths = [len(s.split()) for s in sentences]
    avg_len = sum(lengths) / len(lengths)
    variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
    std_dev = variance ** 0.5

    # Score: higher diversity + higher sentence variation = more likely original
    score = int(min(100, diversity * 120 + std_dev * 2))

    if diversity < 0.15:
        return {"score": score, "passed": False, "reason": "Very low vocabulary diversity — may be repetitive or machine-generated."}
    if std_dev < 1.5 and total_w > 500:
        return {"score": score, "passed": False, "reason": "Extremely uniform sentence structure — may be copy-pasted template."}

    return {"score": score, "passed": True, "reason": "Submission appears original."}


def generate_scribe_quiz(course_title: str, text_snippet: str) -> str:
    """Generate a follow-up comprehension quiz prompt based on the scribe text."""
    return (
        f"The student scribed a lecture for '{course_title}'. "
        f"Based on this excerpt:\n\n\"{text_snippet[:800]}\"\n\n"
        f"Generate 3 short comprehension questions that test whether the student "
        f"actually understood the material they transcribed. Output ONLY the 3 questions, "
        f"numbered 1-3. No answers, no formatting."
    )
