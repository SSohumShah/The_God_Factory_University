"""Academic ledger helpers with stricter, evidence-based rules."""
from __future__ import annotations


GRADE_SCALE = [
    ("A+", 97, 4.0), ("A", 93, 4.0), ("A-", 90, 3.7),
    ("B+", 87, 3.3), ("B", 83, 3.0), ("B-", 80, 2.7),
    ("C+", 77, 2.3), ("C", 73, 2.0), ("C-", 70, 1.7),
    ("D", 60, 1.0), ("F", 0, 0.0),
]

PASSING_PCT = 70.0
VERIFIED_ASSIGNMENT_TYPES = {"quiz", "exam", "midterm", "final", "project", "verification"}
CAPSTONE_TYPES = {"project", "final", "verification"}
RESEARCH_KEYWORDS = ("thesis", "dissertation", "research", "capstone")

DEGREE_TRACKS = {
    "Certificate": {"min_credits": 15, "min_gpa": 2.3, "min_hours": 675, "min_courses": 3, "min_passed_assignments": 6, "min_verified_assessments": 1, "requires_capstone": False, "requires_research": False},
    "Associate": {"min_credits": 60, "min_gpa": 2.5, "min_hours": 2700, "min_courses": 12, "min_passed_assignments": 24, "min_verified_assessments": 4, "requires_capstone": False, "requires_research": False},
    "Bachelor": {"min_credits": 120, "min_gpa": 3.0, "min_hours": 5400, "min_courses": 24, "min_passed_assignments": 48, "min_verified_assessments": 8, "requires_capstone": True, "requires_research": False},
    "Master": {"min_credits": 150, "min_gpa": 3.3, "min_hours": 6750, "min_courses": 30, "min_passed_assignments": 60, "min_verified_assessments": 12, "requires_capstone": True, "requires_research": True},
    "Doctorate": {"min_credits": 180, "min_gpa": 3.7, "min_hours": 8100, "min_courses": 36, "min_passed_assignments": 72, "min_verified_assessments": 16, "requires_capstone": True, "requires_research": True},
}


def score_to_grade(score: float) -> tuple[str, float]:
    for letter, threshold, points in GRADE_SCALE:
        if score >= threshold:
            return letter, points
    return "F", 0.0


def _assignment_pct(row: dict) -> float | None:
    max_score = row.get("max_score")
    score = row.get("score")
    if score is None or not max_score or max_score <= 0:
        return None
    return (score / max_score) * 100


def compute_gpa(tx_func) -> tuple[float, int]:
    with tx_func() as con:
        rows = con.execute("SELECT score, max_score, weight FROM assignments WHERE submitted_at IS NOT NULL AND score IS NOT NULL").fetchall()
    if not rows:
        return 0.0, 0
    total_points = 0.0
    total_weight = 0.0
    count = 0
    for row in rows:
        pct = _assignment_pct(dict(row))
        if pct is None:
            continue
        _, points = score_to_grade(pct)
        weight = float(row["weight"] or 1.0)
        total_points += points * weight
        total_weight += weight
        count += 1
    return (round(total_points / total_weight, 2) if total_weight else 0.0), count


