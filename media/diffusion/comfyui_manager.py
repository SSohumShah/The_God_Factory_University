"""ComfyUI lifecycle manager — install, model download, launch, health check.

All operations are designed to be called from Streamlit UI so students
never need to touch the ComfyUI folder directly.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_COMFYUI_DIR = _ROOT / "ComfyUI-master" / "ComfyUI-master"
_COMFYUI_MAIN = _COMFYUI_DIR / "main.py"
_MODELS_DIR = _COMFYUI_DIR / "models" / "checkpoints"
_DOWNLOAD_DIR = _ROOT / "data" / "_downloads"

COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

COMFYUI_ZIP_URL = "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip"

# Model catalog — small/free models suitable for educational content
MODEL_CATALOG = [
    {
        "name": "SD Turbo",
        "filename": "sd_turbo.safetensors",
        "url": "https://huggingface.co/stabilityai/sd-turbo/resolve/main/sd_turbo.safetensors",
        "size_mb": 2500,
        "description": "Fast 1-step generation, ~2.5 GB",
    },
    {
        "name": "SDXL Turbo",
        "filename": "sdxl_turbo.safetensors",
        "url": "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0.safetensors",
        "size_mb": 6500,
        "description": "Higher quality, 1-4 steps, ~6.5 GB",
    },
]


def is_installed() -> bool:
    """Check if ComfyUI is present."""
    return _COMFYUI_MAIN.exists()


def is_running() -> bool:
    """Check if ComfyUI server is responding."""
    try:
        req = urllib.request.Request(f"{COMFYUI_URL}/system_stats", method="GET")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def get_installed_models() -> list[dict]:
    """List checkpoint models present in ComfyUI models dir."""
    if not _MODELS_DIR.exists():
        return []
    models = []
    for f in _MODELS_DIR.iterdir():
        if f.suffix in (".safetensors", ".ckpt", ".pt"):
            models.append({
                "name": f.stem,
                "filename": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                "path": str(f),
            })
    return models


def get_catalog_status() -> list[dict]:
    """Return model catalog with installed status."""
    installed_names = {m["filename"] for m in get_installed_models()}
    result = []
    for model in MODEL_CATALOG:
        result.append({
            **model,
            "installed": model["filename"] in installed_names,
        })
    return result


def install_comfyui(progress_callback=None) -> tuple[bool, str]:
    """Download and extract ComfyUI from GitHub."""
    try:
        _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = _DOWNLOAD_DIR / "comfyui_master.zip"

        if progress_callback:
            progress_callback("Downloading ComfyUI...")

        req = urllib.request.Request(COMFYUI_ZIP_URL, method="GET")
        req.add_header("User-Agent", "GFU-App/1.0")
        resp = urllib.request.urlopen(req, timeout=300)
        zip_path.write_bytes(resp.read())

        if progress_callback:
            progress_callback("Extracting...")

        extract_to = _ROOT / "ComfyUI-master"
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(str(extract_to))

        # Rename extracted folder if needed (GitHub zips as ComfyUI-master/)
        extracted = extract_to / "ComfyUI-master"
        if not extracted.exists():
            # Find the extracted folder
            subs = [d for d in extract_to.iterdir() if d.is_dir()]
            if subs:
                subs[0].rename(extracted)

        if progress_callback:
            progress_callback("Installing Python dependencies...")

        # Install ComfyUI requirements
        req_file = extracted / "requirements.txt"
        if req_file.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
                capture_output=True, timeout=600,
            )

        # Ensure models directory exists
        (_MODELS_DIR).mkdir(parents=True, exist_ok=True)

        # Clean up zip
        zip_path.unlink(missing_ok=True)

        if progress_callback:
            progress_callback("Done!")

        return True, "ComfyUI installed successfully."
    except Exception as e:
        return False, f"Installation failed: {e}"


def download_model(model_entry: dict, progress_callback=None) -> tuple[bool, str]:
    """Download a model checkpoint to ComfyUI models directory."""
    if not is_installed():
        return False, "ComfyUI is not installed. Install it first."

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _MODELS_DIR / model_entry["filename"]

    if dest.exists():
        return True, "Model already downloaded."

    try:
        if progress_callback:
            progress_callback(f"Downloading {model_entry['name']} (~{model_entry['size_mb']} MB)...")

        req = urllib.request.Request(model_entry["url"], method="GET")
        req.add_header("User-Agent", "GFU-App/1.0")
        resp = urllib.request.urlopen(req, timeout=1800)

        # Stream download to temp then move
        temp = dest.with_suffix(".tmp")
        chunk_size = 1024 * 1024  # 1MB chunks
        downloaded = 0
        with open(temp, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    mb = downloaded / (1024 * 1024)
                    progress_callback(f"Downloading... {mb:.0f} / {model_entry['size_mb']} MB")

        temp.rename(dest)
        if progress_callback:
            progress_callback("Done!")
        return True, f"{model_entry['name']} downloaded successfully."
    except Exception as e:
        # Clean up partial download
        temp = dest.with_suffix(".tmp")
        temp.unlink(missing_ok=True)
        return False, f"Download failed: {e}"


def launch_server() -> tuple[bool, str]:
    """Start ComfyUI server as a background subprocess."""
    if is_running():
        return True, "ComfyUI is already running."
    if not is_installed():
        return False, "ComfyUI is not installed."

    # Auto-install ComfyUI requirements.txt (catches alembic, sqlalchemy, etc.)
    _req_file = _COMFYUI_DIR / "requirements.txt"
    if _req_file.exists():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(_req_file), "--quiet"],
            capture_output=True, timeout=600,
        )
    # Fallback: ensure critical deps individually
    for dep in ["sqlalchemy", "aiohttp", "yarl", "alembic", "blake3"]:
        try:
            __import__(dep)
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", dep, "--quiet"],
                capture_output=True, timeout=120,
            )

    try:
        _log_dir = _ROOT / "data" / "logs"
        _log_dir.mkdir(parents=True, exist_ok=True)
        _log_path = _log_dir / "comfyui_server.log"
        _log_file = open(_log_path, "w", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(_COMFYUI_MAIN),
             "--listen", COMFYUI_HOST,
             "--port", str(COMFYUI_PORT),
             "--preview-method", "none"],
            cwd=str(_COMFYUI_DIR),
            stdout=_log_file,
            stderr=subprocess.STDOUT,
        )
        for _ in range(60):
            time.sleep(0.5)
            if is_running():
                return True, "ComfyUI server started."
        # Read log for diagnostics
        try:
            log_content = _log_path.read_text(encoding="utf-8")[-1500:]
        except Exception:
            log_content = "(no log output)"
        return False, f"Server started but not responding after 30s.\nLog:\n{log_content}"
    except Exception as e:
        return False, f"Launch failed: {e}"


def stop_server() -> tuple[bool, str]:
    """Stop ComfyUI by sending a request (best-effort)."""
    if not is_running():
        return True, "Server is not running."
    # ComfyUI doesn't have a clean shutdown endpoint; we note it
    return True, "ComfyUI will stop when the app closes. To force stop, close the terminal."


def get_status() -> dict:
    """Full status of the ComfyUI installation."""
    installed = is_installed()
    running = is_running() if installed else False
    models = get_installed_models() if installed else []
    has_model = len(models) > 0

    if not installed:
        health = "not_installed"
    elif not has_model:
        health = "no_models"
    elif running:
        health = "ready"
    else:
        health = "stopped"

    return {
        "installed": installed,
        "running": running,
        "health": health,
        "models": models,
        "model_count": len(models),
        "comfyui_path": str(_COMFYUI_DIR),
        "url": COMFYUI_URL if running else None,
    }
