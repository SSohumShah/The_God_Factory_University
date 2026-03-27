"""
SQLite persistence layer for The God Factory University.
All tables are created on first import. Thread-safe via WAL mode.

Sub-modules (DEVELOPMENT.md Rule 5):
  - db_achievements.py  — achievement defs, seeding, triggers
  - db_assignments.py   — assignment CRUD, submission, prove-it flagging
  - db_grades.py        — GPA, grade scale, degree tracks
  - db_import.py        — bulk JSON import, schema validation
  - db_quests.py        — weekly quest logic
  - db_levels.py        — grade level system (K-postdoc)
  - db_subjects.py      — subject taxonomy (domain/field/subfield)
  - db_programs.py      — degree programs & enrollments
  - db_activity.py      — activity logging & student profile
  - placement.py        — placement test engine
  - test_prep.py        — standardized test prep (GED/SAT/ACT/GRE)
  - db_shims.py         — compatibility aliases for UI pages
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

# ─── Sub-module imports (canonical data & helpers) ──────────────────────────
from core.db_achievements import (
    _ACHIEVEMENT_DEFS,
    seed_achievements as _seed_achievements_raw,
    unlock_achievement as _unlock_achievement_raw,
    get_achievements as _get_achievements_raw,
    check_achievements_xp as _check_achievements_xp_raw,
    check_achievements_degrees as _check_achievements_degrees_raw,
)
from core.db_grades import (
    GRADE_SCALE,
    DEGREE_TRACKS,
    score_to_grade,
    compute_gpa as _compute_gpa_raw,
    credits_earned as _credits_earned_raw,
    eligible_degrees as _eligible_degrees_raw,
    time_to_degree_estimate as _time_to_degree_estimate_raw,
    get_academic_progress_summary as _get_academic_progress_summary_raw,
    get_course_completion_audit as _get_course_completion_audit_raw,
)
from core.db_assignments import (
    save_assignment as _save_assignment_raw,
    submit_assignment as _submit_assignment_raw,
    start_assignment as _start_assignment_raw,
    get_assessment_hours as _get_assessment_hours_raw,
    flag_prove_it as _flag_prove_it_raw,
    get_assignments as _get_assignments_raw,
    get_overdue as _get_overdue_raw,
)
from core.db_import import (
    validate_course_json,
    bulk_import_json as _bulk_import_json_raw,
)
from core.db_levels import (
    create_tables as _create_level_tables,
    seed_grade_levels as _seed_grade_levels_raw,
    get_all_levels as _get_all_levels_raw,
    get_level_by_id as _get_level_by_id_raw,
)
from core.db_quests import (
    seed_weekly_quests as _seed_weekly_quests_raw,
    get_active_quests as _get_active_quests_raw,
    update_quest_progress as _update_quest_progress_raw,
)
from core.db_subjects import (
    create_tables as _create_subject_tables,
    seed_subjects as _seed_subjects_raw,
    get_domains as _get_domains_raw,
    get_children as _get_children_raw,
    get_subject as _get_subject_raw,
    get_all_subjects as _get_all_subjects_raw,
)
from core.placement import create_tables as _create_placement_tables
from core.test_prep import create_tables as _create_test_prep_tables
from core.db_programs import (
    create_tables as _create_program_tables,
    seed_programs as _seed_programs_raw,
    get_all_programs as _get_all_programs_raw,
    get_program as _get_program_raw,
    enroll as _enroll_raw,
    get_enrollments as _get_enrollments_raw,
)
from core.db_activity import (
    create_tables as _create_activity_tables,
    log_activity as _log_activity_raw,
    get_activity_summary as _get_activity_summary_raw,
)
from core.db_facade_student import LEVELS, make_student_facade
from core.db_facade_curriculum import make_curriculum_facade
from core.db_facade_ai import make_ai_facade
from core.db_audit import (
    create_tables as _create_audit_tables,
    create_course_audit_job as _create_course_audit_job_raw,
    list_audit_jobs as _list_audit_jobs_raw,
    get_audit_job as _get_audit_job_raw,
    get_audit_packets as _get_audit_packets_raw,
    get_next_pending_packet as _get_next_pending_packet_raw,
    mark_job_started as _mark_job_started_raw,
    record_packet_review as _record_packet_review_raw,
    fail_audit_job as _fail_audit_job_raw,
    add_remediation_item as _add_remediation_item_raw,
    list_remediation_backlog as _list_remediation_backlog_raw,
)
from core.university import create_tables as _create_university_tables
from core.course_tree import (
    create_tables as _create_course_tree_tables,
    seed_benchmarks as _seed_benchmarks_raw,
    CREDIT_HOUR_RATIO,
    AI_POLICY_LEVELS,
    BLOOMS_LEVELS,
    PACING_OPTIONS,
    get_child_courses as _get_child_courses_raw,
    get_course_tree as _get_course_tree_raw,
    get_course_depth as _get_course_depth_raw,
    get_root_course as _get_root_course_raw,
    course_completion_pct as _course_completion_pct_raw,
    course_credit_hours as _course_credit_hours_raw,
    hours_to_credits,
    log_study_hours as _log_study_hours_raw,
    get_study_hours as _get_study_hours_raw,
    check_qualifications as _check_qualifications_raw,
    get_qualifications as _get_qualifications_raw,
    get_all_benchmarks as _get_all_benchmarks_raw,
    get_qualification_roadmap as _get_qualification_roadmap_raw,
    get_pacing_for_course as _get_pacing_for_course_raw,
    PACING_TEMPLATES,
    AI_POLICY_DEFAULTS,
    get_default_ai_policy,
    get_assignment_ai_policy,
    record_competency_score as _record_competency_score_raw,
    get_competency_profile as _get_competency_profile_raw,
    check_mastery as _check_mastery_raw,
    get_benchmark_comparison as _get_benchmark_comparison_raw,
)
from core.db_shims import make_shims

DB_PATH = Path(__file__).resolve().parent.parent / "university.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def tx():
    con = _conn()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with tx() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            credits     INTEGER DEFAULT 3,
            data        TEXT,
            source      TEXT DEFAULT 'imported',
            subject_id  TEXT,
            parent_course_id TEXT,
            depth_level INTEGER DEFAULT 0,
            depth_target INTEGER DEFAULT 0,
            pacing      TEXT DEFAULT 'standard',
            credit_hours REAL DEFAULT 0,
            is_jargon_course INTEGER DEFAULT 0,
            jargon      TEXT,
            created_at  REAL DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS modules (
            id          TEXT PRIMARY KEY,
            course_id   TEXT NOT NULL,
            title       TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            data        TEXT,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lectures (
            id          TEXT PRIMARY KEY,
            module_id   TEXT NOT NULL,
            course_id   TEXT NOT NULL,
            title       TEXT NOT NULL,
            duration_min INTEGER DEFAULT 60,
            order_index INTEGER DEFAULT 0,
            data        TEXT,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS progress (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lecture_id   TEXT NOT NULL,
            status       TEXT DEFAULT 'not_started',
            watch_time_s REAL DEFAULT 0,
            score        REAL,
            completed_at REAL,
            UNIQUE(lecture_id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id           TEXT PRIMARY KEY,
            lecture_id   TEXT,
            course_id    TEXT,
            title        TEXT NOT NULL,
            description  TEXT,
            type         TEXT DEFAULT 'quiz',
            due_at       REAL,
            submitted_at REAL,
            started_at   REAL,
            duration_s   REAL DEFAULT 0,
            score        REAL,
            max_score    REAL DEFAULT 100,
            feedback     TEXT,
            data         TEXT,
            weight       REAL DEFAULT 1.0,
            term_id      TEXT,
            late_penalty REAL DEFAULT 0.0,
            ai_policy    TEXT
        );

        CREATE TABLE IF NOT EXISTS xp_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT,
            xp_gained   INTEGER DEFAULT 0,
            description TEXT,
            occurred_at REAL DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS achievements (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            category    TEXT,
            xp_reward   INTEGER DEFAULT 50,
            unlocked_at REAL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            role        TEXT,
            content     TEXT,
            occurred_at REAL DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS llm_generated (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT,
            type        TEXT,
            imported    INTEGER DEFAULT 0,
            created_at  REAL DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS quests (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            target      INTEGER NOT NULL DEFAULT 1,
            progress    INTEGER NOT NULL DEFAULT 0,
            xp_reward   INTEGER NOT NULL DEFAULT 50,
            week_start  TEXT NOT NULL,
            completed   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS terms (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            start_date  TEXT,
            end_date    TEXT,
            order_index INTEGER DEFAULT 0
        );

        INSERT OR IGNORE INTO settings VALUES ('deadlines_enabled', '0');
        INSERT OR IGNORE INTO settings VALUES ('voice_id', 'en-US-AriaNeural');
        INSERT OR IGNORE INTO settings VALUES ('tts_voice', 'en-US-AriaNeural');
        INSERT OR IGNORE INTO settings VALUES ('tts_rate', '0');
        INSERT OR IGNORE INTO settings VALUES ('tts_pitch', '0');
        INSERT OR IGNORE INTO settings VALUES ('binaural_mode', 'gamma_40hz');
        INSERT OR IGNORE INTO settings VALUES ('binaural_preset', 'gamma_40hz');
        INSERT OR IGNORE INTO settings VALUES ('llm_provider', 'ollama');
        INSERT OR IGNORE INTO settings VALUES ('llm_model', 'llama3');
        INSERT OR IGNORE INTO settings VALUES ('llm_api_key', '');
        INSERT OR IGNORE INTO settings VALUES ('llm_base_url', '');
        INSERT OR IGNORE INTO settings VALUES ('video_fps', '15');
        INSERT OR IGNORE INTO settings VALUES ('video_width', '960');
        INSERT OR IGNORE INTO settings VALUES ('video_height', '540');
        INSERT OR IGNORE INTO settings VALUES ('render_provider', 'local');
        INSERT OR IGNORE INTO settings VALUES ('runway_api_key', '');
        INSERT OR IGNORE INTO settings VALUES ('pika_api_key', '');
        INSERT OR IGNORE INTO settings VALUES ('comfy_endpoint', 'http://localhost:8188');
        INSERT OR IGNORE INTO settings VALUES ('student_name', 'Scholar');
        INSERT OR IGNORE INTO settings VALUES ('xp_total', '0');
        INSERT OR IGNORE INTO settings VALUES ('streak_days', '0');
        INSERT OR IGNORE INTO settings VALUES ('streak_last_date', '');
        INSERT OR IGNORE INTO settings VALUES ('_pending_level_up', '');
        INSERT OR IGNORE INTO settings VALUES ('enrollment_date', '');
        INSERT OR IGNORE INTO settings VALUES ('grade_level', '');

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL DEFAULT (unixepoch())
        );
        """)
    # Sub-module tables
    _create_level_tables(tx)
    _create_subject_tables(tx)
    _create_placement_tables(tx)
    _create_test_prep_tables(tx)
    _create_program_tables(tx)
    _create_activity_tables(tx)
    _create_audit_tables(tx)
    _create_university_tables(tx)
    _create_course_tree_tables(tx)


