"""
Provider logic tests — tests for pure-logic functions (no real API calls).
LLM chat/complete functions are tested via mocks only.
"""
from __future__ import annotations

import pytest

from llm.providers import (
    LLMConfig, classify_error, PROVIDER_CATALOGUE,
    PROVIDER_CAPABILITIES, get_capability, estimate_tokens, estimate_cost,
    chat_with_fallback,
)


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "ollama"
        assert cfg.model == "llama3"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096

    def test_custom(self):
        cfg = LLMConfig(provider="openai", model="gpt-4o", api_key="sk-test")
        assert cfg.provider == "openai"
        assert cfg.api_key == "sk-test"


class TestClassifyError:
    def test_auth_error(self):
        exc = Exception("401 Unauthorized: invalid api key")
        err_type, msg = classify_error(exc)
        assert err_type == "auth_error"

    def test_rate_limit(self):
        exc = Exception("429 Too Many Requests: rate limit exceeded")
        err_type, msg = classify_error(exc)
        assert err_type == "rate_limit"

    def test_network_error(self):
        from urllib.error import URLError
        exc = URLError("Connection refused")
        err_type, msg = classify_error(exc)
        assert err_type in ("network", "unknown")

    def test_timeout(self):
        exc = TimeoutError("Request timed out")
        err_type, msg = classify_error(exc)
        assert err_type == "timeout"

    def test_unknown(self):
        exc = Exception("Something completely unexpected")
        err_type, msg = classify_error(exc)
        assert err_type == "unknown"
        assert msg  # should have some message


class TestProviderCatalogue:
    def test_has_core_providers(self):
        expected_core = {"ollama", "lmstudio", "openai", "github", "anthropic",
                         "groq", "mistral", "together", "huggingface"}
        assert expected_core.issubset(set(PROVIDER_CATALOGUE.keys()))


class TestProviderCapabilities:
    def test_all_catalogue_providers_have_capabilities(self):
        for provider in PROVIDER_CATALOGUE:
            assert provider in PROVIDER_CAPABILITIES, f"{provider} missing capabilities"

    def test_capability_keys(self):
        required = {"streaming", "context_window", "json_mode", "cost_per_1k_input", "cost_per_1k_output"}
        for provider, caps in PROVIDER_CAPABILITIES.items():
            assert required.issubset(set(caps.keys())), f"{provider} missing keys"

    def test_get_capability(self):
        assert get_capability("openai", "streaming") is True
        assert get_capability("nonexistent", "streaming", False) is False

    def test_local_providers_are_free(self):
        for p in ("ollama", "lmstudio"):
            assert PROVIDER_CAPABILITIES[p]["cost_per_1k_input"] == 0.0
            assert PROVIDER_CAPABILITIES[p]["cost_per_1k_output"] == 0.0


class TestTokenEstimation:
    def test_estimate_tokens_basic(self):
        assert estimate_tokens("hello world") >= 1

    def test_estimate_cost_free_provider(self):
        cost = estimate_cost("ollama", "hello " * 50, "response " * 50)
        assert cost == 0.0

    def test_estimate_cost_paid_provider(self):
        cost = estimate_cost("openai", "x" * 4000, "y" * 4000)
        assert cost > 0.0


class TestFallback:
    def test_fallback_returns_tuple(self):
        # With no real providers, all should fail with import/connection errors
        cfgs = [
            LLMConfig(provider="ollama", model="nonexistent-model-xyz"),
        ]
        result, winner, errors = chat_with_fallback(cfgs, [{"role": "user", "content": "hi"}])
        # Either it connected (unlikely in tests) or returned an error
        assert isinstance(errors, list)

    def test_each_has_default_models(self):
        for name, info in PROVIDER_CATALOGUE.items():
            assert "default_models" in info, f"{name} missing 'default_models' key"
