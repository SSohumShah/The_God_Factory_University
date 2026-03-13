"""
Completely rebuilt video engine for Arcane University.

Core fixes vs the broken original:
  1. Uses imageio-ffmpeg (bundled binary - no system ffmpeg required)
  2. Audio duration is measured FIRST; video is made to match it exactly
  3. Frames are actually animated using MoviePy's VideoClip(make_frame) pattern
  4. No more silent static frames - every second has motion and synced narration

Animation system (pure PIL + NumPy, no external assets):
  - Particle field drifting in background
  - Typewriter text reveal synced to narration pace
  - Animated progress bar
  - Pulsing border / scan-line effect
  - Waveform visualiser strip
  - Keyword tokens appearing at the bottom
  - Section banners for scene metadata
"""

from __future__ import annotations

import json
import math
import random
import re
import time
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ─── Configure moviepy to use bundled ffmpeg ──────────────────────────────────
try:
    import imageio_ffmpeg
    from moviepy.config import change_settings
    change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})
except Exception:
    pass

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    VideoClip,
    concatenate_videoclips,
)

from core.database import get_setting, unlock_achievement, add_xp
from media.audio_engine import (
    BINAURAL_PRESETS,
    SAMPLE_RATE,
    audio_duration,
    generate_ambient,
    generate_binaural,
    synth_tts,
    write_wav_stereo,
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "exports" / "_video_cache"

# ─── Colour palette (dungeon academic) ────────────────────────────────────────
PALETTE = {
    "bg_dark":   (6,  8, 18),
    "bg_mid":    (14, 18, 38),
    "cyan":      (0,  212, 255),
    "gold":      (255, 215, 0),
    "silver":    (192, 192, 220),
    "white":     (255, 255, 255),
    "dim":       (120, 130, 160),
    "red":       (220, 50, 50),
    "green":     (50, 220, 120),
    "border":    (0, 180, 220),
}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap(text: str, chars: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        if len(" ".join(cur + [w])) <= chars:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


# ─── Particle system (deterministic per scene) ────────────────────────────────

def _init_particles(seed: int, W: int, H: int, n: int = 70) -> list[tuple]:
    rng = random.Random(seed)
    return [
        (rng.uniform(0, W), rng.uniform(0, H),
         rng.uniform(-18, 18), rng.uniform(-10, 10),
         rng.uniform(0, math.tau),   # phase
         rng.randint(1, 3))           # size
        for _ in range(n)
    ]


def _draw_particles(draw: ImageDraw.ImageDraw, particles: list[tuple], t: float, W: int, H: int) -> None:
    for px, py, vx, vy, phase, sz in particles:
        x = int((px + vx * t) % W)
        y = int((py + vy * t) % H)
        pulse = 0.5 + 0.5 * math.sin(t * 1.5 + phase)
        brightness = int(60 + 120 * pulse)
        alpha = int(140 + 80 * pulse)
        colour = (0, brightness, min(255, brightness + 60))
        draw.ellipse([x - sz, y - sz, x + sz, y + sz], fill=colour)


# ─── Frame renderer ───────────────────────────────────────────────────────────

def _frame_renderer(lecture: dict, scene: dict, particles: list[tuple],
                    narration_words: list[str], total_duration: float,
                    W: int, H: int) -> Callable[[float], np.ndarray]:
    title_font  = _load_font(max(18, W // 48))
    body_font   = _load_font(max(14, W // 62))
    small_font  = _load_font(max(11, W // 80))
    keyword_font= _load_font(max(12, W // 72))

    lecture_id = lecture.get("lecture_id", "")
    lecture_title = lecture.get("title", "Lecture")
    block_id = scene.get("block_id", "A")
    duration_s = scene.get("duration_s", total_duration)
    visual_text = scene.get("visual_prompt", "")
    keywords = lecture.get("core_terms", [])[:8]
    module_title = lecture.get("module_title", "")

    def make_frame(t: float) -> np.ndarray:
        img = Image.new("RGB", (W, H), PALETTE["bg_dark"])
        draw = ImageDraw.Draw(img)

        # Gradient background strip
        for y in range(H):
            ratio = y / H
            r = int(PALETTE["bg_dark"][0] * (1 - ratio) + PALETTE["bg_mid"][0] * ratio)
            g = int(PALETTE["bg_dark"][1] * (1 - ratio) + PALETTE["bg_mid"][1] * ratio)
            b = int(PALETTE["bg_dark"][2] * (1 - ratio) + PALETTE["bg_mid"][2] * ratio)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Particles
        _draw_particles(draw, particles, t, W, H)

        # Scan-line overlay (every 4 pixels)
        for y in range(0, H, 4):
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, 30))

        # ── Outer border with pulse ──────────────────────────────────────────
        pulse_val = int(160 + 80 * math.sin(t * 2.0))
        border_col = (0, pulse_val, min(255, pulse_val + 60))
        pad = 10
        draw.rectangle([pad, pad, W - pad - 1, H - pad - 1], outline=border_col, width=2)

        # ── Header bar ───────────────────────────────────────────────────────
        header_h = int(H * 0.13)
        draw.rectangle([pad + 2, pad + 2, W - pad - 3, pad + header_h], fill=(10, 20, 45))
        draw.text((pad + 16, pad + 10), f"{lecture_id}  {lecture_title}",
                  fill=PALETTE["cyan"], font=title_font)
        draw.text((pad + 16, pad + header_h - small_font.size - 6 if hasattr(small_font, 'size') else pad + header_h - 20),
                  f"Scene {block_id}  |  {int(duration_s)}s  |  {module_title}",
                  fill=PALETTE["dim"], font=small_font)

        # ── Typewriter narration reveal ───────────────────────────────────────
        reveal_end = total_duration * 0.80
        fraction = min(t / reveal_end, 1.0) if reveal_end > 0 else 1.0
        num_words = max(1, int(len(narration_words) * fraction))
        visible = " ".join(narration_words[:num_words])

        text_y = pad + header_h + 20
        for line in _wrap(visible, W // (body_font.size if hasattr(body_font, 'size') else 8)):
            draw.text((pad + 24, text_y), line, fill=PALETTE["white"], font=body_font)
            text_y += (body_font.size if hasattr(body_font, 'size') else 16) + 6

        # ── Visual prompt label (smaller, dimmed) ────────────────────────────
        vis_y = int(H * 0.62)
        draw.text((pad + 24, vis_y), "[ Visual ]", fill=PALETTE["gold"], font=small_font)
        vis_font_sz = small_font.size if hasattr(small_font, 'size') else 12
        for line in _wrap(visual_text, W // (vis_font_sz // 2 + 1) if vis_font_sz > 0 else 60):
            vis_y += vis_font_sz + 4
            draw.text((pad + 24, vis_y), line, fill=PALETTE["silver"], font=small_font)

        # ── Waveform strip ───────────────────────────────────────────────────
        wave_y = int(H * 0.80)
        wave_h = int(H * 0.06)
        bar_count = W // 4
        for i in range(bar_count):
            phase = (i / bar_count) * math.tau + t * 4
            amp = int(wave_h * 0.5 * (0.4 + 0.6 * abs(math.sin(phase))))
            cx = i * 4 + 2
            cy = wave_y + wave_h // 2
            col_r = int(0 + 40 * math.sin(phase + 1))
            col_g = int(180 * abs(math.sin(phase * 0.7 + t)))
            col_b = int(200 + 55 * math.sin(phase * 1.3))
            draw.line([(cx, cy - amp), (cx, cy + amp)], fill=(col_r, col_g, col_b), width=2)

        # ── Keywords ─────────────────────────────────────────────────────────
        kw_y = int(H * 0.90)
        kw_x = pad + 16
        num_visible_kw = max(1, int(len(keywords) * min(t / max(total_duration * 0.5, 1), 1)))
        for kw in keywords[:num_visible_kw]:
            kw_text = f"  {kw}  "
            kw_w = (keyword_font.size if hasattr(keyword_font, 'size') else 12) * len(kw_text) // 2
            draw.rectangle([kw_x - 2, kw_y - 2, kw_x + kw_w + 2, kw_y + 18], fill=(10, 40, 70), outline=PALETTE["cyan"])
            draw.text((kw_x, kw_y), kw_text, fill=PALETTE["cyan"], font=keyword_font)
            kw_x += kw_w + 12
            if kw_x > W - 100:
                break

        # ── Progress bar ─────────────────────────────────────────────────────
        prog_y = H - pad - 16
        prog_w = W - pad * 2 - 4
        progress = min(t / max(total_duration, 1), 1.0)
        draw.rectangle([pad + 2, prog_y, W - pad - 2, prog_y + 10], fill=(20, 30, 50), outline=PALETTE["dim"])
        fill_w = int(prog_w * progress)
        if fill_w > 0:
            bar_col = (int(0 + 100 * progress), int(200 - 80 * progress), int(255 - 100 * progress))
            draw.rectangle([pad + 2, prog_y, pad + 2 + fill_w, prog_y + 10], fill=bar_col)
        pct = f"{int(progress * 100)}%"
        draw.text((W // 2 - 12, prog_y - 1), pct, fill=PALETTE["dim"], font=small_font)

        # ── Timer overlay ─────────────────────────────────────────────────────
        elapsed = f"{int(t // 60):02d}:{int(t % 60):02d}"
        remaining = f"-{int((total_duration - t) // 60):02d}:{int((total_duration - t) % 60):02d}"
        draw.text((W - pad - 100, pad + 12), elapsed, fill=PALETTE["dim"], font=small_font)
        draw.text((W - pad - 100, pad + 27), remaining, fill=PALETTE["dim"], font=small_font)

        return np.array(img)

    return make_frame


# ─── Scene clip builder ───────────────────────────────────────────────────────

def _build_scene_clip(lecture: dict, scene: dict, temp_dir: Path, voice_id: str, binaural_preset: str) -> VideoClip:
    bid = scene.get("block_id", "A")
    lid = lecture.get("lecture_id", "lec")
    W = int(get_setting("video_width", "960"))
    H = int(get_setting("video_height", "540"))
    fps = int(get_setting("video_fps", "15"))

    # ── Narration script ─────────────────────────────────────────────────────
    narration = (
        f"{lecture.get('title', '')}. "
        f"{scene.get('narration_prompt', '')} "
        f"Key concepts: {', '.join(lecture.get('core_terms', [])[:5])}."
    )

    # ── TTS first so we get the real duration ─────────────────────────────────
    tts_path = temp_dir / f"{lid}_{bid}_tts.mp3"
    synth_tts(narration, tts_path, voice_id=voice_id)
    dur = audio_duration(tts_path)
    if dur < 2.0:
        dur = 30.0  # fallback for broken TTS

    # ── Ambient pad (same duration as TTS) ───────────────────────────────────
    amb_data = generate_ambient(dur, volume=0.10)
    amb_path = temp_dir / f"{lid}_{bid}_amb.wav"
    write_wav_stereo(amb_path, amb_data)

    # ── Binaural layer ────────────────────────────────────────────────────────
    bin_data = generate_binaural(dur, preset=binaural_preset, volume=0.12)
    bin_path = temp_dir / f"{lid}_{bid}_bin.wav"
    write_wav_stereo(bin_path, bin_data)

    # ── Mix audio ─────────────────────────────────────────────────────────────
    try:
        tts_clip  = AudioFileClip(str(tts_path)).volumex(1.0)
        amb_clip  = AudioFileClip(str(amb_path)).volumex(0.35)
        bin_clip  = AudioFileClip(str(bin_path)).volumex(0.20)
        audio_mix = CompositeAudioClip([bin_clip, amb_clip, tts_clip])
    except Exception:
        from moviepy.editor import AudioFileClip as AFC
        audio_mix = AFC(str(tts_path))

    # ── Video frames ──────────────────────────────────────────────────────────
    particles = _init_particles(hash(f"{lid}{bid}") & 0xFFFF, W, H)
    narration_words = narration.split()
    make_frame = _frame_renderer(lecture, scene, particles, narration_words, dur, W, H)

    video = VideoClip(make_frame, duration=dur).set_fps(fps)
    video = video.set_audio(audio_mix)
    return video


# ─── Public API ───────────────────────────────────────────────────────────────

def render_lecture(lecture_data: dict, output_dir: Path, chunk_by_scene: bool = False,
                   fps: int | None = None, width: int | None = None, height: int | None = None,
                   suffix: str = "") -> list[Path]:
    """
    Render a lecture to one (or more) MP4 files.
    lecture_data: the full lecture dict as stored in the DB (data field parsed).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    lid = lecture_data.get("lecture_id", lecture_data.get("id", "lec"))
    temp_dir = CACHE_DIR / f"{lid}_{_slug(lecture_data.get('title', 'lecture'))}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    voice_id = get_setting("voice_id", "en-US-AriaNeural")
    binaural = get_setting("binaural_mode", "gamma_40hz")
    scenes = lecture_data.get("video_recipe", {}).get("scene_blocks", [])

    if not scenes:
        # Auto-generate a single scene from lecture metadata
        scenes = [{
            "block_id": "A",
            "duration_s": lecture_data.get("duration_min", 5) * 60,
            "narration_prompt": f"This lecture covers {lecture_data.get('title', 'the topic')}. "
                                f"We will explore: {', '.join(lecture_data.get('learning_objectives', [])[:3])}.",
            "visual_prompt": f"Educational explainer for {lecture_data.get('title', 'lecture')}.",
            "ambiance": {"music": "ambient", "sfx": "gentle", "color_palette": "cyan and dark"},
        }]

    clips: list[tuple[dict, VideoClip]] = []
    for scene in scenes:
        clip = _build_scene_clip(lecture_data, scene, temp_dir, voice_id, binaural)
        clips.append((scene, clip))

    outputs: list[Path] = []
    ffmpeg_params = ["-preset", "fast"]

    actual_fps = fps or int(get_setting("video_fps", "15"))

    if chunk_by_scene:
        for scene, clip in clips:
            out = output_dir / f"{lid}_scene_{scene.get('block_id', 'X')}{suffix}.mp4"
            clip.write_videofile(str(out), fps=actual_fps, codec="libx264", audio_codec="aac",
                                 ffmpeg_params=ffmpeg_params, verbose=False, logger=None)
            clip.close()
            outputs.append(out)
    else:
        if len(clips) == 1:
            final = clips[0][1]
        else:
            final = concatenate_videoclips([c for _, c in clips], method="compose")
        out = output_dir / f"{lid}_full{suffix}.mp4"
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
    return outputs


def batch_render_all(output_dir: Path, progress_callback=None) -> list[Path]:
    """Render every lecture in the database as full MP4s."""
    from core.database import get_all_courses, get_modules, get_lectures
    import concurrent.futures, json as _json

    all_outputs: list[Path] = []
    jobs: list[dict] = []

    for course in get_all_courses():
        for module in get_modules(course["id"]):
            for lec in get_lectures(module["id"]):
                try:
                    data = _json.loads(lec["data"]) if lec.get("data") else {}
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
            print(f"[batch] Failed {lec_data.get('lecture_id', '?')}: {e}")
        if progress_callback:
            progress_callback(i + 1, total)

    if len(all_outputs) >= 5:
        unlock_achievement("batch_render")
    return all_outputs


# ─── Timeline editor support ─────────────────────────────────────────────────

def reorder_and_render(lecture_data: dict, scene_order: list[str],
                       duration_overrides: dict[str, int],
                       output_dir: Path) -> Path:
    """
    Re-render a lecture with scenes in a custom order and optional duration overrides.
    scene_order: list of block_ids in desired order.
    duration_overrides: {block_id: new_duration_s}
    """
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