# ─── Schema migrations ────────────────────────────────────────────────────────

_MIGRATIONS: list[tuple[int, str, str]] = [
    # (version, label, SQL)
    (1, "add subject_id to courses", "ALTER TABLE courses ADD COLUMN subject_id TEXT;"),
    (2, "add course tree columns",
     "ALTER TABLE courses ADD COLUMN parent_course_id TEXT;\n"
     "ALTER TABLE courses ADD COLUMN depth_level INTEGER DEFAULT 0;\n"
     "ALTER TABLE courses ADD COLUMN depth_target INTEGER DEFAULT 0;\n"
     "ALTER TABLE courses ADD COLUMN pacing TEXT DEFAULT 'standard';\n"
     "ALTER TABLE courses ADD COLUMN credit_hours REAL DEFAULT 0;\n"
     "ALTER TABLE courses ADD COLUMN is_jargon_course INTEGER DEFAULT 0;\n"
     "ALTER TABLE courses ADD COLUMN jargon TEXT;"),
    (3, "add ai_policy to assignments",
     "ALTER TABLE assignments ADD COLUMN ai_policy TEXT;"),
    (4, "add assessment time tracking to assignments",
     "ALTER TABLE assignments ADD COLUMN started_at REAL;\n"
     "ALTER TABLE assignments ADD COLUMN duration_s REAL DEFAULT 0;"),
]


