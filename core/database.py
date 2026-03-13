"""
SQLite persistence layer for Arcane University.
All tables are created on first import. Thread-safe via WAL mode.

Sub-modules (DEVELOPMENT.md Rule 5):
  - db_achievements.py  — achievement defs, seeding, triggers
  - db_grades.py        — GPA, grade scale, degree tracks
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

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL DEFAULT (unixepoch())
        );
        """)


# ─── Schema migrations ────────────────────────────────────────────────────────

_MIGRATIONS: list[tuple[int, str, str]] = [
    # (version, label, SQL)
    # Add new migrations here as tuples: (next_int, "description", "SQL;")
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
            con.executescript(sql)
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


# ─── Weekly Quests ──────────────────────────────────────────────────────────────

_QUEST_TEMPLATES = [
    ("complete_3_lectures", "Complete 3 Lectures", "Finish 3 lectures this week", 3, 100),
    ("earn_200_xp", "Earn 200 XP", "Accumulate 200 XP this week", 200, 75),
    ("submit_assignment", "Submit an Assignment", "Turn in at least 1 assignment", 1, 50),
]


def _current_week_start() -> str:
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def seed_weekly_quests() -> None:
    week = _current_week_start()
    with tx() as con:
        existing = con.execute(
            "SELECT id FROM quests WHERE week_start=?", (week,)
        ).fetchall()
    if existing:
        return
    with tx() as con:
        for qid, title, desc, target, xp in _QUEST_TEMPLATES:
            con.execute(
                "INSERT OR IGNORE INTO quests (id,title,description,target,progress,xp_reward,week_start) "
                "VALUES (?,?,?,?,0,?,?)",
                (f"{qid}_{week}", title, desc, target, xp, week),
            )


def get_active_quests() -> list[dict]:
    week = _current_week_start()
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM quests WHERE week_start=? ORDER BY id", (week,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_quest_progress(quest_prefix: str, increment: int = 1) -> None:
    week = _current_week_start()
    qid = f"{quest_prefix}_{week}"
    with tx() as con:
        row = con.execute(
            "SELECT progress, target, completed, xp_reward FROM quests WHERE id=?", (qid,)
        ).fetchone()
    if not row or row["completed"]:
        return
    new_progress = min(row["progress"] + increment, row["target"])
    completed = 1 if new_progress >= row["target"] else 0
    with tx() as con:
        con.execute(
            "UPDATE quests SET progress=?, completed=? WHERE id=?",
            (new_progress, completed, qid),
        )
    if completed:
        add_xp(row["xp_reward"], f"Quest complete: {quest_prefix}", "quest")


# ─── Schema validation ─────────────────────────────────────────────────────────

_SCHEMA_CACHE: dict | None = None

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


# ─── Bulk JSON import ──────────────────────────────────────────────────────────

def bulk_import_json(raw: str, validate_only: bool = False) -> tuple[int, list[str]]:
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
        schema_errors = validate_course_json(obj)
        if schema_errors:
            prefix = f"Object {i + 1}" if len(objects) > 1 else "Input"
            errors.extend(f"{prefix}: {e}" for e in schema_errors)
            continue
        if validate_only:
            imported += 1
            continue
        try:
            with tx() as conn:
                conn.execute("SAVEPOINT import_obj")
                try:
                    _import_one_object(obj)
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


def _import_one_object(obj: dict) -> None:
    if "modules" in obj:
        _import_course(obj)
    elif "lectures" in obj and "course_id" in obj:
        _import_module(obj)
    elif "lecture_id" in obj or ("title" in obj and "video_recipe" in obj):
        _import_lecture_flat(obj)
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


def _import_course(obj: dict) -> None:
    course_id = obj.get("course_id") or obj.get("id") or f"course_{int(time.time())}"
    upsert_course(course_id, obj.get("title", "Imported"), obj.get("description", ""),
                  obj.get("credits", 3), obj)
    for i, module in enumerate(obj.get("modules", [])):
        mid = module.get("module_id") or module.get("id") or f"{course_id}_M{i}"
        upsert_module(mid, course_id, module.get("title", f"Module {i}"), i, module)
        for j, lecture in enumerate(module.get("lectures", [])):
            lid = lecture.get("lecture_id") or lecture.get("id") or f"{mid}_L{j}"
            upsert_lecture(lid, mid, course_id, lecture.get("title", f"Lecture {j}"),
                           lecture.get("duration_min", 60), j, lecture)


def _import_module(obj: dict) -> None:
    course_id = obj.get("course_id", "unknown")
    mid = obj.get("module_id") or obj.get("id") or f"module_{int(time.time())}"
    upsert_module(mid, course_id, obj.get("title", "Module"), 0, obj)
    for j, lecture in enumerate(obj.get("lectures", [])):
        lid = lecture.get("lecture_id") or f"{mid}_L{j}"
        upsert_lecture(lid, mid, course_id, lecture.get("title", f"Lecture {j}"),
                       lecture.get("duration_min", 60), j, lecture)


def _import_lecture_flat(obj: dict) -> None:
    lid = obj.get("lecture_id") or obj.get("id") or f"lecture_{int(time.time())}"
    mid = obj.get("module_id", "unassigned")
    cid = obj.get("course_id", "unassigned")
    upsert_lecture(lid, mid, cid, obj.get("title", "Lecture"), obj.get("duration_min", 60), 0, obj)


# ─── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
run_migrations()
seed_achievements()
seed_weekly_quests()


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
