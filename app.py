"""
The God Factory University — main entry point / Dashboard.
Handles: page config, theme injection, first-run data bootstrap, sidebar.
"""

import json
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="The God Factory University",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.database import (
    bulk_import_json, get_all_courses, get_setting, get_level,
    get_xp, count_completed, get_active_quests, get_student_world_state,
    list_audit_jobs, get_academic_progress_summary,
)
from core.ui_mode import MODE_LABELS, get_ui_mode, set_ui_mode
from core.tts_config import get_tts_settings
from ui.theme import (
    inject_theme, gf_header, section_divider,
    xp_bar, level_badge, stat_card, help_button,
)

inject_theme()


NAV_GROUPS = [
    (
        "Student Route",
        True,
        [
            ("app.py", "[*] Dashboard"),
            ("pages/02_Lecture_Studio.py", "[>] Study"),
            ("pages/03_Professor_AI.py", "[>] Professor Ileices"),
            ("pages/06_Grades.py", "[>] My Progress"),
            ("pages/07_Achievements.py", "[>] Achievements"),
            ("pages/14_Programs.py", "[>] Programs"),
            ("pages/15_Profile.py", "[>] My Profile"),
            ("pages/16_Statistics.py", "[>] Statistics"),
        ],
    ),
    (
        "Builder Route",
        True,
        [
            ("pages/01_Library.py", "[>] Course Library"),
            ("pages/04_Timeline_Editor.py", "[>] Timeline Editor"),
            ("pages/05_Batch_Render.py", "[>] Batch Render"),
            ("pages/17_Agent.py", "[>] AI Agent"),
        ],
    ),
    (
        "Setup & Support",
        True,
        [
            ("pages/11_LLM_Setup.py", "[>] LLM Setup Wizard"),
            ("pages/08_Settings.py", "[>] Settings"),
            ("pages/10_Help.py", "[?] Help & Tutorial"),
        ],
    ),
    (
        "Admin & Prototype",
        False,
        [
            ("pages/09_Diagnostics.py", "[>] Diagnostics"),
            ("pages/18_Qualifications.py", "[>] Qualifications Engine"),
            ("pages/12_Placement.py", "[proto] Placement Testing"),
            ("pages/13_Test_Prep.py", "[proto] Test Prep"),
        ],
    ),
]


def _render_nav_groups(active_mode: str) -> None:
    allowed_by_mode = {
        "student": {"Student Route", "Builder Route", "Setup & Support"},
        "builder": {"Student Route", "Builder Route", "Setup & Support"},
        "operator": {"Student Route", "Builder Route", "Setup & Support", "Admin & Prototype"},
    }
    visible = allowed_by_mode.get(active_mode, allowed_by_mode["student"])
    for title, expanded, links in NAV_GROUPS:
        if title not in visible:
            continue
        with st.expander(title, expanded=expanded):
            for page, label in links:
                st.page_link(page, label=f"  {label}")

# ─── First-run: auto-import the built-in CS/AI course ───────────────────────
NOTES_FILE = ROOT / "notes.txt"
if NOTES_FILE.exists() and not get_all_courses():
    raw = NOTES_FILE.read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        try:
            imported, _ = bulk_import_json(raw)
            if imported:
                st.toast(f"Auto-imported built-in CS/AI course ({imported} objects loaded)")
        except Exception:
            pass

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "```\n╔══════════════════════╗\n"
        "║          Ctrl        ║\n"
        "╚══════════════════════╝\n```"
    )
    level_idx, level_title, xp_in_level, xp_to_next = get_level()
    level_badge(level_idx, level_title)
    xp_bar(xp_in_level, max(xp_to_next, 1), "XP")
    current_mode = get_ui_mode()
    mode_labels = list(MODE_LABELS.values())
    current_index = list(MODE_LABELS.keys()).index(current_mode)
    selected_label = st.selectbox("Mode", mode_labels, index=current_index)
    selected_mode = next(key for key, value in MODE_LABELS.items() if value == selected_label)
    if selected_mode != current_mode:
        set_ui_mode(selected_mode)
        st.rerun()
    st.caption(f"Lectures completed: {count_completed()}")
    st.caption(f"Current route mode: {MODE_LABELS[current_mode]}")
    if current_mode == "student":
        st.caption("Builder tools are available with guided prompts in Student mode.")
    section_divider("Navigation")
    _render_nav_groups(current_mode)

