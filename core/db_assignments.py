"""
Assignment persistence helpers for The God Factory University.
Extracted from database.py to respect the 1000 LOC limit (DEVELOPMENT.md Rule 1).
"""
from __future__ import annotations

import json
import time
from datetime import datetime


def save_assignment(assignment: dict, tx_func) -> None:
    with tx_func() as con:
        con.execute(
            """INSERT OR REPLACE INTO assignments
               (id,lecture_id,course_id,title,description,type,due_at,max_score,data,weight,term_id)
               VALUES (:id,:lecture_id,:course_id,:title,:description,:type,:due_at,:max_score,:data,:weight,:term_id)""",
            {
                "id": assignment["id"],
                "lecture_id": assignment.get("lecture_id"),
                "course_id": assignment.get("course_id"),
                "title": assignment["title"],
                "description": assignment.get("description", ""),
                "type": assignment.get("type", "quiz"),
                "due_at": assignment.get("due_at"),
                "max_score": assignment.get("max_score", 100),
                "data": json.dumps(assignment.get("data", {})),
                "weight": assignment.get("weight", 1.0),
                "term_id": assignment.get("term_id"),
            },
        )


def submit_assignment(assignment_id: str, score: float | None, feedback: str,
                      tx_func, get_setting, add_xp_fn, unlock_fn,
                      quest_fn, check_degrees_fn) -> None:
    now = time.time()
    late_penalty = 0.0
    assignment_data: dict = {}
    max_score = None
    if get_setting("deadlines_enabled", "0") == "1":
        with tx_func() as con:
            row = con.execute("SELECT due_at, data, max_score FROM assignments WHERE id=?", (assignment_id,)).fetchone()
        if row and row["due_at"] and now > row["due_at"]:
            days_late = (now - row["due_at"]) / 86400.0
            late_penalty = min(days_late * 10.0, 50.0)
        if row and row["data"]:
            try:
                assignment_data = json.loads(row["data"])
            except (json.JSONDecodeError, TypeError, ValueError):
                assignment_data = {}
        if row:
            max_score = row["max_score"]
    else:
        with tx_func() as con:
            row = con.execute("SELECT data, max_score FROM assignments WHERE id=?", (assignment_id,)).fetchone()
        if row and row["data"]:
            try:
                assignment_data = json.loads(row["data"])
            except (json.JSONDecodeError, TypeError, ValueError):
                assignment_data = {}
        if row:
            max_score = row["max_score"]

    adjusted_score = None
    stored_feedback = ""
    if score is not None:
        adjusted_score = max(score - (score * late_penalty / 100.0), 0)
        stored_feedback = feedback
        assignment_data["grading_status"] = "graded"
    else:
        assignment_data["student_submission"] = feedback
        assignment_data["grading_status"] = "pending_review"
        assignment_data["submitted_text_at"] = now

    with tx_func() as con:
        row = con.execute("SELECT started_at FROM assignments WHERE id=?", (assignment_id,)).fetchone()
        duration = (now - row["started_at"]) if row and row["started_at"] else 0
        con.execute(
            "UPDATE assignments SET submitted_at=?, score=?, feedback=?, late_penalty=?, duration_s=?, data=? WHERE id=?",
            (now, adjusted_score, stored_feedback, late_penalty, duration, json.dumps(assignment_data), assignment_id),
        )
    unlock_fn("first_quiz")
    if adjusted_score is not None and max_score and max_score > 0 and adjusted_score >= max_score:
        unlock_fn("perfect_score")
    if datetime.now().hour < 5:
        unlock_fn("night_owl")
    add_xp_fn(50 if adjusted_score is not None else 20, f"Submitted assignment {assignment_id}", "assignment")
    quest_fn("submit_assignment")
    check_degrees_fn()


def start_assignment(assignment_id: str, tx_func) -> None:
    """Record the start time for assessment duration tracking."""
    with tx_func() as con:
        con.execute(
            "UPDATE assignments SET started_at=? WHERE id=? AND started_at IS NULL",
            (time.time(), assignment_id),
        )


def get_assessment_hours(course_id: str, tx_func) -> float:
    """Total assessment time (hours) for assignments in a course tree."""
    with tx_func() as con:
        row = con.execute("""
            WITH RECURSIVE tree AS (
                SELECT id FROM courses WHERE id = ?
                UNION ALL
                SELECT c.id FROM courses c JOIN tree t ON c.parent_course_id = t.id
            )
            SELECT COALESCE(SUM(a.duration_s), 0) / 3600.0 AS hours
            FROM assignments a
            JOIN tree ON a.course_id = tree.id
            WHERE a.duration_s > 0
        """, (course_id,)).fetchone()
    return round(row["hours"], 2) if row else 0.0


def flag_prove_it(assignment_id: str, tx_func) -> dict | None:
    """Check if a prove-it verification score is significantly lower than the original.

    Returns flagging info if the prove-it score is <70% of the original, else None.
    """
    with tx_func() as con:
        asn = con.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    if not asn or asn["type"] != "verification":
        return None
    title = asn["title"] or ""
    if not title.startswith("Prove-It:"):
        return None
    original_title = title.replace("Prove-It: ", "", 1).strip()
    with tx_func() as con:
        orig = con.execute(
            "SELECT score, max_score FROM assignments WHERE course_id=? AND title=? AND type != 'verification'",
            (asn["course_id"], original_title),
        ).fetchone()
    if not orig or not orig["max_score"] or not asn["max_score"]:
        return None
    orig_pct = (orig["score"] or 0) / orig["max_score"] * 100
    proveit_pct = (asn["score"] or 0) / asn["max_score"] * 100
    if orig_pct > 0 and proveit_pct < orig_pct * 0.7:
        return {
            "assignment_id": assignment_id,
            "original_pct": round(orig_pct, 1),
            "proveit_pct": round(proveit_pct, 1),
            "flagged": True,
            "message": f"Verification score ({proveit_pct:.0f}%) is significantly lower than original ({orig_pct:.0f}%). Review recommended.",
        }
    return None


def get_assignments(course_id: str | None, tx_func) -> list[dict]:
    with tx_func() as con:
        if course_id:
            rows = con.execute("SELECT * FROM assignments WHERE course_id=? ORDER BY due_at", (course_id,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM assignments ORDER BY due_at").fetchall()
    return [dict(r) for r in rows]


def get_overdue(now: float | None, tx_func) -> list[dict]:
    now = now or time.time()
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM assignments WHERE due_at IS NOT NULL AND due_at < ? AND submitted_at IS NULL",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]
