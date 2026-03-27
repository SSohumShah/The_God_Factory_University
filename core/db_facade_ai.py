"""AI-facing database facade helpers extracted from core.database."""
from __future__ import annotations


def make_ai_facade(*,
                   tx,
                   get_course,
                   get_modules,
                   get_lectures,
                   get_progress,
                   get_assignments,
                   get_competency_profile,
                   get_study_hours,
                   get_course_completion_audit,
                   create_course_audit_job_raw,
                   list_audit_jobs_raw,
                   get_audit_job_raw,
                   get_audit_packets_raw,
                   get_next_pending_packet_raw,
                   mark_job_started_raw,
                   record_packet_review_raw,
                   fail_audit_job_raw,
                   add_remediation_item_raw,
                   list_remediation_backlog_raw,
                   bulk_import_json_raw,
                   upsert_course,
                   upsert_module,
                   upsert_lecture,
                   unlock_achievement,
                   add_xp,
                   save_assignment_raw):
    """Bind AI-facing wrappers to the canonical database dependencies."""

    def append_chat(session_id: str, role: str, content: str) -> None:
        with tx() as con:
            con.execute(
                "INSERT INTO chat_history (session_id,role,content) VALUES (?,?,?)",
                (session_id, role, content),
            )
        from core.chat_store import save_message
        from core.logger import log_event

        save_message(session_id, role, content)
        log_event(
            f"Stored chat message for {session_id}",
            category="chat",
            session_id=session_id,
            role=role,
            content_length=len(content),
        )

    def get_chat(session_id: str, limit: int = 50) -> list[dict]:
        with tx() as con:
            rows = con.execute(
                "SELECT role,content,occurred_at FROM chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return list(reversed([dict(r) for r in rows]))

    def save_llm_generated_raw(content: str, content_type: str) -> int:
        with tx() as con:
            cur = con.execute(
                "INSERT INTO llm_generated (content,type) VALUES (?,?)",
                (content, content_type),
            )
            row_id = cur.lastrowid
        return row_id

    def get_llm_generated(imported: bool = False) -> list[dict]:
        with tx() as con:
            rows = con.execute(
                "SELECT * FROM llm_generated WHERE imported=? ORDER BY created_at DESC",
                (1 if imported else 0,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_imported(row_id: int) -> None:
        with tx() as con:
            con.execute("UPDATE llm_generated SET imported=1 WHERE id=?", (row_id,))

    def create_course_audit_job(course_id: str, provider: str, model: str, model_profile: dict) -> str:
        from core.logger import log_event
        from llm.providers import estimate_tokens

        job_id = create_course_audit_job_raw(
            course_id,
            provider,
            model,
            model_profile,
            tx,
            get_course,
            get_modules,
            get_lectures,
            get_progress,
            get_assignments,
            get_competency_profile,
            get_study_hours,
            get_course_completion_audit,
            estimate_tokens,
        )
        log_event(
            f"Queued audit job {job_id} for {course_id}",
            category="audit",
            job_id=job_id,
            course_id=course_id,
            provider=provider,
            model=model,
        )
        return job_id

    def list_audit_jobs(limit: int = 25) -> list[dict]:
        return list_audit_jobs_raw(tx, limit)

    def get_audit_job(job_id: str) -> dict | None:
        return get_audit_job_raw(job_id, tx)

    def get_audit_packets(job_id: str) -> list[dict]:
        return get_audit_packets_raw(job_id, tx)

    def get_next_pending_packet(job_id: str) -> dict | None:
        return get_next_pending_packet_raw(job_id, tx)

    def mark_audit_job_started(job_id: str) -> None:
        from core.logger import log_event

        mark_job_started_raw(job_id, tx)
        log_event(f"Started audit job {job_id}", category="audit", job_id=job_id)

    def record_audit_packet_review(packet_id: int, review: dict) -> None:
        from core.logger import log_event

        record_packet_review_raw(packet_id, review, tx)
        log_event(
            f"Recorded audit packet review {packet_id}",
            category="audit",
            packet_id=packet_id,
            review_keys=sorted(review.keys()),
        )

    def fail_audit_job(job_id: str, error: str) -> None:
        from core.logger import log_error

        fail_audit_job_raw(job_id, error, tx)
        log_error(
            f"Audit job failed: {job_id}",
            category="audit",
            error_id="AUDIT_JOB_FAILED",
            job_id=job_id,
            details=error,
        )

    def add_remediation_item(source_type: str, source_id: str, course_id: str, weakness: str,
                             severity: str = "medium", suggested_title: str = "",
                             data: dict | None = None) -> None:
        from core.logger import log_event

        add_remediation_item_raw(
            source_type,
            source_id,
            course_id,
            weakness,
            severity,
            suggested_title,
            data or {},
            tx,
        )
        log_event(
            f"Added remediation item for {course_id}",
            category="audit",
            course_id=course_id,
            source_type=source_type,
            source_id=source_id,
            severity=severity,
        )

    def list_remediation_backlog(status: str = "open", limit: int = 50) -> list[dict]:
        return list_remediation_backlog_raw(tx, status, limit)

    def bulk_import_json(raw: str, validate_only: bool = False) -> tuple[int, list[str]]:
        return bulk_import_json_raw(
            raw,
            tx_func=tx,
            upsert_course=upsert_course,
            upsert_module=upsert_module,
            upsert_lecture=upsert_lecture,
            unlock_achievement=unlock_achievement,
            add_xp=add_xp,
            validate_only=validate_only,
            save_assignment_fn=save_assignment_raw,
        )

    return {
        "append_chat": append_chat,
        "get_chat": get_chat,
        "save_llm_generated_raw": save_llm_generated_raw,
        "get_llm_generated": get_llm_generated,
        "mark_imported": mark_imported,
        "create_course_audit_job": create_course_audit_job,
        "list_audit_jobs": list_audit_jobs,
        "get_audit_job": get_audit_job,
        "get_audit_packets": get_audit_packets,
        "get_next_pending_packet": get_next_pending_packet,
        "mark_audit_job_started": mark_audit_job_started,
        "record_audit_packet_review": record_audit_packet_review,
        "fail_audit_job": fail_audit_job,
        "add_remediation_item": add_remediation_item,
        "list_remediation_backlog": list_remediation_backlog,
        "bulk_import_json": bulk_import_json,
    }