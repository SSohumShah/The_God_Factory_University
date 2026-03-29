"""
Regression tests for known bug classes.
Covers: signature mismatches, invalid JSON from LLM, edge cases.
"""

import json
import pytest
import tempfile
from pathlib import Path

import core.database as db

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db.DB_PATH = Path(_tmp.name)


@pytest.fixture(autouse=True)
def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)
    db.init_db()
    db.seed_achievements()
    from datetime import datetime
    db.set_setting("streak_last_date", datetime.now().strftime("%Y-%m-%d"))
    db.set_setting("streak_days", "0")
    yield
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)


# ─── Signature mismatch regression ──────────────────────────────────────────

class TestSignatureMismatch:
    """Ensure public API functions accept the documented parameter signatures."""

    def test_add_xp_three_args(self):
        total = db.add_xp(10, "test", "general")
        assert total == 10

    def test_add_xp_two_args(self):
        total = db.add_xp(10, "test")
        assert total == 10

    def test_set_progress_optional_score(self):
        db.upsert_course("c1", "Course", "desc", 3, {})
        db.upsert_module("m1", "c1", "Module", 0, {})
        db.upsert_lecture("l1", "m1", "c1", "Lec", 60, 0, {})
        db.set_progress("l1", "in_progress")
        p = db.get_progress("l1")
        assert p["status"] == "in_progress"

    def test_set_progress_with_score(self):
        db.upsert_course("c1", "Course", "desc", 3, {})
        db.upsert_module("m1", "c1", "Module", 0, {})
        db.upsert_lecture("l1", "m1", "c1", "Lec", 60, 0, {})
        db.set_progress("l1", "completed", watch_time_s=120, score=95.0)
        p = db.get_progress("l1")
        assert p["status"] == "completed"

    def test_submit_assignment_params(self):
        db.save_assignment({
            "id": "a1", "title": "Quiz 1",
            "course_id": "c1", "max_score": 100,
        })
        db.submit_assignment("a1", 85.0, "Good work")

    def test_bulk_import_validate_only_flag(self):
        obj = {"course_id": "c1", "title": "T", "credits": 3, "modules": []}
        count, errors = db.bulk_import_json(json.dumps(obj), validate_only=True)
        assert count == 0


# ─── Invalid JSON from LLM ──────────────────────────────────────────────────

class TestInvalidLLMJSON:
    """Ensure repair_json handles common LLM output issues."""

    def test_repair_valid_json(self):
        from llm.professor import Professor
        result = Professor.repair_json('{"key": "value"}')
        assert result is not None
        assert json.loads(result)["key"] == "value"

    def test_repair_markdown_fenced_json(self):
        from llm.professor import Professor
        raw = '```json\n{"key": "value"}\n```'
        result = Professor.repair_json(raw)
        assert result is not None
        assert json.loads(result)["key"] == "value"

    def test_repair_trailing_comma(self):
        from llm.professor import Professor
        raw = '{"key": "value",}'
        result = Professor.repair_json(raw)
        assert result is not None
        assert json.loads(result)["key"] == "value"

    def test_repair_unclosed_brace(self):
        from llm.professor import Professor
        raw = '{"key": "value"'
        result = Professor.repair_json(raw)
        assert result is not None
        assert json.loads(result)["key"] == "value"

    def test_repair_json_wrapped_in_prose(self):
        from llm.professor import Professor
        raw = 'Here is the jargon course you requested:\n{"key": "value"}\nUse it well.'
        result = Professor.repair_json(raw)
        assert result is not None
        assert json.loads(result)["key"] == "value"

    def test_repair_python_style_dict(self):
        from llm.professor import Professor
        raw = "{'key': 'value', 'items': ['a', 'b']}"
        result = Professor.repair_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["items"] == ["a", "b"]

    def test_repair_totally_invalid(self):
        from llm.professor import Professor
        result = Professor.repair_json("not json at all")
        assert result is None

    def test_bulk_import_invalid_json_string(self):
        count, errors = db.bulk_import_json("totally invalid json")
        assert count == 0
        # Returns 0 imported, errors may or may not be populated
        # The important thing is it doesn't crash


# ─── Edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_course_modules_list(self):
        obj = {"course_id": "c1", "title": "Empty", "credits": 3, "modules": []}
        count, errors = db.bulk_import_json(json.dumps(obj))
        # Empty modules = nothing to import, should not crash
        assert isinstance(count, int)

    def test_get_setting_nonexistent(self):
        assert db.get_setting("nonexistent_key_xyz", "fallback") == "fallback"

    def test_double_unlock_achievement(self):
        db.unlock_achievement("first_quiz")
        result = db.unlock_achievement("first_quiz")
        assert result is False  # Already unlocked

    def test_xp_never_negative(self):
        assert db.get_xp() >= 0

    def test_gpa_empty_db(self):
        gpa, count = db.compute_gpa()
        assert gpa == 0.0
        assert count == 0