# ─── Level-up Celebration ─────────────────────────────────────────────────
_pending = get_setting("_pending_level_up")
if _pending:
    from core.database import set_setting
    set_setting("_pending_level_up", "")
    st.balloons()
    st.success(f"LEVEL UP!  You have ascended to **{_pending}**!")

# ─── Dashboard ───────────────────────────────────────────────────────────────
gf_header("The God Factory University", "Come across terms in your studies that you want to understand better?\nSend them to Professor AI for an in-depth explanation, related resources, and a quiz to test your understanding.\nNeed more? Turn the unknown into entire courses in the Library. This University was built because Roswan is stupid.")
help_button("dashboard-overview")

courses = get_all_courses()
xp_total = get_xp()
completed = count_completed()
world_state = get_student_world_state()
academic_summary = get_academic_progress_summary()

section_divider("Status")
help_button("xp-and-levels")
c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("Courses", str(len(courses)), colour="#00d4ff")
with c2:
    stat_card("Lectures Done", str(completed), colour="#ffd700")
with c3:
    stat_card("Total XP", f"{xp_total:,}", colour="#40dc80")
with c4:
    stat_card("Rank", level_title, colour="#b8b8d0")

w1, w2, w3, w4 = st.columns(4)
with w1:
    stat_card("Verified Credits", f"{academic_summary['official_credits']:.2f}", colour="#40dc80")
with w2:
    stat_card("Study Hours", f"{world_state['study_hours']:.1f}", colour="#00d4ff")
with w3:
    idle_days = world_state.get("idle_days")
    stat_card("Idle Days", f"{idle_days:.2f}" if idle_days is not None else "--", colour="#e04040")
with w4:
    stat_card("Active Days", str(world_state.get("active_days", 0)), colour="#ffd700")

st.caption(
    f"Professor world state: enrolled {world_state['days_enrolled']} days | "
    f"verified courses {academic_summary['completed_courses']} | "
    f"activity credits {academic_summary['activity_credits']:.2f}"
)

audit_jobs = list_audit_jobs(limit=5)
if audit_jobs:
    section_divider("Audit Queue")
    for job in audit_jobs[:3]:
        remaining_packets = max(job.get("total_packets", 0) - job.get("processed_packets", 0), 0)
        eta_left = int((job.get("estimated_seconds", 0) or 0) * (remaining_packets / max(job.get("total_packets", 1), 1)))
        st.markdown(
            f"[>] **{job['title']}** — {job.get('status', 'queued')} | "
            f"{job.get('processed_packets', 0)}/{job.get('total_packets', 0)} packets | ETA {eta_left}s"
        )

# ─── Weekly Quests ────────────────────────────────────────────────────────────
if get_setting("quests_enabled", "1") == "1":
    quests = get_active_quests()
    if quests:
        section_divider("Weekly Quests")
        for q in quests:
            pct = int(q["progress"] / max(q["target"], 1) * 100)
            icon = "[*]" if q["completed"] else "[>]"
            st.markdown(f"{icon} **{q['title']}** — {q['progress']}/{q['target']}  (+{q['xp_reward']} XP)")
            st.progress(min(pct, 100))

