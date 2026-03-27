"""Getimg.ai provider — official API, 100 images/month free tier."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "diffusion_output"


class GetimgProvider(ImageProvider):
    name = "getimg"
    daily_limit = 3  # ~100/month ≈ 3/day

    def is_available(self) -> bool:
        return bool(get_setting("getimg_api_key", ""))

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = get_setting("getimg_api_key", "")
        if not key:
            return None
        _OUT.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.post(
                "https://api.getimg.ai/v1/stable-diffusion-xl/text-to-image",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": f"educational, clean, academic: {prompt}",
                    "width": min(width, 1024),
                    "height": min(height, 1024),
                    "steps": 30,
                    "output_format": "png",
                },
                timeout=60,
            )
            resp.raise_for_status()
            import base64
            img_b64 = resp.json().get("image", "")
            if img_b64:
                h = hashlib.md5(prompt.encode()).hexdigest()[:10]
                out = _OUT / f"getimg_{h}.png"
                out.write_bytes(base64.b64decode(img_b64))
                return out
        except Exception:
            pass
        return None
