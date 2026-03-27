"""ComfyUI provider — local Stable Diffusion via subprocess on localhost:8188."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from media.diffusion.provider_base import ImageProvider

# Default ComfyUI installation path (relative to project root)
_ROOT = Path(__file__).resolve().parent.parent.parent
_COMFYUI_DIR = _ROOT / "ComfyUI-master" / "ComfyUI-master"
_COMFYUI_MAIN = _COMFYUI_DIR / "main.py"
_OUTPUT_DIR = _ROOT / "data" / "diffusion_output"

COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"


def _text_to_image_workflow(prompt: str, width: int, height: int) -> dict:
    """Build a minimal text-to-image workflow for ComfyUI queue API."""
    return {
        "prompt": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": int(time.time()) % 2**32,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_turbo.safetensors"},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": (
                        "educational motion design, crisp typography, "
                        f"technical diagrams, soft volumetric lighting, {prompt}"
                    ),
                    "clip": ["4", 1],
                },
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "blurry text, logo, watermark, low contrast, nsfw",
                    "clip": ["4", 1],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "gfu_gen", "images": ["8", 0]},
            },
        }
    }


class ComfyUIProvider(ImageProvider):
    """Local ComfyUI Stable Diffusion provider via REST API."""

    name = "comfyui"
    daily_limit = None  # unlimited locally

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def is_available(self) -> bool:
        if not _COMFYUI_MAIN.exists():
            return False
        try:
            req = urllib.request.Request(f"{COMFYUI_URL}/system_stats", method="GET")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False

    def _ensure_running(self) -> bool:
        """Start ComfyUI subprocess if not already running."""
        if self.is_available():
            return True
        if not _COMFYUI_MAIN.exists():
            return False
        try:
            _log_dir = _ROOT / "data" / "logs"
            _log_dir.mkdir(parents=True, exist_ok=True)
            _log_file = open(_log_dir / "comfyui_server.log", "w", encoding="utf-8")
            self._process = subprocess.Popen(
                [sys.executable, str(_COMFYUI_MAIN), "--listen", COMFYUI_HOST,
                 "--port", str(COMFYUI_PORT), "--preview-method", "none"],
                cwd=str(_COMFYUI_DIR),
                stdout=_log_file,
                stderr=subprocess.STDOUT,
            )
            # Wait for startup (up to 30s)
            for _ in range(60):
                time.sleep(0.5)
                if self.is_available():
                    return True
        except Exception:
            pass
        return False

    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        if not self._ensure_running():
            return None

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        workflow = _text_to_image_workflow(prompt, width, height)

        try:
            data = json.dumps(workflow).encode("utf-8")
            req = urllib.request.Request(
                f"{COMFYUI_URL}/prompt",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=120)
            result = json.loads(resp.read())
            prompt_id = result.get("prompt_id", "")
        except Exception:
            return None

        # Poll for completion (up to 120s)
        for _ in range(240):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(
                    f"{COMFYUI_URL}/history/{prompt_id}", method="GET"
                )
                resp = urllib.request.urlopen(req, timeout=10)
                history = json.loads(resp.read())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_out in outputs.items():
                        images = node_out.get("images", [])
                        if images:
                            filename = images[0].get("filename", "")
                            subfolder = images[0].get("subfolder", "")
                            img_url = (
                                f"{COMFYUI_URL}/view?"
                                f"filename={filename}&subfolder={subfolder}&type=output"
                            )
                            req2 = urllib.request.Request(img_url, method="GET")
                            img_resp = urllib.request.urlopen(req2, timeout=30)
                            out_path = _OUTPUT_DIR / filename
                            out_path.write_bytes(img_resp.read())
                            return out_path
            except Exception:
                continue

        return None

    def remaining_quota(self) -> int | None:
        return None  # unlimited local
