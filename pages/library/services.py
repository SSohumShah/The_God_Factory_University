"""Data and summary helpers for the Library page."""
from __future__ import annotations

import json
from typing import Any

from core.database import get_lectures, get_modules, get_progress
from core.course_audit import get_course_readiness_audit


CourseDict = dict[str, Any]


def data_dict(course: CourseDict) -> dict:
    raw = course.get("data")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def split_root_courses(courses: list[CourseDict]) -> tuple[list[CourseDict], dict[str, list[CourseDict]]]:
    roots = [course for course in courses if not course.get("parent_course_id")]
    sub_map: dict[str, list[CourseDict]] = {}
    for course in courses:
        parent_id = course.get("parent_course_id")
        if parent_id:
            sub_map.setdefault(parent_id, []).append(course)
    return roots, sub_map


def course_summary(course: CourseDict, sub_course_map: dict[str, list[CourseDict]]) -> dict:
    modules = get_modules(course["id"])
    lecture_rows = []
    for module in modules:
        lecture_rows.extend(get_lectures(module["id"]))

    completed_lectures = 0
    for lecture in lecture_rows:
        progress = get_progress(lecture["id"])
        if progress.get("status") == "completed":
            completed_lectures += 1

    total_lectures = len(lecture_rows)
    completion_pct = round((completed_lectures / total_lectures) * 100, 1) if total_lectures else 0.0
    readiness = get_course_readiness_audit(course["id"])

    return {
        "modules": modules,
        "lectures": lecture_rows,
        "total_lectures": total_lectures,
        "completed_lectures": completed_lectures,
        "completion_pct": completion_pct,
        "children": sub_course_map.get(course["id"], []),
        "readiness": readiness,
    }


def course_index(root_courses: list[CourseDict], sub_course_map: dict[str, list[CourseDict]]) -> list[dict]:
    index: list[dict] = []
    for course in root_courses:
        summary = course_summary(course, sub_course_map)
        index.append({"course": course, "summary": summary})
    return index


def matches_query(course: CourseDict, query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    desc = course.get("description") or ""
    return q in course["title"].lower() or q in course["id"].lower() or q in desc.lower()
