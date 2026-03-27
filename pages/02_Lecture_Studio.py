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
    get_assignments, get_setting, save_setting, unlock_achievement, add_xp,
    get_assignment_ai_policy, start_assignment, flag_prove_it,
)
from media.output_paths import resolve_full_video_path
from ui.theme import inject_theme, gf_header, section_divider, progress_badge, play_sfx, stat_card, help_button

inject_theme()
gf_header("Lecture Studio", "Enter the chamber of knowledge.")
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
lec_data.setdefault("course_id", course["id"])
lec_data.setdefault("course_title", course["title"])
lec_data.setdefault("module_id", module["id"])
lec_data.setdefault("module_title", module["title"])

section_divider("Details")
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

section_divider("Video Playback")
help_button("playing-lectures")

# Check if video already rendered
lid = lec_row["id"]
full_video = resolve_full_video_path(lec_data, EXPORT_DIR)

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

section_divider("Render Controls")
help_button("rendering-lecture")

# ─── Provider & VFX status ────────────────────────────────────────────────────
render_provider = get_setting("render_provider", "local")
provider_labels = {
    "local": "Built-in PIL Renderer",
    "comfyui": "ComfyUI (Local Diffusion)",
    "free_cloud_mix": "Free Cloud Mix (auto-cycle)",
    "custom_api": "Custom API",
}

# Show diffusion provider status with live check
_diffusion_status = "No AI image provider"
_diffusion_color = "#e04040"
try:
    from media.diffusion.free_tier_cycler import get_best_provider, get_all_providers
    bp = get_best_provider()
    if bp:
        _diffusion_status = f"AI Backgrounds: {bp.name} ready"
        _diffusion_color = "#40dc80"
    else:
        all_p = get_all_providers()
        avail = [p for p in all_p if p["available"]]
        if avail:
            exhausted = [p for p in avail if p.get("remaining") is not None and p["remaining"] <= 0]
            if len(exhausted) == len(avail):
                _diffusion_status = f"AI Backgrounds: {len(avail)} providers — all quotas exhausted"
                _diffusion_color = "#ff8c00"
            else:
                _diffusion_status = f"AI Backgrounds: {len(avail)} providers detected"
                _diffusion_color = "#ffd700"
        else:
            _diffusion_status = "AI Backgrounds: no providers available (set up in Library > Media Sources)"
            _diffusion_color = "#e04040"
except Exception:
    pass

st.markdown(
    f"<div style='font-family:monospace;font-size:0.82rem;padding:6px 12px;"
    f"border-left:3px solid {_diffusion_color};background:#0a1020;margin-bottom:8px;'>"
    f"<span style='color:{_diffusion_color};'>{_diffusion_status}</span>"
    f"<br/><span style='color:#606080;'>Render engine: "
    f"{provider_labels.get(render_provider, render_provider)}</span></div>",
    unsafe_allow_html=True,
)

# ─── LLM Narration Enrichment ────────────────────────────────────────────────
with st.expander("Enrich Narration with LLM (recommended before first render)", expanded=False):
    st.markdown(
        "<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
        "Use the LLM to rewrite generic narration prompts into real educational scripts "
        "that actually teach the subject matter. This updates the lecture data in the database.</span>",
        unsafe_allow_html=True,
    )
    if st.button("Enrich This Lecture's Narration", use_container_width=True):
        from llm.providers import simple_complete, cfg_from_settings

        enrichment_status = st.empty()
        enriched_scenes = []
        recipe = lec_data.get("video_recipe", {})
        scene_blocks = recipe.get("scene_blocks", [])
        cfg = cfg_from_settings()
        all_ok = True

        for i, scene in enumerate(scene_blocks):
            enrichment_status.caption(f"Enriching scene {i+1}/{len(scene_blocks)}: {scene.get('block_id', '?')}...")
            narr = scene.get("narration_prompt", "")
            dur = scene.get("duration_s", 60)
            word_target = int(dur * 2.5)
            prompt = (
                f"You are writing a narration script for an educational video lecture.\n"
                f"Course: {course['title']}\n"
                f"Lecture: {lec_row['title']}\n"
                f"Scene {i+1} of {len(scene_blocks)}\n"
                f"Duration: {dur} seconds (~{word_target} words needed)\n"
                f"Learning objectives: {', '.join(lec_data.get('learning_objectives', []))}\n"
                f"Core terms: {', '.join(lec_data.get('core_terms', []))}\n"
                f"Original prompt: {narr}\n"
                f"Visual context: {scene.get('visual_prompt', '')}\n\n"
                f"Write a {word_target}-word narration script that ACTUALLY TEACHES the subject matter. "
                f"Do NOT just say 'fundamentals are important' — explain WHAT the fundamentals are, "
                f"give examples, define terms, walk through concepts step by step. "
                f"Do NOT use markdown, bullet points, headers, bold, or any formatting. "
                f"Do NOT include praise like 'good job' or 'well done' — this is a lecture, not interactive. "
                f"Write in a clear, engaging, direct teaching voice. Output ONLY plain narration text."
            )
            try:
                result = simple_complete(cfg, prompt)
                if result and len(result.split()) > 20:
                    scene["narration_prompt"] = result.strip()
                else:
                    all_ok = False
            except Exception as e:
                st.warning(f"Scene {i+1} enrichment failed: {e}")
                all_ok = False

        # Save back to database
        if scene_blocks:
            lec_data["video_recipe"]["scene_blocks"] = scene_blocks
            from core.database import update_lecture_data
            try:
                update_lecture_data(lec_row["id"], lec_data)
                enrichment_status.empty()
                if all_ok:
                    st.success(f"All {len(scene_blocks)} scenes enriched with real educational narration!")
                else:
                    st.warning("Some scenes were enriched. Others may need retry.")
                st.info("Now render the video to hear the improved narration.")
            except Exception as e:
                st.error(f"Failed to save enriched data: {e}")

