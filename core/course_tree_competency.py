"""Bloom's taxonomy competency scoring helpers."""
from __future__ import annotations

import time

from core.course_tree_constants import BLOOMS_LEVELS


def record_competency_score(course_id: str, blooms_level: str, score: float,
                            max_score: float = 100, assessment_id: str = "",
                            tx_func=None) -> None:
    """Record a competency score at a Bloom's taxonomy level for a course."""
    if blooms_level not in BLOOMS_LEVELS:
        return
    if tx_func is None:
        return
    with tx_func() as con:
        con.execute("""
            INSERT INTO competency_scores (course_id, blooms_level, score, max_score, assessment_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_id, blooms_level, assessment_id) DO UPDATE SET
                score = excluded.score,
                max_score = excluded.max_score,
                updated_at = excluded.updated_at
        """, (course_id, blooms_level, score, max_score, assessment_id, time.time()))


def get_competency_profile(course_id: str, tx_func) -> dict:
    """Get average competency scores per Bloom's level for a course."""
    with tx_func() as con:
        rows = con.execute("""
            SELECT blooms_level,
                   AVG(score) AS avg_score,
                   AVG(max_score) AS avg_max,
                   COUNT(*) AS assessments
            FROM competency_scores
            WHERE course_id = ?
            GROUP BY blooms_level
        """, (course_id,)).fetchall()
    profile = {}
    for level in BLOOMS_LEVELS:
        profile[level] = {"avg_score": 0, "avg_max": 100, "assessments": 0, "pct": 0}
    for row in rows:
        item = dict(row)
        level = item["blooms_level"]
        pct = round((item["avg_score"] / item["avg_max"] * 100) if item["avg_max"] else 0, 1)
        profile[level] = {
            "avg_score": round(item["avg_score"], 1),
            "avg_max": round(item["avg_max"], 1),
            "assessments": item["assessments"],
            "pct": pct,
        }
    return profile


def check_mastery(course_id: str, tx_func, min_pct: float = 70.0) -> dict:
    """Check if minimum competency was met across all Bloom's levels."""
    profile = get_competency_profile(course_id, tx_func)
    mastered_levels = []
    failed_levels = []
    untested_levels = []
    for level in BLOOMS_LEVELS:
        data = profile[level]
        if data["assessments"] == 0:
            untested_levels.append(level)
        elif data["pct"] >= min_pct:
            mastered_levels.append(level)
        else:
            failed_levels.append(level)
    return {
        "course_id": course_id,
        "mastered": mastered_levels,
        "failed": failed_levels,
        "untested": untested_levels,
        "is_complete": len(failed_levels) == 0 and len(untested_levels) == 0,
        "profile": profile,
    }
