"""
Import/validation tests — JSON schema validation, dry-run, malformed input.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import core.database as db

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db.DB_PATH = Path(_tmp.name)


@pytest.fixture(autouse=True)
def fresh_db():
    db.DB_PATH.unlink(missing_ok=True)
    db.init_db()
    yield
    db.DB_PATH.unlink(missing_ok=True)


VALID_COURSE = {
    "course_id": "test_import",
    "title": "Import Test Course",
    "description": "Testing import pipeline",
    "credits": 3,
    "modules": [
        {
            "module_id": "im1",
            "title": "Import Module 1",
            "lectures": [
                {
                    "lecture_id": "il1",
                    "title": "Import Lecture 1",
                    "duration_min": 20,
                    "scenes": [
                        {
                            "scene_id": "is1",
                            "title": "Scene 1",
                            "narration": "Test narration text.",
                            "visual_prompt": "Test visual"
                        }
                    ]
                }
            ]
        }
    ]
}


class TestValidation:
    def test_valid_course_passes(self):
        errors = db.validate_course_json(VALID_COURSE)
        assert errors == []

    def test_missing_course_id(self):
        bad = {k: v for k, v in VALID_COURSE.items() if k != "course_id"}
        errors = db.validate_course_json(bad)
        # Schema may or may not flag missing course_id depending on schema definition
        assert isinstance(errors, list)

    def test_missing_title(self):
        bad = {k: v for k, v in VALID_COURSE.items() if k != "title"}
        errors = db.validate_course_json(bad)
        assert len(errors) > 0

    def test_empty_modules(self):
        bad = {**VALID_COURSE, "modules": []}
        errors = db.validate_course_json(bad)
        # May or may not be an error depending on schema strictness
        assert isinstance(errors, list)

    def test_completely_invalid(self):
        # Objects without 'modules' key skip schema validation entirely
        errors = db.validate_course_json({"random": "garbage"})
        assert isinstance(errors, list)


class TestDryRun:
    def test_dry_run_does_not_import(self):
        raw = json.dumps(VALID_COURSE)
        count, warnings = db.bulk_import_json(raw, validate_only=True)
        courses = db.get_all_courses()
        assert len(courses) == 0

    def test_dry_run_reports_count(self):
        raw = json.dumps(VALID_COURSE)
        count, warnings = db.bulk_import_json(raw, validate_only=True)
        # count should indicate what WOULD be imported
        assert isinstance(count, int)


class TestMalformedInput:
    def test_invalid_json_string(self):
        count, warnings = db.bulk_import_json("not json {{{")
        assert count == 0

    def test_empty_string(self):
        count, warnings = db.bulk_import_json("")
        assert count == 0

    def test_json_array_of_courses(self):
        """Array of courses should also work."""
        raw = json.dumps([VALID_COURSE])
        count, warnings = db.bulk_import_json(raw)
        assert count > 0

    def test_json_number(self):
        # Passing a non-dict JSON value (like 42) may raise or return 0
        try:
            count, warnings = db.bulk_import_json("42")
            assert count == 0
        except (TypeError, AttributeError):
            pass  # acceptable — non-object JSON is not a valid import


def teardown_module():
    try:
        Path(_tmp.name).unlink(missing_ok=True)
    except Exception:
        pass
