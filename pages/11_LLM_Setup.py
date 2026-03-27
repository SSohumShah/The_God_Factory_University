"""
LLM Setup Wizard — Guided setup for all 10 LLM providers.
Step-by-step walkthroughs, credential validation, local model detection,
hardware profiling, and one-click testing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_setting, save_setting
from core.llm_setup import (
    CLOUD_PROVIDERS,
    OLLAMA_CATALOG,
    check_local_service,
    detect_hardware,
    get_current_llm_config,
    ping_local_health,
    test_provider,
)
from ui.theme import inject_theme, gf_header, section_divider, stat_card, play_sfx, sanitize_llm_output, help_button

inject_theme()
gf_header("LLM Setup Wizard", "Configure your AI model provider step by step.")
help_button("llm-setup-wizard")

# ─── Sidebar: Current Config ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### CURRENT LLM CONFIG")
    current_cfg = get_current_llm_config()
    st.markdown(f"**Provider**: {current_cfg['provider']} {current_cfg['status_badge']}")
    st.markdown(f"**Model**: {current_cfg['model']}")
    st.markdown(f"**API Key**: {'Set' if current_cfg['has_api_key'] else 'Not set'}")

# ─── Step 1: Choose Type ─────────────────────────────────────────────────────
section_divider("STEP 1 — Choose Your Path")

st.markdown("""
**LOCAL models** run on your machine. They are free, private, and work offline.
They require sufficient RAM/VRAM.

**CLOUD models** run on remote servers via API. They require an internet connection
and an API key. Some have free tiers.
""")

col_local, col_cloud = st.columns(2)
with col_local:
    st.markdown("### LOCAL (Free)")
    st.markdown("- No API key needed")
    st.markdown("- Works offline")
    st.markdown("- Requires 8GB+ RAM")
    st.markdown("- Moderate speed (depends on hardware)")
    local_btn = st.button("Set Up Local Model", use_container_width=True)
with col_cloud:
    st.markdown("### CLOUD (API Key)")
    st.markdown("- Requires internet")
    st.markdown("- Some free tiers available")
    st.markdown("- Generally faster")
    st.markdown("- Best model quality")
    cloud_btn = st.button("Set Up Cloud Provider", use_container_width=True)

if local_btn:
    st.session_state["wizard_path"] = "local"
if cloud_btn:
    st.session_state["wizard_path"] = "cloud"

wizard_path = st.session_state.get("wizard_path", "")

# ─── Hardware Profile ─────────────────────────────────────────────────────────
if wizard_path:
    section_divider("HARDWARE PROFILE")
    hw = detect_hardware()
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        stat_card("System RAM", f"{hw['ram_gb']} GB", colour="#00d4ff")
    with h2:
        stat_card("GPU VRAM", f"{hw['gpu_vram_gb']} GB", colour="#ffd700" if hw["gpu_vram_gb"] > 0 else "#e04040")
    with h3:
        stat_card("GPU", hw["gpu_name"], colour="#40dc80" if hw["gpu_name"] != "None" else "#606080")
    with h4:
        import shutil
        disk = shutil.disk_usage(str(ROOT))
        free_gb = round(disk.free / (1024 ** 3), 1)
        stat_card("Disk Free", f"{free_gb} GB", colour="#40dc80" if free_gb > 10 else "#e04040")

    st.markdown(
        f"**Recommended model**: `{hw['recommended_model']}` — {hw.get('recommendation_reason', hw.get('recommended_reason', ''))}"
    )

    # VRAM guide
    with st.expander("Model Size Guide (VRAM / RAM Requirements)"):
        st.markdown("""
| Model Size | VRAM Needed | RAM (CPU Mode) | Examples |
|-----------|-------------|----------------|----------|
| 1-3B (Tiny) | 2 GB | 4 GB | phi3:mini, tinyllama |
| 7-8B (Small) | 5 GB | 8 GB | llama3.1:8b, mistral:7b |
| 13B (Medium) | 9 GB | 16 GB | llama2:13b, codellama:13b |
| 30-34B (Large) | 20 GB | 32 GB | codellama:34b |
| 70B (XL) | 40 GB | 64 GB | llama3.1:70b |

