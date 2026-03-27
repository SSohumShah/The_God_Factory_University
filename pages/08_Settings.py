"""
Settings — voice, binaural preset, video quality, deadlines, student name.
LLM configuration lives in pages/11_LLM_Setup.py (single source of truth).
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_setting, save_setting
from core.tts_config import (
    format_pitch,
    format_rate,
    get_tts_settings,
    save_binaural_setting,
    save_tts_settings,
)
from ui.theme import inject_theme, gf_header, section_divider, play_sfx, help_button

inject_theme()
gf_header("Settings", "Calibrate your knowledge apparatus.")
help_button("voice-settings")

# ─── Student identity ──────────────────────────────────────────────────────────
section_divider("Student Identity")
student_name = st.text_input("Student name", value=get_setting("student_name", "Scholar"))
if st.button("Save Name"):
    save_setting("student_name", student_name)
    play_sfx("click")
    st.success("Name saved.")

# ─── Voice ────────────────────────────────────────────────────────────────────
section_divider("Voice Narration")
help_button("voice-settings")

VOICES = {
    "Aria (US, Female, Natural)":          "en-US-AriaNeural",
    "Jenny (US, Female, Conversational)":  "en-US-JennyNeural",
    "Amber (US, Female, Warm)":            "en-US-AmberNeural",
    "Emma (US, Female, Professional)":     "en-US-EmmaNeural",
    "Guy (US, Male, Warm)":                "en-US-GuyNeural",
    "Brian (US, Male, Deep)":              "en-US-BrianNeural",
    "Davis (US, Male, Casual)":            "en-US-DavisNeural",
    "Andrew (US, Male, Friendly)":         "en-US-AndrewNeural",
    "Sonia (UK, Female, Crisp)":           "en-GB-SoniaNeural",
    "Ryan (UK, Male, Professional)":       "en-GB-RyanNeural",
    "Natasha (AU, Female, Warm)":          "en-AU-NatashaNeural",
    "William (AU, Male, Steady)":          "en-AU-WilliamNeural",
    "Clara (CA, Female, Friendly)":        "en-CA-ClaraNeural",
}

current_voice_id = get_setting("tts_voice", "en-US-AriaNeural")
tts_settings = get_tts_settings()
current_voice_id = tts_settings["voice_id"]
current_voice_label = next((k for k, v in VOICES.items() if v == current_voice_id), list(VOICES.keys())[0])
selected_voice_label = st.selectbox("TTS Voice (edge-tts — Microsoft Neural)", list(VOICES.keys()), index=list(VOICES.keys()).index(current_voice_label))
selected_voice_id = VOICES[selected_voice_label]

voice_rate = st.slider("Speaking rate", -50, 50, int(tts_settings["rate"]), step=5, help="+N = faster, -N = slower")
voice_pitch = st.slider("Pitch", -50, 50, int(tts_settings["pitch"]), step=5)

if st.button("Preview Voice"):
    try:
        import asyncio
        import tempfile
        import os
        import edge_tts
        preview_text = "Greetings, scholar. Your journey through the God Factory begins now."
        rate_str = format_rate(voice_rate)
        pitch_str = format_pitch(voice_pitch)
        comm = edge_tts.Communicate(preview_text, selected_voice_id, rate=rate_str, pitch=pitch_str)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        asyncio.run(comm.save(tmp.name))
        with open(tmp.name, "rb") as f:
            st.audio(f.read(), format="audio/mp3")
        os.unlink(tmp.name)
        play_sfx("click")
    except Exception as e:
        st.error(f"Voice preview failed: {e}")

if st.button("Save Voice Settings"):
    save_tts_settings(selected_voice_id, voice_rate, voice_pitch)
    play_sfx("success")
    st.success("Voice settings saved.")

# ─── Binaural beats ───────────────────────────────────────────────────────────
section_divider("Binaural Beats")
help_button("binaural-beats")
st.markdown(
    "<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
    "Binaural beats are stereo audio tones with different frequencies in each ear. "
    "The brain perceives a 'beat' at the difference frequency, which can modulate "
    "cognitive states. Research indicates 40Hz gamma may enhance focus; alpha (8-12Hz) "
    "supports relaxed absorption; theta enables creative states.</span>",
    unsafe_allow_html=True,
)

BINAURAL_PRESETS = {
    "None":                     None,
    "Gamma 40Hz — Peak Focus":  ("gamma_40hz",  200, 40),
    "Beta 18Hz — Active Study": ("beta_18hz",   200, 18),
    "Alpha 10Hz — Relaxed":     ("alpha_10hz",  200, 10),
    "Theta 6Hz — Creative":     ("theta_6hz",   200,  6),
}
current_binaural = str(tts_settings["binaural"])
current_preset = next((label for label, value in BINAURAL_PRESETS.items() if value and value[0] == current_binaural), "None")
selected_preset = st.radio("Preset", list(BINAURAL_PRESETS.keys()), index=list(BINAURAL_PRESETS.keys()).index(current_preset))

if st.button("Preview Binaural (10 seconds)"):
    preset_data = BINAURAL_PRESETS[selected_preset]
    if preset_data is None:
        st.info("No binaural beats selected.")
    else:
        try:
            from media.audio_engine import generate_binaural_wav
            wav_bytes = generate_binaural_wav(10, base_freq=preset_data[1], beat_freq=preset_data[2])
            st.audio(wav_bytes, format="audio/wav")
        except Exception as e:
            st.error(f"Preview failed: {e}")

if st.button("Save Binaural Setting"):
    preset_value = BINAURAL_PRESETS[selected_preset]
    save_binaural_setting(preset_value[0] if preset_value else "none")
    play_sfx("click")
    st.success("Binaural preset saved.")

# ─── LLM Provider ─────────────────────────────────────────────────────────────
section_divider("LLM Provider")
cur_llm = get_setting("llm_provider", "ollama")
cur_model = get_setting("llm_model", "")
st.markdown(f"**Current:** `{cur_llm}` / `{cur_model or 'not set'}`")
st.page_link("pages/11_LLM_Setup.py", label="Open LLM Setup Wizard")

# ─── Video quality ────────────────────────────────────────────────────────────
section_divider("Video Generation")
help_button("video-settings")

QUALITY_PROFILES = {
    "Draft (Fast)": {"fps": 10, "res": "960x540"},
    "Balanced": {"fps": 15, "res": "960x540"},
    "High Quality": {"fps": 24, "res": "1280x720"},
    "Final (Slow)": {"fps": 24, "res": "1920x1080"},
    "Custom": None,
}
current_profile = get_setting("video_profile", "Balanced")
profile = st.selectbox("Quality Profile", list(QUALITY_PROFILES.keys()),
                        index=list(QUALITY_PROFILES.keys()).index(current_profile)
                        if current_profile in QUALITY_PROFILES else 1)

if profile != "Custom" and QUALITY_PROFILES[profile]:
    p = QUALITY_PROFILES[profile]
    fps = p["fps"]
    resolution = p["res"]
    st.markdown(f"<span style='color:#a0a0c0;font-family:monospace;font-size:0.82rem;'>"
                f"Profile: {fps}fps @ {resolution}</span>", unsafe_allow_html=True)
else:
    fps = st.select_slider("FPS", options=[10, 15, 24, 30], value=int(get_setting("video_fps", "15")))
    resolution = st.selectbox("Resolution", ["960x540", "1280x720", "1920x1080"],
                              index=["960x540", "1280x720", "1920x1080"].index(
                                  get_setting("video_resolution", "960x540")))

render_provider = st.selectbox(
    "Render Engine",
    ["local", "comfyui", "free_cloud_mix", "custom_api"],
    index=["local", "comfyui", "free_cloud_mix", "custom_api"].index(
        get_setting("render_provider", "local")
        if get_setting("render_provider", "local") in ("local", "comfyui", "free_cloud_mix", "custom_api")
        else "local"
    ),
    format_func=lambda x: {
        "local": "Local (Built-in PIL Renderer)",
        "comfyui": "ComfyUI (Local Diffusion)",
        "free_cloud_mix": "Free Cloud Mix (Auto-cycle free tiers)",
        "custom_api": "Custom API",
    }.get(x, x),
)

if render_provider == "custom_api":
    render_api_key = st.text_input("Custom API Key", value=get_setting("render_api_key", ""), type="password")
    save_setting("render_api_key", render_api_key)
elif render_provider == "comfyui":
    st.caption("ComfyUI must be installed locally. See Library → Media Sources for setup.")
elif render_provider == "free_cloud_mix":
    st.caption("Uses HuggingFace, GitHub Models, and other free services. Configure keys in Library → Media Sources.")

if st.button("Save Video Settings"):
    save_setting("video_profile", profile)
    save_setting("video_fps", str(fps))
    w, h = resolution.split("x")
    save_setting("video_width", w)
    save_setting("video_height", h)
    save_setting("video_resolution", resolution)
    save_setting("render_provider", render_provider)
    play_sfx("click")
    st.success("Video settings saved.")

# ─── Deadlines ────────────────────────────────────────────────────────────────
section_divider("Deadline System")
help_button("deadline-system")
deadlines_on_val = get_setting("deadlines_enabled", "0") == "1"
deadlines_toggle = st.toggle("Enable Deadlines", value=deadlines_on_val)
if deadlines_toggle != deadlines_on_val:
    save_setting("deadlines_enabled", "1" if deadlines_toggle else "0")
    play_sfx("click")
    st.rerun()

if deadlines_toggle:
    st.markdown("<span style='color:#e04040;font-family:monospace;font-size:0.82rem;'>Deadline mode is ACTIVE. Assignments will show due dates and countdown timers.</span>", unsafe_allow_html=True)
else:
    st.markdown("<span style='color:#606080;font-family:monospace;font-size:0.82rem;'>Deadline mode is OFF. Take your time.</span>", unsafe_allow_html=True)

# ─── Weekly Quests ────────────────────────────────────────────────────────────
section_divider("Weekly Quests")
quests_on_val = get_setting("quests_enabled", "1") == "1"
quests_toggle = st.toggle("Enable Weekly Quests", value=quests_on_val)
if quests_toggle != quests_on_val:
    save_setting("quests_enabled", "1" if quests_toggle else "0")
    play_sfx("click")
    st.rerun()
