"""
Timeline Editor — drag scene order, set duration overrides, re-export.
"""

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_all_courses, get_modules, get_lectures
from core.ui_mode import require_ui_mode
from media.output_paths import resolve_full_video_path
from ui.theme import inject_theme, gf_header, section_divider, play_sfx, help_button

inject_theme()
require_ui_mode(("builder", "operator"), "Timeline Editor")
gf_header("Timeline Editor", "Reorder and tune scenes before rendering.")
help_button("reordering-scenes")

EXPORT_DIR = ROOT / "exports"

courses = get_all_courses()
if not courses:
    st.warning("No courses loaded.")
    st.stop()

course_map = {f"{c['id']} — {c['title']}": c for c in courses}
selected_course = st.selectbox("Course", list(course_map.keys()))
course = course_map[selected_course]

modules = get_modules(course["id"])
if not modules:
    st.warning("No modules.")
    st.stop()

module_map = {f"{m['order_index']+1}. {m['title']}": m for m in modules}
selected_module = st.selectbox("Module", list(module_map.keys()))
module = module_map[selected_module]

lectures = get_lectures(module["id"])
if not lectures:
    st.warning("No lectures.")
    st.stop()

lec_map = {f"{l['order_index']+1}. {l['title']}": l for l in lectures}
selected_lec = st.selectbox("Lecture", list(lec_map.keys()))
lec_row = lec_map[selected_lec]
lec_data = json.loads(lec_row["data"] or "{}")
lec_data.setdefault("lecture_id", lec_row["id"])
lec_data.setdefault("title", lec_row["title"])
lec_data.setdefault("course_id", course["id"])
lec_data.setdefault("course_title", course["title"])
lec_data.setdefault("module_id", module["id"])
lec_data.setdefault("module_title", module["title"])

scenes = lec_data.get("video_recipe", {}).get("scene_blocks", [])
if not scenes:
    st.info("This lecture has no scene blocks defined.")
    st.stop()

section_divider("Scene Blocks")
help_button("reordering-scenes")
st.markdown(
    "<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
    "Reorder scenes with the arrow buttons. Override duration (0 = use TTS-detected length). "
    "Click Render to apply changes.</span>",
    unsafe_allow_html=True,
)

# Session state for editable scene list
state_key = f"scenes_{lec_row['id']}"
if state_key not in st.session_state or st.button("Reset to Original"):
    st.session_state[state_key] = [dict(s) for s in scenes]

editable = st.session_state[state_key]
n = len(editable)

for i, scene in enumerate(editable):
    with st.container():
        c0, c1, c2, c3 = st.columns([0.5, 4, 2, 0.5])
        with c0:
            st.markdown(f"<span style='color:#00d4ff;font-family:monospace;font-weight:bold;font-size:1.1rem;'>{i+1}</span>", unsafe_allow_html=True)
        with c1:
            st.markdown(f"<span style='font-family:monospace;color:#e8e8ff;'>{scene.get('block_id','')}: {scene.get('ambiance_prompt','')[:80]}</span>", unsafe_allow_html=True)
            narration_preview = scene.get("narration_script", "")[:120]
            st.markdown(f"<span style='font-family:monospace;color:#808099;font-size:0.8rem;'>{narration_preview}...</span>", unsafe_allow_html=True)
        with c2:
            new_dur = st.number_input(
                f"Duration override (s) #{i+1}",
                min_value=0,
                max_value=600,
                value=int(scene.get("duration_override_s", scene.get("duration_s", 0))),
                key=f"dur_{state_key}_{i}",
                label_visibility="collapsed",
            )
            editable[i]["duration_override_s"] = new_dur
        with c3:
            btn_col = st.container()
            if i > 0:
                if btn_col.button("^", key=f"up_{state_key}_{i}", help="Move up"):
                    editable[i], editable[i-1] = editable[i-1], editable[i]
                    st.session_state[state_key] = editable
                    st.rerun()
            if i < n-1:
                if btn_col.button("v", key=f"dn_{state_key}_{i}", help="Move down"):
                    editable[i], editable[i+1] = editable[i+1], editable[i]
                    st.session_state[state_key] = editable
                    st.rerun()

section_divider("Render with Edits")
help_button("exporting-timeline")
rd1, rd2 = st.columns(2)
with rd1:
    if st.button("Render Edited Timeline", use_container_width=True):
        modified_lec = dict(lec_data)
        modified_lec["video_recipe"] = dict(lec_data.get("video_recipe", {}))
        modified_lec["video_recipe"]["scene_blocks"] = editable

        with st.spinner("Rendering edited timeline..."):
            try:
                from media.video_engine import render_lecture
                outs = render_lecture(modified_lec, EXPORT_DIR, chunk_by_scene=False, suffix="_edited")
                play_sfx("success")
                st.success(f"Rendered: {outs[0].name}")
                st.video(str(resolve_full_video_path(modified_lec, EXPORT_DIR, suffix="_edited")))
            except Exception as e:
                st.error(f"Render failed: {e}")

with rd2:
    export_btn = st.button("Export Modified JSON", use_container_width=True)
    if export_btn:
        modified_lec = dict(lec_data)
        modified_lec["video_recipe"] = dict(lec_data.get("video_recipe", {}))
        modified_lec["video_recipe"]["scene_blocks"] = editable
        raw = json.dumps(modified_lec, indent=2)
        st.download_button(
            "Download Modified Lecture JSON",
            raw,
            file_name=f"{lec_row['id']}_edited.json",
            mime="application/json",
            use_container_width=True,
        )
