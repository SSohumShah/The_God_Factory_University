"""
Diagnostics — system health, dependency versions, DB stats, provider checks.
"""

import importlib
import platform
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_all_courses, get_modules, get_lectures, get_setting,
    get_xp, get_level, count_completed, compute_gpa,
    credits_earned, get_assignments,
)
from ui.theme import inject_theme, arcane_header, rune_divider, help_button

inject_theme()
arcane_header("Diagnostics", "Under the hood of the arcane machinery.")
help_button("diagnostics-page")


# ─── Environment ─────────────────────────────────────────────────────────────
rune_divider("Environment")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Runtime**")
    env_lines = [
        f"Python: {platform.python_version()}",
        f"Platform: {platform.system()} {platform.release()}",
        f"Architecture: {platform.machine()}",
        f"Executable: {sys.executable}",
    ]
    st.code("\n".join(env_lines), language="text")

with col2:
    st.markdown("**Working Directory**")
    st.code(str(ROOT), language="text")
    db_path = ROOT / "university.db"
    if db_path.exists():
        st.markdown(f"DB size: **{db_path.stat().st_size / 1024:.1f} KB**")
    else:
        st.warning("university.db not found")


# ─── Dependency Versions ─────────────────────────────────────────────────────
rune_divider("Dependencies")

DEPS = [
    "streamlit", "moviepy", "imageio", "imageio_ffmpeg", "PIL",
    "numpy", "scipy", "edge_tts", "pyttsx3", "openai", "anthropic",
    "httpx", "requests", "psutil",
]

dep_rows = []
for dep_name in DEPS:
    try:
        mod = importlib.import_module(dep_name)
        ver = getattr(mod, "__version__", getattr(mod, "VERSION", "installed"))
        dep_rows.append({"Package": dep_name, "Version": str(ver), "Status": "OK"})
    except ImportError:
        dep_rows.append({"Package": dep_name, "Version": "-", "Status": "MISSING"})

st.dataframe(dep_rows, use_container_width=True, hide_index=True)

# FFmpeg binary
try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    st.markdown(f"FFmpeg binary: `{ffmpeg_path}`")
except Exception as e:
    st.error(f"FFmpeg: {e}")


# ─── Database Stats ──────────────────────────────────────────────────────────
rune_divider("Database Stats")

courses = get_all_courses()
total_mods = 0
total_lecs = 0
for c in courses:
    mods = get_modules(c["id"])
    total_mods += len(mods)
    for m in mods:
        total_lecs += len(get_lectures(m["id"]))

gpa, graded_count = compute_gpa()
xp = get_xp()
level_idx, level_name, xp_in, xp_to = get_level()
creds = credits_earned()
completed = count_completed()
assignments = get_assignments()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Courses", len(courses))
    st.metric("Modules", total_mods)
with c2:
    st.metric("Lectures", total_lecs)
    st.metric("Completed", completed)
with c3:
    st.metric("Assignments", len(assignments))
    st.metric("Graded", graded_count)
with c4:
    st.metric("GPA", f"{gpa:.2f}")
    st.metric("Credits", creds)

st.markdown(f"**XP:** {xp:,}  |  **Level:** {level_idx} ({level_name})  |  "
            f"**Progress:** {xp_in}/{xp_to} to next")


# ─── LLM Provider Config ────────────────────────────────────────────────────
rune_divider("LLM Provider")
help_button("llm-test")

provider = get_setting("llm_provider", "ollama")
model = get_setting("llm_model", "llama3")
base_url = get_setting("llm_base_url", "")
has_key = bool(get_setting("llm_api_key", ""))

st.code(
    f"Provider:  {provider}\n"
    f"Model:     {model}\n"
    f"Base URL:  {base_url or '(default)'}\n"
    f"API Key:   {'configured' if has_key else 'not set'}",
    language="text",
)

if st.button("Test LLM Connection"):
    with st.spinner("Sending test prompt..."):
        try:
            from llm.providers import cfg_from_settings, chat
            cfg = cfg_from_settings()
            result = chat(cfg, [{"role": "user", "content": "Respond with exactly: HEALTH_OK"}])
            if "HEALTH_OK" in result:
                st.success(f"LLM responded correctly: {result.strip()[:80]}")
            else:
                st.warning(f"LLM responded but unexpected output: {result.strip()[:120]}")
        except Exception as e:
            st.error(f"LLM connection failed: {e}")


