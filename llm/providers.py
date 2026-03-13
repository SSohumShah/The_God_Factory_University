"""
Universal LLM provider layer for Arcane University.

Supported providers:
  local    - Ollama (http://localhost:11434)
  lmstudio - LM Studio (http://localhost:1234, OpenAI-compatible)
  openai   - OpenAI API
  github   - GitHub Models (models.inference.ai.azure.com)
  anthropic- Anthropic Claude API
  groq     - Groq (OpenAI-compatible, very fast)
  mistral  - Mistral AI API
  together - Together AI
  cohere   - Cohere API (OpenAI-compatible endpoint)
  huggingface - HuggingFace Inference API (OpenAI-compatible)

All OpenAI-compatible providers use the `openai` SDK with a custom base_url.
Anthropic uses its own SDK.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Generator, Iterable

import psutil
import requests

# ─── Provider catalogue ───────────────────────────────────────────────────────

PROVIDER_CATALOGUE: dict[str, dict] = {
    "ollama": {
        "label": "Ollama (Local / Free)",
        "type": "openai_compat",
        "base_url": "http://localhost:11434/v1",
        "default_api_key": "ollama",
        "default_models": ["llama3", "mistral", "phi3", "codellama", "gemma2"],
        "setup_hint": "Install Ollama from https://ollama.com then run: ollama pull <model>",
        "needs_key": False,
    },
    "lmstudio": {
        "label": "LM Studio (Local / Free)",
        "type": "openai_compat",
        "base_url": "http://localhost:1234/v1",
        "default_api_key": "lm-studio",
        "default_models": [],  # dynamic
        "setup_hint": "Install LM Studio, load a model, and start the local server.",
        "needs_key": False,
    },
    "openai": {
        "label": "OpenAI (api.openai.com)",
        "type": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "default_api_key": None,
        "default_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "setup_hint": "Provide your OpenAI API key from platform.openai.com",
        "needs_key": True,
    },
    "github": {
        "label": "GitHub Models (Free with PAT)",
        "type": "openai_compat",
        "base_url": "https://models.inference.ai.azure.com",
        "default_api_key": None,
        "default_models": [
            "gpt-4o", "gpt-4o-mini",
            "meta-llama-3.1-70b-instruct",
            "meta-llama-3.1-8b-instruct",
            "mistral-large",
            "mistral-small",
            "phi-3-medium-instruct-128k",
        ],
        "setup_hint": "Create a GitHub Personal Access Token at github.com/settings/tokens with no special scopes needed.",
        "needs_key": True,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "type": "anthropic",
        "base_url": "https://api.anthropic.com",
        "default_api_key": None,
        "default_models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "setup_hint": "Create an API key at console.anthropic.com",
        "needs_key": True,
    },
    "groq": {
        "label": "Groq (Fast / Free tier)",
        "type": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "default_api_key": None,
        "default_models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "setup_hint": "Get a free API key at console.groq.com",
        "needs_key": True,
    },
    "mistral": {
        "label": "Mistral AI",
        "type": "openai_compat",
        "base_url": "https://api.mistral.ai/v1",
        "default_api_key": None,
        "default_models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
        "setup_hint": "Get an API key at console.mistral.ai",
        "needs_key": True,
    },
    "together": {
        "label": "Together AI (Free tier)",
        "type": "openai_compat",
        "base_url": "https://api.together.xyz/v1",
        "default_api_key": None,
        "default_models": ["meta-llama/Llama-3.1-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "setup_hint": "Get an API key at api.together.ai",
        "needs_key": True,
    },
    "huggingface": {
        "label": "HuggingFace Inference",
        "type": "openai_compat",
        "base_url": "https://api-inference.huggingface.co/v1",
        "default_api_key": None,
        "default_models": ["meta-llama/Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
        "setup_hint": "Get a free HuggingFace token at huggingface.co/settings/tokens",
        "needs_key": True,
    },
}


# ─── Provider capabilities ────────────────────────────────────────────────────

PROVIDER_CAPABILITIES: dict[str, dict] = {
    "ollama":      {"streaming": True,  "context_window": 8192,   "json_mode": True,  "cost_per_1k_input": 0.0,    "cost_per_1k_output": 0.0},
    "lmstudio":    {"streaming": True,  "context_window": 8192,   "json_mode": True,  "cost_per_1k_input": 0.0,    "cost_per_1k_output": 0.0},
    "openai":      {"streaming": True,  "context_window": 128000, "json_mode": True,  "cost_per_1k_input": 0.005,  "cost_per_1k_output": 0.015},
    "github":      {"streaming": True,  "context_window": 128000, "json_mode": True,  "cost_per_1k_input": 0.0,    "cost_per_1k_output": 0.0},
    "anthropic":   {"streaming": True,  "context_window": 200000, "json_mode": False, "cost_per_1k_input": 0.003,  "cost_per_1k_output": 0.015},
    "groq":        {"streaming": True,  "context_window": 32768,  "json_mode": True,  "cost_per_1k_input": 0.0,    "cost_per_1k_output": 0.0},
    "mistral":     {"streaming": True,  "context_window": 32768,  "json_mode": True,  "cost_per_1k_input": 0.002,  "cost_per_1k_output": 0.006},
    "together":    {"streaming": True,  "context_window": 32768,  "json_mode": True,  "cost_per_1k_input": 0.0008, "cost_per_1k_output": 0.0008},
    "huggingface": {"streaming": True,  "context_window": 8192,   "json_mode": False, "cost_per_1k_input": 0.0,    "cost_per_1k_output": 0.0},
}


def get_capability(provider: str, key: str, default=None):
    """Look up a single capability for a provider."""
    return PROVIDER_CAPABILITIES.get(provider, {}).get(key, default)


# ─── Hardware check ───────────────────────────────────────────────────────────

def check_hardware() -> dict:
    ram_gb = round(psutil.virtual_memory().total / 1024 ** 3, 1)
    gpu_vram_gb = 0.0
    gpu_name = "None"
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            gpu_vram_gb = round(props.total_memory / 1024 ** 3, 1)
            gpu_name = props.name
    except Exception:
        pass

    def rec_model():
        if gpu_vram_gb >= 24:
            return "llama3.3:70b", "Full 70B model on GPU"
        if gpu_vram_gb >= 12:
            return "llama3.1:8b", "8B on GPU"
        if gpu_vram_gb >= 6:
            return "phi3:medium", "Phi-3 medium on GPU"
        if ram_gb >= 32:
            return "llama3.2:3b", "3B on CPU RAM"
        if ram_gb >= 16:
            return "phi3:mini", "Phi-3 mini on CPU"
        return "phi3:mini", "Phi-3 mini (minimum viable)"

    model, reason = rec_model()
    return {
        "ram_gb": ram_gb,
        "gpu_vram_gb": gpu_vram_gb,
        "gpu_name": gpu_name,
        "recommended_model": model,
        "recommendation_reason": reason,
        "ollama_available": _ollama_available(),
    }


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def list_ollama_models() -> list[str]:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def pull_ollama_model(model: str) -> bool:
    try:
        r = requests.post("http://localhost:11434/api/pull", json={"name": model}, timeout=600, stream=True)
        return r.status_code == 200
    except Exception:
        return False


# ─── LLM Client ───────────────────────────────────────────────────────────────

@dataclass
class LLMConfig:
    provider: str = "ollama"
    model: str = "llama3"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str = ""
    extra: dict = field(default_factory=dict)


def _resolve_config(cfg: LLMConfig) -> tuple[str, str, str]:
    """Returns (type, base_url, api_key)."""
    cat = PROVIDER_CATALOGUE.get(cfg.provider, {})
    ptype = cat.get("type", "openai_compat")
    base_url = cfg.base_url or cat.get("base_url", "")
    api_key = cfg.api_key or cat.get("default_api_key") or ""
    return ptype, base_url, api_key


def classify_error(exc: Exception) -> tuple[str, str]:
    """Classify a provider exception into (error_type, user_message).
    Returns one of: auth_error, rate_limit, network, bad_model, timeout, provider_down, unknown.
    """
    msg = str(exc).lower()
    if any(k in msg for k in ("401", "unauthorized", "invalid.*key", "authentication", "api key")):
        return "auth_error", "Authentication failed. Check your API key in Settings or LLM Setup Wizard."
    if any(k in msg for k in ("429", "rate limit", "rate_limit", "too many requests", "quota")):
        return "rate_limit", "Rate limit reached. Wait a moment or switch to a different provider."
    if any(k in msg for k in ("timeout", "timed out", "read timeout")):
        return "timeout", "Request timed out. The provider may be slow or overloaded."
    if any(k in msg for k in ("connection", "connect", "network", "dns", "resolve", "unreachable")):
        return "network", "Network error. Check your internet connection and provider URL."
    if any(k in msg for k in ("model", "not found", "does not exist", "invalid model", "no such model")):
        return "bad_model", "Model not found. Check the model name in Settings."
    if any(k in msg for k in ("500", "502", "503", "server error", "internal error")):
        return "provider_down", "Provider server error. Try again later or switch providers."
    return "unknown", f"LLM error: {exc}"


def chat(cfg: LLMConfig, messages: list[dict], stream: bool = False) -> str | Generator:
    ptype, base_url, api_key = _resolve_config(cfg)
    if ptype == "anthropic":
        return _anthropic_chat(cfg, api_key, messages, stream)
    return _compat_chat(cfg, base_url, api_key, messages, stream)


def _compat_chat(cfg: LLMConfig, base_url: str, api_key: str, messages: list[dict], stream: bool) -> str | Generator:
    try:
        from openai import OpenAI
    except ImportError:
        return "[ERROR] openai package not installed. Run: pip install openai"

    client = OpenAI(base_url=base_url, api_key=api_key or "none")
    full_messages = []
    if cfg.system_prompt:
        full_messages.append({"role": "system", "content": cfg.system_prompt})
    full_messages.extend(messages)

    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=full_messages,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            stream=stream,
        )
        if stream:
            def _gen():
                for chunk in resp:
                    delta = chunk.choices[0].delta.content or ""
                    yield delta
            return _gen()
        return resp.choices[0].message.content or ""
    except Exception as e:
        error_type, user_msg = classify_error(e)
        from core.logger import log_provider_call
        log_provider_call(cfg.provider, cfg.model, f"error:{error_type}")
        return f"[LLM ERROR] ({error_type}) {user_msg}"


def _anthropic_chat(cfg: LLMConfig, api_key: str, messages: list[dict], stream: bool) -> str:
    try:
        import anthropic
    except ImportError:
        return "[ERROR] anthropic package not installed. Run: pip install anthropic"

    client = anthropic.Anthropic(api_key=api_key)
    system = cfg.system_prompt or "You are a helpful professor."
    try:
        resp = client.messages.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            system=system,
            messages=messages,
        )
        return resp.content[0].text
    except Exception as e:
        error_type, user_msg = classify_error(e)
        from core.logger import log_provider_call
        log_provider_call(cfg.provider, cfg.model, f"error:{error_type}")
        return f"[LLM ERROR] ({error_type}) {user_msg}"


def simple_complete(cfg: LLMConfig, prompt: str) -> str:
    return chat(cfg, [{"role": "user", "content": prompt}])


def cfg_from_settings() -> LLMConfig:
    from core.database import get_setting
    return LLMConfig(
        provider=get_setting("llm_provider", "ollama"),
        model=get_setting("llm_model", "llama3"),
        api_key=get_setting("llm_api_key", ""),
        base_url=get_setting("llm_base_url", ""),
    )


# ─── Fallback ─────────────────────────────────────────────────────────────────

def chat_with_fallback(
    configs: list[LLMConfig],
    messages: list[dict],
    stream: bool = False,
) -> tuple[str | Generator, LLMConfig | None, list[str]]:
    """Try each config in order. Returns (response, winning_config, error_log).

    If all fail, response is the last error string and winning_config is None.
    """
    errors: list[str] = []
    for cfg in configs:
        result = chat(cfg, messages, stream=stream)
        if isinstance(result, str) and result.startswith("[LLM ERROR]"):
            errors.append(f"{cfg.provider}/{cfg.model}: {result}")
            continue
        return result, cfg, errors
    return (errors[-1] if errors else "[LLM ERROR] No providers configured"), None, errors


# ─── Token estimation & cost telemetry ────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def estimate_cost(provider: str, input_text: str, output_text: str) -> float:
    """Estimate cost in USD for an interaction."""
    caps = PROVIDER_CAPABILITIES.get(provider, {})
    in_cost = caps.get("cost_per_1k_input", 0.0)
    out_cost = caps.get("cost_per_1k_output", 0.0)
    in_tokens = estimate_tokens(input_text)
    out_tokens = estimate_tokens(output_text)
    return (in_tokens / 1000 * in_cost) + (out_tokens / 1000 * out_cost)
