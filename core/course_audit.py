"""Course completeness and AI-readiness auditing."""
from __future__ import annotations

import json


def _db():
    import core.database as db
    return db


def get_course_readiness_audit(course_id: str) -> dict:
    db = _db()
    course = db.get_course(course_id)
    if not course:
        return {"course_id": course_id, "exists": False, "ai_ready": False, "required_missing": ["course_missing"]}

    raw_data = course.get("data")
    data = json.loads(raw_data) if isinstance(raw_data, str) and raw_data else (raw_data or {})
    modules = db.get_modules(course_id)
    lectures = []
    for module in modules:
        lectures.extend(db.get_lectures(module["id"]))

    required_missing: list[str] = []
    recommended_missing: list[str] = []
    lecture_checks = {
        "learning_objectives": 0,
        "core_terms": 0,
        "assessment": 0,
        "video_recipe": 0,
        "scene_blocks": 0,
        "coding_lab": 0,
    }

    if not (course.get("description") or data.get("description")):
        required_missing.append("course_description")
    if not modules:
        required_missing.append("modules")
    if not lectures:
        required_missing.append("lectures")

    for lecture in lectures:
        lecture_data = lecture.get("data")
        lecture_data = json.loads(lecture_data) if isinstance(lecture_data, str) and lecture_data else (lecture_data or {})
        if lecture_data.get("learning_objectives"):
            lecture_checks["learning_objectives"] += 1
        if lecture_data.get("core_terms"):
            lecture_checks["core_terms"] += 1
        if lecture_data.get("assessment"):
            lecture_checks["assessment"] += 1
        if lecture_data.get("video_recipe"):
            lecture_checks["video_recipe"] += 1
            if lecture_data.get("video_recipe", {}).get("scene_blocks"):
                lecture_checks["scene_blocks"] += 1
        if lecture_data.get("coding_lab"):
            lecture_checks["coding_lab"] += 1

    total_lectures = len(lectures)
    if total_lectures:
        for field in ("learning_objectives", "core_terms", "assessment", "video_recipe", "scene_blocks"):
            if lecture_checks[field] < total_lectures:
                required_missing.append(f"lecture_{field}")
        if lecture_checks["coding_lab"] < total_lectures:
            recommended_missing.append("lecture_coding_lab")

    if not data.get("tags"):
        recommended_missing.append("course_tags")
    if not (data.get("benchmark_ids") or data.get("benchmark_mappings")):
        recommended_missing.append("benchmark_mapping")
    if not (course.get("subject_id") or data.get("subject_id") or data.get("subject_taxonomy")):
        recommended_missing.append("subject_taxonomy")
    if not data.get("continuation_prompt"):
        recommended_missing.append("continuation_prompt")

    score_checks = 2 + max(total_lectures, 1) * 5 + 4
    score_hits = 0
    score_hits += 1 if (course.get("description") or data.get("description")) else 0
    score_hits += 1 if modules and lectures else 0
    if total_lectures:
        for field in ("learning_objectives", "core_terms", "assessment", "video_recipe", "scene_blocks"):
            score_hits += lecture_checks[field]
    score_hits += 1 if data.get("tags") else 0
    score_hits += 1 if (data.get("benchmark_ids") or data.get("benchmark_mappings")) else 0
    score_hits += 1 if (course.get("subject_id") or data.get("subject_id") or data.get("subject_taxonomy")) else 0
    score_hits += 1 if data.get("continuation_prompt") else 0

    completeness_pct = round(score_hits / max(score_checks, 1) * 100, 1)
    return {
        "course_id": course_id,
        "exists": True,
        "ai_ready": not required_missing,
        "completeness_pct": completeness_pct,
        "module_count": len(modules),
        "lecture_count": total_lectures,
        "coverage": lecture_checks,
        "required_missing": required_missing,
        "recommended_missing": recommended_missing,
    }