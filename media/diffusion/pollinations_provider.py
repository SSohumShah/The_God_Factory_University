"""Pollinations.ai provider — completely free, no API key required."""
from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"

POLL_URL = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true&seed={seed}"


class PollinationsProvider(ImageProvider):
    """Pollinations.ai — free image generation, no key needed."""

    name = "pollinations"
    daily_limit = 50

    def is_available(self) -> bool:
        return True  # no key required

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        encoded = urllib.parse.quote(
            f"educational motion design, crisp typography, technical diagrams, "
            f"soft volumetric lighting, {prompt}"
        )
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        url = POLL_URL.format(prompt=encoded, w=min(width, 1024), h=min(height, 1024), seed=seed)

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "GFU-App/1.0")
            resp = urllib.request.urlopen(req, timeout=90)
            ct = resp.headers.get("Content-Type", "")
            if "image" not in ct:
                return None
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"poll_{name}.jpg"
            out_path.write_bytes(resp.read())
            return out_path
        except Exception:
            return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
