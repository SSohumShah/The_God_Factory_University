"""Pollinations.ai provider — free tier with optional API key.

As of 2026 the endpoint is ``gen.pollinations.ai`` and an API key is needed
for reliable access.  A publishable ``pk_`` key from https://enter.pollinations.ai/
is sufficient — it allows rate-limited usage.  Without a key the request will
be attempted but will likely return 401.
"""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"

# New endpoint (2026)
_GEN_URL = "https://gen.pollinations.ai/image/{prompt}"


class PollinationsProvider(ImageProvider):
    """Pollinations.ai — image generation (API key recommended)."""

    name = "pollinations"
    daily_limit = 50

    def _get_key(self) -> str:
        try:
            from core.database import get_setting
            return get_setting("pollinations_api_key", "")
        except Exception:
            return ""

    def is_available(self) -> bool:
        # With a key we're confident; without, we still try but may get 401
        return True

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        full_prompt = (
            "educational motion design, crisp typography, "
            "technical diagrams, soft volumetric lighting, " + prompt
        )
        encoded = urllib.parse.quote(full_prompt, safe="")
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)

        # Build URL with query params
        params = {
            "width": min(width, 1024),
            "height": min(height, 1024),
            "seed": seed,
            "nologo": "true",
            "model": "flux",
        }
        key = self._get_key()
        if key:
            params["key"] = key

        qs = urllib.parse.urlencode(params)
        url = f"{_GEN_URL.format(prompt=encoded)}?{qs}"

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "GFU-App/1.0")
            resp = urllib.request.urlopen(req, timeout=120)
            ct = resp.headers.get("Content-Type", "")
            if "image" not in ct:
                return None
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"poll_{name}.jpg"
            out_path.write_bytes(resp.read())
            if out_path.exists() and out_path.stat().st_size > 500:
                return out_path
            return None
        except Exception:
            pass

        # Fallback: try legacy endpoint without auth (may still work for some)
        try:
            legacy = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={min(width, 1024)}&height={min(height, 1024)}"
                f"&nologo=true&seed={seed}"
            )
            req2 = urllib.request.Request(legacy, method="GET")
            req2.add_header("User-Agent", "GFU-App/1.0")
            resp2 = urllib.request.urlopen(req2, timeout=90)
            ct2 = resp2.headers.get("Content-Type", "")
            if "image" not in ct2:
                return None
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"poll_{name}.jpg"
            out_path.write_bytes(resp2.read())
            if out_path.exists() and out_path.stat().st_size > 500:
                return out_path
        except Exception:
            pass
        return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