def get_course_completion_audit(course_id: str, tx_func) -> dict:
    with tx_func() as con:
        course_row = con.execute("SELECT id, title, credits FROM courses WHERE id=?", (course_id,)).fetchone()
        lecture_row = con.execute(
            """SELECT COUNT(l.id) AS total_lectures,
                      SUM(CASE WHEN p.status='completed' THEN 1 ELSE 0 END) AS completed_lectures
               FROM lectures l
               LEFT JOIN progress p ON p.lecture_id = l.id
               WHERE l.course_id=?""",
            (course_id,),
        ).fetchone()
        assignment_rows = con.execute(
            "SELECT id, type, title, description, score, max_score, weight, submitted_at FROM assignments WHERE course_id=?",
            (course_id,),
        ).fetchall()
        competency_rows = con.execute(
            "SELECT AVG(score) AS avg_score, AVG(max_score) AS avg_max FROM competency_scores WHERE course_id=? GROUP BY blooms_level",
            (course_id,),
        ).fetchall()

    if not course_row:
        return {"course_id": course_id, "exists": False, "verified_complete": False, "official_credits": 0.0, "activity_credits": 0.0}

    total_lectures = int(lecture_row["total_lectures"] or 0)
    completed_lectures = int(lecture_row["completed_lectures"] or 0)
    lecture_completion_pct = (completed_lectures / total_lectures * 100.0) if total_lectures else 0.0
    activity_credits = round((course_row["credits"] or 0) * (lecture_completion_pct / 100.0), 2)

    assignments = [dict(row) for row in assignment_rows]
    total_assignments = len(assignments)
    submitted_assignments = 0
    passed_assignments = 0
    weighted_total = 0.0
    weighted_count = 0.0
    verified_assessments = 0
    capstone_completed = 0
    research_artifacts = 0

    for assignment in assignments:
        pct = _assignment_pct(assignment)
        if assignment.get("submitted_at") is not None:
            submitted_assignments += 1
        if pct is None:
            continue
        weight = float(assignment.get("weight") or 1.0)
        weighted_total += pct * weight
        weighted_count += weight
        if pct >= PASSING_PCT:
            passed_assignments += 1
            if assignment.get("type") in VERIFIED_ASSIGNMENT_TYPES:
                verified_assessments += 1
            if assignment.get("type") in CAPSTONE_TYPES:
                capstone_completed += 1
            haystack = f"{assignment.get('title', '')} {assignment.get('description', '')}".lower()
            if any(keyword in haystack for keyword in RESEARCH_KEYWORDS):
                research_artifacts += 1

    weighted_pct = round(weighted_total / weighted_count, 1) if weighted_count else 0.0
    lectures_complete = total_lectures > 0 and completed_lectures == total_lectures
    assessments_required = total_assignments > 0
    assessments_complete = assessments_required and submitted_assignments == total_assignments and weighted_pct >= PASSING_PCT
    mastery_ready = True
    if competency_rows:
        mastery_ready = all((row["avg_score"] or 0) / max(row["avg_max"] or 100, 1) * 100 >= PASSING_PCT for row in competency_rows)

    verified_complete = lectures_complete and assessments_complete and mastery_ready
    return {
        "course_id": course_row["id"],
        "title": course_row["title"],
        "credits": float(course_row["credits"] or 0),
        "total_lectures": total_lectures,
        "completed_lectures": completed_lectures,
        "lecture_completion_pct": round(lecture_completion_pct, 1),
        "total_assignments": total_assignments,
        "submitted_assignments": submitted_assignments,
        "passed_assignments": passed_assignments,
        "verified_assessments": verified_assessments,
        "weighted_pct": weighted_pct,
        "capstone_completed": capstone_completed,
        "research_artifacts": research_artifacts,
        "assessments_required": assessments_required,
        "mastery_ready": mastery_ready,
        "verified_complete": verified_complete,
        "official_credits": float(course_row["credits"] or 0) if verified_complete else 0.0,
        "activity_credits": activity_credits,
    }