section_divider("Quick Start")
st.markdown(
    "```\n"
    "HOW TO BEGIN\n"
    "─────────────────────────────────────────────────────────────\n"
    "STUDENT ROUTE\n"
    "1. Study          ─ Play lectures and continue active coursework\n"
    "2. Professor      ─ Ask for explanations, quizzes, and feedback\n"
    "3. My Progress    ─ Review verified credits, GPA, and transcript data\n"
    "4. Achievements   ─ Track milestones and momentum\n"
    "5. My Profile     ─ Set your identity and preferences\n"
    "─────────────────────────────────────────────────────────────\n"
    "BUILDER ROUTE\n"
    "6. Course Library ─ Import, inspect, and organize curriculum JSON\n"
    "7. Timeline Editor─ Reorder scenes and re-render custom videos\n"
    "8. Batch Render   ─ Render many lectures in one session\n"
    "9. AI Agent       ─ Run advanced automation workflows\n"
    "─────────────────────────────────────────────────────────────\n"
    "SUPPORT\n"
    "10. LLM Setup     ─ Configure local or cloud models\n"
    "11. Settings      ─ Tune voice, video, and system behavior\n"
    "12. Help          ─ Open contextual walkthroughs and glossary entries\n"
    "─────────────────────────────────────────────────────────────\n"
    "Placement Testing and Test Prep remain in the admin/prototype group until they are fully wired.\n"
    "Generate a course: read schemas/SCHEMA_GUIDE.md\n"
    "```"
)

# ─── Startup Self-Check ─────────────────────────────────────────────────────
section_divider("System Health")
help_button("system-health")
with st.expander("System self-check (click to expand)"):

    def _probe(label, fn):
        try:
            result = fn()
            st.markdown(f"  `[OK]` **{label}** — {result}")
            return True
        except Exception as e:
            st.markdown(f"  `[!!]` **{label}** — {e}")
            return False

    checks_ok = 0
    checks_total = 0

    # DB
    checks_total += 1
    if _probe("Database", lambda: f"{Path('university.db').stat().st_size / 1024:.0f} KB"):
        checks_ok += 1

    # FFmpeg
    checks_total += 1
    def _ffmpeg_check():
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        return f"bundled at ...{Path(p).name}"
    if _probe("FFmpeg", _ffmpeg_check):
        checks_ok += 1

    # TTS engine
    checks_total += 1
    def _tts_check():
        import edge_tts  # noqa: F401
        tts_settings = get_tts_settings()
        return (
            f"edge-tts ready, voice={tts_settings['voice_id']}, "
            f"rate={tts_settings['rate_str']}, pitch={tts_settings['pitch_str']}"
        )
    if _probe("TTS Engine", _tts_check):
        checks_ok += 1

    # LLM provider
    checks_total += 1
    def _llm_check():
        provider = get_setting("llm_provider", "ollama")
        model = get_setting("llm_model", "llama3")
        return f"provider={provider}, model={model}"
    if _probe("LLM Config", _llm_check):
        checks_ok += 1

    # Video engine
    checks_total += 1
    def _video_check():
        from media.video_engine import render_lecture  # noqa: F401
        return "module loads OK"
    if _probe("Video Engine", _video_check):
        checks_ok += 1

    # Audio engine
    checks_total += 1
    def _audio_check():
        from media.audio_engine import generate_binaural_wav  # noqa: F401
        return "module loads OK"
    if _probe("Audio Engine", _audio_check):
        checks_ok += 1

    if checks_ok == checks_total:
        st.success(f"All {checks_total} checks passed.")
    else:
        st.warning(f"{checks_ok}/{checks_total} checks passed. See details above.")

section_divider("Active Courses")
if not courses:
    st.warning("No courses found. Go to Library > Bulk Import and paste a course JSON.")
else:
    for course in courses[:8]:
        st.markdown(
            f"<div style='background:#0e1230;border-left:3px solid #00d4ff;"
            f"padding:8px 16px;margin:4px 0;font-family:monospace;'>"
            f"<span style='color:#00d4ff;'>{course['id']}</span>"
            f"<span style='color:#b8b8d0;margin-left:12px;'>{course['title']}</span>"
            f"<span style='color:#ffd700;margin-left:12px;'> {course['credits']} cr</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


 
# ██      ██ █     █    ██    █ █ █▀▀▀▀█ █▀▀▀▀█ ████████
# █ █    █ █  █   █     █ █   █ █ █      █      █      █
# █  █  █  █   ███      █  █  █ █ █  ▄▄▄ █  ▄▄▄ █▄▄▄▄▄▄█
# █   ██   █    █       █   █ █ █ █    █ █    █ █      █
# █        █    █       █    ██ █ █▄▄▄▄█ █▄▄▄▄█ █      █





# █ ¿≥,↕




