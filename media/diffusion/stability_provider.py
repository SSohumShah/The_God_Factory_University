"""Stability AI provider — free tier via REST API."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"

STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3-turbo"


class StabilityProvider(ImageProvider):
    """Stability AI free-tier image generation (25 credits free on signup)."""

    name = "stability"
    daily_limit = 10

    def _get_key(self) -> str:
        return get_setting("stability_api_key", "")

    def is_available(self) -> bool:
        return bool(self._get_key())

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = self._get_key()
        if not key:
            return None
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Stability API uses multipart form data
        boundary = "----GFUBoundary"
        full_prompt = (
            "educational motion design, crisp typography, technical diagrams, "
            f"soft volumetric lighting, {prompt}"
        )
        neg = "blurry text, logo, watermark, low contrast, nsfw"

        body_parts = []
        for field, val in [("prompt", full_prompt), ("negative_prompt", neg),
                           ("output_format", "jpeg"), ("mode", "text-to-image")]:
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field}"\r\n\r\n{val}\r\n'
            )
        body_parts.append(f"--{boundary}--\r\n")
        body = "".join(body_parts).encode("utf-8")

        try:
            req = urllib.request.Request(
                STABILITY_URL,
                data=body,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Accept": "image/*",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=120)
            ct = resp.headers.get("Content-Type", "")
            if "image" not in ct:
                return None
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"stab_{name}.jpeg"
            out_path.write_bytes(resp.read())
            return out_path
        except Exception:
            return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
