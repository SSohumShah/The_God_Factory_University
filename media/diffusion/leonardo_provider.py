"""Leonardo.ai image provider — official API, 150 tokens/day free tier."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "diffusion_output"


class LeonardoProvider(ImageProvider):
    name = "leonardo"
    daily_limit = 30  # ~30 images at 5 tokens/image

    def is_available(self) -> bool:
        return bool(get_setting("leonardo_api_key", ""))

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        key = get_setting("leonardo_api_key", "")
        if not key:
            return None
        _OUT.mkdir(parents=True, exist_ok=True)
        try:
            # Create generation
            resp = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "prompt": f"educational, clean, academic: {prompt}",
                    "width": min(width, 1024),
                    "height": min(height, 1024),
                    "num_images": 1,
                    "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
                },
                timeout=30,
            )
            resp.raise_for_status()
            gen_id = resp.json()["sdGenerationJob"]["generationId"]

            # Poll for result
            for _ in range(30):
                time.sleep(2)
                poll = requests.get(
                    f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                data = poll.json().get("generations_by_pk", {})
                if data.get("status") == "COMPLETE":
                    images = data.get("generated_images", [])
                    if images:
                        img_url = images[0]["url"]
                        img_data = requests.get(img_url, timeout=30).content
                        h = hashlib.md5(prompt.encode()).hexdigest()[:10]
                        out = _OUT / f"leo_{h}.png"
                        out.write_bytes(img_data)
                        return out
                    break
        except Exception:
            pass
        return None