# ─── Render buttons ───────────────────────────────────────────────────────────
r1, r2, r3 = st.columns(3)

with r1:
    if st.button("Render This Lecture", use_container_width=True, type="primary"):
        from media.video.encoder import render_lecture
        with st.spinner("Rendering video with narration and AI backgrounds..."):
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
        from media.video.encoder import render_lecture
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
    if st.button("Render ALL Course Lectures", use_container_width=True):
        from media.video.encoder import render_lecture
        all_modules = get_modules(course["id"])
        total_lecs = []
        for m in all_modules:
            for l in get_lectures(m["id"]):
                ld = json.loads(l.get("data") or "{}")
                ld.setdefault("lecture_id", l["id"])
                ld.setdefault("title", l["title"])
                ld.setdefault("course_id", course["id"])
                ld.setdefault("course_title", course["title"])
                ld.setdefault("module_id", m["id"])
                ld.setdefault("module_title", m["title"])
                total_lecs.append((l, ld))
        if not total_lecs:
            st.warning("No lectures found in this course.")
        else:
            render_status = st.empty()
            render_progress = st.progress(0)
            render_log = []
            for idx, (lrow, ldata) in enumerate(total_lecs):
                render_status.caption(f"Rendering {idx+1}/{len(total_lecs)}: {lrow['title']}...")
                try:
                    render_lecture(ldata, EXPORT_DIR, chunk_by_scene=False)
                    render_log.append(f"[OK]  {lrow['title']}")
                    set_progress(lrow["id"], "in_progress")
                except Exception as e:
                    render_log.append(f"[ERR] {lrow['title']}: {e}")
                render_progress.progress((idx + 1) / len(total_lecs))
            render_status.empty()
            render_progress.progress(1.0)
            play_sfx("level_up")
            ok_count = sum(1 for l in render_log if l.startswith("[OK]"))
            st.success(f"Rendered {ok_count}/{len(total_lecs)} lectures for {course['title']}.")
            st.code("\n".join(render_log), language="text")

# ─── Visual Effects (inline) ─────────────────────────────────────────────────
_current_vfx = {}
try:
    _current_vfx = json.loads(get_setting("vfx_config", "{}"))
except Exception:
    pass

with st.expander("Visual Effects", expanded=False):
    ve1, ve2 = st.columns(2)
    with ve1:
        _vfx_transitions = st.toggle("Scene transitions (crossfade)", value=_current_vfx.get("transitions", True), key="ls_vfx_trans")
        _vfx_ken = st.toggle("Ken Burns pan/zoom", value=_current_vfx.get("ken_burns", True), key="ls_vfx_ken")
        _vfx_color = st.toggle("Cinematic color grading", value=_current_vfx.get("color_grade", True), key="ls_vfx_color")
    with ve2:
        _vfx_text = st.toggle("Title/term overlays", value=_current_vfx.get("text_overlay", True), key="ls_vfx_text")
        _vfx_particles = st.toggle("Ambient particles", value=_current_vfx.get("ambient_particles", True), key="ls_vfx_part")
        _vfx_wm = st.toggle("Watermark", value=_current_vfx.get("watermark", False), key="ls_vfx_wm")
    _new_vfx = {
        "transitions": _vfx_transitions, "ken_burns": _vfx_ken,
        "color_grade": _vfx_color, "text_overlay": _vfx_text,
        "ambient_particles": _vfx_particles, "watermark": _vfx_wm,
    }
    if _new_vfx != _current_vfx:
        save_setting("vfx_config", json.dumps(_new_vfx))

