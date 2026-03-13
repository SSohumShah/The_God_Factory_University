"""
Settings — voice, LLM provider, binaural preset, video quality, deadlines, student name.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_setting, save_setting
from ui.theme import inject_theme, arcane_header, rune_divider, play_sfx, help_button

inject_theme()
arcane_header("Settings", "Calibrate your arcane apparatus.")
help_button("voice-settings")

# ─── Student identity ──────────────────────────────────────────────────────────
rune_divider("Student Identity")
student_name = st.text_input("Student name", value=get_setting("student_name", "Scholar"))
if st.button("Save Name"):
    save_setting("student_name", student_name)
    play_sfx("click")
    st.success("Name saved.")

# ─── Voice ────────────────────────────────────────────────────────────────────
rune_divider("Voice Narration")
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
current_voice_label = next((k for k, v in VOICES.items() if v == current_voice_id), list(VOICES.keys())[0])
selected_voice_label = st.selectbox("TTS Voice (edge-tts — Microsoft Neural)", list(VOICES.keys()), index=list(VOICES.keys()).index(current_voice_label))
selected_voice_id = VOICES[selected_voice_label]

voice_rate = st.slider("Speaking rate", -50, 50, int(get_setting("tts_rate", "0")), step=5, help="+N = faster, -N = slower")
voice_pitch = st.slider("Pitch", -50, 50, int(get_setting("tts_pitch", "0")), step=5)

if st.button("Preview Voice"):
    try:
        import asyncio
        import tempfile
        import os
        import edge_tts
        preview_text = "Greetings, scholar. Your journey through the arcane academy begins now."
        rate_str = f"+{voice_rate}%" if voice_rate >= 0 else f"{voice_rate}%"
        pitch_str = f"+{voice_pitch}Hz" if voice_pitch >= 0 else f"{voice_pitch}Hz"
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
    save_setting("tts_voice", selected_voice_id)
    save_setting("tts_rate", str(voice_rate))
    save_setting("tts_pitch", str(voice_pitch))
    play_sfx("success")
    st.success("Voice settings saved.")

# ─── Binaural beats ───────────────────────────────────────────────────────────
rune_divider("Binaural Beats")
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
current_preset = get_setting("binaural_preset", "None")
if current_preset not in BINAURAL_PRESETS:
    current_preset = "None"
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
    save_setting("binaural_preset", selected_preset)
    play_sfx("click")
    st.success("Binaural preset saved.")

# ─── LLM Provider ─────────────────────────────────────────────────────────────
rune_divider("LLM Provider")
help_button("llm-provider-settings")

PROVIDERS = {
    "ollama":      {"name": "Ollama (FREE, Local)",             "needs_key": False, "needs_url": False},
    "lm_studio":   {"name": "LM Studio (FREE, Local)",          "needs_key": False, "needs_url": True},
    "openai":      {"name": "OpenAI (GPT-4o, Paid)",            "needs_key": True,  "needs_url": False},
    "github":      {"name": "GitHub Models (FREE tier, PAT)",   "needs_key": True,  "needs_url": False},
    "anthropic":   {"name": "Anthropic Claude (Paid)",          "needs_key": True,  "needs_url": False},
    "groq":        {"name": "Groq (FREE tier, Fast)",           "needs_key": True,  "needs_url": False},
    "mistral":     {"name": "Mistral AI (FREE tier)",           "needs_key": True,  "needs_url": False},
    "together":    {"name": "Together AI (FREE tier)",          "needs_key": True,  "needs_url": False},
    "huggingface": {"name": "HuggingFace Inference (FREE)",     "needs_key": True,  "needs_url": False},
}

provider_labels = {v["name"]: k for k, v in PROVIDERS.items()}
current_prov = get_setting("llm_provider", "ollama")
current_prov_label = next((v["name"] for k, v in PROVIDERS.items() if k == current_prov), list(PROVIDERS.values())[0]["name"])
selected_prov_label = st.selectbox("Provider", list(provider_labels.keys()), index=list(provider_labels.keys()).index(current_prov_label))
selected_prov = provider_labels[selected_prov_label]
prov_info = PROVIDERS[selected_prov]

PROVIDER_MODELS = {
    "ollama":      ["llama3.2:3b", "llama3.1:8b", "llama3.3:70b", "mistral", "phi3:mini", "phi3:medium", "gemma2:9b", "qwen2.5:7b"],
    "lm_studio":   ["(auto-detected — load model in LM Studio first)"],
    "openai":      ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "github":      ["gpt-4o", "gpt-4o-mini", "meta-llama-3.1-70b-instruct", "mistral-large-2407", "Phi-3.5-MoE-instruct"],
    "anthropic":   ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    "groq":        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
    "mistral":     ["mistral-large-latest", "mistral-small-latest", "open-mistral-nemo", "codestral-latest"],
    "together":    ["meta-llama/Llama-3.1-70B-Instruct-Turbo", "mistralai/Mistral-7B-Instruct-v0.3", "Qwen/Qwen2.5-7B-Instruct-Turbo"],
    "huggingface": ["HuggingFaceH4/zephyr-7b-beta", "mistralai/Mistral-7B-Instruct-v0.3", "microsoft/Phi-3.5-mini-instruct"],
}

model_options = PROVIDER_MODELS.get(selected_prov, [])
current_model = get_setting("llm_model", model_options[0] if model_options else "")
if current_model in model_options:
    model_idx = model_options.index(current_model)
else:
    model_idx = 0

selected_model = st.selectbox("Model", model_options, index=model_idx) if model_options else st.text_input("Model name", value=current_model)

if prov_info["needs_key"]:
    current_key = get_setting("llm_api_key", "")
    KEY_DOCS = {
        "openai":      "Get key at: platform.openai.com/api-keys",
        "github":      "Get GitHub PAT at: github.com/settings/tokens (Models permission only)",
        "anthropic":   "Get key at: console.anthropic.com",
        "groq":        "Get key at: console.groq.com",
        "mistral":     "Get key at: console.mistral.ai",
        "together":    "Get key at: api.together.xyz",
        "huggingface": "Get token at: huggingface.co/settings/tokens",
    }
    if selected_prov in KEY_DOCS:
        st.markdown(f"<span style='font-family:monospace;color:#606080;font-size:0.78rem;'>{KEY_DOCS[selected_prov]}</span>", unsafe_allow_html=True)
    api_key = st.text_input("API Key", value=current_key, type="password")
else:
    api_key = ""

base_url = ""
if prov_info["needs_url"] or selected_prov == "lm_studio":
    base_url = st.text_input("Base URL", value=get_setting("llm_base_url", "http://localhost:1234/v1"))

# Ollama quick tools
if selected_prov == "ollama":
    st.markdown("<span style='font-family:monospace;color:#a0a0c0;font-size:0.82rem;'>Ollama: make sure Ollama is running before using. Install from ollama.com</span>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Check Ollama Status"):
            try:
                import requests
                r = requests.get("http://localhost:11434/api/tags", timeout=3)
                models_list = [m["name"] for m in r.json().get("models", [])]
                st.success(f"Ollama running. Models: {', '.join(models_list) or 'none pulled yet'}")
            except Exception as e:
                st.error(f"Ollama offline: {e}")
    with c2:
        pull_model = st.text_input("Pull model", placeholder="llama3.2:3b")
        if st.button("Pull Model"):
            if pull_model.strip():
                with st.spinner(f"Pulling {pull_model}..."):
                    try:
                        import requests
                        r = requests.post("http://localhost:11434/api/pull", json={"name": pull_model, "stream": False}, timeout=300)
                        st.success(f"Pulled: {pull_model}")
                    except Exception as e:
                        st.error(f"Pull failed: {e}")

    if st.button("Hardware Check"):
        try:
            from llm.providers import check_hardware
            hw = check_hardware()
            st.json(hw)
        except Exception as e:
            st.error(str(e))

if st.button("Save LLM Settings", use_container_width=True):
    save_setting("llm_provider", selected_prov)
    save_setting("llm_model", selected_model)
    if api_key:
        save_setting("llm_api_key", api_key)
    if base_url:
        save_setting("llm_base_url", base_url)
    play_sfx("success")
    st.success("LLM settings saved.")

# ─── Test LLM ─────────────────────────────────────────────────────────────────
if st.button("Test LLM Connection"):
    try:
        from llm.providers import UniversalLLMClient
        cfg = {
            "provider": selected_prov,
            "model": selected_model,
            "api_key": api_key or get_setting("llm_api_key", ""),
            "base_url": base_url or get_setting("llm_base_url", ""),
        }
        client = UniversalLLMClient(cfg)
        reply = client.chat([{"role": "user", "content": "Reply with exactly: 'Connection verified.' and nothing else."}])
        st.success(f"LLM responded: {reply}")
    except Exception as e:
        st.error(f"Connection failed: {e}")

# ─── Video quality ────────────────────────────────────────────────────────────
rune_divider("Video Generation")
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

render_provider = st.selectbox("Render Engine", ["local", "runway", "pika", "comfyui"], index=["local", "runway", "pika", "comfyui"].index(get_setting("render_provider", "local")))

if render_provider in ("runway", "pika", "comfyui"):
    render_api_key = st.text_input(f"{render_provider.upper()} API Key (if required)", value=get_setting("render_api_key", ""), type="password")
    save_setting("render_api_key", render_api_key)

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
rune_divider("Deadline System")
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
