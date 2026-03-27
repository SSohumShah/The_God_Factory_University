"""DeepAI provider — free tier text-to-image API."""
from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
import json
from pathlib import Path

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"

DEEPAI_URL = "https://api.deepai.org/api/text2img"


class DeepAIProvider(ImageProvider):
    """DeepAI free-tier text-to-image (5 free/day on signup)."""

    name = "deepai"
    daily_limit = 5

    def _get_key(self) -> str:
        return get_setting("deepai_api_key", "")

    def is_available(self) -> bool:
        return bool(self._get_key())

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = self._get_key()
        if not key:
            return None
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        full_prompt = (
            "educational motion design, crisp typography, technical diagrams, "
            f"soft volumetric lighting, {prompt}"
        )
        body = urllib.parse.urlencode({"text": full_prompt}).encode("utf-8")

        try:
            req = urllib.request.Request(
                DEEPAI_URL,
                data=body,
                headers={"api-key": key},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=90)
            result = json.loads(resp.read())
            img_url = result.get("output_url", "")
            if not img_url:
                return None
            img_req = urllib.request.Request(img_url, method="GET")
            img_resp = urllib.request.urlopen(img_req, timeout=60)
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"dai_{name}.jpg"
            out_path.write_bytes(img_resp.read())
            return out_path
        except Exception:
            return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
