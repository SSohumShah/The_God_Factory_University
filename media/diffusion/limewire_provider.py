"""LimeWire AI provider — official API, 10-20 daily credits free tier."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "diffusion_output"


class LimeWireProvider(ImageProvider):
    name = "limewire"
    daily_limit = 10

    def is_available(self) -> bool:
        return bool(get_setting("limewire_api_key", ""))

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = get_setting("limewire_api_key", "")
        if not key:
            return None
        _OUT.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.post(
                "https://api.limewire.com/api/image/generation",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "X-Api-Version": "v1",
                    "Accept": "application/json",
                },
                json={
                    "prompt": f"educational, clean, academic: {prompt}",
                    "aspect_ratio": "16:9",
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if data:
                img_url = data[0].get("asset_url", "")
                if img_url:
                    img_data = requests.get(img_url, timeout=30).content
                    h = hashlib.md5(prompt.encode()).hexdigest()[:10]
                    out = _OUT / f"lw_{h}.png"
                    out.write_bytes(img_data)
                    return out
        except Exception:
            pass
        return None
