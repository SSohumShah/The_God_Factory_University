"""
End-to-end integration tests — exercise the full workflow path:
import → course → quiz → grade → GPA → degree → achievements → activity
Plus Wave 4 academic infrastructure (levels, subjects, programs, activity).
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

db.DB_PATH = Path(_tmp.name)


@pytest.fixture(autouse=True)
def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)
    db.init_db()
    db.run_migrations()
    db.seed_achievements()
    db.seed_weekly_quests()
    # Seed Wave 4 data
    db._seed_grade_levels_raw(db.tx)
    db._seed_subjects_raw(db.tx)
    db._seed_programs_raw(db.tx)
    from datetime import datetime
    db.set_setting("streak_last_date", datetime.now().strftime("%Y-%m-%d"))
    db.set_setting("streak_days", "0")
    yield
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)


# ─── 3-Course E2E Flow ──────────────────────────────────────────────────────

_COURSES = [
    {
        "course_id": "cs101", "title": "Intro to CS", "description": "CS basics",
        "credits": 3,
        "modules": [{
            "module_id": "cs101_m1", "title": "Algorithms",
            "lectures": [{
                "lecture_id": "cs101_l1", "title": "Big-O",
                "duration_min": 30,
                "scenes": [{"scene_id": "s1", "title": "Intro", "narration": "Welcome.", "visual_prompt": "slide"}]
            }],
            "assignments": [{
                "assignment_id": "cs101_a1", "title": "HW1",
                "assignment_type": "quiz", "max_score": 100,
                "questions": [{"q": "What is O(1)?", "a": "Constant time"}]
            }]
        }]
    },
    {
        "course_id": "math201", "title": "Linear Algebra", "description": "Vectors and matrices",
        "credits": 4,
        "modules": [{
            "module_id": "math201_m1", "title": "Vectors",
            "lectures": [{
                "lecture_id": "math201_l1", "title": "Vector Basics",
                "duration_min": 45,
                "scenes": [{"scene_id": "s1", "title": "Vectors", "narration": "A vector.", "visual_prompt": "arrows"}]
            }],
            "assignments": [{
                "assignment_id": "math201_a1", "title": "Quiz 1",
                "assignment_type": "quiz", "max_score": 100,
                "questions": [{"q": "2D vector?", "a": "(x, y)"}]
            }]
        }]
    },
    {
        "course_id": "eng101", "title": "English Composition", "description": "Writing skills",
        "credits": 3,
        "modules": [{
            "module_id": "eng101_m1", "title": "Essays",
            "lectures": [{
                "lecture_id": "eng101_l1", "title": "Thesis Statements",
                "duration_min": 25,
                "scenes": [{"scene_id": "s1", "title": "Thesis", "narration": "A thesis.", "visual_prompt": "text"}]
            }],
            "assignments": [{
                "assignment_id": "eng101_a1", "title": "Essay 1",
                "assignment_type": "essay", "max_score": 100,
                "questions": [{"q": "Write a thesis", "a": "Open ended"}]
            }]
        }]
    },
]


class TestThreeCourseE2E:
    """F.1 Alpha: 3-course create → grade → GPA → degree → transcript."""

    def test_import_three_courses(self):
        for c in _COURSES:
            count, warnings = db.bulk_import_json(json.dumps(c))
            assert count >= 1, f"Import failed for {c['course_id']}"
        courses = db.get_all_courses()
        assert len(courses) == 3

    def test_full_grade_pipeline(self):
        """Import → create assignments → submit → grade → GPA → credits."""
        for c in _COURSES:
            db.bulk_import_json(json.dumps(c))

        # Create assignments (import doesn't create them)
        assignments = [
            {"id": "cs101_a1", "course_id": "cs101", "title": "HW1", "type": "quiz", "max_score": 100},
            {"id": "math201_a1", "course_id": "math201", "title": "Quiz 1", "type": "quiz", "max_score": 100},
            {"id": "eng101_a1", "course_id": "eng101", "title": "Essay 1", "type": "essay", "max_score": 100},
        ]
        for a in assignments:
            db.save_assignment(a)

        # Submit and grade assignments
        scores = {"cs101_a1": 92, "math201_a1": 88, "eng101_a1": 95}
        for aid, score in scores.items():
            db.submit_assignment(aid, score)

        # Verify grades
        for aid, score in scores.items():
            letter, gpa_pts = db.score_to_grade(score)
            assert letter in ("A+", "A", "A-", "B+"), f"Unexpected grade {letter} for score {score}"

        # GPA should be > 0
        gpa, graded_count = db.compute_gpa()
        assert gpa > 3.0, f"Expected GPA > 3.0, got {gpa}"
        assert graded_count == 3

        # Complete all lectures to earn credits
        db.set_progress("cs101_l1", "completed")
        db.set_progress("math201_l1", "completed")
        db.set_progress("eng101_l1", "completed")

        # Credits earned should be sum of 3 + 4 + 3 = 10
        credits = db.credits_earned()
        assert credits == 10

    def test_lecture_progress_tracking(self):
        """Mark lectures complete, verify progress."""
        for c in _COURSES:
            db.bulk_import_json(json.dumps(c))

        db.set_progress("cs101_l1", "completed")
        db.set_progress("math201_l1", "completed")
        db.set_progress("eng101_l1", "completed")

        assert db.get_progress("cs101_l1")["status"] == "completed"
        assert db.get_progress("math201_l1")["status"] == "completed"
        assert db.count_completed() >= 1

    def test_xp_and_level_progression(self):
        """Submitting assignments and completing lectures earns XP."""
        for c in _COURSES:
            db.bulk_import_json(json.dumps(c))

        # Add XP for lecture completions and quiz scores
        db.add_xp(50, "lecture_complete")
        db.add_xp(50, "lecture_complete")
        db.add_xp(50, "lecture_complete")
        db.add_xp(100, "quiz_score")
        db.add_xp(100, "quiz_score")
        db.add_xp(100, "quiz_score")

        total = db.get_xp()
        assert total >= 450  # At least 450; imports may also award XP

        level_num, title, xp_for, xp_next = db.get_level()
        assert level_num >= 1

    def test_achievements_unlock_during_flow(self):
        """Achievements can be unlocked during the E2E flow."""
        achievements = db.get_achievements()
        assert len(achievements) > 0
        # Unlock the first achievement
        result = db.unlock_achievement(achievements[0]["id"])
        assert result is True


# ─── Degree + Grading + Deadlines + Achievements E2E ────────────────────────

class TestDegreeGradingE2E:
    """F.2: Degree + grading + deadlines + achievements validated end-to-end."""

    def test_degree_eligibility_flow(self):
        """Import courses, create + grade assignments, check degree eligibility."""
        for c in _COURSES:
            db.bulk_import_json(json.dumps(c))
        for cid, aid in [("cs101", "cs101_a1"), ("math201", "math201_a1"), ("eng101", "eng101_a1")]:
            db.save_assignment({"id": aid, "course_id": cid, "title": "Test", "max_score": 100})
            db.submit_assignment(aid, 90)

        eligible = db.eligible_degrees()
        # With 10 credits, at least Associate should be in progress
        assert isinstance(eligible, list)

    def test_deadline_mode_toggle(self):
        """Toggling deadline mode updates setting."""
        db.set_setting("deadlines_enabled", "1")
        assert db.get_setting("deadlines_enabled") == "1"
        db.set_setting("deadlines_enabled", "0")
        assert db.get_setting("deadlines_enabled") == "0"


# ─── Wave 4: Academic Infrastructure ────────────────────────────────────────

class TestGradeLevels:
    def test_seeded_on_init(self):
        levels = db.get_grade_levels()
        assert len(levels) >= 20  # K-12 + college + grad + postdoc

    def test_get_specific_level(self):
        level = db.get_grade_level("K")
        assert level is not None
        assert level["name"] == "Kindergarten"

    def test_college_levels_exist(self):
        for lid in ("freshman", "sophomore", "junior", "senior", "masters", "doctoral"):
            level = db.get_grade_level(lid)
            assert level is not None, f"Missing level: {lid}"


class TestSubjects:
    def test_subjects_seeded(self):
        subjects = db.get_all_subjects()
        assert len(subjects) >= 10  # Minimum 10 domains

    def test_get_domains(self):
        domains = db.get_subject_domains()
        assert len(domains) >= 5
        for d in domains:
            assert "id" in d

    def test_get_subject_by_id(self):
        subjects = db.get_all_subjects()
        if subjects:
            sid = subjects[0]["id"]
            s = db.get_subject(sid)
            assert s is not None


class TestPrograms:
    def test_programs_seeded(self):
        programs = db.get_all_programs()
        assert len(programs) >= 1

    def test_enroll_and_list(self):
        programs = db.get_all_programs()
        if programs:
            pid = programs[0]["id"]
            eid = db.enroll_program(pid)
            assert eid  # Returns enrollment ID
            enrollments = db.get_enrollments()
            assert len(enrollments) >= 1

    def test_get_program_detail(self):
        programs = db.get_all_programs()
        if programs:
            p = db.get_program(programs[0]["id"])
            assert p is not None


class TestActivity:
    def test_log_and_summarize(self):
        db.log_activity("lecture_view", duration_s=300)
        db.log_activity("quiz_attempt", duration_s=60)
        db.log_activity("lecture_view", duration_s=600)
        summary = db.get_activity_summary()
        assert isinstance(summary, dict)


# ─── Chat persistence E2E ───────────────────────────────────────────────────

class TestChatE2E:
    def test_chat_roundtrip(self):
        db.append_chat("default", "user", "Hello professor")
        db.append_chat("default", "assistant", "Greetings, scholar!")
        history = db.get_chat("default")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"


# ─── LLM Generated content persistence ──────────────────────────────────────

class TestLLMGenerated:
    def test_save_and_retrieve(self):
        db.save_llm_generated("test_gen", "quiz", '{"q": "test?"}')
        rows = db.get_llm_generated()
        assert len(rows) >= 1


# ─── Cleanup ────────────────────────────────────────────────────────────────

def teardown_module():
    try:
        Path(_tmp.name).unlink(missing_ok=True)
    except Exception:
        pass
