"""HuggingFace Inference API provider — free-tier SDXL image generation."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"


class HuggingFaceProvider(ImageProvider):
    """HuggingFace Inference API free tier for SDXL."""

    name = "huggingface"
    daily_limit = 30  # approximate free-tier daily limit

    def _get_token(self) -> str:
        return get_setting("hf_api_token", "")

    def is_available(self) -> bool:
        return bool(self._get_token())

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        token = self._get_token()
        if not token:
            return None

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "inputs": (
                "educational motion design, crisp typography, "
                f"technical diagrams, soft volumetric lighting, {prompt}"
            ),
            "parameters": {"width": min(width, 1024), "height": min(height, 1024)},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                HF_API_URL,
                data=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=120)
            ct = resp.headers.get("Content-Type", "")

            if "image" in ct:
                import hashlib
                name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
                ext = "png" if "png" in ct else "jpeg"
                out_path = _OUTPUT_DIR / f"hf_{name}.{ext}"
                out_path.write_bytes(resp.read())
                return out_path

            # API returned JSON error
            return None
        except Exception:
            return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
