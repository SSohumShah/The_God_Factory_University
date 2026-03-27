"""Intelligent free-tier provider rotation for image generation.

Strategy:
  1. Try cloud providers first (save local GPU)
  2. Track daily usage per provider in SQLite
  3. Auto-switch when a provider's quota is exhausted
  4. Fall back to local ComfyUI
  5. Fall back to built-in PIL renderer (returns None)

Provider definitions live in data/media_providers.json for easy editing.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_PROVIDERS_JSON = _ROOT / "data" / "media_providers.json"
_DB_PATH = _ROOT / "data" / "free_tier_usage.db"


def _ensure_db() -> sqlite3.Connection:
    """Create usage tracking database if needed."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            provider TEXT NOT NULL,
            date TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (provider, date)
        )
    """)
    con.commit()
    return con


def _get_daily_usage(provider_name: str) -> int:
    """Get today's usage count for a provider."""
    con = _ensure_db()
    try:
        row = con.execute(
            "SELECT count FROM usage WHERE provider = ? AND date = ?",
            (provider_name, date.today().isoformat()),
        ).fetchone()
        return row[0] if row else 0
    finally:
        con.close()


def _increment_usage(provider_name: str) -> None:
    """Increment today's usage counter for a provider."""
    con = _ensure_db()
    try:
        today = date.today().isoformat()
        con.execute("""
            INSERT INTO usage (provider, date, count) VALUES (?, ?, 1)
            ON CONFLICT(provider, date) DO UPDATE SET count = count + 1
        """, (provider_name, today))
        con.commit()
    finally:
        con.close()


