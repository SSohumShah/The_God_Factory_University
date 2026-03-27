"""Frame renderer — particle system, VFX overlays, PIL compositing."""
from __future__ import annotations

import math
import random
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ─── Colour palette (dark academic) ────────────────────────────────────────
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


# ─── Particle system (deterministic per scene) ────────────────────────────────

def init_particles(seed: int, W: int, H: int, n: int = 70) -> list[tuple]:
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
        colour = (0, brightness, min(255, brightness + 60))
        draw.ellipse([x - sz, y - sz, x + sz, y + sz], fill=colour)


# ─── Frame renderer ───────────────────────────────────────────────────────────

def build_frame_renderer(lecture: dict, scene: dict, particles: list[tuple],
                         narration_words: list[str], total_duration: float,
                         W: int, H: int, vfx: dict | None = None,
                         bg_image: Image.Image | None = None) -> Callable[[float], np.ndarray]:
    """Return a make_frame(t) callable for MoviePy VideoClip."""
    vfx = vfx or {}
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
        # Use AI-generated background if available, otherwise gradient
        if bg_image is not None:
            img = bg_image.copy().resize((W, H), Image.BILINEAR)
            # Apply Ken Burns to background image later
        else:
            img = Image.new("RGB", (W, H), PALETTE["bg_dark"])
            draw_bg = ImageDraw.Draw(img)
            for y in range(H):
                ratio = y / H
                r = int(PALETTE["bg_dark"][0] * (1 - ratio) + PALETTE["bg_mid"][0] * ratio)
                g = int(PALETTE["bg_dark"][1] * (1 - ratio) + PALETTE["bg_mid"][1] * ratio)
                b = int(PALETTE["bg_dark"][2] * (1 - ratio) + PALETTE["bg_mid"][2] * ratio)
                draw_bg.line([(0, y), (W, y)], fill=(r, g, b))

        draw = ImageDraw.Draw(img)

        # Particles (respects VFX toggle)
        if vfx.get("ambient_particles", True):
            _draw_particles(draw, particles, t, W, H)

        # Scan-line overlay (every 4 pixels)
        for y in range(0, H, 4):
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, 30))

        # ── Outer border with pulse ──────────────────────────────────────────
        pulse_val = int(160 + 80 * math.sin(t * 2.0))
        border_col = (0, pulse_val, min(255, pulse_val + 60))
        pad = 10
        draw.rectangle([pad, pad, W - pad - 1, H - pad - 1], outline=border_col, width=2)

        # ── Header bar ────────────────────────────────────────────────────────
        if vfx.get("text_overlay", True):
            header_h = int(H * 0.13)
            draw.rectangle([pad + 2, pad + 2, W - pad - 3, pad + header_h], fill=(10, 20, 45))
            draw.text((pad + 16, pad + 10), f"{lecture_id}  {lecture_title}",
                      fill=PALETTE["cyan"], font=title_font)
            draw.text((pad + 16, pad + header_h - small_font.size - 6 if hasattr(small_font, 'size') else pad + header_h - 20),
                      f"Scene {block_id}  |  {int(duration_s)}s  |  {module_title}",
                      fill=PALETTE["dim"], font=small_font)
        else:
            header_h = int(H * 0.05)

        # ── Typewriter narration reveal (windowed to avoid overflow) ────────
        reveal_end = total_duration * 0.80
        fraction = min(t / reveal_end, 1.0) if reveal_end > 0 else 1.0
        num_words = max(1, int(len(narration_words) * fraction))
        visible = " ".join(narration_words[:num_words])

        font_h = body_font.size if hasattr(body_font, 'size') else 16
        line_spacing = font_h + 6
        chars_per_line = max(1, W // max(font_h, 8))
        text_top = pad + header_h + 20
        # Reserve space: stop before waveform area (0.62 * H)
        text_bottom = int(H * 0.58)
        max_visible_lines = max(1, (text_bottom - text_top) // line_spacing)

        all_lines = _wrap(visible, chars_per_line)
        # Sliding window: show only the last N lines that fit
        if len(all_lines) > max_visible_lines:
            all_lines = all_lines[-max_visible_lines:]

        text_y = text_top
        for line in all_lines:
            draw.text((pad + 24, text_y), line, fill=PALETTE["white"], font=body_font)
            text_y += line_spacing

        # ── Visual prompt label — only when NO AI background image ─────────
        if bg_image is None and visual_text:
            vis_y = int(H * 0.60)
            vis_max_y = int(H * 0.76)  # stop before waveform
            draw.text((pad + 24, vis_y), "[ Visual ]", fill=PALETTE["gold"], font=small_font)
            vis_font_sz = small_font.size if hasattr(small_font, 'size') else 12
            for line in _wrap(visual_text, W // (vis_font_sz // 2 + 1) if vis_font_sz > 0 else 60):
                vis_y += vis_font_sz + 4
                if vis_y > vis_max_y:
                    break
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

        # ── Keywords (single row, clipped to width) ────────────────────────
        kw_y = int(H * 0.90)
        kw_x = pad + 16
        kw_max_x = W - pad - 16  # don't draw past right edge
        num_visible_kw = max(1, int(len(keywords) * min(t / max(total_duration * 0.5, 1), 1)))
        for kw in keywords[:num_visible_kw]:
            kw_text = f"  {kw}  "
            kw_w = (keyword_font.size if hasattr(keyword_font, 'size') else 12) * len(kw_text) // 2
            if kw_x + kw_w > kw_max_x:
                break
            draw.rectangle([kw_x - 2, kw_y - 2, kw_x + kw_w + 2, kw_y + 18], fill=(10, 40, 70), outline=PALETTE["cyan"])
            draw.text((kw_x, kw_y), kw_text, fill=PALETTE["cyan"], font=keyword_font)
            kw_x += kw_w + 12

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

        # ── Watermark (VFX toggle) ───────────────────────────────────────────
        if vfx.get("watermark", False):
            wm_text = "The God Factory University"
            draw.text((W - pad - 220, H - pad - 30), wm_text, fill=(60, 60, 80), font=small_font)

        frame = np.array(img)

        # ── Cinematic color grading ──────────────────────────────────────────
        if vfx.get("color_grade", True):
            frame = frame.astype(np.float32)
            frame[:, :, 0] = np.clip(frame[:, :, 0] * 0.95, 0, 255)
            frame[:, :, 1] = np.clip(frame[:, :, 1] * 1.0, 0, 255)
            frame[:, :, 2] = np.clip(frame[:, :, 2] * 1.08, 0, 255)
            frame = frame.astype(np.uint8)

        # ── Ken Burns pan/zoom ───────────────────────────────────────────────
        if vfx.get("ken_burns", True):
            progress = t / max(total_duration, 1)
            zoom = 1.0 + 0.05 * progress
            cH, cW = frame.shape[:2]
            new_h = int(cH / zoom)
            new_w = int(cW / zoom)
            y_off = int((cH - new_h) / 2 * (0.5 + 0.5 * math.sin(progress * math.pi)))
            x_off = int((cW - new_w) / 2)
            cropped = frame[y_off:y_off + new_h, x_off:x_off + new_w]
            if cropped.shape[0] > 0 and cropped.shape[1] > 0:
                resized = Image.fromarray(cropped).resize((cW, cH), Image.BILINEAR)
                frame = np.array(resized)

        return frame

    return make_frame
