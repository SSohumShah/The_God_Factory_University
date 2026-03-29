"""Encoder — final rendering, batch export, timeline support."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable

from core.database import get_setting, unlock_achievement, add_xp
from core.logger import log_render, log_error
from core.tts_config import get_tts_settings
from media.output_paths import (
    get_full_video_path,
    get_scene_video_path,
    get_video_cache_dir,
    write_render_metadata,
)
from media.video.scene_builder import build_scene_clip, load_vfx_config, assemble_clips

CACHE_DIR = get_video_cache_dir()


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def render_lecture(lecture_data: dict, output_dir: Path, chunk_by_scene: bool = False,
                   fps: int | None = None, width: int | None = None, height: int | None = None,
                   suffix: str = "", output_mode: str = "full") -> list[Path]:
    """Render a lecture to one (or more) MP4 files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _render_t0 = time.time()
    lid = lecture_data.get("lecture_id", lecture_data.get("id", "lec"))
    temp_dir = CACHE_DIR / f"{lid}_{_slug(lecture_data.get('title', 'lecture'))}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    tts_settings = get_tts_settings()
    scenes = lecture_data.get("video_recipe", {}).get("scene_blocks", [])

    if not scenes:
        scenes = [{
            "block_id": "A",
            "duration_s": lecture_data.get("duration_min", 5) * 60,
            "narration_prompt": f"This lecture covers {lecture_data.get('title', 'the topic')}. "
                                f"We will explore: {', '.join(lecture_data.get('learning_objectives', [])[:3])}.",
            "visual_prompt": f"Educational explainer for {lecture_data.get('title', 'lecture')}.",
            "ambiance": {"music": "ambient", "sfx": "gentle", "color_palette": "cyan and dark"},
        }]

    # ── Try to get AI-generated background for scenes with visual_prompt ─────
    bg_images: dict[str, "Image.Image | None"] = {}
    try:
        from media.diffusion.free_tier_cycler import generate_image_with_fallback
        gen_count = 0
        for i, scene in enumerate(scenes):
            visual = scene.get("visual_prompt", "")
            bid = scene.get("block_id", "?")
            if visual and "title card" not in visual.lower():
                try:
                    img_path, prov_name = generate_image_with_fallback(
                        visual, 960, 540,
                        course_id=lecture_data.get("course_id", ""),
                        lecture_id=lid,
                    )
                    if img_path and img_path.exists():
                        from PIL import Image
                        bg_images[bid] = Image.open(img_path).convert("RGB")
                        gen_count += 1
                        log_render(lid, "img_gen_ok", scene=bid, provider=prov_name)
                    else:
                        log_render(lid, "img_gen_miss", scene=bid,
                                   reason="all_providers_returned_none")
                except Exception as img_err:
                    log_error(f"Image gen failed for scene {bid}: {img_err}",
                              category="diffusion", error_id="IMG_GEN_FAIL")
        log_render(lid, "img_gen_done", generated=gen_count, total=len(scenes))
    except ImportError:
        log_render(lid, "img_gen_skip", reason="diffusion_not_installed")

    clips: list[tuple[dict, "VideoClip"]] = []
    failed_scenes: list[str] = []
    total_scenes = len(scenes)
    for scene_idx, scene in enumerate(scenes):
        bid = scene.get("block_id", "?")
        clip = None
        bg_img = bg_images.get(bid)
        for attempt in range(2):
            try:
                clip = build_scene_clip(lecture_data, scene, temp_dir, tts_settings,
                                        output_mode=output_mode, bg_image=bg_img,
                                        scene_index=scene_idx, total_scenes=total_scenes)
                break
            except Exception as e:
                if attempt == 0:
                    log_error(f"Scene {bid} attempt 1 failed: {e}, retrying",
                              category="render", error_id="SCENE_RETRY")
                else:
                    log_error(f"Scene {bid} failed after retry: {e}",
                              category="render", error_id="SCENE_FAIL")
                    failed_scenes.append(bid)
        if clip is not None:
            clips.append((scene, clip))

    outputs: list[Path] = []
    ffmpeg_params = ["-preset", "fast", "-movflags", "+faststart"]
    vfx = load_vfx_config()
    actual_fps = fps or int(get_setting("video_fps", "15"))

    if not clips:
        log_error(f"No valid clips for {lid} — nothing to render",
                  category="render", error_id="NO_CLIPS")
        return outputs

    if chunk_by_scene:
        for scene, clip in clips:
            out = get_scene_video_path(lecture_data, str(scene.get("block_id", "X")), output_dir, suffix=suffix)
            out.parent.mkdir(parents=True, exist_ok=True)
            clip.write_videofile(str(out), fps=actual_fps, codec="libx264", audio_codec="aac",
                                 ffmpeg_params=ffmpeg_params, verbose=False, logger=None)
            clip.close()
            outputs.append(out)
    else:
        final = assemble_clips(clips, vfx)
        out = get_full_video_path(lecture_data, output_dir, suffix=suffix)
        out.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(str(out), fps=actual_fps, codec="libx264", audio_codec="aac",
                              ffmpeg_params=ffmpeg_params, verbose=False, logger=None)
        final.close()
        outputs.append(out)

    for _, c in clips:
        try:
            c.close()
        except Exception:
            pass

    unlock_achievement("video_render")
    add_xp(100, f"Rendered lecture {lid}", "video")
    log_render(lid, "completed", duration_s=time.time() - _render_t0, scenes=len(scenes))
    write_render_metadata(lecture_data, outputs, output_dir, chunk_by_scene=chunk_by_scene, suffix=suffix, output_mode=output_mode)
    return outputs


