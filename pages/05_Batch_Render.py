"""
Batch Render — queue and render all lectures overnight with progress bar.
Includes Runway / Pika / ComfyUI prompt export.
"""

import json
import sys
import threading
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_all_courses, get_modules, get_lectures, get_setting
from ui.theme import inject_theme, arcane_header, rune_divider, play_sfx, help_button

inject_theme()
arcane_header("Batch Render", "Queue all lectures for overnight rendering.")
help_button("batch-render")

EXPORT_DIR = ROOT / "exports"

# ─── Collect all lectures ─────────────────────────────────────────────────────
courses = get_all_courses()
if not courses:
    st.warning("No courses loaded.")
    st.stop()

all_lectures = []
for course in courses:
    for module in get_modules(course["id"]):
        for lec in get_lectures(module["id"]):
            all_lectures.append({
                "course_title": course["title"],
                "module_title": module["title"],
                "lecture": lec,
            })

if not all_lectures:
    st.info("No lectures found.")
    st.stop()

rune_divider("Select Lectures to Render")
st.markdown(
    f"<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
    f"{len(all_lectures)} lectures available. Select those to render, then start the queue.</span>",
    unsafe_allow_html=True,
)

select_all = st.checkbox("Select all lectures", value=True)
selected_ids = set()
for item in all_lectures:
    lec = item["lecture"]
    label = f"{item['course_title']} / {item['module_title']} / {lec['title']}"
    checked = st.checkbox(label, value=select_all, key=f"sel_{lec['id']}")
    if checked:
        selected_ids.add(lec["id"])

rune_divider("Render Queue")
help_button("batch-render")
render_provider = get_setting("render_provider", "local")
st.markdown(f"<span style='font-family:monospace;color:#606080;font-size:0.8rem;'>Render backend: {render_provider}</span>", unsafe_allow_html=True)

queue = [item for item in all_lectures if item["lecture"]["id"] in selected_ids]

col_a, col_b = st.columns(2)
with col_a:
    fps = st.select_slider("Output FPS", options=[10, 15, 24], value=15)
with col_b:
    resolution = st.selectbox("Resolution", ["960x540", "1280x720", "1920x1080"], index=0)
res_w, res_h = map(int, resolution.split("x"))

if "render_state" not in st.session_state:
    st.session_state["render_state"] = "idle"
    st.session_state["render_log"] = []
    st.session_state["render_progress"] = 0

START_KEY = "batch_start"

def do_batch_render(queue_snapshot, fps, res_w, res_h):
    from media.video_engine import render_lecture
    log = []
    total = len(queue_snapshot)
    for idx, item in enumerate(queue_snapshot):
        lec_row = item["lecture"]
        lec_data = json.loads(lec_row["data"] or "{}")
        lec_data.setdefault("lecture_id", lec_row["id"])
        lec_data.setdefault("title", lec_row["title"])
        try:
            render_lecture(lec_data, EXPORT_DIR, fps=fps, width=res_w, height=res_h)
            log.append(f"[OK]  {lec_row['title']}")
        except Exception as e:
            log.append(f"[ERR] {lec_row['title']}: {e}")
        st.session_state["render_progress"] = (idx + 1) / total
        st.session_state["render_log"] = log[:]
    st.session_state["render_state"] = "done"
    st.session_state["render_log"] = log

if st.session_state["render_state"] == "idle":
    if st.button(f"Start Batch Render ({len(queue)} lectures)", use_container_width=True, type="primary"):
        if not queue:
            st.warning("Select at least one lecture.")
        else:
            st.session_state["render_state"] = "running"
            st.session_state["render_log"] = []
            st.session_state["render_progress"] = 0
            t = threading.Thread(target=do_batch_render, args=(queue, fps, res_w, res_h), daemon=True)
            t.start()
            play_sfx("collect")
            st.rerun()