section_divider("Assignments")
help_button("assignment-submission")
assignments = [a for a in get_assignments(course["id"]) if a.get("lecture_id") == lec_row["id"]]

deadlines_on = get_setting("deadlines_enabled", "0") == "1"

# ── Professor AI for assignments ──────────────────────────────────────────────
with st.expander("Ask Professor about assignments"):
    _ls_prof_q = st.text_input(
        "Question", key="ls_prof_q",
        placeholder=f"Ask about assignments for {lec_row['title']}...",
        label_visibility="collapsed",
    )
    if _ls_prof_q and st.button("Ask", key="ls_prof_go"):
        from llm.providers import simple_complete, cfg_from_settings as _ls_cfg_fn
        _ls_cfg = _ls_cfg_fn()
        _ls_prompt = (
            f"You are a university professor. The student is studying '{course['title']}', "
            f"lecture '{lec_row['title']}'. They have a question about assignments:\n{_ls_prof_q}\n\n"
            f"Answer concisely. Do NOT use markdown."
        )
        try:
            with st.spinner("Professor is thinking..."):
                _ls_answer = simple_complete(_ls_cfg, _ls_prompt)
            st.info(_ls_answer)
        except Exception as _ls_exc:
            st.error(f"Professor offline: {_ls_exc}")

_AI_BADGE = {
    "unrestricted": "<span style='color:#40dc80;font-weight:bold;'>[OPEN]</span> AI use allowed freely",
    "assisted": "<span style='color:#ffd700;font-weight:bold;'>[AIDED]</span> AI for specific tasks only",
    "supervised": "<span style='color:#ff8c00;font-weight:bold;'>[WATCH]</span> AI under constraints",
    "prohibited": "<span style='color:#e04040;font-weight:bold;'>[NONE]</span> No AI assistance",
}

if not assignments:
    st.info("No assignments for this lecture yet. Ask the Professor AI to generate some.")
else:
    for asn in assignments:
        now = time.time()
        due = asn.get("due_at")
        submitted = asn.get("submitted_at")
        policy = get_assignment_ai_policy(asn)
        level = policy.get("level", "assisted")
        badge_html = _AI_BADGE.get(level, _AI_BADGE["assisted"])

        with st.expander(f"  {asn['type'].upper()}  {asn['title']}", expanded=False):
            # AI policy badge
            st.markdown(
                f"<div style='font-family:monospace;font-size:0.85rem;margin-bottom:8px;'>"
                f"AI Policy: {badge_html}</div>",
                unsafe_allow_html=True,
            )
            st.write(asn.get("description", ""))
            if deadlines_on and due:
                remaining = due - now
                from ui.theme import deadline_pill
                st.markdown(deadline_pill(remaining), unsafe_allow_html=True)
            if submitted:
                score = asn.get("score")
                max_s = asn.get("max_score", 100)
                assignment_data = asn.get("data") or {}
                if isinstance(assignment_data, str):
                    import json
                    try:
                        assignment_data = json.loads(assignment_data)
                    except json.JSONDecodeError:
                        assignment_data = {}
                grading_status = assignment_data.get("grading_status", "graded" if score is not None else "pending_review")
                if score is None:
                    st.info("Submitted for review. This work is recorded, but it does not count as graded evidence yet.")
                else:
                    from core.database import score_to_grade
                    grade, _ = score_to_grade((score / max_s) * 100 if max_s else 0)
                    st.success(f"Submitted -- Score: {score}/{max_s}  Grade: {grade}")
                dur = asn.get("duration_s") or 0
                if dur > 0:
                    st.caption(f"Time spent: {dur / 60:.0f} min")
                if grading_status == "pending_review":
                    submitted_text = assignment_data.get("student_submission", "")
                    if submitted_text:
                        st.caption("Submitted response")
                        st.write(submitted_text)
                elif asn.get("feedback"):
                    st.write(asn.get("feedback", ""))

                # Prove-it flagging for verification assignments
                flag = flag_prove_it(asn["id"])
                if flag:
                    st.warning(flag["message"])

                # Prove-it challenge prompt for AI-assisted submissions
                if level in ("assisted", "supervised") and asn["type"] != "verification":
                    st.markdown("---")
                    st.markdown(
                        "<div style='font-family:monospace;color:#ff8c00;'>"
                        "A prove-it verification may be required to confirm mastery. "
                        "Ask Professor AI to generate one.</div>",
                        unsafe_allow_html=True,
                    )
            else:
                # Start timer on first view
                start_assignment(asn["id"])
                with st.form(key=f"submit_{asn['id']}"):
                    answer = st.text_area("Your answer / submission")
                    if st.form_submit_button("Submit"):
                        submit_assignment(asn["id"], None, answer)
                        play_sfx("success")
                        st.success("Submitted for review.")
                        st.rerun()

