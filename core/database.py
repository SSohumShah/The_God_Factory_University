"""
SQLite persistence layer for Arcane University.
All tables are created on first import. Thread-safe via WAL mode.

Sub-modules (DEVELOPMENT.md Rule 5):
  - db_achievements.py  — achievement defs, seeding, triggers
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
            score        REAL,
            max_score    REAL DEFAULT 100,
            feedback     TEXT,
            data         TEXT,
            weight       REAL DEFAULT 1.0,
            term_id      TEXT,
            late_penalty REAL DEFAULT 0.0
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
        INSERT OR IGNORE INTO settings VALUES ('binaural_mode', 'gamma_40hz');
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


# ─── Schema migrations ────────────────────────────────────────────────────────

_MIGRATIONS: list[tuple[int, str, str]] = [
    # (version, label, SQL)
    (1, "add subject_id to courses", "ALTER TABLE courses ADD COLUMN subject_id TEXT;"),
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


# ─── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with tx() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with tx() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))


# ─── XP & Level ────────────────────────────────────────────────────────────────

LEVELS = [
    (0,     "Seeker"),
    (100,   "Initiate"),
    (300,   "Scholar"),
    (700,   "Adept"),
    (1500,  "Sorcerer"),
    (3000,  "Sage"),
    (6000,  "Arcane"),
    (10000, "Grandmaster"),
    (20000, "Luminary"),
    (50000, "Archon"),
]


def add_xp(amount: int, description: str, event_type: str = "general") -> int:
    old_total = int(get_setting("xp_total", "0"))
    # Streak bonus: consecutive days with activity
    today = datetime.now().strftime("%Y-%m-%d")
    last_date = get_setting("streak_last_date", "")
    streak = int(get_setting("streak_days", "0"))
    if last_date != today:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last_date == yesterday:
            streak += 1
        elif last_date:
            streak = 1
        else:
            streak = 1
        set_setting("streak_days", str(streak))
        set_setting("streak_last_date", today)
    # Apply streak bonus (5% per day, max 50%)
    bonus_pct = min(streak * 5, 50) / 100.0
    effective = amount + int(amount * bonus_pct)
    total = old_total + effective
    set_setting("xp_total", str(total))
    with tx() as con:
        con.execute(
            "INSERT INTO xp_events (event_type,xp_gained,description) VALUES (?,?,?)",
            (event_type, effective, description),
        )
    # Detect level-up
    old_level = get_level(old_total)[0]
    new_level = get_level(total)[0]
    if new_level > old_level:
        set_setting("_pending_level_up", LEVELS[new_level][1])
    _check_achievements_xp(total)
    # Update XP quest (skip if this XP is from a quest to avoid recursion)
    if event_type != "quest":
        update_quest_progress("earn_200_xp", effective)
    return total


def get_xp() -> int:
    return int(get_setting("xp_total", "0"))


def get_level(xp: int | None = None) -> tuple[int, str, int, int]:
    """Returns (level_index, title, current_xp_in_level, xp_to_next)."""
    if xp is None:
        xp = get_xp()
    idx = 0
    for i, (threshold, _) in enumerate(LEVELS):
        if xp >= threshold:
            idx = i
    title = LEVELS[idx][1]
    current = LEVELS[idx][0]
    nxt = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else LEVELS[idx][0] + 99999
    return idx, title, xp - current, nxt - current


# ─── Courses ───────────────────────────────────────────────────────────────────

def upsert_course(course_id: str, title: str, description: str, credits: int, data: dict, source: str = "imported") -> None:
    with tx() as con:
        con.execute(
            "INSERT OR REPLACE INTO courses (id,title,description,credits,data,source) VALUES (?,?,?,?,?,?)",
            (course_id, title, description, credits, json.dumps(data), source),
        )


def upsert_module(module_id: str, course_id: str, title: str, order_index: int, data: dict) -> None:
    with tx() as con:
        con.execute(
            "INSERT OR REPLACE INTO modules (id,course_id,title,order_index,data) VALUES (?,?,?,?,?)",
            (module_id, course_id, title, order_index, json.dumps(data)),
        )


def upsert_lecture(lecture_id: str, module_id: str, course_id: str, title: str, duration_min: int, order_index: int, data: dict) -> None:
    with tx() as con:
        con.execute(
            "INSERT OR REPLACE INTO lectures (id,module_id,course_id,title,duration_min,order_index,data) VALUES (?,?,?,?,?,?,?)",
            (lecture_id, module_id, course_id, title, duration_min, order_index, json.dumps(data)),
        )


def get_all_courses() -> list[dict]:
    with tx() as con:
        rows = con.execute("SELECT * FROM courses ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def get_modules(course_id: str) -> list[dict]:
    with tx() as con:
        rows = con.execute("SELECT * FROM modules WHERE course_id=? ORDER BY order_index", (course_id,)).fetchall()
    return [dict(r) for r in rows]


def get_lectures(module_id: str) -> list[dict]:
    with tx() as con:
        rows = con.execute("SELECT * FROM lectures WHERE module_id=? ORDER BY order_index", (module_id,)).fetchall()
    return [dict(r) for r in rows]


def get_lecture(lecture_id: str) -> dict | None:
    with tx() as con:
        row = con.execute("SELECT * FROM lectures WHERE id=?", (lecture_id,)).fetchone()
    return dict(row) if row else None


def delete_course(course_id: str) -> None:
    with tx() as con:
        con.execute("DELETE FROM courses WHERE id=?", (course_id,))


# ─── Progress ──────────────────────────────────────────────────────────────────

def get_progress(lecture_id: str) -> dict:
    with tx() as con:
        row = con.execute("SELECT * FROM progress WHERE lecture_id=?", (lecture_id,)).fetchone()
    return dict(row) if row else {"status": "not_started", "watch_time_s": 0, "score": None}


def set_progress(lecture_id: str, status: str, watch_time_s: float = 0, score: float | None = None) -> None:
    completed_at = time.time() if status == "completed" else None
    with tx() as con:
        con.execute(
            "INSERT OR REPLACE INTO progress (lecture_id,status,watch_time_s,score,completed_at) VALUES (?,?,?,?,?)",
            (lecture_id, status, watch_time_s, score, completed_at),
        )
    if status == "completed":
        add_xp(75, f"Completed lecture {lecture_id}", "lecture_complete")
        unlock_achievement("speed_reader")
        if count_completed() >= 10:
            unlock_achievement("ten_lectures")
        if datetime.now().hour < 5:
            unlock_achievement("night_owl")
        update_quest_progress("complete_3_lectures")


def count_completed() -> int:
    with tx() as con:
        row = con.execute("SELECT COUNT(*) as n FROM progress WHERE status='completed'").fetchone()
    return row["n"]


# ─── Assignments ───────────────────────────────────────────────────────────────

def save_assignment(assignment: dict) -> None:
    with tx() as con:
        con.execute(
            """INSERT OR REPLACE INTO assignments
               (id,lecture_id,course_id,title,description,type,due_at,max_score,data,weight,term_id)
               VALUES (:id,:lecture_id,:course_id,:title,:description,:type,:due_at,:max_score,:data,:weight,:term_id)""",
            {
                "id": assignment["id"],
                "lecture_id": assignment.get("lecture_id"),
                "course_id": assignment.get("course_id"),
                "title": assignment["title"],
                "description": assignment.get("description", ""),
                "type": assignment.get("type", "quiz"),
                "due_at": assignment.get("due_at"),
                "max_score": assignment.get("max_score", 100),
                "data": json.dumps(assignment.get("data", {})),
                "weight": assignment.get("weight", 1.0),
                "term_id": assignment.get("term_id"),
            },
        )



def submit_assignment(assignment_id: str, score: float, feedback: str = "") -> None:
    now = time.time()
    late_penalty = 0.0
    if get_setting("deadlines_enabled", "0") == "1":
        with tx() as con:
            row = con.execute("SELECT due_at FROM assignments WHERE id=?", (assignment_id,)).fetchone()
        if row and row["due_at"] and now > row["due_at"]:
            days_late = (now - row["due_at"]) / 86400.0
            late_penalty = min(days_late * 10.0, 50.0)
    adjusted_score = max(score - (score * late_penalty / 100.0), 0)
    with tx() as con:
        con.execute(
            "UPDATE assignments SET submitted_at=?, score=?, feedback=?, late_penalty=? WHERE id=?",
            (now, adjusted_score, feedback, late_penalty, assignment_id),
        )
        max_sc = con.execute("SELECT max_score FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    unlock_achievement("first_quiz")
    if max_sc and max_sc["max_score"] and max_sc["max_score"] > 0 and adjusted_score >= max_sc["max_score"]:
        unlock_achievement("perfect_score")
    if datetime.now().hour < 5:
        unlock_achievement("night_owl")
    add_xp(50, f"Submitted assignment {assignment_id}", "assignment")
    update_quest_progress("submit_assignment")
    _check_achievements_degrees()


def get_assignments(course_id: str | None = None) -> list[dict]:
    with tx() as con:
        if course_id:
            rows = con.execute("SELECT * FROM assignments WHERE course_id=? ORDER BY due_at", (course_id,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM assignments ORDER BY due_at").fetchall()
    return [dict(r) for r in rows]


def get_overdue(now: float | None = None) -> list[dict]:
    now = now or time.time()
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM assignments WHERE due_at IS NOT NULL AND due_at < ? AND submitted_at IS NULL",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


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


def compute_gpa() -> tuple[float, int]:
    return _compute_gpa_raw(tx)


def credits_earned() -> int:
    return _credits_earned_raw(tx)


def eligible_degrees(gpa: float | None = None, credits: int | None = None) -> list[str]:
    return _eligible_degrees_raw(tx, gpa, credits)


# ─── Chat History ──────────────────────────────────────────────────────────────

def append_chat(session_id: str, role: str, content: str) -> None:
    with tx() as con:
        con.execute(
            "INSERT INTO chat_history (session_id,role,content) VALUES (?,?,?)",
            (session_id, role, content),
        )


def get_chat(session_id: str, limit: int = 50) -> list[dict]:
    with tx() as con:
        rows = con.execute(
            "SELECT role,content,occurred_at FROM chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


def _save_llm_generated_canonical(content: str, content_type: str) -> int:
    with tx() as con:
        cur = con.execute(
            "INSERT INTO llm_generated (content,type) VALUES (?,?)", (content, content_type)
        )
        row_id = cur.lastrowid
    return row_id


def get_llm_generated(imported: bool = False) -> list[dict]:
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM llm_generated WHERE imported=? ORDER BY created_at DESC", (1 if imported else 0,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_imported(row_id: int) -> None:
    with tx() as con:
        con.execute("UPDATE llm_generated SET imported=1 WHERE id=?", (row_id,))


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


# ─── Activity (delegated to db_activity.py) ────────────────────────────────────

def log_activity(event_type: str, duration_s: float = 0, metadata: dict | None = None) -> None:
    _log_activity_raw(event_type, tx, duration_s, metadata)


def get_activity_summary() -> dict:
    return _get_activity_summary_raw(tx)


# ─── Schema validation & Bulk import (delegated to db_import.py) ───────────────

# validate_course_json imported directly from db_import


def bulk_import_json(raw: str, validate_only: bool = False) -> tuple[int, list[str]]:
    return _bulk_import_json_raw(
        raw, tx_func=tx, upsert_course=upsert_course, upsert_module=upsert_module,
        upsert_lecture=upsert_lecture, unlock_achievement=unlock_achievement,
        add_xp=add_xp, validate_only=validate_only,
    )


# ─── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
run_migrations()
_seed_programs_raw(tx)
seed_achievements()
seed_weekly_quests()
_seed_grade_levels_raw(tx)
_seed_subjects_raw(tx)


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