"""
SQLite persistence layer for Arcane University.
All tables are created on first import. Thread-safe via WAL mode.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

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
            data         TEXT
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
        """)


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
    total = int(get_setting("xp_total", "0")) + amount
    set_setting("xp_total", str(total))
    with tx() as con:
        con.execute(
            "INSERT INTO xp_events (event_type,xp_gained,description) VALUES (?,?,?)",
            (event_type, amount, description),
        )
    _check_achievements_xp(total)
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


def count_completed() -> int:
    with tx() as con:
        row = con.execute("SELECT COUNT(*) as n FROM progress WHERE status='completed'").fetchone()
    return row["n"]


# ─── Assignments ───────────────────────────────────────────────────────────────

def save_assignment(assignment: dict) -> None:
    with tx() as con:
        con.execute(
            """INSERT OR REPLACE INTO assignments
               (id,lecture_id,course_id,title,description,type,due_at,max_score,data)
               VALUES (:id,:lecture_id,:course_id,:title,:description,:type,:due_at,:max_score,:data)""",
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
            },
        )


def submit_assignment(assignment_id: str, score: float, feedback: str = "") -> None:
    with tx() as con:
        con.execute(
            "UPDATE assignments SET submitted_at=?, score=?, feedback=? WHERE id=?",
            (time.time(), score, feedback, assignment_id),
        )
    add_xp(50, f"Submitted assignment {assignment_id}", "assignment")


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


# ─── GPA & Grades ──────────────────────────────────────────────────────────────

GRADE_SCALE = [
    ("A+", 97, 4.0), ("A", 93, 4.0), ("A-", 90, 3.7),
    ("B+", 87, 3.3), ("B", 83, 3.0), ("B-", 80, 2.7),
    ("C+", 77, 2.3), ("C", 73, 2.0), ("C-", 70, 1.7),
    ("D", 60, 1.0), ("F", 0, 0.0),
]


def score_to_grade(score: float) -> tuple[str, float]:
    for letter, threshold, points in GRADE_SCALE:
        if score >= threshold:
            return letter, points
    return "F", 0.0


def compute_gpa() -> tuple[float, int]:
    with tx() as con:
        rows = con.execute("SELECT score, max_score FROM assignments WHERE submitted_at IS NOT NULL").fetchall()
    if not rows:
        return 0.0, 0
    total_points = 0.0
    count = 0
    for r in rows:
        if r["score"] is not None and r["max_score"] and r["max_score"] > 0:
            pct = (r["score"] / r["max_score"]) * 100
            _, points = score_to_grade(pct)
            total_points += points
            count += 1
    return (round(total_points / count, 2) if count else 0.0), count


DEGREE_TRACKS = {
    "Certificate":  {"min_credits": 15,  "min_gpa": 2.0},
    "Associate":    {"min_credits": 60,  "min_gpa": 2.0},
    "Bachelor":     {"min_credits": 120, "min_gpa": 2.0},
    "Master":       {"min_credits": 150, "min_gpa": 3.0},
    "Doctorate":    {"min_credits": 180, "min_gpa": 3.5},
}


def credits_earned() -> int:
    with tx() as con:
        row = con.execute(
            """SELECT SUM(c.credits) as total
               FROM courses c
               WHERE c.id IN (
                   SELECT DISTINCT l.course_id FROM lectures l
                   JOIN progress p ON p.lecture_id = l.id
                   WHERE p.status='completed'
               )""",
        ).fetchone()
    return int(row["total"] or 0)


def eligible_degrees(gpa: float | None = None, credits: int | None = None) -> list[str]:
    _gpa, count = compute_gpa()
    if gpa is None:
        gpa = _gpa
    if credits is None:
        credits = credits_earned()
    return [
        d for d, req in DEGREE_TRACKS.items()
        if credits >= req["min_credits"] and gpa >= req["min_gpa"] and count > 0
    ]


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


def save_llm_generated(content: str, content_type: str) -> int:
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


# ─── Achievements ──────────────────────────────────────────────────────────────

_ACHIEVEMENT_DEFS = [
    ("first_lecture",   "Awakening",        "Complete your first lecture",          "progress", 50),
    ("ten_lectures",    "Apprentice Path",  "Complete 10 lectures",                 "progress", 200),
    ("first_quiz",      "Trial Taker",      "Submit your first assignment",         "academic", 75),
    ("perfect_score",   "Flawless Rune",    "Score 100% on any assignment",         "academic", 150),
    ("speed_reader",    "Swift Scholar",    "Complete a lecture in one session",    "efficiency", 100),
    ("xp_1000",         "Novice Mage",      "Earn 1000 XP",                         "xp",       100),
    ("xp_5000",         "Arcane Adept",     "Earn 5000 XP",                         "xp",       250),
    ("degree_cert",     "Certified",        "Earn Certificate eligibility",         "degree",   500),
    ("degree_assoc",    "Associate Sage",   "Earn Associate eligibility",           "degree",   1000),
    ("degree_bachelor", "Bachelor Mage",    "Earn Bachelor eligibility",            "degree",   2000),
    ("degree_master",   "Grand Scholar",    "Earn Master eligibility",              "degree",   5000),
    ("degree_doctor",   "Doctor Arcanum",   "Earn Doctorate eligibility",           "degree",   10000),
    ("night_owl",       "Night Owl",        "Study after midnight",                 "habit",    75),
    ("bulk_import",     "Archivist",        "Import a bulk JSON curriculum",        "system",   100),
    ("professor_query", "The Asking",       "Query the Professor AI 10 times",      "llm",      100),
    ("video_render",    "Projector",        "Render your first lecture video",      "media",    150),
    ("batch_render",    "Dreamweaver",      "Batch render 5 or more lectures",      "media",    300),
]


