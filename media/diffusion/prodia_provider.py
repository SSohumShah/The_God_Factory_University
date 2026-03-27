"""Prodia API provider — pay-as-you-go overflow ($0.002/image), fast SDXL."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "diffusion_output"


class ProdiaProvider(ImageProvider):
    name = "prodia"
    daily_limit = 20  # Soft self-imposed limit for cost control

    def is_available(self) -> bool:
        return bool(get_setting("prodia_api_key", ""))

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = get_setting("prodia_api_key", "")
        if not key:
            return None
        _OUT.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.post(
                "https://api.prodia.com/v1/sdxl/generate",
                headers={"X-Prodia-Key": key, "Content-Type": "application/json"},
                json={
                    "prompt": f"educational, clean, academic: {prompt}",
                    "model": "sdxl",
                    "width": min(width, 1024),
                    "height": min(height, 1024),
                },
                timeout=30,
            )
            resp.raise_for_status()
            job_id = resp.json().get("job")
            if not job_id:
                return None

            # Poll for completion
            for _ in range(30):
                time.sleep(2)
                poll = requests.get(
                    f"https://api.prodia.com/v1/job/{job_id}",
                    headers={"X-Prodia-Key": key},
                    timeout=15,
                )
                status = poll.json().get("status")
                if status == "succeeded":
                    img_url = poll.json().get("imageUrl", "")
                    if img_url:
                        img_data = requests.get(img_url, timeout=30).content
                        h = hashlib.md5(prompt.encode()).hexdigest()[:10]
                        out = _OUT / f"prod_{h}.png"
                        out.write_bytes(img_data)
                        return out
                    break
                if status == "failed":
                    break
        except Exception:
            pass
        return None
