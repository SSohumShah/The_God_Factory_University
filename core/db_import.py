"""
Bulk JSON import logic for The God Factory University.
Extracted from database.py for modularity (DEVELOPMENT.md Rule 5).
"""
from __future__ import annotations

import json
import time
from pathlib import Path


_SCHEMA_CACHE: dict | None = None
_ASSIGNMENT_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict | None:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "course_validation_schema.json"
    if not schema_path.exists():
        return None
    try:
        _SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
        return _SCHEMA_CACHE
    except Exception:
        return None


def _load_assignment_schema() -> dict | None:
    global _ASSIGNMENT_SCHEMA_CACHE
    if _ASSIGNMENT_SCHEMA_CACHE is not None:
        return _ASSIGNMENT_SCHEMA_CACHE
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "assignment_schema.json"
    if not schema_path.exists():
        return None
    try:
        _ASSIGNMENT_SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
        return _ASSIGNMENT_SCHEMA_CACHE
    except Exception:
        return None


def validate_course_json(obj: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = _load_schema()
    if schema is None:
        return []
    errors = []
    if "modules" not in obj:
        return []
    v = jsonschema.Draft7Validator(schema)
    for error in v.iter_errors(obj):
        path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        errors.append(f"Schema: {path}: {error.message}")
    return errors


def validate_assignment_batch(obj: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = _load_assignment_schema()
    if schema is None:
        return []
    errors = []
    v = jsonschema.Draft7Validator(schema)
    for error in v.iter_errors(obj):
        path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        errors.append(f"AssignmentSchema: {path}: {error.message}")
    return errors


def _is_assignment_batch(obj: dict) -> bool:
    return "assignments" in obj and isinstance(obj.get("assignments"), list) and "modules" not in obj


def bulk_import_json(raw: str, *, tx_func, upsert_course, upsert_module, upsert_lecture,
                     unlock_achievement, add_xp, validate_only: bool = False,
                     save_assignment_fn=None) -> tuple[int, list[str]]:
    objects = []
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        objects = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    objects.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    imported = 0
    errors = []
    for i, obj in enumerate(objects):
        if not isinstance(obj, dict):
            errors.append(f"Object {i + 1}: expected a JSON object, got {type(obj).__name__}")
            continue
        if _is_assignment_batch(obj):
            schema_errors = validate_assignment_batch(obj)
            if schema_errors:
                prefix = f"Object {i + 1}" if len(objects) > 1 else "Input"
                errors.extend(f"{prefix}: {e}" for e in schema_errors)
                continue
            if validate_only:
                imported += 1
                continue
            if save_assignment_fn is None:
                errors.append(f"Object {i + 1}: assignment batch detected but no assignment handler available")
                continue
            try:
                _import_assignment_batch(obj, tx_func=tx_func, save_assignment_fn=save_assignment_fn)
                imported += 1
            except Exception as e:
                errors.append(f"Object {i + 1}: {e}")
            continue
        schema_errors = validate_course_json(obj)
        if schema_errors:
            prefix = f"Object {i + 1}" if len(objects) > 1 else "Input"
            errors.extend(f"{prefix}: {e}" for e in schema_errors)
            continue
        if validate_only:
            imported += 1
            continue
        try:
            with tx_func() as conn:
                conn.execute("SAVEPOINT import_obj")
                try:
                    _import_one_object(obj, upsert_course=upsert_course,
                                       upsert_module=upsert_module, upsert_lecture=upsert_lecture)
                    conn.execute("RELEASE SAVEPOINT import_obj")
                    imported += 1
                except Exception as e:
                    conn.execute("ROLLBACK TO SAVEPOINT import_obj")
                    errors.append(f"Object {i + 1}: {e}")
        except Exception as e:
            errors.append(f"Object {i + 1}: {e}")

    if imported > 0 and not validate_only:
        unlock_achievement("bulk_import")
        add_xp(imported * 25, f"Bulk imported {imported} objects", "import")
        from core.logger import log_import
        log_import("bulk_json", "completed", items=imported)

    if errors:
        from core.logger import log_import
        log_import("bulk_json", "errors", items=len(errors))

    return imported, errors


def _import_one_object(obj: dict, *, upsert_course, upsert_module, upsert_lecture) -> None:
    if "modules" in obj:
        _import_course(obj, upsert_course=upsert_course, upsert_module=upsert_module,
                       upsert_lecture=upsert_lecture)
    elif "lectures" in obj and "course_id" in obj:
        _import_module(obj, upsert_module=upsert_module, upsert_lecture=upsert_lecture)
    elif "lecture_id" in obj or ("title" in obj and "video_recipe" in obj):
        _import_lecture_flat(obj, upsert_lecture=upsert_lecture)
    elif "course_spec_version" in obj:
        for module in obj.get("modules", []):
            for lecture in module.get("lectures", []):
                course_id = obj.get("course_id", "imported_course")
                upsert_course(course_id, obj.get("title", "Imported Course"),
                              obj.get("audience", ""), obj.get("total_lectures", 3), obj)
                upsert_module(module["module_id"], course_id, module["title"],
                              int(module["module_id"].replace("M", "") if module.get("module_id", "").startswith("M") else 0), module)
                upsert_lecture(lecture["lecture_id"], module["module_id"], course_id,
                               lecture["title"], lecture.get("duration_min", 60), 0, lecture)
    else:
        raise ValueError(f"Cannot detect object type: keys={list(obj.keys())[:6]}")


def _import_course(obj: dict, *, upsert_course, upsert_module, upsert_lecture) -> None:
    course_id = obj.get("course_id") or obj.get("id") or f"course_{int(time.time())}"
    upsert_course(course_id, obj.get("title", "Imported"), obj.get("description", ""),
                  obj.get("credits", 3), obj, parent_course_id=obj.get("parent_course_id"),
                  depth_level=obj.get("depth_level", 0),
                  depth_target=obj.get("depth_target", 0),
                  pacing=obj.get("pacing", "standard"),
                  is_jargon_course=1 if obj.get("is_jargon_course") else 0,
                  jargon=json.dumps(obj["jargon"]) if obj.get("jargon") else None)
    for i, module in enumerate(obj.get("modules", [])):
        mid = module.get("module_id") or module.get("id") or f"{course_id}_M{i}"
        upsert_module(mid, course_id, module.get("title", f"Module {i}"), i, module)
        for j, lecture in enumerate(module.get("lectures", [])):
            lid = lecture.get("lecture_id") or lecture.get("id") or f"{mid}_L{j}"
            upsert_lecture(lid, mid, course_id, lecture.get("title", f"Lecture {j}"),
                           lecture.get("duration_min", 60), j, lecture)


def _import_module(obj: dict, *, upsert_module, upsert_lecture) -> None:
    course_id = obj.get("course_id", "unknown")
    mid = obj.get("module_id") or obj.get("id") or f"module_{int(time.time())}"
    upsert_module(mid, course_id, obj.get("title", "Module"), 0, obj)
    for j, lecture in enumerate(obj.get("lectures", [])):
        lid = lecture.get("lecture_id") or f"{mid}_L{j}"
        upsert_lecture(lid, mid, course_id, lecture.get("title", f"Lecture {j}"),
                       lecture.get("duration_min", 60), j, lecture)


def _import_lecture_flat(obj: dict, *, upsert_lecture) -> None:
    lid = obj.get("lecture_id") or obj.get("id") or f"lecture_{int(time.time())}"
    mid = obj.get("module_id", "unassigned")
    cid = obj.get("course_id", "unassigned")
    upsert_lecture(lid, mid, cid, obj.get("title", "Lecture"), obj.get("duration_min", 60), 0, obj)


def _import_assignment_batch(obj: dict, *, tx_func, save_assignment_fn) -> None:
    course_id = obj["course_id"]
    for i, asn in enumerate(obj["assignments"]):
        asn_id = asn.get("assignment_id") or f"{course_id}-A{i:02d}"
        save_assignment_fn({
            "id": asn_id,
            "course_id": course_id,
            "lecture_id": asn.get("due_after_lecture"),
            "title": asn["title"],
            "description": asn.get("description", ""),
            "type": asn.get("type", "quiz"),
            "max_score": asn.get("max_score", 100),
            "weight": asn.get("weight", 1.0),
            "data": {
                "rubric": asn.get("rubric", []),
                "questions": asn.get("questions", []),
                "difficulty_level": asn.get("difficulty_level"),
                "time_limit_minutes": asn.get("time_limit_minutes"),
                "resources": asn.get("resources", []),
            },
        }, tx_func)
