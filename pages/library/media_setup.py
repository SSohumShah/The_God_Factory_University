"""Media Sources tab — full GUI setup for all free image generation services."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.database import get_setting, save_setting
from ui.theme import section_divider

# All cloud services with their configuration
CLOUD_SERVICES = [
    {
        "name": "Pollinations.ai",
        "provider": "pollinations",
        "key_setting": None,
        "signup_url": None,
        "daily_limit": 50,
        "description": "Completely free — no API key or signup needed",
        "setup_note": "Works out of the box. Nothing to configure.",
    },
    {
        "name": "HuggingFace",
        "provider": "huggingface",
        "key_setting": "hf_api_token",
        "signup_url": "https://huggingface.co/settings/tokens",
        "daily_limit": 30,
        "description": "SDXL image generation via free Inference API",
        "setup_note": "1. Create free account  2. Go to Settings → Tokens  3. Create read token  4. Paste below",
    },
    {
        "name": "Leonardo.ai",
        "provider": "leonardo",
        "key_setting": "leonardo_api_key",
        "signup_url": "https://app.leonardo.ai/api",
        "daily_limit": 30,
        "description": "150 tokens/day — multi-model (SDXL, custom fine-tunes)",
        "setup_note": "1. Create free account at leonardo.ai  2. Go to API settings  3. Generate API key  4. Paste below",
    },
    {
        "name": "GitHub Models",
        "provider": "github_models",
        "key_setting": "github_token",
        "signup_url": "https://github.com/settings/tokens",
        "daily_limit": 15,
        "description": "Image generation via GitHub Models free tier",
        "setup_note": "1. Go to Settings → Developer settings → Personal access tokens  2. Create classic token  3. Paste below",
    },
    {
        "name": "LimeWire AI",
        "provider": "limewire",
        "key_setting": "limewire_api_key",
        "signup_url": "https://limewire.com/studio",
        "daily_limit": 10,
        "description": "10-20 daily credits — clean REST API",
        "setup_note": "1. Create account at limewire.com  2. Go to Studio → API  3. Generate key  4. Paste below",
    },
    {
        "name": "Stability AI",
        "provider": "stability",
        "key_setting": "stability_api_key",
        "signup_url": "https://platform.stability.ai/account/keys",
        "daily_limit": 10,
        "description": "SD3 Turbo — 25 free credits on signup",
        "setup_note": "1. Create account at stability.ai  2. Get API key from dashboard  3. Paste below",
    },
    {
        "name": "Getimg.ai",
        "provider": "getimg",
        "key_setting": "getimg_api_key",
        "signup_url": "https://getimg.ai/dashboard",
        "daily_limit": 3,
        "description": "100 images/month (~3/day) — clean API, SDXL",
        "setup_note": "1. Create free account  2. Go to Dashboard → API  3. Copy key  4. Paste below",
    },
    {
        "name": "DeepAI",
        "provider": "deepai",
        "key_setting": "deepai_api_key",
        "signup_url": "https://deepai.org/dashboard/profile",
        "daily_limit": 5,
        "description": "Text-to-image, 5 free generations per day",
        "setup_note": "1. Create free account  2. Copy API key from profile page  3. Paste below",
    },
    {
        "name": "Prodia",
        "provider": "prodia",
        "key_setting": "prodia_api_key",
        "signup_url": "https://app.prodia.com/api",
        "daily_limit": 20,
        "description": "Pay-as-you-go overflow — $0.002/image, fast SDXL",
        "setup_note": "1. Create account at prodia.com  2. Go to API dashboard  3. Copy key  4. Paste below  (paid per image)",
    },
]


def _test_provider(provider_name: str) -> tuple[bool, str]:
    """Test if a provider is available and ready."""
    try:
        from media.diffusion.free_tier_cycler import _instantiate_provider
        p = _instantiate_provider(provider_name)
        if p and p.is_available():
            return True, "Connected and ready"
        return False, "Not connected — check API key"
    except Exception as e:
        return False, str(e)


def _render_cloud_services() -> None:
    """Render the cloud services configuration section."""
    section_divider("Cloud Services (Free Tier)")
    st.markdown(
        "Configure free image generation services. "
        "The app automatically cycles through available providers to maximize your daily free quota. "
        f"**Combined daily capacity: ~{sum(s['daily_limit'] for s in CLOUD_SERVICES)} images/day.**"
    )

    # Provider status overview
    try:
        from media.diffusion.free_tier_cycler import get_all_providers
        providers = get_all_providers()
        rows = []
        for p in providers:
            if p["name"] == "comfyui":
                continue
            status = "Ready" if p["available"] else "Needs setup"
            remaining = str(p["remaining"]) if p["remaining"] is not None else "Unlimited"
            rows.append({
                "Service": p["name"].replace("_", " ").title(),
                "Status": status,
                "Used Today": str(p["used_today"]),
                "Remaining": remaining,
                "Daily Limit": str(p["daily_limit"]) if p["daily_limit"] else "Unlimited",
            })
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
    except Exception:
        st.caption("Provider status unavailable — run setup below.")

    # Per-service setup
    for svc in CLOUD_SERVICES:
        icon = "✅" if svc["key_setting"] is None else ""
        if svc["key_setting"]:
            current = get_setting(svc["key_setting"], "")
            icon = "✅" if current else "⚙️"

        with st.expander(f"{icon} {svc['name']} — {svc['description']} ({svc['daily_limit']}/day)", expanded=False):
            st.caption(svc["setup_note"])

            if svc["signup_url"]:
                st.markdown(f"[Open {svc['name']} signup / key page]({svc['signup_url']})")

            if svc["key_setting"]:
                current = get_setting(svc["key_setting"], "")
                if current:
                    masked = f"{current[:6]}...{current[-4:]}" if len(current) > 10 else "***set***"
                    st.success(f"Key configured: {masked}")
                else:
                    st.warning("No API key set.")

                new_key = st.text_input(
                    f"API Key", value="", type="password",
                    key=f"media_key_{svc['provider']}",
                    placeholder=f"Paste your {svc['name']} API key",
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"Save Key", key=f"save_{svc['provider']}", use_container_width=True):
                        if new_key.strip():
                            save_setting(svc["key_setting"], new_key.strip())
                            st.success("Key saved!")
                            st.rerun()
                        else:
                            st.warning("Enter a key first.")
                with c2:
                    if st.button(f"Test Connection", key=f"test_{svc['provider']}", use_container_width=True):
                        ok, msg = _test_provider(svc["provider"])
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
            else:
                st.success("No setup needed — works automatically!")
                if st.button("Test Connection", key=f"test_{svc['provider']}", use_container_width=True):
                    ok, msg = _test_provider(svc["provider"])
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


def _render_comfyui_setup() -> None:
    """Render the ComfyUI local setup section."""
    section_divider("Local AI (ComfyUI)")
    st.markdown(
        "Run Stable Diffusion locally for **unlimited** image generation. "
        "Requires a GPU with 4+ GB VRAM. Everything is managed through this interface."
    )

    try:
        from media.diffusion.comfyui_manager import (
            get_status, get_catalog_status, install_comfyui,
            download_model, launch_server, stop_server,
        )
    except ImportError:
        st.error("ComfyUI manager module not found.")
        return

    status = get_status()

    # Health indicator
    health_map = {
        "ready": ("✅ ComfyUI is installed, has models, and server is running.", "success"),
        "stopped": ("⚠️ ComfyUI is installed with models but server is not running.", "warning"),
        "no_models": ("⚠️ ComfyUI is installed but no models downloaded yet.", "warning"),
        "not_installed": ("ComfyUI is not installed. Click below to set it up.", "info"),
    }
    msg, level = health_map.get(status["health"], ("Unknown status", "info"))
    getattr(st, level)(msg)

    # Step 1: Install ComfyUI
    st.markdown("#### Step 1: Install ComfyUI")
    if status["installed"]:
        st.success(f"Installed at: {status['comfyui_path']}")
    else:
        st.caption("Downloads ComfyUI from GitHub and installs Python dependencies.")
        if st.button("Install ComfyUI", use_container_width=True, type="primary"):
            progress = st.empty()
            def _cb(msg):
                progress.caption(msg)
            with st.spinner("Installing ComfyUI..."):
                ok, result_msg = install_comfyui(progress_callback=_cb)
            if ok:
                st.success(result_msg)
                st.rerun()
            else:
                st.error(result_msg)

    # Step 2: Download models
    st.markdown("#### Step 2: Download a Model")
    if not status["installed"]:
        st.caption("Install ComfyUI first.")
    else:
        catalog = get_catalog_status()
        for model in catalog:
            col1, col2 = st.columns([3, 1])
            with col1:
                icon = "✅" if model["installed"] else "📥"
                st.markdown(
                    f"{icon} **{model['name']}** — {model['description']}"
                )
            with col2:
                if model["installed"]:
                    st.caption("Installed")
                else:
                    if st.button(f"Download", key=f"dl_{model['filename']}", use_container_width=True):
                        progress = st.empty()
                        def _dl_cb(msg, _p=progress):
                            _p.caption(msg)
                        with st.spinner(f"Downloading {model['name']}..."):
                            ok, msg = download_model(model, progress_callback=_dl_cb)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # Show installed models
        if status["models"]:
            st.caption(f"Installed models: {', '.join(m['name'] for m in status['models'])}")

    # Step 3: Launch server
    st.markdown("#### Step 3: Start Server")
    if not status["installed"]:
        st.caption("Install ComfyUI first.")
    elif status["running"]:
        st.success(f"Server running at {status['url']}")
        if st.button("Stop Server", use_container_width=True):
            ok, msg = stop_server()
            st.info(msg)
    else:
        st.caption("Start the ComfyUI server to enable local image generation.")
        if st.button("Start ComfyUI Server", use_container_width=True, type="primary"):
            with st.spinner("Starting server (may take up to 30s)..."):
                ok, msg = launch_server()
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def _render_strategy_info() -> None:
    """Render the cycling strategy explanation."""
    section_divider("How It Works")
    st.markdown(
        "**Automatic provider cycling** ensures maximum free usage:\n\n"
        "1. **Pollinations** is tried first (free, no key needed)\n"
        "2. **Cloud APIs** are used next by priority (saves your GPU)\n"
        "3. When all cloud quotas hit their daily limit, **ComfyUI** takes over (unlimited)\n"
        "4. If nothing is available, the built-in **PIL renderer** is used (gradient backgrounds)\n\n"
        "Daily counters reset at midnight. Provider priority and limits can be edited in "
        "`data/media_providers.json`.\n\n"
        "---\n\n"
        "**Shared Asset Library:** Generated images are automatically cataloged. "
        "When another student studies the same course, matching images are reused "
        "instead of burning quota. Control sharing in the Asset Library tab.\n\n"
        "---\n\n"
        "**Voice cycling** works the same way for TTS:\n\n"
        "1. **Local engines** first (Kokoro \u2192 Piper \u2192 Coqui) \u2014 unlimited, no internet\n"
        "2. **Cloud free tier** (ElevenLabs \u2192 Edge-TTS) \u2014 high quality, limited\n"
        "3. **Offline fallback** (pyttsx3) \u2014 always works, lowest quality\n\n"
        "All engines are installed automatically via the **Voice Engines** tab\u2014\n"
        "no manual pip commands needed.\n"
    )


# ─── TTS engine info for install buttons ───────────────────────────────────
_TTS_ENGINE_INFO = [
    {"name": "kokoro", "label": "Kokoro", "desc": "Best quality local TTS, fast inference",
     "type": "local", "note": "~300 MB download (model auto-fetched on first use)"},
    {"name": "piper", "label": "Piper", "desc": "Mozilla, many languages & voices",
     "type": "local", "note": "~50 MB download. Place .onnx models in data/piper_models/"},
    {"name": "coqui", "label": "Coqui TTS", "desc": "Most model variety, local inference",
     "type": "local", "note": "Large download (~1 GB+). Requires decent hardware."},
    {"name": "elevenlabs", "label": "ElevenLabs", "desc": "Cloud, 10k chars/month free",
     "type": "cloud", "note": "Requires free API key (link below)",
     "api_url": "https://elevenlabs.io/app/settings/api-keys",
     "key_setting": "elevenlabs_api_key"},
    {"name": "edge_tts", "label": "Edge TTS", "desc": "Microsoft cloud, unlimited, no key needed",
     "type": "cloud", "note": "Lightweight install, works immediately"},
    {"name": "pyttsx3", "label": "pyttsx3", "desc": "Offline fallback, lowest quality",
     "type": "offline", "note": "Tiny install, always works, robotic voice"},
]


def _render_tts_engines() -> None:
    """Render TTS engine configuration with one-click install buttons."""
    section_divider("Voice Engines (TTS)")
    st.markdown(
        "Multiple TTS engines are cycled automatically. "
        "Click **Install** to set up any engine — no terminal commands needed."
    )

    # Status table
    try:
        from media.tts_providers import get_all_engine_status
        statuses = get_all_engine_status()
        _status_map = {s["name"]: s for s in statuses}
    except Exception:
        _status_map = {}

    # Preferred engine selection
    current_pref = get_setting("tts_engine", "")
    engine_opts = ["Auto (best available)", "kokoro", "piper", "coqui",
                   "elevenlabs", "edge_tts", "pyttsx3"]
    idx = 0
    if current_pref in engine_opts:
        idx = engine_opts.index(current_pref)
    choice = st.selectbox("Preferred TTS engine", engine_opts, index=idx)
    if choice != current_pref:
        save_setting("tts_engine", "" if choice.startswith("Auto") else choice)

    st.markdown("---")
    # Per-engine cards
    for info in _TTS_ENGINE_INFO:
        s = _status_map.get(info["name"], {})
        installed = s.get("available", False)
        icon = "\u2705" if installed else "\u2b07\ufe0f"
        with st.expander(f"{icon} **{info['label']}** \u2014 {info['desc']}", expanded=False):
            st.caption(info["note"])
            if installed:
                st.success("Installed and ready")
                rem = s.get("remaining_chars")
                if rem is not None:
                    st.caption(f"Remaining today: {rem:,} chars")
            else:
                if st.button(f"Install {info['label']}", key=f"install_tts_{info['name']}",
                             use_container_width=True, type="primary"):
                    from media.tts_providers import auto_install
                    with st.spinner(f"Installing {info['label']}... this may take a minute"):
                        ok, msg = auto_install(info["name"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"Install failed: {msg}")

            # API key input for cloud services that need one
            if info.get("key_setting"):
                st.markdown("---")
                if info.get("api_url"):
                    st.markdown(f"[\u2197 Get your API key here]({info['api_url']})")
                cur_key = get_setting(info["key_setting"], "")
                if cur_key:
                    masked = f"{cur_key[:6]}...{cur_key[-4:]}" if len(cur_key) > 10 else "***set***"
                    st.success(f"Key configured: {masked}")
                new_key = st.text_input(
                    f"{info['label']} API Key", type="password",
                    key=f"tts_key_{info['name']}",
                    placeholder=f"Paste your {info['label']} API key",
                )
                if new_key and st.button(f"Save Key", key=f"save_tts_key_{info['name']}",
                                         use_container_width=True):
                    save_setting(info["key_setting"], new_key.strip())
                    st.success("Saved!")
                    st.rerun()


def _render_asset_library() -> None:
    """Render shared asset library management."""
    section_divider("Shared Asset Library")
    st.markdown(
        "Generated images are cataloged here. Shared assets can be reused by "
        "other students studying the same courses — saving everyone's daily quota."
    )
    try:
        from core.asset_library import get_library_stats
        stats = get_library_stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", stats["total_assets"])
        c2.metric("Shared", stats["shared_assets"])
        c3.metric("Times Reused", stats["total_reuses"])
    except Exception:
        st.info("Asset library will populate as you generate images.")

    # Sharing preference
    share_pref = get_setting("share_generated_media", "course_shared")
    options = ["private", "course_shared", "global"]
    labels = {
        "private": "Private — only I can reuse my images",
        "course_shared": "Course Shared — students in the same course can reuse",
        "global": "Global — any student can reuse my images",
    }
    current_idx = options.index(share_pref) if share_pref in options else 1
    choice = st.radio("Default sharing for new images",
                      [labels[o] for o in options], index=current_idx)
    selected = options[[labels[o] for o in options].index(choice)]
    if selected != share_pref:
        save_setting("share_generated_media", selected)

    # Paid tier toggle for providers
    st.markdown("---")
    st.markdown("**Paid Tier Overrides**")
    st.caption(
        "If you have a paid subscription to any provider, enable bypass below "
        "so the app uses your full paid quota instead of the free-tier limit."
    )
    for svc in CLOUD_SERVICES:
        if svc["key_setting"]:
            key = get_setting(svc["key_setting"], "")
            if key:
                paid_key = f"{svc['provider']}_paid_tier"
                is_paid = bool(get_setting(paid_key, ""))
                if st.checkbox(f"{svc['name']} — I have a paid plan",
                               value=is_paid, key=f"paid_{svc['provider']}"):
                    if not is_paid:
                        save_setting(paid_key, "1")
                else:
                    if is_paid:
                        save_setting(paid_key, "")


def render_media_sources_tab() -> None:
    """Render the Media Sources tab in the Library."""
    section_divider("Media Sources")
    st.markdown(
        "Set up image generation, voice engines, and shared assets. "
        "Everything cycles automatically to maximize free quota."
    )

    tab_cloud, tab_local, tab_voice, tab_assets, tab_info = st.tabs([
        "☁️ Cloud Services", "🖥️ Local AI (ComfyUI)",
        "🎙️ Voice Engines", "📦 Asset Library", "ℹ️ How It Works",
    ])

    with tab_cloud:
        _render_cloud_services()
    with tab_local:
        _render_comfyui_setup()
    with tab_voice:
        _render_tts_engines()
    with tab_assets:
        _render_asset_library()
    with tab_info:
        _render_strategy_info()