# ─── Audio Engine ────────────────────────────────────────────────────────────
rune_divider("Audio Engine")

voice_id = get_setting("voice_id", "en-US-AriaNeural")
binaural = get_setting("binaural_mode", "gamma_40hz")
st.code(f"Voice: {voice_id}\nBinaural preset: {binaural}", language="text")

if st.button("Test TTS"):
    with st.spinner("Generating test speech..."):
        try:
            from media.audio_engine import synth_tts, audio_duration
            test_path = ROOT / "exports" / "_diag_tts_test.mp3"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            synth_tts("System diagnostics check complete.", test_path, voice_id=voice_id)
            dur = audio_duration(test_path)
            st.success(f"TTS generated: {dur:.1f}s, {test_path.stat().st_size / 1024:.1f} KB")
            st.audio(str(test_path))
            test_path.unlink(missing_ok=True)
        except Exception as e:
            st.error(f"TTS failed: {e}")


# ─── Video Engine ────────────────────────────────────────────────────────────
rune_divider("Video Engine")

vid_fps = get_setting("video_fps", "15")
vid_w = get_setting("video_width", "960")
vid_h = get_setting("video_height", "540")
st.code(f"Resolution: {vid_w}x{vid_h} @ {vid_fps} fps", language="text")


# ─── Settings Dump ──────────────────────────────────────────────────────────
rune_divider("All Settings")

with st.expander("View raw settings table"):
    try:
        from core.database import tx
        with tx() as con:
            rows = con.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        # Mask API keys
        display_rows = []
        for r in rows:
            val = r["value"]
            if "key" in r["key"].lower() and val:
                val = val[:4] + "****" if len(val) > 4 else "****"
            display_rows.append({"Key": r["key"], "Value": val})
        st.dataframe(display_rows, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Could not read settings: {e}")


# ─── Page Import Check ──────────────────────────────────────────────────────
rune_divider("Module Health")
help_button("compile-check")

with st.expander("Compile check for all pages and modules"):
    import py_compile

    targets = {
        "app.py": ROOT / "app.py",
        "core/database.py": ROOT / "core" / "database.py",
        "llm/providers.py": ROOT / "llm" / "providers.py",
        "llm/professor.py": ROOT / "llm" / "professor.py",
        "media/audio_engine.py": ROOT / "media" / "audio_engine.py",
        "media/video_engine.py": ROOT / "media" / "video_engine.py",
        "ui/theme.py": ROOT / "ui" / "theme.py",
    }
    # Add all pages
    pages_dir = ROOT / "pages"
    if pages_dir.exists():
        for p in sorted(pages_dir.glob("*.py")):
            targets[f"pages/{p.name}"] = p

    results = []
    for label, path in targets.items():
        try:
            py_compile.compile(str(path), doraise=True)
            results.append({"File": label, "Status": "OK"})
        except py_compile.PyCompileError as e:
            results.append({"File": label, "Status": f"ERROR: {e}"})

    ok_count = sum(1 for r in results if r["Status"] == "OK")
    st.dataframe(results, use_container_width=True, hide_index=True)
    if ok_count == len(results):
        st.success(f"All {len(results)} files compile OK.")
    else:
        st.warning(f"{ok_count}/{len(results)} files OK.")


# ─── Recent Error Log ───────────────────────────────────────────────────────
rune_divider("Recent Errors")
log_file = ROOT / "logs" / "arcane.log"
if log_file.exists():
    import json as _json
    with st.expander("View recent error log entries"):
        lines = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        errors = []
        for line in reversed(lines[-200:]):
            try:
                entry = _json.loads(line)
                if entry.get("level") == "ERROR":
                    eid = entry.get("error_id", "—")
                    errors.append({
                        "Error ID": eid,
                        "Category": entry.get("category", ""),
                        "Message": entry.get("message", "")[:120],
                        "Timestamp": entry.get("ts", ""),
                    })
            except _json.JSONDecodeError:
                continue
            if len(errors) >= 50:
                break
        if errors:
            st.dataframe(errors, use_container_width=True, hide_index=True)
        else:
            st.info("No errors in recent log.")
else:
    st.info("No log file found yet. Errors will appear here after operations.")