def batch_render_all(output_dir: Path, progress_callback: Callable | None = None) -> dict:
    """Render every lecture in the database as full MP4s."""
    from core.database import get_all_courses, get_modules, get_lectures

    all_outputs: list[Path] = []
    jobs: list[dict] = []
    errors: list[str] = []
    t0 = time.time()

    for course in get_all_courses():
        for module in get_modules(course["id"]):
            for lec in get_lectures(module["id"]):
                try:
                    data = json.loads(lec["data"]) if lec.get("data") else {}
                    data.setdefault("lecture_id", lec["id"])
                    data.setdefault("title", lec["title"])
                    jobs.append(data)
                except Exception:
                    pass

    total = len(jobs)
    for i, lec_data in enumerate(jobs):
        try:
            outs = render_lecture(lec_data, output_dir)
            all_outputs.extend(outs)
        except Exception as e:
            err_msg = f"{lec_data.get('lecture_id', '?')}: {e}"
            errors.append(err_msg)
            log_error(f"Batch render failed: {err_msg}",
                      category="render", error_id="BATCH_RENDER_FAIL")
        if progress_callback:
            progress_callback(i + 1, total)

    if len(all_outputs) >= 5:
        unlock_achievement("batch_render")

    elapsed = time.time() - t0
    log_render("batch", "completed", duration_s=elapsed,
               total=total, succeeded=len(all_outputs), failed=len(errors))

    return {
        "outputs": all_outputs,
        "total": total,
        "succeeded": len(all_outputs),
        "failed": len(errors),
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
    }


def reorder_and_render(lecture_data: dict, scene_order: list[str],
                       duration_overrides: dict[str, int],
                       output_dir: Path) -> Path:
    """Re-render a lecture with scenes in a custom order and optional duration overrides."""
    original_scenes = {s["block_id"]: s for s in lecture_data.get("video_recipe", {}).get("scene_blocks", [])}
    reordered = []
    for bid in scene_order:
        if bid in original_scenes:
            scene = original_scenes[bid].copy()
            if bid in duration_overrides:
                scene["duration_s"] = duration_overrides[bid]
            reordered.append(scene)

    modified = {**lecture_data}
    modified.setdefault("video_recipe", {})["scene_blocks"] = reordered
    return render_lecture(modified, output_dir, chunk_by_scene=False)[0]