Quantized models (Q4, Q5) use roughly 40-60% of full precision memory.
""")

# ─── Local Provider Setup ─────────────────────────────────────────────────────
if wizard_path == "local":
    section_divider("STEP 2 — Choose Local Provider")

    local_choice = st.radio("Select local LLM server:", ["Ollama", "LM Studio"], horizontal=True)

    if local_choice == "Ollama":
        section_divider("OLLAMA SETUP")
        help_button("llm-local-setup")
        st.markdown("""
### Getting Started with Ollama

**What is Ollama?** A lightweight tool that runs large language models locally on your machine.

**Step 1: Install Ollama**
1. Visit [ollama.com](https://ollama.com)
2. Download the installer for your operating system
3. Run the installer — it adds the `ollama` command to your system

**Step 2: Pull a Model**
Open a terminal/command prompt and run:
```
ollama pull llama3.2
```
This downloads the model (a few GB). Popular choices:
- `llama3.2` — 3B parameters, fast, good for most tasks
- `llama3.1:8b` — 8B parameters, better quality, needs 8GB+ RAM
- `codellama` — Optimized for code generation
- `mistral` — Good general-purpose model
- `phi3` — Small and fast from Microsoft

**Step 3: Verify**
The Ollama service starts automatically after installation.
""")

        # Auto-detect Ollama
        st.markdown("---")
        st.markdown("**Auto-Detection:**")
        ollama_running = check_local_service("http://localhost:11434")
        if ollama_running:
            _hp = ping_local_health("http://localhost:11434")
            _ping_txt = f" (ping: {_hp['latency_ms']}ms)" if _hp else ""
            st.success(f"Ollama service detected at localhost:11434{_ping_txt}")
            # Try to list models
            try:
                from llm.providers import list_ollama_models
                models = list_ollama_models()
                if models:
                    st.markdown(f"**Installed models**: {', '.join(models)}")
                    selected_model = st.selectbox("Choose a model:", models)
                else:
                    st.warning("No models installed yet. Use 'Pull a New Model' below to download one.")
                    selected_model = st.text_input("Model name:", "llama3.2")
            except Exception:
                selected_model = st.text_input("Model name:", "llama3.2")

            if st.button("Save & Test Ollama", use_container_width=True):
                save_setting("llm_provider", "ollama")
                save_setting("llm_model", selected_model)
                save_setting("llm_api_key", "ollama")
                save_setting("llm_base_url", "http://localhost:11434/v1")
                result = test_provider("ollama", "ollama", selected_model, "http://localhost:11434/v1")
                if result["ok"]:
                    play_sfx("success")
                    st.success(f"Ollama is working. Response in {result['latency_ms']}ms · ~{result['tokens']} tokens")
                    st.markdown(f"> {sanitize_llm_output(result['response'])}")
                else:
                    st.error(f"Test failed: {result['error']}")
        else:
            st.warning(
                "Ollama not detected. Make sure it is installed and running. "
                "After installing, restart this page."
            )

        # Pull a model directly from the UI
        with st.expander("Pull a New Model"):
            size_cat = st.selectbox("Model size category:", list(OLLAMA_CATALOG.keys()))
            pull_model = st.selectbox("Model to pull:", OLLAMA_CATALOG[size_cat], key="ollama_pull")

            pc1, pc2 = st.columns(2)
            with pc1:
                if st.button("Pull Model via API", use_container_width=True):
                    import requests as _req
                    with st.spinner(f"Pulling {pull_model} — this may take several minutes..."):
                        try:
                            resp = _req.post(
                                "http://localhost:11434/api/pull",
                                json={"name": pull_model},
                                timeout=600,
                                stream=True,
                            )
                            resp.raise_for_status()
                            status_area = st.empty()
                            for line in resp.iter_lines():
                                if line:
                                    import json as _json
                                    data = _json.loads(line)
                                    status_area.text(data.get("status", ""))
                            play_sfx("success")
                            st.success(f"Successfully pulled {pull_model}")
                            st.rerun()
                        except Exception as pull_err:
                            st.error(f"Pull failed: {pull_err}")
            with pc2:
                st.markdown(f"**Or run in terminal:**")
                st.code(f"ollama pull {pull_model}", language="bash")

        # Troubleshooting
        with st.expander("Troubleshooting"):
            st.markdown("""
- **Service not detected**: Make sure Ollama is installed. On Windows, check
  the system tray for the Ollama icon. Try restarting your computer.
- **Model download stuck**: Check your internet connection. Large models
  (10GB+) take time on slow connections.
- **Out of memory**: Try a smaller model like `phi3:mini` or `llama3.2:1b`.
- **Port conflict**: If another app uses port 11434, you can change it in
  Ollama's config. Default: `OLLAMA_HOST=0.0.0.0:11434`.
""")

    elif local_choice == "LM Studio":
        section_divider("LM STUDIO SETUP")
        help_button("llm-local-setup")
        st.markdown("""
### Getting Started with LM Studio

**What is LM Studio?** A desktop app for downloading and running LLMs with a visual interface.

**Step 1: Install LM Studio**
1. Visit [lmstudio.ai](https://lmstudio.ai)
2. Download the Windows installer
3. Run the installer

**Step 2: Download a Model**
1. Open LM Studio
2. Go to the **Discover** tab (magnifying glass icon)
3. Search for a model (e.g., "llama 3.1 8b" or "mistral 7b")
4. Click Download on a GGUF quantization (Q4_K_M is recommended)

**Step 3: Start the Server**
1. Go to the **Local Server** tab (plug icon)
2. Select your downloaded model in the dropdown
3. Click **Start Server**
4. The server runs at `http://localhost:1234`

**RAM Guide:**
- 4 GB RAM: Tiny models only (1-2B)
- 8 GB RAM: 7B models (Q4 quantization)
- 16 GB RAM: 13B models
- 32 GB RAM: 30B+ models
""")

        # Auto-detect
        st.markdown("---")
        st.markdown("**Auto-Detection:**")
        lms_running = check_local_service("http://localhost:1234")
        if lms_running:
            _hp = ping_local_health("http://localhost:1234")
            _ping_txt = f" (ping: {_hp['latency_ms']}ms)" if _hp else ""
            st.success(f"LM Studio server detected at localhost:1234{_ping_txt}")
            model_name = st.text_input("Model name (shown in LM Studio):", "")
            if st.button("Save & Test LM Studio", use_container_width=True):
                save_setting("llm_provider", "lmstudio")
                save_setting("llm_model", model_name or "default")
                save_setting("llm_api_key", "lm-studio")
                save_setting("llm_base_url", "http://localhost:1234/v1")
                result = test_provider("lmstudio", "lm-studio", model_name or "default", "http://localhost:1234/v1")
                if result["ok"]:
                    play_sfx("success")
                    st.success(f"LM Studio is working. Response in {result['latency_ms']}ms · ~{result['tokens']} tokens")
                    st.markdown(f"> {sanitize_llm_output(result['response'])}")
                else:
                    st.error(f"Test failed: {result['error']}")
        else:
            st.warning(
                "LM Studio server not detected. Open LM Studio, load a model, "
                "and click Start Server on the Local Server tab."
            )

        with st.expander("Troubleshooting"):
            st.markdown("""
- **Server not detected**: Make sure LM Studio is open and the server is started.
  Check the Local Server tab for the green "Running" indicator.
- **No model loaded**: You must download and select a model before starting the server.
- **Slow responses**: Try a smaller quantization (Q4 instead of Q8) or a smaller model.
- **Out of memory**: Close other applications. Try models with fewer parameters.
""")

# ─── Cloud Provider Setup ─────────────────────────────────────────────────────
if wizard_path == "cloud":
    section_divider("STEP 2 — Choose Cloud Provider")

    provider_label = st.selectbox("Select a cloud provider:", list(CLOUD_PROVIDERS.keys()))
    prov = CLOUD_PROVIDERS[provider_label]

    section_divider(provider_label.split("(")[0].strip())
    help_button("llm-cloud-setup")

    # Cost and notes
    st.markdown(f"**Cost**: {prov['cost']}")
    st.link_button(
        f"Get {provider_label.split('(')[0].strip()} API Key",
        prov["signup_url"],
        use_container_width=True,
    )
    st.info(prov["notes"])

    # Step-by-step
    st.markdown("### Setup Steps")
    for i, step in enumerate(prov["setup"], 1):
        st.markdown(f"**{i}.** {step}")

    st.markdown("---")

    # Configuration inputs
    st.markdown("### Configure")
    api_key = st.text_input(
        "API Key / Token:",
        value=get_setting("llm_api_key", "") if get_setting("llm_provider", "") == prov["key"] else "",
        type="password",
        help=f"Get from {prov['signup']}" + (f" (starts with {prov['key_prefix']})" if prov["key_prefix"] else ""),
    )

    model = st.selectbox("Model:", prov["models"])
    base_url = st.text_input("Base URL (advanced):", value=prov["url"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save & Test", use_container_width=True):
            if not api_key.strip():
                st.warning("Please enter an API key.")
            else:
                save_setting("llm_provider", prov["key"])
                save_setting("llm_model", model)
                save_setting("llm_api_key", api_key.strip())
                save_setting("llm_base_url", base_url.strip())
                play_sfx("click")
                st.success(f"Saved! Provider: {prov['key']}, Model: {model}")
                with st.spinner("Testing connection..."):
                    result = test_provider(prov["key"], api_key.strip(), model, base_url.strip())
                if result["ok"]:
                    play_sfx("success")
                    st.success(f"Working! Response in {result['latency_ms']}ms · ~{result['tokens']} tokens")
                    st.markdown(f"> {sanitize_llm_output(result['response'])}")
                else:
                    st.error(f"Test failed: {result['error']}")
                    st.markdown("Check your API key and internet connection.")

    with c2:
        if st.button("Test Connection", use_container_width=True):
            if not api_key.strip():
                st.warning("Enter an API key first.")
            else:
                with st.spinner("Testing..."):
                    result = test_provider(prov["key"], api_key.strip(), model, base_url.strip())
                if result["ok"]:
                    play_sfx("success")
                    st.success(f"Working! Response in {result['latency_ms']}ms · ~{result['tokens']} tokens")
                    st.markdown(f"> {sanitize_llm_output(result['response'])}")
                else:
                    st.error(f"Failed: {result['error']}")
                    st.markdown("Check your API key and internet connection.")

# ─── Provider Comparison ──────────────────────────────────────────────────────
section_divider("PROVIDER COMPARISON")

with st.expander("All Providers At a Glance"):
    st.markdown("""
| Provider | Type | Cost | Speed | Quality | Context | Best For |
|----------|------|------|-------|---------|---------|----------|
| **Ollama** | Local | Free | Medium | Varies | Varies | Privacy, offline use |
| **LM Studio** | Local | Free | Medium | Varies | Varies | Visual model management |
| **Groq** | Cloud | Free | Very Fast | High | 32K-128K | Fast free inference |
| **GitHub Models** | Cloud | Free | Fast | High | 128K | GitHub users, free GPT-4o |
| **OpenAI** | Cloud | Paid | Fast | Best | 128K | Best quality, reliable |
| **Anthropic** | Cloud | Paid | Fast | Best | 200K | Long documents, safety |
| **Mistral** | Cloud | Free/Paid | Fast | High | 32K-128K | Multilingual, code |
| **Together AI** | Cloud | Free $5 | Fast | High | Varies | Open model variety |
| **HuggingFace** | Cloud | Free | Slow | Medium | Varies | Experimentation |
| **Cohere** | Cloud | Free trial | Medium | High | 128K | RAG, search tasks |

**Recommendation for new users**: Start with **Groq** (free, fast) or **Ollama** (free, private).
""")
    st.markdown("**Quick Switch** — activate a previously configured provider:")
    _switch_providers = [
        ("ollama", "llama3", "http://localhost:11434/v1"),
        ("groq", None, None),
        ("github", None, None),
        ("openai", None, None),
        ("anthropic", None, None),
    ]
    _sw_cols = st.columns(len(_switch_providers))
    for _sw_col, (_sw_key, _sw_model, _sw_url) in zip(_sw_cols, _switch_providers):
        with _sw_col:
            if st.button(_sw_key.title(), key=f"switch_{_sw_key}", use_container_width=True):
                save_setting("llm_provider", _sw_key)
                if _sw_model:
                    save_setting("llm_model", _sw_model)
                if _sw_url:
                    save_setting("llm_base_url", _sw_url)
                st.rerun()

# ─── Quick Recommendation ─────────────────────────────────────────────────────
section_divider("RECOMMENDATION")
hw_check = detect_hardware()
if hw_check["ram_gb"] >= 16 or hw_check["gpu_vram_gb"] >= 6:
    st.markdown(
        "Your hardware can run local models. **Recommended**: Install Ollama and pull "
        f"`{hw_check['recommended_model']}` for a free, private experience."
    )
else:
    st.markdown(
        "Your hardware is limited for local models. **Recommended**: Use **Groq** (free tier) "
        "or **GitHub Models** (free with GitHub account) for the best experience."
    )
