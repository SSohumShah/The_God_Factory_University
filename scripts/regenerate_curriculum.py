"""Regenerate all 84 built-in curriculum JSONs to schema v2.0.

Enriches each course with:
  - difficulty_level, recommended_prerequisites, depth_target, pacing
  - learning_outcomes derived from module titles
  - Per-lecture: math_focus, ai_focus, coding_lab, assessment, ambiance
  - Per-module: assignments stubs
  - _token_estimate metadata
  - Validates every output against course_validation_schema.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRICULUM_DIR = ROOT / "data" / "curriculum"
VALIDATION_SCHEMA = ROOT / "schemas" / "course_validation_schema.json"

# ─── Grade-band metadata ─────────────────────────────────────────────────────

GRADE_BANDS = {
    "K":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 50_000},
    "1":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 50_000},
    "2":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 50_000},
    "3":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 60_000},
    "4":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 60_000},
    "5":         {"difficulty": "K-5",      "depth_target": 1, "credits": 1, "token_est": 70_000},
    "6":         {"difficulty": "6-8",      "depth_target": 2, "credits": 1, "token_est": 200_000},
    "7":         {"difficulty": "6-8",      "depth_target": 2, "credits": 1, "token_est": 200_000},
    "8":         {"difficulty": "6-8",      "depth_target": 2, "credits": 1, "token_est": 200_000},
    "9":         {"difficulty": "9-12",     "depth_target": 2, "credits": 2, "token_est": 500_000},
    "10":        {"difficulty": "9-12",     "depth_target": 2, "credits": 2, "token_est": 500_000},
    "11":        {"difficulty": "9-12",     "depth_target": 2, "credits": 2, "token_est": 500_000},
    "12":        {"difficulty": "9-12",     "depth_target": 2, "credits": 2, "token_est": 500_000},
    "freshman":  {"difficulty": "Freshman",  "depth_target": 3, "credits": 3, "token_est": 2_000_000},
    "sophomore": {"difficulty": "Sophomore", "depth_target": 3, "credits": 3, "token_est": 2_000_000},
    "junior":    {"difficulty": "Junior",    "depth_target": 3, "credits": 3, "token_est": 2_000_000},
    "senior":    {"difficulty": "Senior",    "depth_target": 3, "credits": 3, "token_est": 2_000_000},
    "masters":   {"difficulty": "Masters",   "depth_target": 4, "credits": 3, "token_est": 8_000_000},
    "doctoral":  {"difficulty": "Doctoral",  "depth_target": 5, "credits": 3, "token_est": 50_000_000},
}

# Prerequisite chains: {course_id: [prerequisite_course_ids]}
PREREQUISITE_MAP = {
    # K-5: sequential by grade number within same subject
    "2_math": ["1_math"], "3_math": ["2_math"], "4_math": ["3_math"],
    "5_math": ["4_math"], "6_math": ["5_math"], "7_math": ["6_math"],
    "8_math": ["7_math"], "9_math": ["8_math"], "10_math": ["9_math"],
    "11_math": ["10_math"], "12_math": ["11_math"],
    "2_reading": ["1_reading"], "3_reading": ["2_reading"],
    "2_science": ["1_science"], "3_science": ["2_science"], "4_science": ["3_science"],
    "5_science": ["4_science"], "6_science": ["5_science"], "7_science": ["6_science"],
    "8_science": ["7_science"], "9_science": ["8_science"], "10_science": ["9_science"],
    "11_science": ["10_science"], "12_science": ["11_science"],
    "3_social_studies": ["1_social_studies"], "5_social_studies": ["3_social_studies"],
    "6_social_studies": ["5_social_studies"], "7_social_studies": ["6_social_studies"],
    "8_social_studies": ["7_social_studies"], "9_social_studies": ["8_social_studies"],
    "10_social_studies": ["9_social_studies"], "11_social_studies": ["10_social_studies"],
    "7_ela": ["6_ela"], "8_ela": ["7_ela"],
    "9_english": ["8_ela"], "10_english": ["9_english"],
    "11_english": ["10_english"], "12_english": ["11_english"],
    "11_ap_cs": ["9_cs"],
    # College chains
    "sophomore_calc": ["freshman_math"],
    "sophomore_cs201": ["freshman_cs101"],
    "sophomore_stats": ["freshman_math"],
    "junior_cs301": ["sophomore_cs201"],
    "junior_cs350": ["sophomore_cs201"],
    "junior_math301": ["sophomore_calc"],
    "junior_research": ["sophomore_lit", "sophomore_stats"],
    "senior_cs401": ["junior_cs301"],
    "senior_cs450": ["junior_cs350"],
    "senior_capstone": ["junior_cs301", "junior_research"],
    "senior_ethics": ["junior_research"],
    "masters_cs500": ["senior_cs401"],
    "masters_cs510": ["senior_cs401"],
    "masters_cs520": ["senior_cs450"],
    "masters_research": ["senior_capstone"],
    "masters_thesis": ["masters_research", "masters_cs500"],
    "doctoral_cs600": ["masters_cs500"],
    "doctoral_cs610": ["masters_cs510"],
    "doctoral_quals": ["doctoral_cs600", "doctoral_cs610"],
    "doctoral_dissertation": ["doctoral_quals"],
}

# Subjects that get coding_lab stubs (grade 9+)
CS_SUBJECTS = {"cs", "cs101", "cs201", "cs301", "cs350", "cs401", "cs450",
               "cs500", "cs510", "cs520", "cs600", "cs610", "ap_cs",
               "comp", "capstone", "quals", "dissertation", "thesis"}

# Subjects that get math_focus
MATH_SUBJECTS = {"math", "calc", "stats", "math301"}

# Subjects that get ai_focus (grade 9+ CS)
AI_SUBJECTS = {"cs", "cs201", "cs301", "cs350", "cs401", "cs450",
               "cs500", "cs510", "cs520", "cs600", "cs610", "ap_cs"}


def _grade_from_path(json_path: Path) -> str:
    """Return the grade folder name (e.g. 'K', '9', 'freshman')."""
    return json_path.parent.name


def _subject_from_path(json_path: Path) -> str:
    """Return the subject slug (e.g. 'math', 'cs101')."""
    return json_path.stem


def _is_cs_eligible(grade: str, subject: str) -> bool:
    """Whether this course should have coding_lab stubs."""
    if subject in CS_SUBJECTS:
        return True
    if grade in ("9", "10", "11", "12", "freshman", "sophomore",
                 "junior", "senior", "masters", "doctoral"):
        return subject in CS_SUBJECTS
    return False


def _enrichment_for_lecture(lecture: dict, grade: str, subject: str, module_title: str) -> dict:
    """Add missing v2.0 fields to a lecture dict, in-place."""
    # learning_objectives — ensure at least one
    if not lecture.get("learning_objectives"):
        lecture["learning_objectives"] = [
            f"Understand key concepts of {lecture.get('title', module_title)}"
        ]

    # math_focus
    if subject in MATH_SUBJECTS and "math_focus" not in lecture:
        lecture["math_focus"] = [module_title.lower().replace(" ", "_")]
    elif "math_focus" not in lecture:
        lecture["math_focus"] = []

    # ai_focus
    if subject in AI_SUBJECTS and "ai_focus" not in lecture:
        lecture["ai_focus"] = [f"{subject}_fundamentals"]
    elif "ai_focus" not in lecture:
        lecture["ai_focus"] = []

    # coding_lab
    if _is_cs_eligible(grade, subject) and "coding_lab" not in lecture:
        lecture["coding_lab"] = {
            "language": "Python",
            "task": f"Implement concepts from {lecture.get('title', 'this lecture')}",
            "deliverable": f"{lecture.get('lecture_id', 'lab')}.py",
        }

    # assessment
    if "assessment" not in lecture:
        lecture["assessment"] = {
            "quiz_questions": 5,
            "programming_exercises": 1 if _is_cs_eligible(grade, subject) else 0,
            "reflection_prompt": f"Reflect on what you learned about {lecture.get('title', 'this topic')}.",
        }

    # Ensure all scene blocks have ambiance
    recipe = lecture.get("video_recipe", {})
    for block in recipe.get("scene_blocks", []):
        if "ambiance" not in block:
            block["ambiance"] = {
                "music": "low ambient electronic",
                "sfx": "gentle",
                "color_palette": "dark blue and cyan",
            }

    return lecture


def _build_module_assignments(module: dict, course_id: str, mod_idx: int,
                              grade: str, subject: str) -> list[dict]:
    """Generate assignment stubs for a module."""
    lectures = module.get("lectures", [])
    if not lectures:
        return []
    last_lid = lectures[-1].get("lecture_id", f"{course_id}-M{mod_idx + 1}-L{len(lectures)}")
    assignments = [
        {
            "assignment_id": f"{course_id}-A{mod_idx + 1}",
            "title": f"{module['title']} Assessment",
            "type": "quiz",
            "max_score": 100,
            "weight": 0.25,
            "due_after_lecture": last_lid,
            "rubric": [
                {"criterion": "Conceptual understanding", "points": 60},
                {"criterion": "Application", "points": 40},
            ],
            "questions": [],
        }
    ]
    if _is_cs_eligible(grade, subject):
        assignments.append({
            "assignment_id": f"{course_id}-LAB{mod_idx + 1}",
            "title": f"{module['title']} Lab",
            "type": "lab",
            "max_score": 100,
            "weight": 0.25,
            "due_after_lecture": last_lid,
            "rubric": [
                {"criterion": "Code correctness", "points": 50},
                {"criterion": "Code quality", "points": 30},
                {"criterion": "Documentation", "points": 20},
            ],
            "questions": [],
        })
    return assignments


def enrich_course(course: dict, json_path: Path) -> dict:
    """Enrich a course JSON to full schema v2.0."""
    grade = _grade_from_path(json_path)
    subject = _subject_from_path(json_path)
    band = GRADE_BANDS.get(grade, GRADE_BANDS["freshman"])

    # Top-level fields
    course.setdefault("_schema_version", "2.0")
    course.setdefault("difficulty_level", band["difficulty"])
    course.setdefault("depth_target", band["depth_target"])
    course.setdefault("pacing", "standard")

    cid = course.get("course_id", f"{grade}_{subject}")
    course["recommended_prerequisites"] = PREREQUISITE_MAP.get(cid, [])

    # learning_outcomes from module titles
    module_titles = [m.get("title", "") for m in course.get("modules", [])]
    course["learning_outcomes"] = [
        f"Demonstrate understanding of {t}" for t in module_titles if t
    ]

    # Enrich each lecture
    all_assignments: list[dict] = []
    for mod_idx, module in enumerate(course.get("modules", [])):
        for lecture in module.get("lectures", []):
            _enrichment_for_lecture(lecture, grade, subject, module.get("title", ""))
        all_assignments.extend(
            _build_module_assignments(module, cid, mod_idx, grade, subject)
        )

    course["assignments"] = all_assignments

    # _token_estimate
    num_lectures = sum(len(m.get("lectures", [])) for m in course.get("modules", []))
    course["_token_estimate"] = {
        "total_tokens": band["token_est"],
        "min_output_tokens": 1500,
        "overhead_tokens": 500,
        "lectures": num_lectures,
    }

    return course


def validate_course(course: dict) -> list[str]:
    """Validate against course_validation_schema.json. Returns error messages."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — skipping validation"]

    schema = json.loads(VALIDATION_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [e.message for e in validator.iter_errors(course)]


def main() -> int:
    total = 0
    errors_total = 0
    files = sorted(CURRICULUM_DIR.rglob("*.json"))
    print(f"Found {len(files)} curriculum files to regenerate.\n")

    for path in files:
        try:
            course = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP {path.relative_to(ROOT)}: {exc}")
            errors_total += 1
            continue

        if not isinstance(course, dict):
            print(f"  SKIP {path.relative_to(ROOT)}: root is not an object")
            errors_total += 1
            continue

        enriched = enrich_course(course, path)
        errs = validate_course(enriched)
        if errs:
            print(f"  WARN {path.relative_to(ROOT)}: {len(errs)} validation issues")
            for e in errs[:3]:
                print(f"       - {e}")
            errors_total += len(errs)

        path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        total += 1

    print(f"\nRegenerated {total} files. Validation issues: {errors_total}.")
    return 1 if errors_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