def get_schema_version() -> int:
    with tx() as con:
        row = con.execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()
    return row["v"] if row and row["v"] is not None else 0


def run_migrations() -> int:
    current = get_schema_version()
    applied = 0
    for version, _label, sql in _MIGRATIONS:
        if version <= current:
            continue
        with tx() as con:
            try:
                con.executescript(sql)
            except sqlite3.OperationalError:
                pass  # e.g. column already exists from DDL
            con.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
        applied += 1
    return applied


# ─── Assignments (delegated to db_assignments.py) ──────────────────────────────

def save_assignment(assignment: dict) -> None:
    _save_assignment_raw(assignment, tx)


def submit_assignment(assignment_id: str, score: float | None, feedback: str = "") -> None:
    _submit_assignment_raw(
        assignment_id, score, feedback, tx, get_setting,
        add_xp, unlock_achievement, update_quest_progress,
        _check_achievements_degrees,
    )
    log_activity("assignment_submit", metadata={"assignment_id": assignment_id, "graded": score is not None})


def start_assignment(assignment_id: str) -> None:
    _start_assignment_raw(assignment_id, tx)


def get_assessment_hours(course_id: str) -> float:
    return _get_assessment_hours_raw(course_id, tx)


def flag_prove_it(assignment_id: str) -> dict | None:
    return _flag_prove_it_raw(assignment_id, tx)


