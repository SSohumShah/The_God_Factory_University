"""
Arcane University — main entry point / Dashboard.
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
    page_title="Arcane University",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.database import (
    bulk_import_json, get_all_courses, get_setting, get_level,
    get_xp, count_completed,
)
from ui.theme import (
    inject_theme, arcane_header, rune_divider,
    xp_bar, level_badge, stat_card, help_button,
)

inject_theme()

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
        "║   ARCANE UNIVERSITY   ║\n"
        "╚══════════════════════╝\n```"
    )
    level_idx, level_title, xp_in_level, xp_to_next = get_level()
    level_badge(level_idx, level_title)
    xp_bar(xp_in_level, max(xp_to_next, 1), "XP")
    st.caption(f"Lectures completed: {count_completed()}")
    rune_divider("Navigation")
    st.page_link("app.py",                       label="  [*] Dashboard")
    st.page_link("pages/01_Library.py",           label="  [>] Library")
    st.page_link("pages/02_Lecture_Studio.py",    label="  [>] Lecture Studio")
    st.page_link("pages/03_Professor_AI.py",      label="  [>] Professor AI")
    st.page_link("pages/04_Timeline_Editor.py",   label="  [>] Timeline Editor")
    st.page_link("pages/05_Batch_Render.py",      label="  [>] Batch Render")
    st.page_link("pages/06_Grades.py",            label="  [>] Grades & Transcript")
    st.page_link("pages/07_Achievements.py",      label="  [>] Achievements")
    st.page_link("pages/08_Settings.py",          label="  [>] Settings")
    st.page_link("pages/09_Diagnostics.py",       label="  [>] Diagnostics")
    st.page_link("pages/10_Help.py",              label="  [?] Help")
    st.page_link("pages/11_LLM_Setup.py",         label="  [>] LLM Setup Wizard")

# ─── Dashboard ───────────────────────────────────────────────────────────────
arcane_header("Arcane University", "Where knowledge is power and every lesson is a quest.")
help_button("dashboard-overview")

courses = get_all_courses()
xp_total = get_xp()
completed = count_completed()

rune_divider("Status")
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

rune_divider("Quick Start")
st.markdown(
    "```\n"
    "HOW TO BEGIN\n"
    "─────────────────────────────────────────────────────────────\n"
    "1. Library        ─ Browse & import courses (paste any LLM JSON)\n"
    "2. Lecture Studio ─ Play lectures, watch animated videos\n"
    "3. Professor AI   ─ Chat, generate quizzes, get feedback\n"
    "4. Timeline Editor─ Reorder scenes and re-render custom videos\n"
    "5. Batch Render   ─ Overnight render entire curriculum\n"
    "6. Grades         ─ GPA, credits, degree eligibility\n"
    "7. Achievements   ─ Unlock dungeon milestones\n"
    "8. Settings       ─ Voice, LLM provider, video quality\n"
    "─────────────────────────────────────────────────────────────\n"
    "Generate a course: read schemas/SCHEMA_GUIDE.md\n"
    "```"
)

# ─── Startup Self-Check ─────────────────────────────────────────────────────
rune_divider("System Health")
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
        voice = get_setting("voice_id", "en-US-AriaNeural")
        return f"edge-tts ready, voice={voice}"
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

rune_divider("Active Courses")
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