# ─── Scribe Submission ────────────────────────────────────────────────────────
section_divider("Scribe Credit")
help_button("scribe-submission")

from core.db_scribe import (
    save_scribe, get_scribes, total_scribe_words, scribe_complete,
    SCRIBE_MIN_WORDS, verify_scribe_originality, generate_scribe_quiz,
    level_scribe_complete, get_scribe_status_for_level,
)

_cur_depth = course.get("depth_level", 0)
_lvl_status = get_scribe_status_for_level(course["id"], _cur_depth)
_scribe_done = _lvl_status["complete"]
_scribe_total = _lvl_status["words_submitted"]
_scribe_pct = _lvl_status["progress_pct"]

sc1, sc2, sc3 = st.columns(3)
sc1.metric("Words submitted", f"{_scribe_total:,}")
sc2.metric("Requirement", f"{SCRIBE_MIN_WORDS:,}")
sc3.metric("Progress", f"{_scribe_pct}%")

if _scribe_done:
    st.success(
        "Scribe requirement met! You have submitted enough transcription to earn Scribe credit for this course."
    )
else:
    st.info(
        f"**Scribe Credit** — Submit a real-world lecture transcription (~1.5 hours, "
        f"≥{SCRIBE_MIN_WORDS:,} words) to earn Scribe credit for this course. "
        f"You can submit in multiple installments. This is required for full course credit."
    )

with st.expander("Submit Transcription / Notes", expanded=not _scribe_done):
    _scribe_text = st.text_area(
        "Paste your lecture transcription or notes here",
        height=220,
        placeholder=(
            "Transcribe or paste the text from a real-world 90-minute lecture related to this course. "
            "Min ~10,000 words total (across all submissions)."
        ),
        key=f"scribe_text_{course['id']}",
    )
    _wc_preview = len(_scribe_text.split()) if _scribe_text.strip() else 0
    st.caption(f"Word count: {_wc_preview:,}")

    if st.button("Submit Scribe", use_container_width=True, type="primary", key="scribe_submit_btn"):
        if _wc_preview < 100:
            st.warning("Please paste at least 100 words to submit.")
        else:
            # Originality check
            _orig = verify_scribe_originality(_scribe_text.strip())
            if not _orig["passed"]:
                st.warning(f"Originality check: {_orig['reason']} (score: {_orig['score']}/100)")
                st.caption("Your submission was saved but flagged. A follow-up quiz may be required.")
            result = save_scribe(course["id"], lec_row["id"], _scribe_text.strip(),
                               depth_level=_cur_depth)
            add_xp(50 if result["complete"] and not _scribe_done else 10,
                   "Scribe submission", "scribe")
            if result["complete"] and not _scribe_done:
                unlock_achievement("scribe_complete")
                play_sfx("unlock")
            st.success(f"Submitted {_wc_preview:,} words. Total for course: {_scribe_total + _wc_preview:,}")

            # Generate comprehension quiz if enough text
            if _wc_preview >= 500:
                _quiz_prompt = generate_scribe_quiz(course["title"], _scribe_text.strip())
                try:
                    from llm.providers import simple_complete, cfg_from_settings as _sq_cfg
                    _sq = simple_complete(_sq_cfg(), _quiz_prompt)
                    if _sq:
                        st.markdown("**Comprehension Check** — answer these to confirm understanding:")
                        st.info(_sq)
                except Exception:
                    pass
            st.rerun()

_prev_scribes = get_scribes(course["id"])
if _prev_scribes:
    with st.expander(f"Previous submissions ({len(_prev_scribes)})"):
        for _s in _prev_scribes:
            st.markdown(
                f"- {_s['word_count']:,} words — "
                f"{_s.get('text_snippet', '')[:80]}…"
            )
