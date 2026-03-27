"""Course-building tool definitions for the agent tool registry."""
from __future__ import annotations

import json

from llm.tool_registry import register


@register(
    name="create_course_outline",
    description="Create a new course with title, description, and module skeleton. Returns course_id.",
    parameters={
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "Unique course ID (e.g. CS101)"},
            "title": {"type": "string", "description": "Course title"},
            "description": {"type": "string", "description": "Course description"},
            "credits": {"type": "integer", "description": "Credit hours (default 3)"},
            "module_titles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of module titles for the course",
            },
        },
        "required": ["course_id", "title", "description", "module_titles"],
    },
    category="course",
)
def create_course_outline(course_id: str, title: str, description: str,
                          module_titles: list[str], credits: int = 3) -> dict:
    from core.database import upsert_course, upsert_module

    data = {
        "course_id": course_id,
        "title": title,
        "description": description,
        "credits": credits,
        "difficulty_level": "Undergraduate",
        "modules": [],
    }
    upsert_course(course_id, title, description, credits, data)
    modules = []
    for i, module_title in enumerate(module_titles):
        module_id = f"{course_id}-M{i+1}"
        upsert_module(module_id, course_id, module_title, i, {"module_id": module_id, "title": module_title})
        modules.append({"module_id": module_id, "title": module_title})
    data["modules"] = modules
    upsert_course(course_id, title, description, credits, data)
    return {"course_id": course_id, "modules_created": len(modules)}


@register(
    name="add_module",
    description="Add a new module to an existing course.",
    parameters={
        "type": "object",
        "properties": {
            "course_id": {"type": "string"},
            "module_id": {"type": "string"},
            "title": {"type": "string"},
            "order_index": {"type": "integer"},
        },
        "required": ["course_id", "module_id", "title"],
    },
    category="course",
)
def add_module(course_id: str, module_id: str, title: str, order_index: int = 0) -> dict:
    from core.database import upsert_module

    upsert_module(module_id, course_id, title, order_index, {"module_id": module_id, "title": title})
    return {"module_id": module_id, "status": "created"}


@register(
    name="add_lecture",
    description="Add a lecture with full video recipe to a module.",
    parameters={
        "type": "object",
        "properties": {
            "module_id": {"type": "string"},
            "course_id": {"type": "string"},
            "lecture_id": {"type": "string"},
            "title": {"type": "string"},
            "duration_min": {"type": "integer"},
            "learning_objectives": {"type": "array", "items": {"type": "string"}},
            "core_terms": {"type": "array", "items": {"type": "string"}},
            "scene_blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "block_id": {"type": "string"},
                        "duration_s": {"type": "integer"},
                        "narration_prompt": {"type": "string"},
                        "visual_prompt": {"type": "string"},
                    },
                },
            },
        },
        "required": ["module_id", "course_id", "lecture_id", "title"],
    },
    category="course",
)
def add_lecture(module_id: str, course_id: str, lecture_id: str, title: str,
                duration_min: int = 60, learning_objectives: list[str] | None = None,
                core_terms: list[str] | None = None,
                scene_blocks: list[dict] | None = None, order_index: int = 0) -> dict:
    from core.database import upsert_lecture

    data = {
        "lecture_id": lecture_id,
        "title": title,
        "duration_min": duration_min,
        "learning_objectives": learning_objectives or [],
        "core_terms": core_terms or [],
        "video_recipe": {
            "narrative_arc": ["hook", "concept", "demo", "practice", "recap"],
            "scene_blocks": scene_blocks or [],
        },
    }
    upsert_lecture(lecture_id, module_id, course_id, title, duration_min, order_index, data)
    return {"lecture_id": lecture_id, "status": "created"}


