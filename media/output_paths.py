"""Canonical output path helpers for rendered lecture media."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPORTS_ROOT = ROOT / "exports"
VIDEO_CACHE_DIR = EXPORTS_ROOT / "_video_cache"


def _slug(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or "unknown"


def _segment(primary: str | None, fallback: str | None, prefix: str) -> str:
    candidate = (primary or "").strip()
    if candidate:
        return candidate
    backup = _slug(fallback or "")
    if backup and backup != "unknown":
        return backup
    return prefix


def get_exports_root(base_dir: Path | None = None) -> Path:
    return base_dir or EXPORTS_ROOT


def get_video_cache_dir(base_dir: Path | None = None) -> Path:
    root = get_exports_root(base_dir)
    return root / "_video_cache"


def get_course_dir(lecture_data: dict, base_dir: Path | None = None) -> Path:
    root = get_exports_root(base_dir)
    course_id = _segment(lecture_data.get("course_id"), lecture_data.get("course_title"), "unknown_course")
    return root / course_id


def get_module_dir(lecture_data: dict, base_dir: Path | None = None) -> Path:
    course_dir = get_course_dir(lecture_data, base_dir)
    module_id = _segment(lecture_data.get("module_id"), lecture_data.get("module_title"), "unknown_module")
    return course_dir / module_id


def get_full_video_path(lecture_data: dict, base_dir: Path | None = None, suffix: str = "") -> Path:
    module_dir = get_module_dir(lecture_data, base_dir)
    lecture_id = _segment(lecture_data.get("lecture_id") or lecture_data.get("id"), lecture_data.get("title"), "unknown_lecture")
    return module_dir / f"{lecture_id}_full{suffix}.mp4"


def get_scene_video_path(lecture_data: dict, scene_block_id: str, base_dir: Path | None = None, suffix: str = "") -> Path:
    module_dir = get_module_dir(lecture_data, base_dir)
    lecture_id = _segment(lecture_data.get("lecture_id") or lecture_data.get("id"), lecture_data.get("title"), "unknown_lecture")
    block_id = scene_block_id or "X"
    return module_dir / f"{lecture_id}_scene_{block_id}{suffix}.mp4"


def get_metadata_path(lecture_data: dict, base_dir: Path | None = None, suffix: str = "") -> Path:
    module_dir = get_module_dir(lecture_data, base_dir)
    lecture_id = _segment(lecture_data.get("lecture_id") or lecture_data.get("id"), lecture_data.get("title"), "unknown_lecture")
    return module_dir / f"{lecture_id}_render{suffix}.json"


def resolve_full_video_path(lecture_data: dict, base_dir: Path | None = None, suffix: str = "") -> Path:
    root = get_exports_root(base_dir)
    nested = get_full_video_path(lecture_data, root, suffix=suffix)
    if nested.exists():
        return nested
    lecture_id = _segment(lecture_data.get("lecture_id") or lecture_data.get("id"), lecture_data.get("title"), "unknown_lecture")
    legacy = root / f"{lecture_id}_full{suffix}.mp4"
    if legacy.exists():
        return legacy
    return nested


def write_render_metadata(lecture_data: dict, outputs: list[Path], base_dir: Path | None = None,
                          *, chunk_by_scene: bool, suffix: str = "", output_mode: str = "full") -> Path:
    metadata_path = get_metadata_path(lecture_data, base_dir, suffix=suffix)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "course_id": lecture_data.get("course_id", ""),
        "module_id": lecture_data.get("module_id", ""),
        "lecture_id": lecture_data.get("lecture_id") or lecture_data.get("id", ""),
        "title": lecture_data.get("title", ""),
        "chunk_by_scene": chunk_by_scene,
        "suffix": suffix,
        "output_mode": output_mode,
        "rendered_at": time.time(),
        "outputs": [str(path) for path in outputs],
    }
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metadata_path