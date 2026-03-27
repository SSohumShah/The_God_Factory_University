"""Student-facing database facade helpers extracted from core.database."""
from __future__ import annotations

import time
from datetime import datetime, timedelta


LEVELS = [
    (0, "Seeker"),
    (100, "Initiate"),
    (300, "Scholar"),
    (700, "Adept"),
    (1500, "Expert"),
    (3000, "Sage"),
    (6000, "Transcendent"),
    (10000, "Grandmaster"),
    (20000, "Luminary"),
    (50000, "Archon"),
]


def make_student_facade(*,
                        tx,
                        compute_gpa_raw,
                        credits_earned_raw,
                        eligible_degrees_raw,
                        get_academic_progress_summary_raw,
                        get_course_completion_audit_raw,
                        log_activity_raw,
                        get_activity_summary_raw,
                        unlock_achievement_raw,
                        check_achievements_xp_raw,
                        update_quest_progress_raw,
                        get_enrollment_date,
                        time_to_degree_days):
    """Bind student-facing wrappers to the canonical database dependencies."""

    def get_setting(key: str, default: str = "") -> str:
        with tx() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(key: str, value: str) -> None:
        with tx() as con:
            con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))

    def get_xp() -> int:
        return int(get_setting("xp_total", "0"))

    def get_level(xp: int | None = None) -> tuple[int, str, int, int]:
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

    def unlock_achievement_inline(achievement_id: str) -> bool:
        return unlock_achievement_raw(achievement_id, tx, add_xp)

    def update_quest_progress_inline(quest_prefix: str, increment: int = 1) -> None:
        update_quest_progress_raw(quest_prefix, tx, add_xp, increment)

    def add_xp(amount: int, description: str, event_type: str = "general") -> int:
        old_total = int(get_setting("xp_total", "0"))
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
        bonus_pct = min(streak * 5, 50) / 100.0
        effective = amount + int(amount * bonus_pct)
        total = old_total + effective
        set_setting("xp_total", str(total))
        with tx() as con:
            con.execute(
                "INSERT INTO xp_events (event_type,xp_gained,description) VALUES (?,?,?)",
                (event_type, effective, description),
            )
        old_level = get_level(old_total)[0]
        new_level = get_level(total)[0]
        if new_level > old_level:
            set_setting("_pending_level_up", LEVELS[new_level][1])
        check_achievements_xp_raw(total, unlock_achievement_inline)
        if event_type != "quest":
            update_quest_progress_inline("earn_200_xp", effective)
        return total

    def get_progress(lecture_id: str) -> dict:
        with tx() as con:
            row = con.execute("SELECT * FROM progress WHERE lecture_id=?", (lecture_id,)).fetchone()
        return dict(row) if row else {"status": "not_started", "watch_time_s": 0, "score": None}

    def count_completed() -> int:
        with tx() as con:
            row = con.execute("SELECT COUNT(*) as n FROM progress WHERE status='completed'").fetchone()
        return row["n"]

    def log_activity(event_type: str, duration_s: float = 0, metadata: dict | None = None) -> None:
        log_activity_raw(event_type, tx, duration_s, metadata)

    def set_progress(lecture_id: str, status: str, watch_time_s: float = 0, score: float | None = None) -> None:
        completed_at = time.time() if status == "completed" else None
        with tx() as con:
            con.execute(
                "INSERT OR REPLACE INTO progress (lecture_id,status,watch_time_s,score,completed_at) VALUES (?,?,?,?,?)",
                (lecture_id, status, watch_time_s, score, completed_at),
            )
        log_activity(f"lecture_{status}", duration_s=watch_time_s, metadata={"lecture_id": lecture_id, "score": score})
        if status == "completed":
            add_xp(75, f"Completed lecture {lecture_id}", "lecture_complete")
            unlock_achievement_inline("speed_reader")
            if count_completed() >= 10:
                unlock_achievement_inline("ten_lectures")
            if datetime.now().hour < 5:
                unlock_achievement_inline("night_owl")
            update_quest_progress_inline("complete_3_lectures")

    def compute_gpa() -> tuple[float, int]:
        return compute_gpa_raw(tx)

    def credits_earned() -> float:
        return credits_earned_raw(tx)

    def eligible_degrees(gpa: float | None = None, credits: float | None = None) -> list[str]:
        return eligible_degrees_raw(tx, gpa, credits)

    def get_academic_progress_summary() -> dict:
        return get_academic_progress_summary_raw(tx)

    def get_course_completion_audit(course_id: str) -> dict:
        return get_course_completion_audit_raw(course_id, tx)

    def get_activity_summary() -> dict:
        return get_activity_summary_raw(tx)

    def get_student_world_state() -> dict:
        summary = get_activity_summary()
        enrollment = get_enrollment_date()
        days_enrolled = time_to_degree_days()
        last_event_at = summary.get("last_event_at")
        idle_seconds = summary.get("idle_seconds")
        return {
            "enrollment_date": enrollment,
            "days_enrolled": days_enrolled,
            "total_events": summary.get("total_events", 0),
            "study_hours": summary.get("study_hours", 0.0),
            "active_days": summary.get("active_days", 0),
            "last_event_at": last_event_at,
            "idle_seconds": idle_seconds,
            "idle_days": round(idle_seconds / 86400.0, 2) if idle_seconds is not None else None,
        }

    return {
        "get_setting": get_setting,
        "set_setting": set_setting,
        "add_xp": add_xp,
        "get_xp": get_xp,
        "get_level": get_level,
        "get_progress": get_progress,
        "set_progress": set_progress,
        "count_completed": count_completed,
        "compute_gpa": compute_gpa,
        "credits_earned": credits_earned,
        "eligible_degrees": eligible_degrees,
        "get_academic_progress_summary": get_academic_progress_summary,
        "get_course_completion_audit": get_course_completion_audit,
        "log_activity": log_activity,
        "get_activity_summary": get_activity_summary,
        "get_student_world_state": get_student_world_state,
    }