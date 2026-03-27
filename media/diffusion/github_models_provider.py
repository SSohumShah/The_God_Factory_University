"""GitHub Models provider — image generation via existing GitHub PAT."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path

from core.database import get_setting
from media.diffusion.provider_base import ImageProvider

_ROOT = Path(__file__).resolve().parent.parent.parent
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"
GH_MODELS_URL = "https://models.inference.ai.azure.com"


class GitHubModelsProvider(ImageProvider):
    """GitHub Models free-tier image generation."""

    name = "github_models"
    daily_limit = 15  # conservative estimate for free tier

    def _get_token(self) -> str:
        return get_setting("github_token", "") or get_setting("gh_pat", "")

    def is_available(self) -> bool:
        return bool(self._get_token())

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        token = self._get_token()
        if not token:
            return None

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "model": "dall-e-3",
            "prompt": (
                "educational motion design, crisp typography, "
                f"technical diagrams, soft volumetric lighting, {prompt}"
            ),
            "size": "1024x1024",
            "n": 1,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{GH_MODELS_URL}/images/generations",
                data=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=120)
            result = json.loads(resp.read())
            data = result.get("data", [])
            if not data:
                return None

            img_url = data[0].get("url", "")
            if not img_url:
                return None

            # Download the image
            img_req = urllib.request.Request(img_url, method="GET")
            img_resp = urllib.request.urlopen(img_req, timeout=60)
            import hashlib
            name = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            out_path = _OUTPUT_DIR / f"ghm_{name}.png"
            out_path.write_bytes(img_resp.read())
            return out_path
        except Exception:
            return None

    def remaining_quota(self) -> int | None:
        return self.daily_limit
