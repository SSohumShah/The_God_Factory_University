"""Backend helpers and provider catalogs for the LLM setup wizard."""
from __future__ import annotations

import time

from core.database import get_setting, save_setting
from llm.providers import LLMConfig, chat, check_hardware, estimate_tokens


def detect_hardware() -> dict:
    """Collect host hardware recommendations for model setup."""
    return check_hardware()


def get_current_llm_config() -> dict:
    """Return current provider/model/key-presence and status badge."""
    provider = get_setting("llm_provider", "ollama")
    status = get_setting(f"provider_status_{provider}", "")
    emoji = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}.get(status, "\u26aa")
    return {
        "provider": provider,
        "model": get_setting("llm_model", "llama3"),
        "has_api_key": bool(get_setting("llm_api_key", "")),
        "status_badge": emoji,
    }


def test_provider(provider: str, api_key: str, model: str, base_url: str) -> dict:
    """Send a low-cost test prompt and persist provider health status."""
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
        save_setting(f"provider_status_{provider}", "green" if elapsed < 3000 else "yellow")
        return {"ok": True, "response": text, "latency_ms": elapsed, "tokens": tokens}
    except Exception as exc:
        save_setting(f"provider_status_{provider}", "red")
        return {"ok": False, "error": str(exc), "latency_ms": 0, "tokens": 0}


def check_local_service(url: str) -> bool:
    """Check if a local model service endpoint is reachable."""
    import requests

    try:
        resp = requests.get(url.rstrip("/").replace("/v1", "") + "/", timeout=3)
        return resp.status_code < 500
    except Exception:
        return False


def ping_local_health(url: str) -> dict | None:
    """Ping a local model endpoint and report simple status/latency."""
    import requests

    try:
        start = time.time()
        resp = requests.get(url.rstrip("/").replace("/v1", "") + "/", timeout=3)
        ms = round((time.time() - start) * 1000)
        if resp.status_code < 500:
            return {"status": "online", "latency_ms": ms}
    except Exception:
        pass
    return None


OLLAMA_CATALOG = {
    "Tiny (1-3B) - 4 GB RAM": [
        "llama3.2:1b", "qwen3:0.6b", "qwen3:1.7b", "qwen2.5:0.5b",
        "qwen2.5:1.5b", "qwen2.5-coder:0.5b", "qwen2.5-coder:1.5b",
        "gemma3:1b", "deepseek-r1:1.5b", "phi3:mini", "tinyllama",
        "smollm2:135m", "smollm2:360m", "smollm2:1.7b",
    ],
    "Small (7-8B) - 8 GB RAM": [
        "llama3.2", "llama3.1:8b", "llama3:8b", "qwen3:8b",
        "qwen2.5:7b", "qwen2.5-coder:7b", "mistral:7b",
        "gemma3:4b", "gemma2:9b", "deepseek-r1:7b", "deepseek-r1:8b",
        "phi4:14b", "codellama:7b", "starcoder2:7b",
        "dolphin-mistral", "neural-chat", "starling-lm",
        "nous-hermes2", "orca-mini", "stable-code",
        "nomic-embed-text", "mxbai-embed-large",
    ],
    "Medium (13-14B) - 16 GB RAM": [
        "qwen3:14b", "qwen2.5:14b", "qwen2.5-coder:14b",
        "gemma3:12b", "deepseek-r1:14b", "codellama:13b",
        "llava:13b", "wizard-math:13b", "vicuna:13b",
        "starcoder2:15b",
    ],
    "Large (27-34B) - 32 GB RAM": [
        "qwen3:30b", "qwen3:32b", "qwen2.5:32b",
        "qwen2.5-coder:32b", "gemma3:27b", "gemma2:27b",
        "deepseek-r1:32b", "codellama:34b",
        "command-r:35b", "llava:34b", "yi:34b",
    ],
    "XL (70B+) - 64 GB RAM": [
        "llama3.1:70b", "llama3:70b", "qwen3:235b",
        "qwen2.5:72b", "deepseek-r1:70b", "deepseek-r1:671b",
        "codellama:70b", "command-r-plus",
    ],
}