@register(
    name="add_assignment",
    description="Add a quiz or homework assignment to a lecture or course.",
    parameters={
        "type": "object",
        "properties": {
            "assignment_id": {"type": "string"},
            "title": {"type": "string"},
            "lecture_id": {"type": "string"},
            "course_id": {"type": "string"},
            "type": {"type": "string", "enum": ["quiz", "homework", "essay", "code"]},
            "questions": {"type": "array", "items": {"type": "object"}},
            "max_score": {"type": "number"},
        },
        "required": ["assignment_id", "title", "type"],
    },
    category="course",
)
def add_assignment(assignment_id: str, title: str, type: str = "quiz",
                   lecture_id: str = "", course_id: str = "",
                   questions: list[dict] | None = None,
                   max_score: float = 100) -> dict:
    from core.database import save_assignment

    save_assignment({
        "id": assignment_id,
        "title": title,
        "type": type,
        "lecture_id": lecture_id,
        "course_id": course_id,
        "max_score": max_score,
        "data": {"questions": questions or []},
    })
    return {"assignment_id": assignment_id, "status": "created"}


@register(
    name="get_course_manifest",
    description="Get a compact manifest of a course (modules and lectures).",
    parameters={
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "The course ID to look up"},
        },
        "required": ["course_id"],
    },
    category="course",
)
def get_course_manifest(course_id: str) -> dict:
    from core.database import get_all_courses, get_modules, get_lectures

    courses = get_all_courses()
    course = next((c for c in courses if c.get("id") == course_id), None)
    if not course:
        return {"error": f"Course {course_id} not found"}
    modules = get_modules(course_id)
    result = {
        "course_id": course_id,
        "title": course.get("title", ""),
        "credits": course.get("credits", 3),
        "modules": [],
    }
    for module in modules:
        lectures = get_lectures(module["id"])
        result["modules"].append({
            "module_id": module["id"],
            "title": module["title"],
            "lectures": [{"lecture_id": lecture["id"], "title": lecture["title"]} for lecture in lectures],
        })
    return result


@register(
    name="get_all_courses_summary",
    description="Get a summary list of all courses in the university.",
    parameters={"type": "object", "properties": {}},
    category="course",
)
def get_all_courses_summary() -> dict:
    from core.database import get_all_courses, get_modules

    courses = get_all_courses()
    result = []
    for course in courses:
        modules = get_modules(course["id"])
        result.append({
            "course_id": course["id"],
            "title": course.get("title", ""),
            "credits": course.get("credits", 3),
            "module_count": len(modules),
        })
    return {"courses": result, "total": len(result)}


@register(
    name="validate_and_import",
    description="Validate a course JSON object against the schema and import it to the database.",
    parameters={
        "type": "object",
        "properties": {
            "course_json": {"type": "object", "description": "Full course JSON to validate and import"},
        },
        "required": ["course_json"],
    },
    category="course",
    requires_review=True,
)
def validate_and_import(course_json: dict) -> dict:
    from core.database import bulk_import_json

    raw = json.dumps(course_json)
    imported, errors = bulk_import_json(raw)
    return {"imported": imported, "errors": errors}


@register(
    name="search_courses",
    description="Search courses by keyword in title or description.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword"},
        },
        "required": ["query"],
    },
    category="course",
)
def search_courses(query: str) -> dict:
    from core.database import get_all_courses

    q = query.lower()
    courses = get_all_courses()
    matches = [
        {"course_id": course["id"], "title": course.get("title", "")}
        for course in courses
        if q in course.get("title", "").lower() or q in (course.get("description") or "").lower()
    ]
    return {"matches": matches, "count": len(matches)}


@register(
    name="generate_quiz_for_lecture",
    description="Generate a quiz for a specific lecture using the LLM.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "num_questions": {"type": "integer", "description": "Number of quiz questions (default 5)"},
        },
        "required": ["lecture_id"],
    },
    category="course",
)
def generate_quiz_for_lecture(lecture_id: str, num_questions: int = 5) -> dict:
    from core.database import get_lecture
    from llm.professor import Professor

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    data["title"] = lecture.get("title", data.get("title", ""))
    prof = Professor()
    response = prof.generate_quiz(data, num_questions)
    if response.parsed_json:
        return {"status": "generated", "quiz": response.parsed_json}
    return {"status": "generated", "raw": response.raw_text[:500]}
