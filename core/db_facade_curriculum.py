"""Curriculum-facing database facade helpers extracted from core.database."""
from __future__ import annotations

import json


def make_curriculum_facade(*,
                           tx,
                           get_child_courses_raw,
                           get_course_tree_raw,
                           get_course_depth_raw,
                           get_root_course_raw,
                           course_completion_pct_raw,
                           course_credit_hours_raw,
                           log_study_hours_raw,
                           get_study_hours_raw,
                           check_qualifications_raw,
                           get_qualifications_raw,
                           get_all_benchmarks_raw,
                           get_qualification_roadmap_raw,
                           get_pacing_for_course_raw,
                           record_competency_score_raw,
                           get_competency_profile_raw,
                           check_mastery_raw,
                           time_to_degree_estimate_raw,
                           get_benchmark_comparison_raw,
                           compute_gpa,
                           credits_earned):
    """Bind curriculum-facing wrappers to the canonical database dependencies."""

    def upsert_course(course_id: str, title: str, description: str, credits: int, data: dict,
                      source: str = "imported", parent_course_id: str | None = None,
                      depth_level: int = 0, depth_target: int = 0, pacing: str = "standard",
                      is_jargon_course: int = 0, jargon: str | None = None) -> None:
        with tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO courses "
                "(id,title,description,credits,data,source,parent_course_id,depth_level,"
                "depth_target,pacing,is_jargon_course,jargon) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (course_id, title, description, credits, json.dumps(data), source,
                 parent_course_id, depth_level, depth_target, pacing,
                 is_jargon_course, jargon),
            )

    def upsert_module(module_id: str, course_id: str, title: str, order_index: int, data: dict) -> None:
        with tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO modules (id,course_id,title,order_index,data) VALUES (?,?,?,?,?)",
                (module_id, course_id, title, order_index, json.dumps(data)),
            )

    def upsert_lecture(lecture_id: str, module_id: str, course_id: str, title: str,
                       duration_min: int, order_index: int, data: dict) -> None:
        with tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO lectures (id,module_id,course_id,title,duration_min,order_index,data) VALUES (?,?,?,?,?,?,?)",
                (lecture_id, module_id, course_id, title, duration_min, order_index, json.dumps(data)),
            )

    def get_all_courses() -> list[dict]:
        with tx() as con:
            rows = con.execute("SELECT * FROM courses ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def get_course(course_id: str) -> dict | None:
        with tx() as con:
            row = con.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        return dict(row) if row else None

    def get_modules(course_id: str) -> list[dict]:
        with tx() as con:
            rows = con.execute("SELECT * FROM modules WHERE course_id=? ORDER BY order_index", (course_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_lectures(module_id: str) -> list[dict]:
        with tx() as con:
            rows = con.execute("SELECT * FROM lectures WHERE module_id=? ORDER BY order_index", (module_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_lecture(lecture_id: str) -> dict | None:
        with tx() as con:
            row = con.execute("SELECT * FROM lectures WHERE id=?", (lecture_id,)).fetchone()
        return dict(row) if row else None

    def delete_course(course_id: str) -> None:
        with tx() as con:
            con.execute("DELETE FROM courses WHERE id=?", (course_id,))

    def get_child_courses(parent_id: str) -> list[dict]:
        return get_child_courses_raw(parent_id, tx)

    def get_course_tree(root_id: str) -> list[dict]:
        return get_course_tree_raw(root_id, tx)

    def get_course_depth(course_id: str) -> int:
        return get_course_depth_raw(course_id, tx)

    def get_root_course(course_id: str) -> str:
        return get_root_course_raw(course_id, tx)

    def course_completion_pct(course_id: str) -> float:
        return course_completion_pct_raw(course_id, tx)

    def course_credit_hours(course_id: str) -> float:
        return course_credit_hours_raw(course_id, tx)

    def log_study_hours(course_id: str, hours: float, activity_type: str = "study", notes: str = "") -> None:
        log_study_hours_raw(course_id, hours, activity_type, notes, tx_func=tx)

    def get_study_hours(course_id: str) -> list[dict]:
        return get_study_hours_raw(course_id, tx)

    def check_qualifications() -> list[dict]:
        return check_qualifications_raw(tx, compute_gpa, credits_earned)

    def get_qualifications() -> list[dict]:
        return get_qualifications_raw(tx)

    def get_all_benchmarks() -> list[dict]:
        return get_all_benchmarks_raw(tx)

    def get_qualification_roadmap(benchmark_id: str) -> dict:
        return get_qualification_roadmap_raw(benchmark_id, tx)

    def get_pacing_for_course(course_id: str) -> str:
        return get_pacing_for_course_raw(course_id, tx)

    def record_competency_score(course_id: str, blooms_level: str, score: float,
                                max_score: float = 100, assessment_id: str = "") -> None:
        record_competency_score_raw(course_id, blooms_level, score, max_score, assessment_id, tx_func=tx)

    def get_competency_profile(course_id: str) -> dict:
        return get_competency_profile_raw(course_id, tx)

    def check_mastery(course_id: str, min_pct: float = 70.0) -> dict:
        return check_mastery_raw(course_id, tx, min_pct)

    def time_to_degree_estimate(target_degree: str = "Bachelor") -> dict | None:
        return time_to_degree_estimate_raw(tx, target_degree)

    def get_benchmark_comparison(benchmark_id: str) -> dict:
        return get_benchmark_comparison_raw(benchmark_id, tx)

    return {
        "upsert_course": upsert_course,
        "upsert_module": upsert_module,
        "upsert_lecture": upsert_lecture,
        "get_all_courses": get_all_courses,
        "get_course": get_course,
        "get_modules": get_modules,
        "get_lectures": get_lectures,
        "get_lecture": get_lecture,
        "delete_course": delete_course,
        "get_child_courses": get_child_courses,
        "get_course_tree": get_course_tree,
        "get_course_depth": get_course_depth,
        "get_root_course": get_root_course,
        "course_completion_pct": course_completion_pct,
        "course_credit_hours": course_credit_hours,
        "log_study_hours": log_study_hours,
        "get_study_hours": get_study_hours,
        "check_qualifications": check_qualifications,
        "get_qualifications": get_qualifications,
        "get_all_benchmarks": get_all_benchmarks,
        "get_qualification_roadmap": get_qualification_roadmap,
        "get_pacing_for_course": get_pacing_for_course,
        "record_competency_score": record_competency_score,
        "get_competency_profile": get_competency_profile,
        "check_mastery": check_mastery,
        "time_to_degree_estimate": time_to_degree_estimate,
        "get_benchmark_comparison": get_benchmark_comparison,
    }