def get_assignments(course_id: str | None = None) -> list[dict]:
    return _get_assignments_raw(course_id, tx)


def get_overdue(now: float | None = None) -> list[dict]:
    return _get_overdue_raw(now, tx)


# ─── GPA & Grades (delegated to db_grades.py) ─────────────────────────────────

# score_to_grade, GRADE_SCALE, DEGREE_TRACKS impor


# ─── Terms & Enrollment ───────────────────────────────────────────────────────

def upsert_term(term_id: str, title: str, start_date: str = "", end_date: str = "", order_index: int = 0) -> None:
    with tx() as con:
        con.execute(
            "INSERT OR REPLACE INTO terms (id,title,start_date,end_date,order_index) VALUES (?,?,?,?,?)",
            (term_id, title, start_date, end_date, order_index),
        )


def get_terms() -> list[dict]:
    with tx() as con:
        rows = con.execute("SELECT * FROM terms ORDER BY order_index, id").fetchall()
    return [dict(r) for r in rows]


def get_assignments_by_term(term_id: str) -> list[dict]:
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM assignments WHERE term_id=? ORDER BY due_at", (term_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_enrollment_date() -> str:
    ed = get_setting("enrollment_date", "")
    if not ed:
        ed = datetime.now().strftime("%Y-%m-%d")
        set_setting("enrollment_date", ed)
    return ed


def time_to_degree_days() -> int:
    ed = get_enrollment_date()
    start = datetime.strptime(ed, "%Y-%m-%d")
    return (datetime.now() - start).days


_student_facade = make_student_facade(
    tx=tx,
    compute_gpa_raw=_compute_gpa_raw,
    credits_earned_raw=_credits_earned_raw,
    eligible_degrees_raw=_eligible_degrees_raw,
    get_academic_progress_summary_raw=_get_academic_progress_summary_raw,
    get_course_completion_audit_raw=_get_course_completion_audit_raw,
    log_activity_raw=_log_activity_raw,
    get_activity_summary_raw=_get_activity_summary_raw,
    unlock_achievement_raw=_unlock_achievement_raw,
    check_achievements_xp_raw=_check_achievements_xp_raw,
    update_quest_progress_raw=_update_quest_progress_raw,
    get_enrollment_date=get_enrollment_date,
    time_to_degree_days=time_to_degree_days,
)

get_setting = _student_facade["get_setting"]
set_setting = _student_facade["set_setting"]
add_xp = _student_facade["add_xp"]
get_xp = _student_facade["get_xp"]
get_level = _student_facade["get_level"]
get_progress = _student_facade["get_progress"]
set_progress = _student_facade["set_progress"]
count_completed = _student_facade["count_completed"]
compute_gpa = _student_facade["compute_gpa"]
credits_earned = _student_facade["credits_earned"]
eligible_degrees = _student_facade["eligible_degrees"]
get_academic_progress_summary = _student_facade["get_academic_progress_summary"]
get_course_completion_audit = _student_facade["get_course_completion_audit"]
log_activity = _student_facade["log_activity"]
get_activity_summary = _student_facade["get_activity_summary"]
get_student_world_state = _student_facade["get_student_world_state"]