CLOUD_PROVIDERS = {
    "Groq (Free Tier, Very Fast)": {
        "key": "groq",
        "url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "signup": "console.groq.com",
        "signup_url": "https://console.groq.com/keys",
        "key_prefix": "gsk_",
        "cost": "FREE tier - generous rate limits, no payment required",
        "setup": [
            "Go to console.groq.com and create an account (Google or GitHub login works)",
            "Navigate to API Keys in the left sidebar",
            "Click 'Create API Key' and copy the key",
            "Paste the key below",
        ],
        "notes": "Groq uses custom LPU hardware for extremely fast inference (~500 tokens/sec). Free tier includes ~500K tokens/day. Best choice for getting started with zero cost.",
    },
    "GitHub Models (Free with GitHub Account)": {
        "key": "github",
        "url": "https://models.inference.ai.azure.com",
        "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "o3-mini", "Meta-Llama-3.1-405B-Instruct", "Meta-Llama-3.1-70B-Instruct", "Mistral-large-2411", "Phi-4", "DeepSeek-R1"],
        "signup": "github.com/settings/tokens",
        "signup_url": "https://github.com/settings/tokens",
        "key_prefix": "ghp_",
        "cost": "FREE during preview - uses your GitHub Personal Access Token",
        "setup": [
            "Log into GitHub",
            "Go to Settings > Developer settings > Personal access tokens > Tokens (classic)",
            "Click 'Generate new token (classic)'",
            "No special scopes needed - just give it a name and generate",
            "Copy the token (starts with ghp_) and paste below",
        ],
        "notes": "GitHub Models gives free access to GPT-4o, Llama, Mistral, and more. Rate limits apply per model. Great if you already have a GitHub account.",
    },
    "OpenAI (GPT-4o, Best Quality)": {
        "key": "openai",
        "url": "https://api.openai.com/v1",
        "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini", "o3-mini"],
        "signup": "platform.openai.com",
        "signup_url": "https://platform.openai.com/api-keys",
        "key_prefix": "sk-",
        "cost": "PAID - gpt-4o: ~$2.50 input / $10 output per 1M tokens; gpt-4o-mini: ~$0.15 / $0.60",
        "setup": [
            "Go to platform.openai.com and create an account",
            "Navigate to API Keys section",
            "Click 'Create new secret key' and copy it",
            "IMPORTANT: Add a payment method under Billing (required before API works)",
            "Paste the API key below",
        ],
        "notes": "OpenAI provides the highest quality models. gpt-4o-mini is an excellent balance of quality and cost for academic use. Tier 1 rate limits: 500 RPM, 30K TPM.",
    },
    "Anthropic Claude (200K Context)": {
        "key": "anthropic",
        "url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
        "signup": "console.anthropic.com",
        "signup_url": "https://console.anthropic.com/settings/keys",
        "key_prefix": "sk-ant-",
        "cost": "PAID - Sonnet: ~$3/$15 per 1M tokens; Haiku: ~$0.25/$1.25",
        "setup": [
            "Go to console.anthropic.com and create an account",
            "Navigate to API Keys",
            "Click 'Create Key' and copy it",
            "Add billing (prepaid credits or credit card)",
            "Paste the API key below",
        ],
        "notes": "Claude models have a 200K token context window - excellent for processing long documents and complex conversations. Uses its own SDK (handled internally).",
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
        "notes": "Mistral models are strong at reasoning and multilingual tasks. Codestral is specialized for code generation. 32K-128K context windows.",
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
        "notes": "Together AI runs open-source models on fast GPU clusters. Great for testing many different open models. $5 free credit goes a long way.",
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
        "notes": "HuggingFace hosts thousands of models. The free Inference API has cold-start delays (30-60s on first request). Best for experimentation.",
    },
}
