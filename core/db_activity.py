"""
Activity logging and analytics for The God Factory University.
Instruments key user actions for the statistics dashboard.
"""
from __future__ import annotations

import json
import time


def create_tables(tx_func) -> None:
    with tx_func() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                duration_s  REAL DEFAULT 0,
                metadata_json TEXT,
                occurred_at REAL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS student_profile (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)


def log_activity(event_type: str, tx_func, duration_s: float = 0, metadata: dict | None = None) -> None:
    with tx_func() as con:
        con.execute(
            "INSERT INTO activity_log (event_type, duration_s, metadata_json) VALUES (?, ?, ?)",
            (event_type, duration_s, json.dumps(metadata or {})),
        )


def get_activity(event_type: str | None, tx_func, limit: int = 200) -> list[dict]:
    with tx_func() as con:
        if event_type:
            rows = con.execute(
                "SELECT * FROM activity_log WHERE event_type=? ORDER BY occurred_at DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM activity_log ORDER BY occurred_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_activity_summary(tx_func) -> dict:
    """Return aggregate stats for the dashboard."""
    with tx_func() as con:
        total = con.execute("SELECT COUNT(*) as n FROM activity_log").fetchone()["n"]
        hours = con.execute("SELECT COALESCE(SUM(duration_s), 0) as s FROM activity_log").fetchone()["s"] / 3600.0
        last_event = con.execute("SELECT MAX(occurred_at) AS ts FROM activity_log").fetchone()["ts"]
        active_days = con.execute(
            "SELECT COUNT(DISTINCT date(occurred_at, 'unixepoch')) AS n FROM activity_log"
        ).fetchone()["n"]
        by_type = con.execute(
            "SELECT event_type, COUNT(*) as cnt FROM activity_log GROUP BY event_type ORDER BY cnt DESC"
        ).fetchall()
    idle_seconds = max(time.time() - last_event, 0) if last_event else None
    return {
        "total_events": total,
        "study_hours": round(hours, 1),
        "last_event_at": last_event,
        "active_days": active_days,
        "idle_seconds": idle_seconds,
        "by_type": {r["event_type"]: r["cnt"] for r in by_type},
    }


def get_daily_counts(tx_func, days: int = 30) -> list[dict]:
    """Return daily activity counts for the last N days."""
    cutoff = time.time() - days * 86400
    with tx_func() as con:
        rows = con.execute(
            "SELECT date(occurred_at, 'unixepoch') as day, COUNT(*) as cnt "
            "FROM activity_log WHERE occurred_at >= ? GROUP BY day ORDER BY day",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Student Profile helpers ──────────────────────────────────────────────────

def set_profile(key: str, value: str, tx_func) -> None:
    with tx_func() as con:
        con.execute("INSERT OR REPLACE INTO student_profile VALUES (?, ?)", (key, value))


def get_profile(key: str, tx_func, default: str = "") -> str:
    with tx_func() as con:
        row = con.execute("SELECT value FROM student_profile WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def get_all_profile(tx_func) -> dict[str, str]:
    with tx_func() as con:
        rows = con.execute("SELECT * FROM student_profile").fetchall()
    return {r["key"]: r["value"] for r in rows}
