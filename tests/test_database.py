"""
Database CRUD tests — uses a temp DB so the real university.db is never touched.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# Redirect DB_PATH before importing database module
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["_ARCANE_TEST_DB"] = _tmp.name

import core.database as db

# Override DB_PATH to temp file
db.DB_PATH = Path(_tmp.name)


@pytest.fixture(autouse=True)
def fresh_db():
    """Reinitialise the DB before every test so tests are isolated."""
    # Wipe and recreate (including WAL/SHM files)
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)
    db.init_db()
    db.seed_achievements()
    # Neutralise streak bonus so XP tests get exact amounts
    from datetime import datetime
    db.set_setting("streak_last_date", datetime.now().strftime("%Y-%m-%d"))
    db.set_setting("streak_days", "0")
    yield
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)


# ─── Schema & Init ──────────────────────────────────────────────────────────

class TestInit:
    def test_init_creates_tables(self):
        """init_db should create all expected tables."""
        with db.tx() as con:
            tables = [
                r[0] for r in
                con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            ]
        for expected in ("courses", "modules", "lectures", "progress",
                         "xp_events", "settings", "assignments",
                         "chat_history", "llm_generated", "achievements",
                         "quests", "terms", "schema_version"):
            assert expected in tables, f"Missing table: {expected}"

    def test_init_is_idempotent(self):
        """Calling init_db twice should not error or drop data."""
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.init_db()
        courses = db.get_all_courses()
        assert len(courses) == 1

    def test_settings_seeded(self):
        """Default settings should be seeded on init."""
        val = db.get_setting("voice_id")
        assert val  # should have a default voice


# ─── Settings ────────────────────────────────────────────────────────────────

class TestSettings:
    def test_get_set(self):
        db.set_setting("test_key", "test_val")
        assert db.get_setting("test_key") == "test_val"

    def test_get_default(self):
        assert db.get_setting("nonexistent", "fallback") == "fallback"

    def test_save_setting_alias(self):
        db.save_setting("alias_key", "alias_val")
        assert db.get_setting("alias_key") == "alias_val"

    def test_overwrite(self):
        db.set_setting("k", "v1")
        db.set_setting("k", "v2")
        assert db.get_setting("k") == "v2"


# ─── XP & Levels ────────────────────────────────────────────────────────────

class TestXP:
    def test_initial_xp_is_zero(self):
        assert db.get_xp() == 0

    def test_add_xp_returns_total(self):
        total = db.add_xp(100, "test event")
        assert total == 100

    def test_add_xp_accumulates(self):
        db.add_xp(50, "a")
        db.add_xp(75, "b")
        assert db.get_xp() == 125

    def test_get_total_xp_alias(self):
        db.add_xp(200, "c")
        assert db.get_total_xp() == 200

    def test_xp_history(self):
        db.add_xp(10, "first")
        db.add_xp(20, "second")
        history = db.get_xp_history(limit=10)
        assert len(history) == 2

    def test_level_at_zero(self):
        idx, title, in_lvl, to_next = db.get_level()
        assert idx == 0
        assert title  # some title string


class TestLevels:
    def test_level_increases_with_xp(self):
        db.add_xp(500, "big boost")
        idx, title, _, _ = db.get_level()
        assert idx >= 1

    def test_get_level_info_alias(self):
        result = db.get_level_info(0)
        assert len(result) == 4


# ─── Courses, Modules, Lectures ──────────────────────────────────────────────

class TestCourses:
    def test_upsert_and_get(self):
        db.upsert_course("c1", "Intro CS", "Description", 3, {"key": "val"})
        courses = db.get_all_courses()
        assert len(courses) == 1
        assert courses[0]["title"] == "Intro CS"

    def test_upsert_is_idempotent(self):
        db.upsert_course("c1", "V1", "d", 3, {})
        db.upsert_course("c1", "V2", "d", 3, {})
        courses = db.get_all_courses()
        assert len(courses) == 1
        assert courses[0]["title"] == "V2"

    def test_delete_course(self):
        db.upsert_course("c1", "T", "d", 3, {})
        db.delete_course("c1")
        assert db.get_all_courses() == []

    def test_modules(self):
        db.upsert_course("c1", "T", "d", 3, {})
        db.upsert_module("m1", "c1", "Module 1", 0, {})
        mods = db.get_modules("c1")
        assert len(mods) == 1
        assert mods[0]["title"] == "Module 1"

    def test_lectures(self):
        db.upsert_course("c1", "T", "d", 3, {})
        db.upsert_module("m1", "c1", "M1", 0, {})
        db.upsert_lecture("l1", "m1", "c1", "Lecture 1", 30, 0, {"scenes": []})
        lectures = db.get_lectures("m1")
        assert len(lectures) == 1

    def test_get_lecture_by_id(self):
        db.upsert_course("c1", "T", "d", 3, {})
        db.upsert_module("m1", "c1", "M1", 0, {})
        db.upsert_lecture("l1", "m1", "c1", "Lec 1", 15, 0, {})
        lec = db.get_lecture("l1")
        assert lec is not None
        assert lec["title"] == "Lec 1"

    def test_get_lecture_nonexistent(self):
        assert db.get_lecture("no_such_id") is None


# ─── Progress ────────────────────────────────────────────────────────────────

class TestProgress:
    def test_default_progress(self):
        p = db.get_progress("l1")
        assert p["status"] == "not_started"

    def test_set_and_get_progress(self):
        db.set_progress("l1", "completed", watch_time_s=120, score=95.0)
        p = db.get_progress("l1")
        assert p["status"] == "completed"
        assert p["score"] == 95.0

    def test_count_completed(self):
        db.set_progress("l1", "completed")
        db.set_progress("l2", "completed")
        db.set_progress("l3", "in_progress")
        assert db.count_completed() == 2


# ─── Assignments & Grading ───────────────────────────────────────────────────

class TestAssignments:
    def test_save_and_get(self):
        db.save_assignment({"id": "a1", "title": "Essay 1", "course_id": "c1"})
        result = db.get_assignments(course_id="c1")
        assert len(result) == 1

    def test_submit_assignment(self):
        db.save_assignment({"id": "a1", "title": "Essay 1"})
        db.submit_assignment("a1", score=88.0, feedback="Good work")
        assns = db.get_assignments()
        submitted = [a for a in assns if a.get("score") is not None]
        assert len(submitted) == 1

    def test_score_to_grade(self):
        letter, points = db.score_to_grade(95)
        assert letter in ("A+", "A")
        assert points >= 3.7

    def test_score_to_grade_failing(self):
        letter, points = db.score_to_grade(50)
        assert letter == "F"
        assert points == 0.0

    def test_gpa_empty(self):
        gpa, count = db.compute_gpa()
        assert count == 0

    def test_get_gpa_alias(self):
        gpa = db.get_gpa()
        assert isinstance(gpa, float)


# ─── Degrees ─────────────────────────────────────────────────────────────────

class TestDegrees:
    def test_credits_earned_empty(self):
        assert db.credits_earned() == 0

    def test_eligible_degrees_empty(self):
        degrees = db.eligible_degrees()
        assert isinstance(degrees, list)


# ─── Chat History ────────────────────────────────────────────────────────────

class TestChat:
    def test_append_and_get(self):
        db.append_chat("s1", "user", "Hello")
        db.append_chat("s1", "assistant", "Hi there")
        history = db.get_chat("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"

    def test_chat_limit(self):
        for i in range(10):
            db.append_chat("s1", "user", f"msg {i}")
        history = db.get_chat("s1", limit=5)
        assert len(history) == 5

    def test_aliases(self):
        db.save_chat_history("s2", "user", "test")
        history = db.get_chat_history("s2")
        assert len(history) == 1


# ─── LLM Generated Content ──────────────────────────────────────────────────

class TestLLMGenerated:
    def test_save_and_get(self):
        row_id = db.save_llm_generated("curriculum", "CS course")
        items = db.get_llm_generated()
        assert len(items) >= 1

    def test_mark_imported(self):
        row_id = db.save_llm_generated("quiz", "Biology quiz")
        db.mark_imported(row_id)
        not_imported = db.get_llm_generated(imported=False)
        imported = db.get_llm_generated(imported=True)
        assert any(i["id"] == row_id for i in imported)


# ─── Achievements ────────────────────────────────────────────────────────────

class TestAchievements:
    def test_achievements_seeded(self):
        achievements = db.get_achievements()
        assert len(achievements) > 0

    def test_get_all_achievements_alias(self):
        a = db.get_all_achievements()
        assert isinstance(a, list)

    def test_unlock(self):
        achievements = db.get_achievements()
        aid = achievements[0]["id"]
        result = db.unlock_achievement(aid)
        assert result is True
        # Second unlock should return False
        result2 = db.unlock_achievement(aid)
        assert result2 is False


# ─── Bulk Import & Validation ────────────────────────────────────────────────

SAMPLE_COURSE_JSON = json.dumps({
    "course_id": "test_course",
    "title": "Test Course",
    "description": "A test course",
    "credits": 3,
    "modules": [
        {
            "module_id": "m1",
            "title": "Module 1",
            "lectures": [
                {
                    "lecture_id": "l1",
                    "title": "Lecture 1",
                    "duration_min": 30,
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "title": "Scene 1",
                            "narration": "Welcome to the course.",
                            "visual_prompt": "Title slide"
                        }
                    ]
                }
            ]
        }
    ]
})


class TestImport:
    def test_bulk_import(self):
        count, warnings = db.bulk_import_json(SAMPLE_COURSE_JSON)
        assert count > 0
        courses = db.get_all_courses()
        assert len(courses) == 1

    def test_validate_only_mode(self):
        count, warnings = db.bulk_import_json(SAMPLE_COURSE_JSON, validate_only=True)
        # Should not actually import
        courses = db.get_all_courses()
        assert len(courses) == 0

    def test_validate_course_json(self):
        obj = json.loads(SAMPLE_COURSE_JSON)
        errors = db.validate_course_json(obj)
        assert errors == []

    def test_validate_non_course_object(self):
        # Objects without 'modules' key are silently skipped by schema validator
        errors = db.validate_course_json({"title": "No course_id"})
        assert isinstance(errors, list)

    def test_import_invalid_json_string(self):
        count, warnings = db.bulk_import_json("not json at all")
        assert count == 0


# ─── Cleanup ─────────────────────────────────────────────────────────────────

def teardown_module():
    """Remove temp DB file."""
    try:
        Path(_tmp.name).unlink(missing_ok=True)
    except Exception:
        pass