_curriculum_facade = make_curriculum_facade(
    tx=tx,
    get_child_courses_raw=_get_child_courses_raw,
    get_course_tree_raw=_get_course_tree_raw,
    get_course_depth_raw=_get_course_depth_raw,
    get_root_course_raw=_get_root_course_raw,
    course_completion_pct_raw=_course_completion_pct_raw,
    course_credit_hours_raw=_course_credit_hours_raw,
    log_study_hours_raw=_log_study_hours_raw,
    get_study_hours_raw=_get_study_hours_raw,
    check_qualifications_raw=_check_qualifications_raw,
    get_qualifications_raw=_get_qualifications_raw,
    get_all_benchmarks_raw=_get_all_benchmarks_raw,
    get_qualification_roadmap_raw=_get_qualification_roadmap_raw,
    get_pacing_for_course_raw=_get_pacing_for_course_raw,
    record_competency_score_raw=_record_competency_score_raw,
    get_competency_profile_raw=_get_competency_profile_raw,
    check_mastery_raw=_check_mastery_raw,
    time_to_degree_estimate_raw=_time_to_degree_estimate_raw,
    get_benchmark_comparison_raw=_get_benchmark_comparison_raw,
    compute_gpa=compute_gpa,
    credits_earned=credits_earned,
)

upsert_course = _curriculum_facade["upsert_course"]
upsert_module = _curriculum_facade["upsert_module"]
upsert_lecture = _curriculum_facade["upsert_lecture"]
get_all_courses = _curriculum_facade["get_all_courses"]
get_course = _curriculum_facade["get_course"]
get_modules = _curriculum_facade["get_modules"]
get_lectures = _curriculum_facade["get_lectures"]
get_lecture = _curriculum_facade["get_lecture"]
delete_course = _curriculum_facade["delete_course"]
get_child_courses = _curriculum_facade["get_child_courses"]
get_course_tree = _curriculum_facade["get_course_tree"]
get_course_depth = _curriculum_facade["get_course_depth"]
get_root_course = _curriculum_facade["get_root_course"]
course_completion_pct = _curriculum_facade["course_completion_pct"]
course_credit_hours = _curriculum_facade["course_credit_hours"]
log_study_hours = _curriculum_facade["log_study_hours"]
get_study_hours = _curriculum_facade["get_study_hours"]
check_qualifications = _curriculum_facade["check_qualifications"]
get_qualifications = _curriculum_facade["get_qualifications"]
get_all_benchmarks = _curriculum_facade["get_all_benchmarks"]
get_qualification_roadmap = _curriculum_facade["get_qualification_roadmap"]
get_pacing_for_course = _curriculum_facade["get_pacing_for_course"]
record_competency_score = _curriculum_facade["record_competency_score"]
get_competency_profile = _curriculum_facade["get_competency_profile"]
check_mastery = _curriculum_facade["check_mastery"]
time_to_degree_estimate = _curriculum_facade["time_to_degree_estimate"]
get_benchmark_comparison = _curriculum_facade["get_benchmark_comparison"]


def update_lecture_data(lecture_id: str, data: dict) -> None:
    """Update only the data JSON column for an existing lecture."""
    with tx() as con:
        con.execute("UPDATE lectures SET data = ? WHERE id = ?", (json.dumps(data), lecture_id))


# ─── Achievements (delegated to db_achievements.py) ────────────────────────────


def seed_achievements() -> None:
    _seed_achievements_raw(tx)


def unlock_achievement(achievement_id: str) -> bool:
    return _unlock_achievement_raw(achievement_id, tx, add_xp)


def get_achievements() -> list[dict]:
    return _get_achievements_raw(tx)


def _check_achievements_xp(total_xp: int) -> None:
    _check_achievements_xp_raw(total_xp, unlock_achievement)


def _check_achievements_degrees() -> None:
    _check_achievements_degrees_raw(eligible_degrees, unlock_achievement)


_ai_facade = make_ai_facade(
    tx=tx,
    get_course=get_course,
    get_modules=get_modules,
    get_lectures=get_lectures,
    get_progress=get_progress,
    get_assignments=get_assignments,
    get_competency_profile=get_competency_profile,
    get_study_hours=get_study_hours,
    get_course_completion_audit=get_course_completion_audit,
    create_course_audit_job_raw=_create_course_audit_job_raw,
    list_audit_jobs_raw=_list_audit_jobs_raw,
    get_audit_job_raw=_get_audit_job_raw,
    get_audit_packets_raw=_get_audit_packets_raw,
    get_next_pending_packet_raw=_get_next_pending_packet_raw,
    mark_job_started_raw=_mark_job_started_raw,
    record_packet_review_raw=_record_packet_review_raw,
    fail_audit_job_raw=_fail_audit_job_raw,
    add_remediation_item_raw=_add_remediation_item_raw,
    list_remediation_backlog_raw=_list_remediation_backlog_raw,
    bulk_import_json_raw=_bulk_import_json_raw,
    upsert_course=upsert_course,
    upsert_module=upsert_module,
    upsert_lecture=upsert_lecture,
    unlock_achievement=unlock_achievement,
    add_xp=add_xp,
    save_assignment_raw=_save_assignment_raw,
)

