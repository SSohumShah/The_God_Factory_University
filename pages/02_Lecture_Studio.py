"""
Lecture Studio — play lectures, render videos, take notes, submit assignments.
"""

import json
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_all_courses, get_modules, get_lectures, get_lecture,
    get_progress, set_progress, save_assignment, submit_assignment,
    get_assignments, get_setting, unlock_achievement, add_xp,
)
from ui.theme import inject_theme, arcane_header, rune_divider, progress_badge, play_sfx, stat_card, help_button

inject_theme()
arcane_header("Lecture Studio", "Enter the chamber of knowledge.")
help_button("playing-lectures")

EXPORT_DIR = ROOT / "exports"

# ─── Course / module / lecture selector ──────────────────────────────────────
courses = get_all_courses()
if not courses:
    st.warning("No courses loaded. Visit Library to import.")
    st.stop()

course_map = {f"{c['id']} — {c['title']}": c for c in courses}
selected_course = st.selectbox("Course", list(course_map.keys()))
course = course_map[selected_course]

modules = get_modules(course["id"])
if not modules:
    st.warning("No modules in this course.")
    st.stop()

module_map = {f"{m['order_index']+1}. {m['title']}": m for m in modules}
selected_module = st.selectbox("Module", list(module_map.keys()))
module = module_map[selected_module]

lectures = get_lectures(module["id"])
if not lectures:
    st.warning("No lectures in this module.")
    st.stop()

lec_map = {f"{l['order_index']+1}. {l['title']}": l for l in lectures}
selected_lec = st.selectbox("Lecture", list(lec_map.keys()))
lec_row = lec_map[selected_lec]
lec_data = json.loads(lec_row["data"] or "{}")
lec_data.setdefault("lecture_id", lec_row["id"])
lec_data.setdefault("title", lec_row["title"])
lec_data.setdefault("module_title", module["title"])

rune_divider("Details")
d1, d2, d3 = st.columns(3)
with d1:
    stat_card("Duration", f"{lec_row['duration_min']} min", colour="#00d4ff")
with d2:
    scenes = lec_data.get("video_recipe", {}).get("scene_blocks", [])
    stat_card("Scenes", str(len(scenes)), colour="#ffd700")
with d3:
    prog = get_progress(lec_row["id"])
    stat_card("Status", prog.get("status", "not_started").replace("_", " ").upper(), colour="#40dc80")

# ─── Objectives & terms ───────────────────────────────────────────────────────
with st.expander("Learning Objectives & Core Terms", expanded=False):
    for obj in lec_data.get("learning_objectives", []):
        st.markdown(f"<span style='color:#00d4ff;font-family:monospace;'>  ► {obj}</span>", unsafe_allow_html=True)
    st.divider()
    terms = lec_data.get("core_terms", [])
    st.markdown(
        " ".join(
            f"<span style='background:#0e1230;border:1px solid #00d4ff44;padding:3px 8px;"
            f"border-radius:2px;color:#00d4ff;font-family:monospace;margin:3px;'>{t}</span>"
            for t in terms
        ),
        unsafe_allow_html=True,
    )

rune_divider("Video Playback")
help_button("playing-lectures")

# Check if video already rendered
lid = lec_row["id"]
full_video = EXPORT_DIR / f"{lid}_full.mp4"

if full_video.exists():
    st.video(str(full_video))
    if prog.get("status") != "completed":
        if st.button("Mark as Completed", use_container_width=True):
            set_progress(lec_row["id"], "completed")
            play_sfx("success")
            unlock_achievement("first_lecture")
            st.success("Quest complete! XP awarded.")
            st.rerun()
else:
    st.info("Video not yet rendered. Use the controls below.")

rune_divider("Render Controls")
help_button("rendering-lecture")
r1, r2, r3 = st.columns(3)

with r1:
    if st.button("Render Full Lecture Video", use_container_width=True):
        from media.video_engine import render_lecture
        with st.spinner("Generating animated video with narration... (first render is slowest)"):
            try:
                outs = render_lecture(lec_data, EXPORT_DIR, chunk_by_scene=False)
                set_progress(lec_row["id"], "in_progress")
                play_sfx("collect")
                st.success(f"Video ready: {outs[0].name}")
                st.video(str(outs[0]))
            except Exception as e:
                st.error(f"Render failed: {e}")

with r2:
    if st.button("Export Scene Chunks", use_container_width=True):
        from media.video_engine import render_lecture
        with st.spinner("Rendering scene chunks..."):
            try:
                outs = render_lecture(lec_data, EXPORT_DIR, chunk_by_scene=True)
                play_sfx("collect")
                st.success(f"Exported {len(outs)} chunk files.")
                for p in outs:
                    st.write(str(p))
            except Exception as e:
                st.error(f"Chunk export failed: {e}")

with r3:
    render_provider = get_setting("render_provider", "local")
    st.markdown(f"<span style='color:#606080;font-family:monospace;font-size:0.8rem;'>Render: {render_provider}</span>", unsafe_allow_html=True)
    if render_provider != "local":
        if st.button("Send to External Engine", use_container_width=True):
            st.info("External engine API integration — configure in Settings.")

rune_divider("Assignments")
help_button("assignment-submission")
assignments = [a for a in get_assignments(course["id"]) if a.get("lecture_id") == lec_row["id"]]

deadlines_on = get_setting("deadlines_enabled", "0") == "1"

if not assignments:
    st.info("No assignments for this lecture yet. Ask the Professor AI to generate some.")
else:
    for asn in assignments:
        now = time.time()
        due = asn.get("due_at")
        submitted = asn.get("submitted_at")
        with st.expander(f"  {asn['type'].upper()}  {asn['title']}", expanded=False):
            st.write(asn.get("description", ""))
            if deadlines_on and due:
                remaining = due - now
                from ui.theme import deadline_pill
                st.markdown(deadline_pill(remaining), unsafe_allow_html=True)
            if submitted:
                score = asn.get("score", 0)
                max_s = asn.get("max_score", 100)
                from core.database import score_to_grade
                grade, _ = score_to_grade((score / max_s) * 100 if max_s else 0)
                st.success(f"Submitted — Score: {score}/{max_s}  Grade: {grade}")
                st.write(asn.get("feedback", ""))
            else:
                with st.form(key=f"submit_{asn['id']}"):
                    answer = st.text_area("Your answer / submission")
                    submitted_score = st.slider("Self-score (if applicable)", 0, 100, 75)
                    if st.form_submit_button("Submit"):
                        submit_assignment(asn["id"], submitted_score, answer)
                        play_sfx("success")
                        st.success("Submitted!")
                        st.rerun()
