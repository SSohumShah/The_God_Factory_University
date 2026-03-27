"""Shared media asset library — label, index, and reuse generated images.

When a student generates an image for a course, the asset is cataloged here.
Other students studying the same course can automatically reuse existing assets
instead of burning generation quota.

All sharing is opt-in. Assets are tagged with:
  - prompt hash (for dedup / fuzzy matching)
  - course_id (for course-level sharing)
  - provider (provenance)
  - permissions (private | course_shared | global)
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "data" / "asset_library.db"


def _ensure_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS media_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT NOT NULL,
            prompt TEXT NOT NULL,
            course_id TEXT,
            lecture_id TEXT,
            provider TEXT,
            file_path TEXT NOT NULL,
            width INTEGER,
            height INTEGER,
            permission TEXT DEFAULT 'private',
            created_at TEXT NOT NULL,
            reuse_count INTEGER DEFAULT 0
        )
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_assets_course ON media_assets(course_id)
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_assets_hash ON media_assets(prompt_hash)
    """)
    con.commit()
    return con


def _hash_prompt(prompt: str) -> str:
    """Normalize and hash a prompt for dedup matching."""
    normalized = " ".join(prompt.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def store_asset(prompt: str, file_path: str | Path, provider: str = "",
                course_id: str = "", lecture_id: str = "",
                width: int = 0, height: int = 0,
                permission: str = "private") -> int:
    """Store a newly generated image in the asset library. Returns asset ID."""
    con = _ensure_db()
    try:
        cur = con.execute("""
            INSERT INTO media_assets
                (prompt_hash, prompt, course_id, lecture_id, provider,
                 file_path, width, height, permission, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            _hash_prompt(prompt), prompt, course_id, lecture_id, provider,
            str(file_path), width, height, permission,
            datetime.utcnow().isoformat(),
        ))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def find_reusable_asset(prompt: str, course_id: str = "") -> dict | None:
    """Find an existing shared asset matching this prompt + course.

    Looks for exact prompt-hash matches that are shared (course or global).
    Returns asset dict or None.
    """
    con = _ensure_db()
    try:
        ph = _hash_prompt(prompt)
        # First: exact hash match shared for this course or globally
        row = con.execute("""
            SELECT id, prompt, file_path, provider, width, height, reuse_count
            FROM media_assets
            WHERE prompt_hash = ?
              AND (permission = 'global'
                   OR (permission = 'course_shared' AND course_id = ?))
            ORDER BY created_at DESC LIMIT 1
        """, (ph, course_id)).fetchone()
        if row and Path(row[2]).exists():
            con.execute("UPDATE media_assets SET reuse_count = reuse_count + 1 WHERE id = ?",
                        (row[0],))
            con.commit()
            return {
                "id": row[0], "prompt": row[1], "file_path": row[2],
                "provider": row[3], "width": row[4], "height": row[5],
                "reuse_count": row[6] + 1,
            }
        return None
    finally:
        con.close()


def get_course_assets(course_id: str, limit: int = 50) -> list[dict]:
    """Get all shared assets for a course."""
    con = _ensure_db()
    try:
        rows = con.execute("""
            SELECT id, prompt, file_path, provider, width, height,
                   permission, reuse_count, created_at
            FROM media_assets
            WHERE course_id = ? AND permission != 'private'
            ORDER BY reuse_count DESC, created_at DESC
            LIMIT ?
        """, (course_id, limit)).fetchall()
        return [
            {
                "id": r[0], "prompt": r[1], "file_path": r[2], "provider": r[3],
                "width": r[4], "height": r[5], "permission": r[6],
                "reuse_count": r[7], "created_at": r[8],
            }
            for r in rows
        ]
    finally:
        con.close()


def set_asset_permission(asset_id: int, permission: str) -> None:
    """Update sharing permission for an asset."""
    if permission not in ("private", "course_shared", "global"):
        return
    con = _ensure_db()
    try:
        con.execute("UPDATE media_assets SET permission = ? WHERE id = ?",
                    (permission, asset_id))
        con.commit()
    finally:
        con.close()


def get_library_stats() -> dict:
    """Get overall asset library statistics."""
    con = _ensure_db()
    try:
        total = con.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0]
        shared = con.execute(
            "SELECT COUNT(*) FROM media_assets WHERE permission != 'private'"
        ).fetchone()[0]
        reuses = con.execute(
            "SELECT COALESCE(SUM(reuse_count), 0) FROM media_assets"
        ).fetchone()[0]
        return {"total_assets": total, "shared_assets": shared, "total_reuses": reuses}
    finally:
        con.close()
