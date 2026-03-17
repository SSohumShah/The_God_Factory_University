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
from ui.theme import inject_theme, gf_header, section_divider, stat_card, play_sfx, sanitize_llm_output, help_button

inject_theme()
gf_header("LLM Setup Wizard", "Configure your AI model provider step by step.")
help_button("llm-setup-wizard")

# ─── Hardware Detection ───────────────────────────────────────────────────────
def _detect_hardware() -> dict:
    from llm.providers import check_hardware
    return check_hardware()

def _test_provider(provider: str, api_key: str, model: str, base_url: str) -> dict:
    """Send a test prompt to the provider and return result dict."""
    import time
    from llm.providers import LLMConfig, chat, estimate_tokens
    cfg = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key or "none",
        base_url=base_url,
        temperature=0.1,
        max_tokens=50,
    )
    start = time.time()
    try:
        result = chat(cfg, [{"role": "user", "content": "Respond with exactly: Hello from The God Factory University"}])
        elapsed = round((time.time() - start) * 1000)
        text = str(result)[:200]
        tokens = estimate_tokens(text)
        # Store status badge for this provider
        save_setting(f"provider_status_{provider}", "green" if elapsed < 3000 else "yellow")
        return {"ok": True, "response": text, "latency_ms": elapsed, "tokens": tokens}
    except Exception as e:
        save_setting(f"provider_status_{provider}", "red")
        return {"ok": False, "error": str(e), "latency_ms": 0, "tokens": 0}

def _check_local_service(url: str) -> bool:
    """Check if a local service is accessible."""
    import requests
    try:
        resp = requests.get(url.rstrip("/").replace("/v1", "") + "/", timeout=3)
        return resp.status_code < 500
    except Exception:
        return False

def _ping_local_health(url: str) -> dict | None:
    """Ping a local LLM endpoint and return latency, or None if unreachable."""
    import time, requests
    try:
        start = time.time()
        resp = requests.get(url.rstrip("/").replace("/v1", "") + "/", timeout=3)
        ms = round((time.time() - start) * 1000)
        if resp.status_code < 500:
            return {"status": "online", "latency_ms": ms}
    except Exception:
        pass
    return None

