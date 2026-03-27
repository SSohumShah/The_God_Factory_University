"""Course tree traversal and hour/credit aggregation helpers."""
from __future__ import annotations

from core.course_tree_constants import CREDIT_HOUR_RATIO


def get_child_courses(parent_id: str, tx_func) -> list[dict]:
    """Direct children of a course."""
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM courses WHERE parent_course_id = ? ORDER BY created_at",
            (parent_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_course_tree(root_id: str, tx_func) -> list[dict]:
    """Full recursive tree using CTE. Returns flat list with depth-level ordering."""
    with tx_func() as con:
        rows = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, title, parent_course_id, depth_level, credits, pacing,
                       is_jargon_course, credit_hours, depth_target
                FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id, c.title, c.parent_course_id, c.depth_level, c.credits,
                       c.pacing, c.is_jargon_course, c.credit_hours, c.depth_target
                FROM courses c
                JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT * FROM tree ORDER BY depth_level, title
        """, (root_id,)).fetchall()
    return [dict(r) for r in rows]


def get_course_depth(course_id: str, tx_func) -> int:
    """Maximum depth of a course's sub-tree."""
    with tx_func() as con:
        row = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, 0 AS depth FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id, t.depth + 1
                FROM courses c JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT MAX(depth) AS max_depth FROM tree
        """, (course_id,)).fetchone()
    return row["max_depth"] or 0 if row else 0


def get_root_course(course_id: str, tx_func) -> str:
    """Walk up parent chain to find root course ID."""
    with tx_func() as con:
        current = course_id
        for _ in range(50):
            row = con.execute(
                "SELECT parent_course_id FROM courses WHERE id = ?", (current,)
            ).fetchone()
            if not row or not row["parent_course_id"]:
                return current
            current = row["parent_course_id"]
    return current


def course_completion_pct(course_id: str, tx_func) -> float:
    """Percentage of lectures completed across the entire sub-tree."""
    with tx_func() as con:
        row = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id FROM courses c JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT
                COUNT(l.id) AS total_lectures,
                SUM(CASE WHEN p.status = 'completed' THEN 1 ELSE 0 END) AS completed
            FROM lectures l
            JOIN tree ON l.course_id = tree.id
            LEFT JOIN progress p ON p.lecture_id = l.id
        """, (course_id,)).fetchone()
    if not row or not row["total_lectures"]:
        return 0.0
    return round((row["completed"] or 0) / row["total_lectures"] * 100, 1)


def course_credit_hours(course_id: str, tx_func) -> float:
    """Sum of logged study hours across the entire sub-tree."""
    with tx_func() as con:
        row1 = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id FROM courses c JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT COALESCE(SUM(p.watch_time_s), 0) / 3600.0 AS watch_hours
            FROM lectures l
            JOIN tree ON l.course_id = tree.id
            LEFT JOIN progress p ON p.lecture_id = l.id
        """, (course_id,)).fetchone()
        watch_hours = row1["watch_hours"] if row1 else 0.0

        row2 = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id FROM courses c JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT COALESCE(SUM(h.hours), 0) AS study_hours
            FROM study_hours_log h
            JOIN tree ON h.course_id = tree.id
        """, (course_id,)).fetchone()
        study_hours = row2["study_hours"] if row2 else 0.0

    return round(watch_hours + study_hours, 2)


def hours_to_credits(hours: float) -> float:
    """Convert total hours to credits using the Carnegie Unit standard."""
    return round(hours / CREDIT_HOUR_RATIO, 2)


def log_study_hours(course_id: str, hours: float, activity_type: str = "study",
                    notes: str = "", tx_func=None) -> None:
    """Record a study-hour entry for a course."""
    if tx_func is None:
        return
    with tx_func() as con:
        con.execute(
            "INSERT INTO study_hours_log (course_id, hours, activity_type, notes) VALUES (?, ?, ?, ?)",
            (course_id, hours, activity_type, notes),
        )


def get_study_hours(course_id: str, tx_func) -> list[dict]:
    """Get study-hour log entries for a course."""
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM study_hours_log WHERE course_id = ? ORDER BY logged_at DESC",
            (course_id,),
        ).fetchall()
    return [dict(r) for r in rows]