if st.session_state["render_state"] == "running":
    prog = st.session_state["render_progress"]
    st.progress(prog, text=f"Rendering... {int(prog*100)}%")
    log_text = "\n".join(st.session_state["render_log"][-20:])
    if log_text:
        st.code(log_text, language="bash")
    if st.button("Abort", type="secondary"):
        st.session_state["render_state"] = "idle"
        st.rerun()
    time.sleep(1)
    st.rerun()

if st.session_state["render_state"] == "done":
    play_sfx("level_up")
    st.success("Batch render complete.")
    log_text = "\n".join(st.session_state["render_log"])
    st.code(log_text, language="bash")
    if st.button("Reset", use_container_width=True):
        st.session_state["render_state"] = "idle"
        st.session_state["render_log"] = []
        st.session_state["render_progress"] = 0
        st.rerun()

# ─── Prompt Export ────────────────────────────────────────────────────────────
rune_divider("Export Visual Prompts")
st.markdown(
    "<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
    "Export all scene prompts formatted for Runway Gen-3, Pika, or ComfyUI workflows.</span>",
    unsafe_allow_html=True,
)

ep1, ep2, ep3 = st.columns(3)

def collect_prompts():
    out = []
    for item in all_lectures:
        lec_data = json.loads(item["lecture"]["data"] or "{}")
        for s in lec_data.get("video_recipe", {}).get("scene_blocks", []):
            out.append({
                "lecture": item["lecture"]["title"],
                "block_id": s.get("block_id"),
                "visual_prompt": s.get("visual_prompt", s.get("ambiance_prompt", "")),
                "keywords": s.get("keywords", []),
                "duration_s": s.get("duration_s", 60),
            })
    return out

with ep1:
    if st.button("Runway Gen-3 Pack", use_container_width=True):
        prompts = collect_prompts()
        lines = [
            f"# Scene {p['block_id']} — {p['lecture']}\n"
            f"--prompt \"{p['visual_prompt']}\" --duration {min(p['duration_s'], 10)}\n"
            for p in prompts
        ]
        st.download_button(
            "Download Runway Script",
            "\n".join(lines),
            file_name="runway_prompts.txt",
            mime="text/plain",
            use_container_width=True,
        )

with ep2:
    if st.button("Pika Prompt Pack", use_container_width=True):
        prompts = collect_prompts()
        pack = [{"prompt": p["visual_prompt"], "scene": p["block_id"], "lecture": p["lecture"]} for p in prompts]
        st.download_button(
            "Download Pika JSONL",
            "\n".join(json.dumps(r) for r in pack),
            file_name="pika_prompts.jsonl",
            mime="application/json",
            use_container_width=True,
        )

with ep3:
    if st.button("ComfyUI Prompt Pack", use_container_width=True):
        prompts = collect_prompts()
        workflow_batch = {
            "version": "1.0",
            "scenes": [
                {
                    "id": p["block_id"],
                    "positive": p["visual_prompt"],
                    "negative": "blurry, text, watermark, ugly, low quality",
                    "steps": 25,
                    "cfg": 7.5,
                    "width": 1280,
                    "height": 720,
                }
                for p in prompts
            ],
        }
        st.download_button(
            "Download ComfyUI Batch",
            json.dumps(workflow_batch, indent=2),
            file_name="comfyui_batch.json",
            mime="application/json",
            use_container_width=True,
        )

# ─── Already rendered files ───────────────────────────────────────────────────
rune_divider("Rendered Files")
video_files = sorted(EXPORT_DIR.glob("*.mp4"))
if video_files:
    for vf in video_files[-30:]:
        size_mb = vf.stat().st_size / (1024 * 1024)
        st.markdown(
            f"<span style='font-family:monospace;color:#606080;font-size:0.82rem;'>"
            f"  {vf.name}  —  {size_mb:.1f} MB</span>",
            unsafe_allow_html=True,
        )
else:
    st.info("No videos rendered yet.")
