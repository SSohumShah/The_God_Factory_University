"""Persistent content tracking for repetition prevention in enrichment/next-level courses.

Every generated topic, enrichment pass, and level is logged so the LLM can
be told exactly what has already been covered. This prevents the 50th
enrichment from rehashing lesson 1 topics.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "university.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    return con


def _ensure_table() -> None:
    con = _conn()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS content_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                root_course_id TEXT NOT NULL,
                course_id    TEXT,
                action       TEXT NOT NULL,
                topics       TEXT,
                level        INTEGER DEFAULT 1,
                created_at   REAL NOT NULL DEFAULT (unixepoch())
            )
        """)
        con.commit()
    finally:
        con.close()


_ensure_table()


def log_generated_content(root_course_id: str, course_id: str,
                          action: str, topics: list[str], level: int = 1) -> None:
    """Record topics generated in an enrichment or next-level pass."""
    con = _conn()
    try:
        con.execute(
            "INSERT INTO content_log (root_course_id, course_id, action, topics, level, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (root_course_id, course_id, action, json.dumps(topics), level, time.time()),
        )
        con.commit()
    finally:
        con.close()


def get_covered_topics(root_course_id: str, max_topics: int = 200) -> list[str]:
    """Return all topics already covered for a root course lineage."""
    _ensure_table()
    con = _conn()
    try:
        rows = con.execute(
            "SELECT topics FROM content_log WHERE root_course_id = ? ORDER BY created_at",
            (root_course_id,),
        ).fetchall()
    finally:
        con.close()

    all_topics: list[str] = []
    for row in rows:
        try:
            items = json.loads(row["topics"] or "[]")
            if isinstance(items, list):
                all_topics.extend(items)
        except (json.JSONDecodeError, TypeError):
            pass
    # Deduplicate while preserving order, cap at max_topics
    seen: set[str] = set()
    unique: list[str] = []
    for t in all_topics:
        low = t.lower().strip()
        if low not in seen:
            seen.add(low)
            unique.append(t)
        if len(unique) >= max_topics:
            break
    return unique


def get_level_count(root_course_id: str) -> int:
    """Return the highest level generated for this root course."""
    _ensure_table()
    con = _conn()
    try:
        row = con.execute(
            "SELECT MAX(level) as max_lvl FROM content_log WHERE root_course_id = ?",
            (root_course_id,),
        ).fetchone()
        return int(row["max_lvl"]) if row and row["max_lvl"] else 0
    finally:
        con.close()
