"""Qualification and benchmark evaluation helpers."""
from __future__ import annotations

import json
import time

from core.course_tree_competency import check_mastery
from core.course_tree_constants import BLOOMS_LEVELS
from core.course_tree_queries import course_credit_hours


def get_all_benchmarks(tx_func) -> list[dict]:
    """Return all competency benchmarks with parsed required-course lists."""
    with tx_func() as con:
        rows = con.execute("SELECT * FROM competency_benchmarks ORDER BY category, name").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["required_courses"] = json.loads(item.get("required_courses") or "[]")
        result.append(item)
    return result


def _assignment_pct(row: dict) -> float | None:
    score = row.get("score")
    max_score = row.get("max_score")
    if score is None or not max_score or max_score <= 0:
        return None
    return (score / max_score) * 100


def _course_evidence_summary(course_id: str, tx_func) -> dict:
    with tx_func() as con:
        lecture_row = con.execute(
            """SELECT COUNT(l.id) AS total_lectures,
                      SUM(CASE WHEN p.status='completed' THEN 1 ELSE 0 END) AS completed_lectures
               FROM lectures l
               LEFT JOIN progress p ON p.lecture_id = l.id
               WHERE l.course_id=?""",
            (course_id,),
        ).fetchone()
        assignment_rows = con.execute(
            "SELECT id, type, title, description, score, max_score, submitted_at FROM assignments WHERE course_id=?",
            (course_id,),
        ).fetchall()

    total_lectures = int(lecture_row["total_lectures"] or 0)
    completed_lectures = int(lecture_row["completed_lectures"] or 0)
    lecture_pct = (completed_lectures / total_lectures * 100.0) if total_lectures else 0.0
    assignments = [dict(row) for row in assignment_rows]
    total_assignments = len(assignments)
    submitted_assignments = sum(1 for item in assignments if item.get("submitted_at"))
    passed_assignments = 0
    verified_assessments = 0
    for item in assignments:
        pct = _assignment_pct(item)
        if pct is None or pct < 70.0:
            continue
        passed_assignments += 1
        if item.get("type") in {"quiz", "exam", "midterm", "final", "project", "verification"}:
            verified_assessments += 1

    mastery = check_mastery(course_id, tx_func, 70.0)
    mastery_levels = len(BLOOMS_LEVELS)
    mastered_count = len(mastery["mastered"])
    mastery_pct = (mastered_count / mastery_levels * 100.0) if mastery_levels else 0.0
    assessments_complete = total_assignments > 0 and submitted_assignments == total_assignments and passed_assignments == total_assignments
    lectures_complete = total_lectures > 0 and completed_lectures == total_lectures
    verified_complete = lectures_complete and assessments_complete and mastery["is_complete"]
    return {
        "course_id": course_id,
        "lecture_pct": round(lecture_pct, 1),
        "total_lectures": total_lectures,
        "completed_lectures": completed_lectures,
        "total_assignments": total_assignments,
        "submitted_assignments": submitted_assignments,
        "passed_assignments": passed_assignments,
        "verified_assessments": verified_assessments,
        "mastery_pct": round(mastery_pct, 1),
        "verified_complete": verified_complete,
    }


def check_qualifications(tx_func, compute_gpa_func, credits_func) -> list[dict]:
    """Evaluate all benchmarks against current student progress."""
    benchmarks = get_all_benchmarks(tx_func)
    gpa, _ = compute_gpa_func()
    results = []

    for benchmark in benchmarks:
        required = benchmark["required_courses"]
        total_required = len(required) if required else 1
        verified_count = 0
        total_hours = 0.0
        mastery_sum = 0.0
        verified_assessment_count = 0
        evidence_rows = []
        for course_id in required:
            evidence = _course_evidence_summary(course_id, tx_func)
            evidence_rows.append(evidence)
            if evidence["verified_complete"]:
                verified_count += 1
            mastery_sum += evidence["mastery_pct"]
            verified_assessment_count += evidence["verified_assessments"]
            total_hours += course_credit_hours(course_id, tx_func)

        course_pct = (verified_count / total_required * 100) if total_required else 0
        hours_pct = (total_hours / benchmark["min_hours"] * 100) if benchmark["min_hours"] else 100
        mastery_pct = (mastery_sum / len(evidence_rows)) if evidence_rows else 0
        assessment_target = max(total_required, 1)
        assessment_pct = min(verified_assessment_count / assessment_target * 100, 100)
        gpa_met = gpa >= benchmark["min_gpa"]

        progress = min(course_pct * 0.45 + mastery_pct * 0.25 + hours_pct * 0.15 + assessment_pct * 0.05 + (100 if gpa_met else 0) * 0.10, 100)

        status = "locked"
        earned_at = None
        if verified_count == total_required and mastery_pct >= 70 and hours_pct >= 100 and gpa_met:
            status = "earned"
            earned_at = time.time()
        elif progress > 0:
            status = "in_progress"

        with tx_func() as con:
            con.execute("""
                INSERT INTO qualification_progress (benchmark_id, status, progress_pct, earned_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(benchmark_id) DO UPDATE SET
                    status = excluded.status,
                    progress_pct = excluded.progress_pct,
                    earned_at = COALESCE(qualification_progress.earned_at, excluded.earned_at),
                    updated_at = excluded.updated_at
            """, (benchmark["id"], status, round(progress, 1), earned_at, time.time()))

        results.append({
            **benchmark,
            "status": status,
            "progress_pct": round(progress, 1),
            "earned_at": earned_at,
            "course_progress": f"{verified_count}/{total_required}",
            "hours_logged": round(total_hours, 1),
            "gpa_met": gpa_met,
            "verified_course_count": verified_count,
            "mastery_pct": round(mastery_pct, 1),
            "assessment_pct": round(assessment_pct, 1),
            "benchmark_evidence": evidence_rows,
        })

    return results