def get_academic_progress_summary(tx_func) -> dict:
    with tx_func() as con:
        course_rows = con.execute("SELECT id FROM courses ORDER BY id").fetchall()
        submitted_rows = con.execute("SELECT title, description, type, score, max_score FROM assignments WHERE submitted_at IS NOT NULL").fetchall()
        watch_row = con.execute("SELECT COALESCE(SUM(watch_time_s), 0) AS total FROM progress WHERE status='completed'").fetchone()
        study_row = con.execute("SELECT COALESCE(SUM(hours), 0) AS total FROM study_hours_log").fetchone()

    audits = [get_course_completion_audit(row["id"], tx_func) for row in course_rows]
    official_credits = float(round(sum(audit["official_credits"] for audit in audits), 2))
    activity_credits = float(round(sum(audit["activity_credits"] for audit in audits), 2))
    completed_courses = sum(1 for audit in audits if audit["verified_complete"])
    lecture_complete_courses = sum(1 for audit in audits if audit["total_lectures"] > 0 and audit["completed_lectures"] == audit["total_lectures"])
    passed_assignments = 0
    verified_assessments = 0
    capstones = 0
    research_artifacts = 0

    for row in submitted_rows:
        pct = _assignment_pct(dict(row))
        if pct is None or pct < PASSING_PCT:
            continue
        passed_assignments += 1
        if row["type"] in VERIFIED_ASSIGNMENT_TYPES:
            verified_assessments += 1
        if row["type"] in CAPSTONE_TYPES:
            capstones += 1
        haystack = f"{row['title'] or ''} {row['description'] or ''}".lower()
        if any(keyword in haystack for keyword in RESEARCH_KEYWORDS):
            research_artifacts += 1

    hours_logged = round((watch_row["total"] or 0) / 3600.0 + (study_row["total"] or 0), 2)
    return {
        "official_credits": official_credits,
        "activity_credits": activity_credits,
        "completed_courses": completed_courses,
        "lecture_complete_courses": lecture_complete_courses,
        "passed_assignments": passed_assignments,
        "verified_assessments": verified_assessments,
        "capstones": capstones,
        "research_artifacts": research_artifacts,
        "hours_logged": hours_logged,
        "course_audits": audits,
    }


def credits_earned(tx_func) -> float:
    return float(get_academic_progress_summary(tx_func)["official_credits"])


def eligible_degrees(tx_func, gpa: float | None = None, credits: float | None = None) -> list[str]:
    summary = get_academic_progress_summary(tx_func)
    _gpa, count = compute_gpa(tx_func)
    gpa = _gpa if gpa is None else gpa
    official_credits = summary["official_credits"] if credits is None else credits
    if count == 0:
        return []

    eligible = []
    for degree, req in DEGREE_TRACKS.items():
        if official_credits < req["min_credits"]:
            continue
        if gpa < req["min_gpa"]:
            continue
        if summary["hours_logged"] < req["min_hours"]:
            continue
        if summary["completed_courses"] < req["min_courses"]:
            continue
        if summary["passed_assignments"] < req["min_passed_assignments"]:
            continue
        if summary["verified_assessments"] < req["min_verified_assessments"]:
            continue
        if req["requires_capstone"] and summary["capstones"] < 1:
            continue
        if req["requires_research"] and summary["research_artifacts"] < 1:
            continue
        eligible.append(degree)
    return eligible


def time_to_degree_estimate(tx_func, target_degree: str = "Bachelor") -> dict | None:
    track = DEGREE_TRACKS.get(target_degree)
    if not track:
        return None
    summary = get_academic_progress_summary(tx_func)
    credits = summary["official_credits"]
    gpa, _ = compute_gpa(tx_func)
    needed_credits = max(track["min_credits"] - credits, 0)
    needed_hours = max(track["min_hours"] - summary["hours_logged"], 0)

    with tx_func() as con:
        row = con.execute("SELECT MIN(logged_at) AS first FROM study_hours_log").fetchone()
    import time as _time
    first_log = row["first"] if row and row["first"] else None
    days_active = ((_time.time() - first_log) / 86400.0) if first_log else 0
    if days_active > 0 and credits > 0:
        rate_credits_per_day = credits / days_active
        est_days = needed_credits / rate_credits_per_day if rate_credits_per_day > 0 else 0
    else:
        rate_credits_per_day = 0
        est_days = 0

    return {
        "target": target_degree,
        "credits_earned": round(credits, 2),
        "activity_credits": round(summary["activity_credits"], 2),
        "credits_needed": round(needed_credits, 2),
        "hours_needed": round(needed_hours, 1),
        "days_active": round(days_active, 0),
        "rate_credits_per_day": round(rate_credits_per_day, 4),
        "est_days_remaining": round(est_days, 0),
        "gpa_met": gpa >= track["min_gpa"],
    }
