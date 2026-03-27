"""Persistent audit workbench helpers for chunked LLM grading."""
from __future__ import annotations

import json
import time
import uuid


def create_tables(tx_func) -> None:
    with tx_func() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS audit_jobs (
                id                TEXT PRIMARY KEY,
                audit_type        TEXT NOT NULL,
                title             TEXT NOT NULL,
                course_id         TEXT,
                assignment_id     TEXT,
                provider          TEXT,
                model             TEXT,
                model_profile_json TEXT,
                status            TEXT DEFAULT 'queued',
                total_packets     INTEGER DEFAULT 0,
                processed_packets INTEGER DEFAULT 0,
                total_passes      INTEGER DEFAULT 1,
                estimated_seconds INTEGER DEFAULT 0,
                created_at        REAL DEFAULT (unixepoch()),
                started_at        REAL,
                completed_at      REAL,
                last_error        TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_packets (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id            TEXT NOT NULL,
                packet_index      INTEGER DEFAULT 0,
                packet_kind       TEXT NOT NULL,
                source_ref        TEXT,
                title             TEXT,
                payload_json      TEXT NOT NULL,
                token_estimate    INTEGER DEFAULT 0,
                status            TEXT DEFAULT 'pending',
                llm_score         REAL,
                llm_verdict       TEXT,
                llm_feedback      TEXT,
                weaknesses_json   TEXT,
                strengths_json    TEXT,
                reviewer_model    TEXT,
                review_passes     INTEGER DEFAULT 0,
                reviewed_at       REAL,
                created_at        REAL DEFAULT (unixepoch()),
                updated_at        REAL DEFAULT (unixepoch()),
                FOREIGN KEY (job_id) REFERENCES audit_jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS remediation_backlog (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type       TEXT NOT NULL,
                source_id         TEXT,
                course_id         TEXT,
                weakness          TEXT NOT NULL,
                severity          TEXT DEFAULT 'medium',
                status            TEXT DEFAULT 'open',
                suggested_title   TEXT,
                data_json         TEXT,
                created_at        REAL DEFAULT (unixepoch()),
                updated_at        REAL DEFAULT (unixepoch())
            );
        """)


def _loads_maybe(raw: str | None) -> dict | list:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _chunks(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def create_course_audit_job(
    course_id: str,
    provider: str,
    model: str,
    model_profile: dict,
    tx_func,
    get_course_fn,
    get_modules_fn,
    get_lectures_fn,
    get_progress_fn,
    get_assignments_fn,
    get_competency_profile_fn,
    get_study_hours_fn,
    get_course_completion_audit_fn,
    estimate_tokens_fn,
) -> str:
    course = get_course_fn(course_id)
    if not course:
        raise ValueError(f"Course not found: {course_id}")

    modules = get_modules_fn(course_id)
    assignments = get_assignments_fn(course_id)
    competency = get_competency_profile_fn(course_id)
    study_hours = get_study_hours_fn(course_id)
    course_audit = get_course_completion_audit_fn(course_id)

    packets: list[dict] = []
    lectures_per_packet = 3 if model_profile.get("chunk_token_target", 1200) <= 1200 else 5
    job_id = f"audit-{uuid.uuid4().hex[:10]}"

    overview_payload = {
        "course_id": course["id"],
        "title": course["title"],
        "description": course.get("description", ""),
        "credits": course.get("credits", 0),
        "course_audit": course_audit,
        "module_count": len(modules),
        "assignment_count": len(assignments),
    }
    packets.append({
        "packet_kind": "course_overview",
        "source_ref": course_id,
        "title": f"Course overview for {course['title']}",
        "payload": overview_payload,
    })

    for module in modules:
        lecture_rows = []
        for lecture in get_lectures_fn(module["id"]):
            progress = get_progress_fn(lecture["id"])
            lecture_rows.append({
                "lecture_id": lecture["id"],
                "title": lecture["title"],
                "status": progress.get("status", "not_started"),
                "watch_time_s": progress.get("watch_time_s", 0),
                "score": progress.get("score"),
                "completed_at": progress.get("completed_at"),
            })
        for index, chunk in enumerate(_chunks(lecture_rows, lectures_per_packet)):
            packets.append({
                "packet_kind": "lecture_evidence",
                "source_ref": module["id"],
                "title": f"{module['title']} lecture evidence {index + 1}",
                "payload": {
                    "module_id": module["id"],
                    "module_title": module["title"],
                    "lectures": chunk,
                },
            })

    for assignment in assignments:
        data = assignment.get("data")
        packet_payload = {
            "assignment_id": assignment["id"],
            "title": assignment["title"],
            "type": assignment.get("type", "quiz"),
            "description": assignment.get("description", ""),
            "score": assignment.get("score"),
            "max_score": assignment.get("max_score", 100),
            "feedback": assignment.get("feedback", ""),
            "submitted_at": assignment.get("submitted_at"),
            "duration_s": assignment.get("duration_s", 0),
            "data": _loads_maybe(data),
        }
        packets.append({
            "packet_kind": "assignment_evidence",
            "source_ref": assignment["id"],
            "title": f"Assignment evidence: {assignment['title']}",
            "payload": packet_payload,
        })

    if study_hours:
        for index, chunk in enumerate(_chunks(study_hours, 6)):
            packets.append({
                "packet_kind": "study_log",
                "source_ref": course_id,
                "title": f"Study log chunk {index + 1}",
                "payload": {"entries": chunk},
            })

    if competency:
        packets.append({
            "packet_kind": "competency_profile",
            "source_ref": course_id,
            "title": "Competency profile",
            "payload": competency,
        })

    total_tokens = 0
    for index, packet in enumerate(packets):
        payload_json = json.dumps(packet["payload"], ensure_ascii=True)
        packet["packet_index"] = index
        packet["payload_json"] = payload_json
        packet["token_estimate"] = estimate_tokens_fn(payload_json)
        total_tokens += packet["token_estimate"]

    estimated_seconds = int(total_tokens / max(model_profile.get("estimated_tokens_per_second", 80.0), 1.0) * max(model_profile.get("recommended_passes", 1), 1))
    with tx_func() as con:
        con.execute(
            """INSERT INTO audit_jobs
               (id, audit_type, title, course_id, provider, model, model_profile_json,
                status, total_packets, total_passes, estimated_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
            (
                job_id,
                "course_audit",
                f"Course audit: {course['title']}",
                course_id,
                provider,
                model,
                json.dumps(model_profile),
                len(packets),
                model_profile.get("recommended_passes", 1),
                estimated_seconds,
            ),
        )
        for packet in packets:
            con.execute(
                """INSERT INTO audit_packets
                   (job_id, packet_index, packet_kind, source_ref, title, payload_json, token_estimate)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    packet["packet_index"],
                    packet["packet_kind"],
                    packet["source_ref"],
                    packet["title"],
                    packet["payload_json"],
                    packet["token_estimate"],
                ),
            )
    return job_id


def list_audit_jobs(tx_func, limit: int = 25) -> list[dict]:
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM audit_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_audit_job(job_id: str, tx_func) -> dict | None:
    with tx_func() as con:
        row = con.execute("SELECT * FROM audit_jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_audit_packets(job_id: str, tx_func) -> list[dict]:
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM audit_packets WHERE job_id=? ORDER BY packet_index, id",
            (job_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_next_pending_packet(job_id: str, tx_func) -> dict | None:
    with tx_func() as con:
        row = con.execute(
            "SELECT * FROM audit_packets WHERE job_id=? AND status='pending' ORDER BY packet_index LIMIT 1",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def mark_job_started(job_id: str, tx_func) -> None:
    with tx_func() as con:
        con.execute(
            "UPDATE audit_jobs SET status='running', started_at=COALESCE(started_at, ?), last_error='' WHERE id=?",
            (time.time(), job_id),
        )


def record_packet_review(packet_id: int, review: dict, tx_func) -> None:
    with tx_func() as con:
        packet = con.execute("SELECT job_id FROM audit_packets WHERE id=?", (packet_id,)).fetchone()
        if not packet:
            return
        con.execute(
            """UPDATE audit_packets
               SET status='reviewed', llm_score=?, llm_verdict=?, llm_feedback=?,
                   weaknesses_json=?, strengths_json=?, reviewer_model=?, review_passes=?,
                   reviewed_at=?, updated_at=?
               WHERE id=?""",
            (
                review.get("score"),
                review.get("verdict", ""),
                review.get("feedback", ""),
                json.dumps(review.get("weaknesses", [])),
                json.dumps(review.get("strengths", [])),
                review.get("reviewer_model", ""),
                review.get("review_passes", 1),
                time.time(),
                time.time(),
                packet_id,
            ),
        )
        done = con.execute(
            "SELECT COUNT(*) AS n FROM audit_packets WHERE job_id=? AND status='reviewed'",
            (packet["job_id"],),
        ).fetchone()["n"]
        total = con.execute(
            "SELECT total_packets FROM audit_jobs WHERE id=?",
            (packet["job_id"],),
        ).fetchone()["total_packets"]
        status = "completed" if done >= total else "running"
        completed_at = time.time() if status == "completed" else None
        con.execute(
            "UPDATE audit_jobs SET processed_packets=?, status=?, completed_at=COALESCE(completed_at, ?) WHERE id=?",
            (done, status, completed_at, packet["job_id"]),
        )


def fail_audit_job(job_id: str, error: str, tx_func) -> None:
    with tx_func() as con:
        con.execute(
            "UPDATE audit_jobs SET status='failed', last_error=?, completed_at=? WHERE id=?",
            (error, time.time(), job_id),
        )


def add_remediation_item(source_type: str, source_id: str, course_id: str, weakness: str,
                         severity: str, suggested_title: str, data: dict, tx_func) -> None:
    with tx_func() as con:
        con.execute(
            """INSERT INTO remediation_backlog
               (source_type, source_id, course_id, weakness, severity, suggested_title, data_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_type,
                source_id,
                course_id,
                weakness,
                severity,
                suggested_title,
                json.dumps(data),
                time.time(),
            ),
        )


def list_remediation_backlog(tx_func, status: str = "open", limit: int = 50) -> list[dict]:
    with tx_func() as con:
        rows = con.execute(
            "SELECT * FROM remediation_backlog WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    return [dict(row) for row in rows]