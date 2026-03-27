"""
Tests for course_tree module — recursive decomposition, credit-hours,
pacing, competency tracking, qualifications, and AI policy.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["_GF_TEST_DB"] = _tmp.name

import core.database as db

db.DB_PATH = Path(_tmp.name)


def _cleanup_db_files() -> None:
    paths = [Path(str(db.DB_PATH) + suffix) for suffix in ("", "-wal", "-shm")]
    for _ in range(10):
        blocked = False
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                blocked = True
        if not blocked:
            return
        time.sleep(0.05)


@pytest.fixture(autouse=True)
def fresh_db():
    _cleanup_db_files()
    db.init_db()
    db.seed_achievements()
    db._seed_benchmarks_raw(db.tx)
    from datetime import datetime
    db.set_setting("streak_last_date", datetime.now().strftime("%Y-%m-%d"))
    db.set_setting("streak_days", "0")
    yield
    _cleanup_db_files()


# ─── Course Tree Schema ─────────────────────────────────────────────────────

class TestCourseTreeSchema:
    def test_course_tree_tables_exist(self):
        with db.tx() as con:
            tables = [
                r[0] for r in
                con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            ]
        for expected in ("competency_benchmarks", "qualification_progress",
                         "study_hours_log", "competency_scores"):
            assert expected in tables, f"Missing table: {expected}"

    def test_courses_has_tree_columns(self):
        db.upsert_course("c1", "Test", "desc", 3, {},
                         parent_course_id="parent1", depth_level=2,
                         depth_target=5, pacing="fast",
                         is_jargon_course=1, jargon='{"terms":[]}')
        course = db.get_course("c1")
        assert course is not None
        assert course["parent_course_id"] == "parent1"
        assert course["depth_level"] == 2
        assert course["depth_target"] == 5
        assert course["pacing"] == "fast"
        assert course["is_jargon_course"] == 1

    def test_assignments_has_ai_policy(self):
        db.upsert_course("c1", "T", "d", 3, {})
        with db.tx() as con:
            con.execute(
                "INSERT INTO assignments (id, course_id, title, ai_policy) "
                "VALUES ('a1', 'c1', 'Test', ?)",
                (json.dumps({"level": "prohibited"}),),
            )
            row = con.execute("SELECT ai_policy FROM assignments WHERE id='a1'").fetchone()
        assert row is not None
        policy = json.loads(row["ai_policy"])
        assert policy["level"] == "prohibited"


# ─── Course Tree Queries ────────────────────────────────────────────────────

class TestCourseTreeQueries:
    def _setup_tree(self):
        db.upsert_course("root", "Root CS", "Root", 3, {})
        db.upsert_course("child1", "Algorithms", "Alg", 3, {},
                         parent_course_id="root", depth_level=1)
        db.upsert_course("child2", "Data Structures", "DS", 3, {},
                         parent_course_id="root", depth_level=1)
        db.upsert_course("grandchild", "Sorting", "Sort", 3, {},
                         parent_course_id="child1", depth_level=2)

    def test_get_child_courses(self):
        self._setup_tree()
        children = db.get_child_courses("root")
        assert len(children) == 2
        ids = {c["id"] for c in children}
        assert ids == {"child1", "child2"}

    def test_get_course_tree(self):
        self._setup_tree()
        tree = db.get_course_tree("root")
        assert len(tree) == 4  # root + 2 children + 1 grandchild
        ids = {n["id"] for n in tree}
        assert ids == {"root", "child1", "child2", "grandchild"}

    def test_get_course_depth(self):
        self._setup_tree()
        assert db.get_course_depth("root") == 2

    def test_get_root_course(self):
        self._setup_tree()
        assert db.get_root_course("grandchild") == "root"
        assert db.get_root_course("root") == "root"

    def test_get_course(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        course = db.get_course("c1")
        assert course is not None
        assert course["title"] == "Test"
        assert db.get_course("nonexistent") is None


# ─── Credit Hours ────────────────────────────────────────────────────────────

class TestCreditHours:
    def test_log_and_get_study_hours(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.log_study_hours("c1", 2.5, "study", "Chapter 1")
        db.log_study_hours("c1", 1.0, "lab", "Lab 1")
        hours = db.get_study_hours("c1")
        assert len(hours) == 2
        all_hours = {h["hours"] for h in hours}
        assert all_hours == {2.5, 1.0}

    def test_hours_to_credits(self):
        from core.course_tree import hours_to_credits, CREDIT_HOUR_RATIO
        assert CREDIT_HOUR_RATIO == 45
        assert hours_to_credits(45) == 1.0
        assert hours_to_credits(90) == 2.0
        assert hours_to_credits(0) == 0.0
        assert hours_to_credits(22.5) == 0.5

    def test_course_credit_hours(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.log_study_hours("c1", 5.0)
        assert db.course_credit_hours("c1") >= 5.0


# ─── Pacing ──────────────────────────────────────────────────────────────────

class TestPacing:
    def test_pacing_options(self):
        from core.course_tree import PACING_OPTIONS, PACING_TEMPLATES
        assert set(PACING_OPTIONS) == {"fast", "standard", "slow"}
        for p in PACING_OPTIONS:
            assert p in PACING_TEMPLATES
            assert "concepts_per_lecture" in PACING_TEMPLATES[p]
            assert "lectures_per_module" in PACING_TEMPLATES[p]
            assert "instruction" in PACING_TEMPLATES[p]

    def test_pacing_inheritance(self):
        db.upsert_course("parent", "Parent", "desc", 3, {}, pacing="fast")
        db.upsert_course("child", "Child", "desc", 3, {},
                         parent_course_id="parent", pacing="standard")
        # standard = default, so inherits parent's fast pacing
        assert db.get_pacing_for_course("child") == "fast"

    def test_pacing_explicit_override(self):
        db.upsert_course("parent", "Parent", "desc", 3, {}, pacing="fast")
        db.upsert_course("child", "Child", "desc", 3, {},
                         parent_course_id="parent", pacing="slow")
        # slow != standard, so child's explicit pacing is used
        assert db.get_pacing_for_course("child") == "slow"

    def test_pacing_stored_on_course(self):
        db.upsert_course("c1", "Test", "desc", 3, {}, pacing="slow")
        course = db.get_course("c1")
        assert course["pacing"] == "slow"


# ─── AI Policy ───────────────────────────────────────────────────────────────

class TestAIPolicy:
    def test_default_policies(self):
        from core.course_tree import (
            get_default_ai_policy, AI_POLICY_DEFAULTS, AI_POLICY_LEVELS,
        )
        exam_policy = get_default_ai_policy("exam")
        assert exam_policy["level"] == "prohibited"

        hw_policy = get_default_ai_policy("homework")
        assert hw_policy["level"] == "assisted"

        proj_policy = get_default_ai_policy("project")
        assert proj_policy["level"] == "supervised"

        # All levels are valid
        for atype, policy in AI_POLICY_DEFAULTS.items():
            assert policy["level"] in AI_POLICY_LEVELS

    def test_get_assignment_ai_policy_stored(self):
        from core.course_tree import get_assignment_ai_policy
        stored = json.dumps({"level": "supervised", "verification_type": "oral_explanation"})
        policy = get_assignment_ai_policy({"ai_policy": stored, "type": "homework"})
        assert policy["level"] == "supervised"

    def test_get_assignment_ai_policy_default(self):
        from core.course_tree import get_assignment_ai_policy
        policy = get_assignment_ai_policy({"type": "exam"})
        assert policy["level"] == "prohibited"


# ─── Competency Tracking ────────────────────────────────────────────────────

class TestCompetencyTracking:
    def test_record_and_get_profile(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.record_competency_score("c1", "recall", 85, 100, "quiz1")
        db.record_competency_score("c1", "understanding", 70, 100, "hw1")
        db.record_competency_score("c1", "application", 90, 100, "lab1")

        profile = db.get_competency_profile("c1")
        assert profile["recall"]["avg_score"] == 85.0
        assert profile["understanding"]["avg_score"] == 70.0
        assert profile["application"]["avg_score"] == 90.0
        assert profile["analysis"]["assessments"] == 0

    def test_check_mastery_incomplete(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.record_competency_score("c1", "recall", 85, 100, "q1")
        mastery = db.check_mastery("c1")
        assert not mastery["is_complete"]
        assert "recall" in mastery["mastered"]
        assert len(mastery["untested"]) > 0

    def test_check_mastery_failed(self):
        db.upsert_course("c1", "Test", "desc", 3, {})
        db.record_competency_score("c1", "recall", 50, 100, "q1")
        mastery = db.check_mastery("c1")
        assert "recall" in mastery["failed"]

    def test_blooms_levels(self):
        from core.course_tree import BLOOMS_LEVELS
        assert len(BLOOMS_LEVELS) == 6
        assert BLOOMS_LEVELS[0] == "recall"
        assert BLOOMS_LEVELS[-1] == "evaluation"


# ─── Qualifications ─────────────────────────────────────────────────────────

class TestQualifications:
    def test_benchmarks_seeded(self):
        benchmarks = db.get_all_benchmarks()
        assert len(benchmarks) >= 6
        names = {b["name"] for b in benchmarks}
        assert any("MIT" in n for n in names)
        assert any("Stanford" in n for n in names)
        assert any("CompTIA" in n for n in names)

    def test_qualification_roadmap(self):
        roadmap = db.get_qualification_roadmap("mit_6006")
        assert "benchmark" in roadmap
        assert "remaining" in roadmap
        assert "completed" in roadmap

    def test_check_qualifications(self):
        results = db.check_qualifications()
        assert len(results) >= 6
        for r in results:
            assert "status" in r
            assert r["status"] in ("earned", "in_progress", "locked")

    def test_qualification_roadmap_requires_verified_course_completion(self):
        db.upsert_course("junior_cs301", "Algorithms", "desc", 3, {})
        db.upsert_module("junior_cs301_m1", "junior_cs301", "Sorting", 0, {})
        db.upsert_lecture("junior_cs301_l1", "junior_cs301_m1", "junior_cs301", "Lecture 1", 20, 0, {})
        db.set_progress("junior_cs301_l1", "completed", watch_time_s=1200)

        roadmap = db.get_qualification_roadmap("mit_6006")
        assert "junior_cs301" in roadmap["remaining"]

    def test_qualification_can_progress_with_verified_course_evidence(self):
        db.upsert_course("junior_cs301", "Algorithms", "desc", 3, {})
        db.upsert_module("junior_cs301_m1", "junior_cs301", "Sorting", 0, {})
        db.upsert_lecture("junior_cs301_l1", "junior_cs301_m1", "junior_cs301", "Lecture 1", 20, 0, {})
        db.set_progress("junior_cs301_l1", "completed", watch_time_s=7200)
        db.save_assignment({
            "id": "junior_cs301_q1", "course_id": "junior_cs301",
            "lecture_id": "junior_cs301_l1", "title": "Quiz 1", "type": "quiz", "max_score": 100,
        })
        db.submit_assignment("junior_cs301_q1", 95.0, "Excellent")
        for level in db.BLOOMS_LEVELS:
            db.record_competency_score("junior_cs301", level, 90.0, 100.0, f"{level}_1")
        db.log_study_hours("junior_cs301", 140.0)

        results = db.check_qualifications()
        mit = next(item for item in results if item["id"] == "mit_6006")
        assert mit["verified_course_count"] >= 1
        assert mit["progress_pct"] > 0


# ─── Decomposition Prompts ──────────────────────────────────────────────────

class TestDecompositionPrompts:
    def test_build_decomposition_prompt(self):
        from core.course_tree import build_decomposition_prompt
        course = {"title": "Intro to Algorithms"}
        modules = [{"title": "Sorting"}, {"title": "Searching"}]
        prompt = build_decomposition_prompt(course, modules, depth=1, pacing="standard")
        assert "Intro to Algorithms" in prompt
        assert "Sorting" in prompt
        assert "Searching" in prompt
        assert "standard" in prompt.lower()

    def test_build_decomposition_prompt_depth_3(self):
        from core.course_tree import build_decomposition_prompt
        course = {"title": "Advanced CS"}
        modules = [{"title": "Module 1"}]
        prompt = build_decomposition_prompt(course, modules, depth=3, pacing="slow")
        assert "real-world application" in prompt.lower()
        assert "industry" in prompt.lower()

    def test_build_jargon_prompt(self):
        from core.course_tree import build_jargon_prompt
        course = {"title": "Data Structures"}
        modules = [{"title": "Arrays"}, {"title": "Trees"}]
        prompt = build_jargon_prompt(course, modules)
        assert "Data Structures" in prompt
        assert "etymology" in prompt.lower()

    def test_build_verification_prompt(self):
        from core.course_tree import build_verification_prompt
        assignment = {"title": "Homework 1", "type": "homework", "score": 90}
        prompt = build_verification_prompt(assignment, "Sorting Algorithms")
        assert "Homework 1" in prompt
        assert "prohibited" in prompt.lower()

    def test_register_sub_courses(self):
        from core.course_tree import register_sub_courses
        db.upsert_course("parent", "Parent", "desc", 3, {})
        sub = [{
            "course_id": "parent_sub1",
            "title": "Sub Course 1",
            "description": "A sub-course",
            "credits": 3,
            "modules": [{
                "module_id": "parent_sub1_m1",
                "title": "Module 1",
                "lectures": [{
                    "lecture_id": "parent_sub1_m1_l1",
                    "title": "Lecture 1",
                    "duration_min": 20,
                }],
            }],
        }]
        ids = register_sub_courses(
            "parent", sub, depth=1, pacing="standard", tx_func=db.tx,
            upsert_course_func=db.upsert_course,
            upsert_module_func=db.upsert_module,
            upsert_lecture_func=db.upsert_lecture,
        )
        assert ids == ["parent_sub1"]
        course = db.get_course("parent_sub1")
        assert course is not None
        assert course["parent_course_id"] == "parent"
        assert course["depth_level"] == 1
        mods = db.get_modules("parent_sub1")
        assert len(mods) == 1
        lecs = db.get_lectures(mods[0]["id"])
        assert len(lecs) == 1


# ─── Assessment Time Tracking ───────────────────────────────────────────────

class TestAssessmentTimeTracking:
    def test_start_and_submit_records_duration(self):
        import time
        db.upsert_course("cs100", "CS 100", "", 3, {})
        db.upsert_module("cs100_m1", "cs100", "Mod 1", 0, {})
        db.upsert_lecture("cs100_m1_l1", "cs100_m1", "cs100", "Lec 1", 20, 0, {})
        db.save_assignment({
            "id": "cs100_a1", "lecture_id": "cs100_m1_l1",
            "course_id": "cs100", "title": "Quiz 1", "type": "quiz", "max_score": 100,
        })
        db.start_assignment("cs100_a1")
        # Verify started_at is set
        with db.tx() as con:
            row = con.execute("SELECT started_at FROM assignments WHERE id='cs100_a1'").fetchone()
        assert row["started_at"] is not None
        # Submit and check duration is recorded
        db.submit_assignment("cs100_a1", 85.0, "Nice work")
        with db.tx() as con:
            row = con.execute("SELECT duration_s FROM assignments WHERE id='cs100_a1'").fetchone()
        assert row["duration_s"] >= 0

    def test_get_assessment_hours(self):
        db.upsert_course("cs200", "CS 200", "", 3, {})
        # Manually set a duration on an assignment
        with db.tx() as con:
            con.execute(
                "INSERT INTO assignments (id, course_id, title, type, duration_s, submitted_at, max_score) "
                "VALUES ('cs200_a1', 'cs200', 'HW 1', 'homework', 3600, 1000, 100)"
            )
        hours = db.get_assessment_hours("cs200")
        assert hours == 1.0

    def test_start_assignment_idempotent(self):
        import time
        db.upsert_course("cs300", "CS 300", "", 3, {})
        db.save_assignment({
            "id": "cs300_a1", "course_id": "cs300", "title": "Q1", "type": "quiz", "max_score": 100,
        })
        db.start_assignment("cs300_a1")
        with db.tx() as con:
            first = con.execute("SELECT started_at FROM assignments WHERE id='cs300_a1'").fetchone()["started_at"]
        time.sleep(0.05)
        db.start_assignment("cs300_a1")  # second call should not update
        with db.tx() as con:
            second = con.execute("SELECT started_at FROM assignments WHERE id='cs300_a1'").fetchone()["started_at"]
        assert first == second


# ─── Prove-It Flagging ──────────────────────────────────────────────────────

class TestProveItFlagging:
    def test_flag_prove_it_low_score(self):
        db.upsert_course("cs400", "CS 400", "", 3, {})
        db.upsert_module("cs400_m1", "cs400", "Mod", 0, {})
        db.upsert_lecture("cs400_m1_l1", "cs400_m1", "cs400", "Lec", 20, 0, {})
        # Original assignment
        db.save_assignment({
            "id": "cs400_hw1", "lecture_id": "cs400_m1_l1",
            "course_id": "cs400", "title": "Homework 1", "type": "homework", "max_score": 100,
        })
        db.submit_assignment("cs400_hw1", 90.0, "Great")
        # Prove-it assignment (much lower score)
        with db.tx() as con:
            con.execute(
                "INSERT INTO assignments (id, course_id, title, type, max_score, score, submitted_at) "
                "VALUES ('cs400_pv1', 'cs400', 'Prove-It: Homework 1', 'verification', 100, 30.0, 1000)"
            )
        flag = db.flag_prove_it("cs400_pv1")
        assert flag is not None
        assert flag["flagged"] is True

    def test_no_flag_when_scores_close(self):
        db.upsert_course("cs500", "CS 500", "", 3, {})
        db.upsert_module("cs500_m1", "cs500", "M", 0, {})
        db.upsert_lecture("cs500_m1_l1", "cs500_m1", "cs500", "L", 20, 0, {})
        db.save_assignment({
            "id": "cs500_hw1", "lecture_id": "cs500_m1_l1",
            "course_id": "cs500", "title": "HW 1", "type": "homework", "max_score": 100,
        })
        db.submit_assignment("cs500_hw1", 80.0, "OK")
        with db.tx() as con:
            con.execute(
                "INSERT INTO assignments (id, course_id, title, type, max_score, score, submitted_at) "
                "VALUES ('cs500_pv1', 'cs500', 'Prove-It: HW 1', 'verification', 100, 75.0, 1000)"
            )
        flag = db.flag_prove_it("cs500_pv1")
        assert flag is None

    def test_flag_returns_none_for_non_verification(self):
        db.upsert_course("cs600", "CS 600", "", 3, {})
        db.save_assignment({
            "id": "cs600_hw1", "course_id": "cs600", "title": "HW", "type": "homework", "max_score": 100,
        })
        flag = db.flag_prove_it("cs600_hw1")
        assert flag is None


# ─── Time-to-Degree Estimate ────────────────────────────────────────────────

class TestTimeToDegree:
    def test_time_to_degree_returns_dict(self):
        result = db.time_to_degree_estimate("Bachelor")
        assert result is not None
        assert result["target"] == "Bachelor"
        assert "credits_needed" in result
        assert "hours_needed" in result

    def test_time_to_degree_invalid_degree(self):
        result = db.time_to_degree_estimate("Fake Degree")
        assert result is None

    def test_degree_tracks_have_min_hours(self):
        from core.db_grades import DEGREE_TRACKS
        for deg, info in DEGREE_TRACKS.items():
            assert "min_hours" in info, f"{deg} missing min_hours"
            assert info["min_hours"] == info["min_credits"] * 45


# ─── Benchmark Comparison ───────────────────────────────────────────────────

class TestBenchmarkComparison:
    def test_get_benchmark_comparison(self):
        result = db.get_benchmark_comparison("mit_6006")
        assert "error" not in result
        assert "coverage_pct" in result
        assert "rigor_pct" in result
        assert "gap_topics" in result
        assert result["school"] == "MIT"

    def test_benchmark_comparison_uses_verified_course_evidence(self):
        db.upsert_course("junior_cs301", "Algorithms", "desc", 3, {})
        db.upsert_module("junior_cs301_m1", "junior_cs301", "Sorting", 0, {})
        db.upsert_lecture("junior_cs301_l1", "junior_cs301_m1", "junior_cs301", "Lecture 1", 20, 0, {})
        db.set_progress("junior_cs301_l1", "completed", watch_time_s=600)

        result = db.get_benchmark_comparison("mit_6006")
        assert result["coverage_pct"] == 0
        assert "junior_cs301" in result["gap_topics"]

    def test_benchmark_comparison_not_found(self):
        result = db.get_benchmark_comparison("nonexistent_benchmark")
        assert "error" in result

    def test_credits_earned_returns_float(self):
        credits = db.credits_earned()
        assert isinstance(credits, float)