# ─── Sidebar: Current Config ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### CURRENT LLM CONFIG")
    _cur_provider = get_setting('llm_provider', 'ollama')
    _badge_color = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}.get(
        get_setting(f"provider_status_{_cur_provider}", ""), "\u26aa")
    st.markdown(f"**Provider**: {_cur_provider} {_badge_color}")
    st.markdown(f"**Model**: {get_setting('llm_model', 'llama3')}")
    has_key = bool(get_setting("llm_api_key", ""))
    st.markdown(f"**API Key**: {'Set' if has_key else 'Not set'}")

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
    hw = _detect_hardware()
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
        ollama_running = _check_local_service("http://localhost:11434")
        if ollama_running:
            _hp = _ping_local_health("http://localhost:11434")
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
                result = _test_provider("ollama", "ollama", selected_model, "http://localhost:11434/v1")
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
            OLLAMA_CATALOG = {
                "Tiny (1-3B) — 4 GB RAM": [
                    "llama3.2:1b", "qwen3:0.6b", "qwen3:1.7b", "qwen2.5:0.5b",
                    "qwen2.5:1.5b", "qwen2.5-coder:0.5b", "qwen2.5-coder:1.5b",
                    "gemma3:1b", "deepseek-r1:1.5b", "phi3:mini", "tinyllama",
                    "smollm2:135m", "smollm2:360m", "smollm2:1.7b",
                ],
                "Small (7-8B) — 8 GB RAM": [
                    "llama3.2", "llama3.1:8b", "llama3:8b", "qwen3:8b",
                    "qwen2.5:7b", "qwen2.5-coder:7b", "mistral:7b",
                    "gemma3:4b", "gemma2:9b", "deepseek-r1:7b", "deepseek-r1:8b",
                    "phi4:14b", "codellama:7b", "starcoder2:7b",
                    "dolphin-mistral", "neural-chat", "starling-lm",
                    "nous-hermes2", "orca-mini", "stable-code",
                    "nomic-embed-text", "mxbai-embed-large",
                ],
                "Medium (13-14B) — 16 GB RAM": [
                    "qwen3:14b", "qwen2.5:14b", "qwen2.5-coder:14b",
                    "gemma3:12b", "deepseek-r1:14b", "codellama:13b",
                    "llava:13b", "wizard-math:13b", "vicuna:13b",
                    "starcoder2:15b",
                ],
                "Large (27-34B) — 32 GB RAM": [
                    "qwen3:30b", "qwen3:32b", "qwen2.5:32b",
                    "qwen2.5-coder:32b", "gemma3:27b", "gemma2:27b",
                    "deepseek-r1:32b", "codellama:34b",
                    "command-r:35b", "llava:34b", "yi:34b",
                ],
                "XL (70B+) — 64 GB RAM": [
                    "llama3.1:70b", "llama3:70b", "qwen3:235b",
                    "qwen2.5:72b", "deepseek-r1:70b", "deepseek-r1:671b",
                    "codellama:70b", "command-r-plus",
                ],
            }
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
        lms_running = _check_local_service("http://localhost:1234")
        if lms_running:
            _hp = _ping_local_health("http://localhost:1234")
            _ping_txt = f" (ping: {_hp['latency_ms']}ms)" if _hp else ""
            st.success(f"LM Studio server detected at localhost:1234{_ping_txt}")
            model_name = st.text_input("Model name (shown in LM Studio):", "")
            if st.button("Save & Test LM Studio", use_container_width=True):
                save_setting("llm_provider", "lmstudio")
                save_setting("llm_model", model_name or "default")
                save_setting("llm_api_key", "lm-studio")
                save_setting("llm_base_url", "http://localhost:1234/v1")
                result = _test_provider("lmstudio", "lm-studio", model_name or "default", "http://localhost:1234/v1")
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

    CLOUD_PROVIDERS = {
        "Groq (Free Tier, Very Fast)": {
            "key": "groq",
            "url": "https://api.groq.com/openai/v1",
            "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
            "signup": "console.groq.com",
            "signup_url": "https://console.groq.com/keys",
            "key_prefix": "gsk_",
            "cost": "FREE tier — generous rate limits, no payment required",
            "setup": [
                "Go to console.groq.com and create an account (Google or GitHub login works)",
                "Navigate to API Keys in the left sidebar",
                "Click 'Create API Key' and copy the key",
                "Paste the key below",
            ],
            "notes": "Groq uses custom LPU hardware for extremely fast inference (~500 tokens/sec). "
                     "Free tier includes ~500K tokens/day. Best choice for getting started with zero cost.",
        },
        "GitHub Models (Free with GitHub Account)": {
            "key": "github",
            "url": "https://models.inference.ai.azure.com",
            "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "o3-mini", "Meta-Llama-3.1-405B-Instruct", "Meta-Llama-3.1-70B-Instruct", "Mistral-large-2411", "Phi-4", "DeepSeek-R1"],
            "signup": "github.com/settings/tokens",
            "signup_url": "https://github.com/settings/tokens",
            "key_prefix": "ghp_",
            "cost": "FREE during preview — uses your GitHub Personal Access Token",
            "setup": [
                "Log into GitHub",
                "Go to Settings > Developer settings > Personal access tokens > Tokens (classic)",
                "Click 'Generate new token (classic)'",
                "No special scopes needed — just give it a name and generate",
                "Copy the token (starts with ghp_) and paste below",
            ],
            "notes": "GitHub Models gives free access to GPT-4o, Llama, Mistral, and more. "
                     "Rate limits apply per model. Great if you already have a GitHub account.",
        },
        "OpenAI (GPT-4o, Best Quality)": {
            "key": "openai",
            "url": "https://api.openai.com/v1",
            "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini", "o3-mini"],
            "signup": "platform.openai.com",
            "signup_url": "https://platform.openai.com/api-keys",
            "key_prefix": "sk-",
            "cost": "PAID — gpt-4o: ~$2.50 input / $10 output per 1M tokens; gpt-4o-mini: ~$0.15 / $0.60",
            "setup": [
                "Go to platform.openai.com and create an account",
                "Navigate to API Keys section",
                "Click 'Create new secret key' and copy it",
                "IMPORTANT: Add a payment method under Billing (required before API works)",
                "Paste the API key below",
            ],
            "notes": "OpenAI provides the highest quality models. gpt-4o-mini is an excellent "
                     "balance of quality and cost for academic use. Tier 1 rate limits: 500 RPM, 30K TPM.",
        },
        "Anthropic Claude (200K Context)": {
            "key": "anthropic",
            "url": "https://api.anthropic.com",
            "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
            "signup": "console.anthropic.com",
            "signup_url": "https://console.anthropic.com/settings/keys",
            "key_prefix": "sk-ant-",
            "cost": "PAID — Sonnet: ~$3/$15 per 1M tokens; Haiku: ~$0.25/$1.25",
            "setup": [
                "Go to console.anthropic.com and create an account",
                "Navigate to API Keys",
                "Click 'Create Key' and copy it",
                "Add billing (prepaid credits or credit card)",
                "Paste the API key below",
            ],
            "notes": "Claude models have a 200K token context window — excellent for processing "
                     "long documents and complex conversations. Uses its own SDK (handled internally).",
        },
        "Mistral AI (Free Experiment Tier)": {
            "key": "mistral",
            "url": "https://api.mistral.ai/v1",
            "models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
            "signup": "console.mistral.ai",
            "signup_url": "https://console.mistral.ai/api-keys",
            "key_prefix": "",
            "cost": "FREE experiment tier; Scale tier: Small ~$0.1/$0.3, Large ~$2/$6 per 1M tokens",
            "setup": [
                "Go to console.mistral.ai and create an account",
                "Select the Experiment plan (free) or Scale plan (pay-as-you-go)",
                "Navigate to API Keys and create a new key",
                "Copy the key and paste below",
            ],
            "notes": "Mistral models are strong at reasoning and multilingual tasks. "
                     "Codestral is specialized for code generation. 32K-128K context windows.",
        },
        "Together AI (Free $5 Credit)": {
            "key": "together",
            "url": "https://api.together.xyz/v1",
            "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "meta-llama/Llama-3.1-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo", "deepseek-ai/DeepSeek-R1"],
            "signup": "api.together.xyz",
            "signup_url": "https://api.together.xyz/settings/api-keys",
            "key_prefix": "",
            "cost": "FREE $5 credit on signup; then pay-as-you-go (Llama 8B: ~$0.18/1M tokens)",
            "setup": [
                "Go to api.together.xyz and create an account",
                "Your API key is visible on the dashboard after signup",
                "Copy the key and paste below",
            ],
            "notes": "Together AI runs open-source models on fast GPU clusters. "
                     "Great for testing many different open models. $5 free credit goes a long way.",
        },
        "HuggingFace Inference (Free Tier)": {
            "key": "huggingface",
            "url": "https://api-inference.huggingface.co/v1",
            "models": ["meta-llama/Llama-3.3-70B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
            "signup": "huggingface.co/settings/tokens",
            "signup_url": "https://huggingface.co/settings/tokens",
            "key_prefix": "hf_",
            "cost": "FREE tier for Inference API (rate-limited); Pro for dedicated endpoints",
            "setup": [
                "Go to huggingface.co and create an account",
                "Navigate to Settings > Access Tokens",
                "Create a new token with read permissions",
                "Copy the token (starts with hf_) and paste below",
            ],
            "notes": "HuggingFace hosts thousands of models. The free Inference API has cold-start "
                     "delays (30-60s on first request). Best for experimentation.",
        },
    }

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
                    result = _test_provider(prov["key"], api_key.strip(), model, base_url.strip())
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
                    result = _test_provider(prov["key"], api_key.strip(), model, base_url.strip())
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
hw_check = _detect_hardware()
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
