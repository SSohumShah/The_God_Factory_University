"""LLM hardware benchmark — times a real test call, then estimates generation time.

Usage:
    from llm.benchmark import run_benchmark, estimate_generation_time, format_eta

    result = run_benchmark(cfg)          # {"tokens_per_second": 42.5, "latency_s": 1.2, ...}
    eta = estimate_generation_time(5000, result["tokens_per_second"])
    print(format_eta(eta["seconds"]))    # "23 minutes"
"""
from __future__ import annotations

import time

from llm.providers import LLMConfig, simple_complete

TEST_PROMPT = (
    "List exactly 20 key concepts in mathematics education, one per line, "
    "no numbering, no extra text."
)
EXPECTED_OUTPUT_WORDS = 60
EXPECTED_OUTPUT_TOKENS = 80

# Context-window probe: ask for a very long output and measure truncation
CONTEXT_PROBE_PROMPT = (
    "Write a numbered list from 1 to 500. Each line: the number followed by "
    "the word 'item'. Example: '1 item'. Output ALL 500 lines."
)


def run_benchmark(cfg: LLMConfig) -> dict:
    """Time a single LLM call. Returns benchmark dict with tokens_per_second.

    Falls back to the model-profile estimate if the call fails.
    """
    start = time.perf_counter()
    try:
        output = simple_complete(cfg, TEST_PROMPT)
    except Exception as exc:
        return {"tokens_per_second": None, "error": str(exc), "latency_s": None}
    elapsed = time.perf_counter() - start

    word_count = len((output or "").split())
    tokens_out = max(int(word_count * 1.35), EXPECTED_OUTPUT_TOKENS)
    tps = tokens_out / max(elapsed, 0.01)

    return {
        "tokens_per_second": round(tps, 1),
        "latency_s": round(elapsed, 2),
        "output_tokens": tokens_out,
        "word_count": word_count,
        "provider": cfg.provider,
        "model": cfg.model,
    }


def probe_context_window(cfg: LLMConfig) -> dict:
    """Estimate the model's effective output context window.

    Sends a prompt requesting 500 numbered lines. The highest number returned
    approximates the max output tokens. Returns {"estimated_max_output_tokens": int}.
    """
    try:
        output = simple_complete(cfg, CONTEXT_PROBE_PROMPT)
    except Exception as exc:
        return {"estimated_max_output_tokens": None, "error": str(exc)}

    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    max_num = 0
    for ln in lines:
        parts = ln.split()
        if parts and parts[0].isdigit():
            max_num = max(max_num, int(parts[0]))
    # Each numbered line ≈ 3 tokens
    estimated = max(max_num * 3, len((output or "").split()))
    return {"estimated_max_output_tokens": estimated, "lines_returned": max_num}


def estimate_generation_time(total_tokens: int, tokens_per_second: float) -> dict:
    """Estimate wall-clock seconds to generate *total_tokens* output tokens."""
    tps = max(tokens_per_second, 0.5)
    seconds = total_tokens / tps
    minutes = seconds / 60
    hours = minutes / 60
    return {
        "seconds": seconds,
        "minutes": round(minutes, 1),
        "hours": round(hours, 2),
    }


def format_eta(seconds: float) -> str:
    """Return a human-readable ETA string."""
    if seconds < 90:
        return f"{int(seconds)} seconds"
    if seconds < 3600:
        return f"{int(seconds / 60)} minutes"
    h = int(seconds / 3600)
    m = int((seconds % 3600) / 60)
    if m == 0:
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{h}h {m}m"


def save_benchmark(provider: str, model: str, tps: float) -> None:
    """Persist benchmark result to settings table."""
    try:
        from core.database import save_setting
        key = f"benchmark_{provider}_{model}"
        save_setting(key, str(round(tps, 1)))
    except Exception:
        pass


def load_benchmark(provider: str, model: str) -> float | None:
    """Load a saved benchmark tps value, or None if not yet benchmarked."""
    try:
        from core.database import get_setting
        key = f"benchmark_{provider}_{model}"
        val = get_setting(key, None)
        if val is not None:
            return float(val)
    except Exception:
        pass
    return None


def get_tps(provider: str, model: str) -> float:
    """Return best known tps: saved benchmark > model-profile estimate > fallback."""
    saved = load_benchmark(provider, model)
    if saved:
        return saved
    try:
        from llm.model_profiles import resolve_audit_profile
        profile = resolve_audit_profile(provider, model)
        return profile.estimated_tokens_per_second
    except Exception:
        pass
    return 30.0


def save_context_window(provider: str, model: str, max_tokens: int) -> None:
    """Persist detected context window size."""
    try:
        from core.database import save_setting
        save_setting(f"ctx_{provider}_{model}", str(max_tokens))
    except Exception:
        pass


def load_context_window(provider: str, model: str) -> int | None:
    """Load saved context window estimate."""
    try:
        from core.database import get_setting
        val = get_setting(f"ctx_{provider}_{model}", None)
        if val is not None:
            return int(val)
    except Exception:
        pass
    return None


def needs_benchmark(provider: str, model: str) -> bool:
    """Return True if this provider/model combo has never been benchmarked."""
    return load_benchmark(provider, model) is None


def get_last_benchmarked_key() -> str:
    """Return the 'provider/model' string of the last benchmark run."""
    try:
        from core.database import get_setting
        return get_setting("last_benchmarked_key", "") or ""
    except Exception:
        return ""


def set_last_benchmarked_key(provider: str, model: str) -> None:
    """Record which provider/model was last benchmarked."""
    try:
        from core.database import save_setting
        save_setting("last_benchmarked_key", f"{provider}/{model}")
    except Exception:
        pass