def _load_provider_config() -> list[dict]:
    """Load provider definitions from JSON. Falls back to built-in defaults."""
    if _PROVIDERS_JSON.exists():
        try:
            return json.loads(_PROVIDERS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_providers()


def _default_providers() -> list[dict]:
    """Built-in provider list when JSON file doesn't exist."""
    return [
        {"name": "pollinations", "daily_limit": 50, "priority": 1,
         "key_setting": None, "signup_url": None},
        {"name": "huggingface", "daily_limit": 30, "priority": 2,
         "key_setting": "hf_api_token",
         "signup_url": "https://huggingface.co/settings/tokens"},
        {"name": "leonardo", "daily_limit": 30, "priority": 3,
         "key_setting": "leonardo_api_key",
         "signup_url": "https://app.leonardo.ai/api"},
        {"name": "github_models", "daily_limit": 15, "priority": 4,
         "key_setting": "github_token",
         "signup_url": "https://github.com/settings/tokens"},
        {"name": "limewire", "daily_limit": 10, "priority": 5,
         "key_setting": "limewire_api_key",
         "signup_url": "https://limewire.com/studio"},
        {"name": "stability", "daily_limit": 10, "priority": 6,
         "key_setting": "stability_api_key",
         "signup_url": "https://platform.stability.ai/account/keys"},
        {"name": "getimg", "daily_limit": 3, "priority": 7,
         "key_setting": "getimg_api_key",
         "signup_url": "https://getimg.ai/dashboard"},
        {"name": "deepai", "daily_limit": 5, "priority": 8,
         "key_setting": "deepai_api_key",
         "signup_url": "https://deepai.org/dashboard/profile"},
        {"name": "prodia", "daily_limit": 20, "priority": 9,
         "key_setting": "prodia_api_key",
         "signup_url": "https://app.prodia.com/api"},
        {"name": "comfyui", "daily_limit": None, "priority": 20,
         "key_setting": None, "signup_url": None},
    ]


def _instantiate_provider(name: str) -> ImageProvider | None:
    """Create a provider instance by name."""
    try:
        if name == "pollinations":
            from media.diffusion.pollinations_provider import PollinationsProvider
            return PollinationsProvider()
        elif name == "huggingface":
            from media.diffusion.huggingface_provider import HuggingFaceProvider
            return HuggingFaceProvider()
        elif name == "leonardo":
            from media.diffusion.leonardo_provider import LeonardoProvider
            return LeonardoProvider()
        elif name == "github_models":
            from media.diffusion.github_models_provider import GitHubModelsProvider
            return GitHubModelsProvider()
        elif name == "limewire":
            from media.diffusion.limewire_provider import LimeWireProvider
            return LimeWireProvider()
        elif name == "stability":
            from media.diffusion.stability_provider import StabilityProvider
            return StabilityProvider()
        elif name == "getimg":
            from media.diffusion.getimg_provider import GetimgProvider
            return GetimgProvider()
        elif name == "deepai":
            from media.diffusion.deepai_provider import DeepAIProvider
            return DeepAIProvider()
        elif name == "prodia":
            from media.diffusion.prodia_provider import ProdiaProvider
            return ProdiaProvider()
        elif name == "comfyui":
            from media.diffusion.comfyui_provider import ComfyUIProvider
            return ComfyUIProvider()
    except Exception:
        pass
    return None


def get_all_providers() -> list[dict]:
    """Return provider config list with current status info."""
    configs = _load_provider_config()
    result = []
    for cfg in configs:
        name = cfg["name"]
        provider = _instantiate_provider(name)
        daily_limit = cfg.get("daily_limit")
        used = _get_daily_usage(name)
        available = provider.is_available() if provider else False
        remaining = (daily_limit - used) if daily_limit is not None else None

        result.append({
            "name": name,
            "daily_limit": daily_limit,
            "used_today": used,
            "remaining": remaining,
            "available": available,
            "priority": cfg.get("priority", 99),
            "signup_url": cfg.get("signup_url"),
        })
    return result


def get_best_provider() -> ImageProvider | None:
    """Get the best available provider based on quota and priority.

    Returns None if no provider is available or all quotas exhausted.
    The caller can also check for shared assets via core.asset_library
    before invoking generate_image to save quota.
    """
    configs = _load_provider_config()
    # Check for student-provided paid keys — these bypass quota
    try:
        from core.database import get_setting
    except Exception:
        get_setting = None

    # Sort by priority (lower = preferred)
    configs.sort(key=lambda c: c.get("priority", 99))

    for cfg in configs:
        name = cfg["name"]
        daily_limit = cfg.get("daily_limit")

        # Student paid key override: if student has a key for this provider
        # and a paid_override flag, treat as unlimited
        if get_setting and cfg.get("key_setting"):
            student_key = get_setting(cfg["key_setting"], "")
            paid_flag = get_setting(f"{name}_paid_tier", "")
            if student_key and paid_flag:
                provider = _instantiate_provider(name)
                if provider and provider.is_available():
                    return _TrackedProvider(provider, skip_quota=True)

        # Check quota
        if daily_limit is not None:
            used = _get_daily_usage(name)
            if used >= daily_limit:
                continue

        # Try to instantiate and check availability
        provider = _instantiate_provider(name)
        if provider and provider.is_available():
            return _TrackedProvider(provider)

    return None


class _TrackedProvider(ImageProvider):
    """Wrapper that tracks usage and catalogs assets on generate_image."""

    def __init__(self, inner: ImageProvider, skip_quota: bool = False) -> None:
        self._inner = inner
        self._skip_quota = skip_quota
        self.name = inner.name
        self.daily_limit = inner.daily_limit

    def is_available(self) -> bool:
        return self._inner.is_available()

    def generate_image(self, prompt: str, width: int = 960, height: int = 540,
                       course_id: str = "", lecture_id: str = "") -> Path | None:
        # Check shared asset library first
        try:
            from core.asset_library import find_reusable_asset
            cached = find_reusable_asset(prompt, course_id)
            if cached and Path(cached["file_path"]).exists():
                return Path(cached["file_path"])
        except Exception:
            pass

        result = self._inner.generate_image(prompt, width, height)
        if result is not None:
            if not self._skip_quota:
                _increment_usage(self._inner.name)
            # Store in asset library
            try:
                from core.asset_library import store_asset
                from core.database import get_setting
                share_pref = get_setting("share_generated_media", "course_shared")
                store_asset(prompt, result, provider=self._inner.name,
                            course_id=course_id, lecture_id=lecture_id,
                            width=width, height=height, permission=share_pref)
            except Exception:
                pass
        return result

    def remaining_quota(self) -> int | None:
        if self._skip_quota:
            return None
        if self._inner.daily_limit is not None:
            used = _get_daily_usage(self._inner.name)
            return max(0, self._inner.daily_limit - used)
        return None