append_chat = _ai_facade["append_chat"]
get_chat = _ai_facade["get_chat"]
_save_llm_generated_canonical = _ai_facade["save_llm_generated_raw"]
get_llm_generated = _ai_facade["get_llm_generated"]
mark_imported = _ai_facade["mark_imported"]
create_course_audit_job = _ai_facade["create_course_audit_job"]
list_audit_jobs = _ai_facade["list_audit_jobs"]
get_audit_job = _ai_facade["get_audit_job"]
get_audit_packets = _ai_facade["get_audit_packets"]
get_next_pending_packet = _ai_facade["get_next_pending_packet"]
mark_audit_job_started = _ai_facade["mark_audit_job_started"]
record_audit_packet_review = _ai_facade["record_audit_packet_review"]
fail_audit_job = _ai_facade["fail_audit_job"]
add_remediation_item = _ai_facade["add_remediation_item"]
list_remediation_backlog = _ai_facade["list_remediation_backlog"]
bulk_import_json = _ai_facade["bulk_import_json"]


# ─── Weekly Quests (delegated to db_quests.py) ──────────────────────────────────

def seed_weekly_quests() -> None:
    _seed_weekly_quests_raw(tx)


def get_active_quests() -> list[dict]:
    return _get_active_quests_raw(tx)


def update_quest_progress(quest_prefix: str, increment: int = 1) -> None:
    _update_quest_progress_raw(quest_prefix, tx, add_xp, increment)


# ─── Grade Levels (delegated to db_levels.py) ──────────────────────────────────

def get_grade_levels() -> list[dict]:
    return _get_all_levels_raw(tx)


def get_grade_level(level_id: str) -> dict | None:
    return _get_level_by_id_raw(level_id, tx)


# ─── Subjects (delegated to db_subjects.py) ────────────────────────────────────

def get_subject_domains() -> list[dict]:
    return _get_domains_raw(tx)


def get_subject_children(parent_id: str) -> list[dict]:
    return _get_children_raw(parent_id, tx)


def get_subject(subject_id: str) -> dict | None:
    return _get_subject_raw(subject_id, tx)


def get_all_subjects() -> list[dict]:
    return _get_all_subjects_raw(tx)


# ─── Programs (delegated to db_programs.py) ────────────────────────────────────────

def get_all_programs() -> list[dict]:
    return _get_all_programs_raw(tx)


def get_program(program_id: str) -> dict | None:
    return _get_program_raw(program_id, tx)


def enroll_program(program_id: str) -> str:
    return _enroll_raw(program_id, tx)


def get_enrollments() -> list[dict]:
    return _get_enrollments_raw(tx)


# ─── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
run_migrations()
_seed_programs_raw(tx)
seed_achievements()
seed_weekly_quests()
_seed_grade_levels_raw(tx)
_seed_subjects_raw(tx)
_seed_benchmarks_raw(tx)


# ─── Compatibility shims (re-exported for UI pages) ────────────────────────────

_shims = make_shims(
    set_setting=set_setting,
    get_setting=get_setting,
    get_achievements=get_achievements,
    get_xp=get_xp,
    append_chat=append_chat,
    get_chat=get_chat,
    get_level=get_level,
    compute_gpa=compute_gpa,
    tx=tx,
    save_llm_generated_raw=_save_llm_generated_canonical,
)

save_setting = _shims["save_setting"]
get_all_achievements = _shims["get_all_achievements"]
get_total_xp = _shims["get_total_xp"]
save_chat_history = _shims["save_chat_history"]
get_chat_history = _shims["get_chat_history"]
get_xp_history = _shims["get_xp_history"]
get_level_info = _shims["get_level_info"]
get_gpa = _shims["get_gpa"]
save_llm_generated = _shims["save_llm_generated"]
save_llm_generated_raw = _save_llm_generated_canonical