def seed_achievements() -> None:
    with tx() as con:
        for aid, title, desc, cat, xp in _ACHIEVEMENT_DEFS:
            con.execute(
                "INSERT OR IGNORE INTO achievements (id,title,description,category,xp_reward) VALUES (?,?,?,?,?)",
                (aid, title, desc, cat, xp),
            )


def unlock_achievement(achievement_id: str) -> bool:
    with tx() as con:
        row = con.execute("SELECT unlocked_at FROM achievements WHERE id=?", (achievement_id,)).fetchone()
        if not row or row["unlocked_at"]:
            return False
        con.execute(
            "UPDATE achievements SET unlocked_at=? WHERE id=?", (time.time(), achievement_id)
        )
        reward = con.execute("SELECT xp_reward FROM achievements WHERE id=?", (achievement_id,)).fetchone()
    if reward:
        add_xp(reward["xp_reward"], f"Achievement: {achievement_id}", "achievement")
    return True


def get_achievements() -> list[dict]:
    with tx() as con:
        rows = con.execute("SELECT * FROM achievements ORDER BY category, id").fetchall()
    return [dict(r) for r in rows]


def _check_achievements_xp(total_xp: int) -> None:
    if total_xp >= 1000:
        unlock_achievement("xp_1000")
    if total_xp >= 5000:
        unlock_achievement("xp_5000")


# ─── Schema validation ─────────────────────────────────────────────────────────

_SCHEMA_CACHE: dict | None = None

def _load_schema() -> dict | None:
    """Load course_schema.json for validation. Returns None if unavailable."""
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
    """Validate a course object against the schema. Returns list of error messages."""
    try:
        import jsonschema
    except ImportError:
        return []  # Silently skip if jsonschema not installed
    schema = _load_schema()
    if schema is None:
        return []
    errors = []
    # Only validate objects that look like full courses
    if "modules" not in obj:
        return []
    v = jsonschema.Draft7Validator(schema)
    for error in v.iter_errors(obj):
        path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        errors.append(f"Schema: {path}: {error.message}")
    return errors


# ─── Bulk JSON import ──────────────────────────────────────────────────────────

def bulk_import_json(raw: str, validate_only: bool = False) -> tuple[int, list[str]]:
    """
    Accept a string that is either:
    - a single course JSON object
    - a JSON array of course objects
    - newline-delimited JSON objects
    If validate_only is True, only validate without writing to DB.
    Returns (count_imported_or_validated, list_of_errors).
    """
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
                except json.JSONDecodeError as e:
                    pass

    imported = 0
    errors = []
    for i, obj in enumerate(objects):
        # Schema validation
        schema_errors = validate_course_json(obj)
        if schema_errors:
            prefix = f"Object {i + 1}" if len(objects) > 1 else "Input"
            errors.extend(f"{prefix}: {e}" for e in schema_errors)
            continue
        if validate_only:
            imported += 1
            continue
        try:
            _import_one_object(obj)
            imported += 1
        except Exception as e:
            errors.append(str(e))

    if imported > 0 and not validate_only:
        unlock_achievement("bulk_import")
        add_xp(imported * 25, f"Bulk imported {imported} objects", "import")

    return imported, errors


def _import_one_object(obj: dict) -> None:
    """Try to interpret an arbitrary JSON blob as a course, module, or lecture."""
    # Detect type by presence of keys
    if "modules" in obj:
        # Full course spec or single course with modules
        _import_course(obj)
    elif "lectures" in obj and "course_id" in obj:
        _import_module(obj)
    elif "lecture_id" in obj or ("title" in obj and "video_recipe" in obj):
        _import_lecture_flat(obj)
    elif "course_spec_version" in obj:
        # Our own course spec format
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


# Bootstrap
init_db()
seed_achievements()


# ─── Compatibility shims (used by UI pages) ───────────────────────────────────

def save_setting(key: str, value: str) -> None:
    """Alias for set_setting."""
    set_setting(key, value)


def get_all_achievements() -> list[dict]:
    """Alias for get_achievements."""
    return get_achievements()


def get_total_xp() -> int:
    """Alias for get_xp."""
    return get_xp()


def save_chat_history(session_id: str, role: str, content: str) -> None:
    """Alias for append_chat."""
    append_chat(session_id, role, content)


def get_chat_history(session_id: str, limit: int = 50) -> list[dict]:
    """Alias for get_chat."""
    return get_chat(session_id, limit)


def get_xp_history(limit: int = 50) -> list[dict]:
    """Return most recent XP events, newest last."""
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM xp_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


def get_level_info(total_xp: int | None = None) -> tuple[int, str, int, int]:
    """get_level() wrapper that optionally accepts a pre-fetched xp value."""
    return get_level()


def get_gpa() -> float:
    """Return GPA as a plain float (not tuple)."""
    gpa, _ = compute_gpa()
    return gpa


def save_llm_generated(type_or_content: str, topic_or_type: str = "", content: str = "") -> int:
    """Flexible wrapper — accepts (content, type) or (type, topic, content_obj)."""
    if content:
        # Called as: save_llm_generated("curriculum", "topic text", json_string_or_dict)
        import json as _json
        if isinstance(content, (dict, list)):
            stored = _json.dumps(content)
        else:
            stored = str(content)
        return save_llm_generated_raw(stored, type_or_content)
    else:
        # Called as: save_llm_generated(content_str, content_type)
        return save_llm_generated_raw(type_or_content, topic_or_type or "general")


def save_llm_generated_raw(content: str, content_type: str) -> int:
    """The original save_llm_generated logic."""
    with tx() as con:
        cur = con.execute(
            "INSERT INTO llm_generated (content,type) VALUES (?,?)", (content, content_type)
        )
        row_id = cur.lastrowid
    return row_id