def get_qualifications(tx_func) -> list[dict]:
    """Get current qualification progress without recomputing."""
    with tx_func() as con:
        rows = con.execute("""
            SELECT b.*, q.status AS q_status, q.progress_pct, q.earned_at AS q_earned_at
            FROM competency_benchmarks b
            LEFT JOIN qualification_progress q ON q.benchmark_id = b.id
            ORDER BY b.category, b.name
        """).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["required_courses"] = json.loads(item.get("required_courses") or "[]")
        item["status"] = item.pop("q_status", None) or "locked"
        item["earned_at"] = item.pop("q_earned_at", None)
        result.append(item)
    return result


def get_qualification_roadmap(benchmark_id: str, tx_func) -> dict:
    """Get remaining courses needed for a specific qualification."""
    with tx_func() as con:
        row = con.execute(
            "SELECT * FROM competency_benchmarks WHERE id = ?", (benchmark_id,)
        ).fetchone()
    if not row:
        return {"error": "Benchmark not found"}

    benchmark = dict(row)
    required = json.loads(benchmark.get("required_courses") or "[]")
    completed = []
    remaining = []

    for course_id in required:
        evidence = _course_evidence_summary(course_id, tx_func)
        if evidence["verified_complete"]:
            completed.append(course_id)
        else:
            remaining.append(course_id)

    return {
        "benchmark": benchmark["name"],
        "total_required": len(required),
        "completed": completed,
        "remaining": remaining,
        "hours_needed": benchmark.get("min_hours", 0),
        "hours_logged": sum(course_credit_hours(course_id, tx_func) for course_id in required),
        "min_gpa": benchmark.get("min_gpa", 0),
        "verified_completed": len(completed),
    }


def get_benchmark_comparison(benchmark_id: str, tx_func) -> dict:
    """Compare student evidence against a benchmark using verified course audits."""
    with tx_func() as con:
        row = con.execute(
            "SELECT * FROM competency_benchmarks WHERE id = ?", (benchmark_id,)
        ).fetchone()
    if not row:
        return {"error": "Benchmark not found"}

    benchmark = dict(row)
    required = json.loads(benchmark.get("required_courses") or "[]")

    covered_courses = 0
    total_hours = 0.0
    mastery_total = 0.0
    verified_assessments = 0
    gap_topics = []
    for course_id in required:
        evidence = _course_evidence_summary(course_id, tx_func)
        if evidence["verified_complete"]:
            covered_courses += 1
        else:
            gap_topics.append(course_id)
        mastery_total += evidence["mastery_pct"]
        verified_assessments += evidence["verified_assessments"]
        total_hours += course_credit_hours(course_id, tx_func)

    total_courses = len(required)
    coverage_pct = round(covered_courses / total_courses * 100, 1) if total_courses else 0
    hours_pct = round(total_hours / benchmark["min_hours"] * 100, 1) if benchmark["min_hours"] else 100
    mastery_pct = round(mastery_total / total_courses, 1) if total_courses else 0
    assessment_target = max(total_courses, 1)
    assessment_pct = round(min(verified_assessments / assessment_target * 100, 100), 1)
    rigor_pct = round(coverage_pct * 0.45 + mastery_pct * 0.30 + hours_pct * 0.20 + assessment_pct * 0.05, 1)

    return {
        "benchmark": benchmark["name"],
        "school": benchmark.get("school_ref", ""),
        "total_topics": total_courses,
        "covered_topics": covered_courses,
        "coverage_pct": coverage_pct,
        "hours_logged": round(total_hours, 1),
        "hours_required": benchmark["min_hours"],
        "hours_pct": hours_pct,
        "mastery_pct": mastery_pct,
        "assessment_pct": assessment_pct,
        "rigor_pct": rigor_pct,
        "gap_topics": gap_topics,
    }
