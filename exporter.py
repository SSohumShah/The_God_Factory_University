import json
import math
import re
import wave
from pathlib import Path

import numpy as np
import pyttsx3
from moviepy.editor import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
COURSE_FILE = ROOT / "notes.txt"
CACHE_DIR = ROOT / "exports" / "_cache"


def load_course() -> dict:
    return json.loads(COURSE_FILE.read_text(encoding="utf-8"))


def all_lectures(course: dict) -> list[dict]:
    rows = []
    for module in course.get("modules", []):
        for lecture in module.get("lectures", []):
            rows.append({"module_title": module.get("title", ""), **lecture})
    return rows


def find_lecture(course: dict, lecture_id: str) -> dict:
    for lec in all_lectures(course):
        if lec.get("lecture_id") == lecture_id:
            return lec
    raise ValueError(f"Lecture not found: {lecture_id}")


def slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _gradient_background(width: int, height: int, start, end) -> Image.Image:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / max(1, height - 1)
        arr[y, :, :] = [int(start[i] * (1 - t) + end[i] * t) for i in range(3)]
    return Image.fromarray(arr, mode="RGB")


def make_scene_image(lecture: dict, scene: dict, out_path: Path, width: int = 1920, height: int = 1080) -> None:
    bg = _gradient_background(width, height, (14, 20, 30), (25, 70, 90))
    draw = ImageDraw.Draw(bg)

    try:
        font_title = ImageFont.truetype("arial.ttf", 56)
        font_body = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    title = f"{lecture.get('lecture_id', '')}  {lecture.get('title', '')}"
    scene_line = f"Scene {scene.get('block_id', 'X')}  |  {scene.get('duration_s', 120)}s"
    visual_prompt = scene.get("visual_prompt", "")
    narration_prompt = scene.get("narration_prompt", "")

    draw.rectangle([(80, 80), (1840, 1000)], outline=(120, 220, 255), width=3)
    draw.text((120, 130), title, fill=(235, 245, 250), font=font_title)
    draw.text((120, 220), scene_line, fill=(170, 220, 240), font=font_small)

    y = 310
    for line in wrap_text(f"Visual: {visual_prompt}", 74):
        draw.text((120, y), line, fill=(240, 250, 255), font=font_body)
        y += 48

    y += 18
    for line in wrap_text(f"Narration: {narration_prompt}", 74):
        draw.text((120, y), line, fill=(220, 235, 245), font=font_body)
        y += 48

    tags = ", ".join(lecture.get("core_terms", [])[:6])
    draw.text((120, 930), f"Keywords: {tags}", fill=(160, 210, 230), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path)


def wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines = []
    cur = []
    for w in words:
        test = " ".join(cur + [w])
        if len(test) <= width:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def synth_tts_wav(text: str, out_path: Path, rate: int = 170) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    return out_path


def synth_ambient_wav(out_path: Path, duration_s: int, sample_rate: int = 22050) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    base = 0.06 * np.sin(2.0 * math.pi * 130.0 * t)
    overtone = 0.03 * np.sin(2.0 * math.pi * 260.0 * t)
    slow = 0.02 * np.sin(2.0 * math.pi * 0.25 * t)
    noise = 0.005 * np.random.randn(len(t))
    signal = np.clip(base + overtone + slow + noise, -1.0, 1.0)
    pcm = (signal * 32767).astype(np.int16)

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return out_path


def scene_script(lecture: dict, scene: dict) -> str:
    return (
        f"{lecture.get('title', '')}. "
        f"{scene.get('narration_prompt', '')} "
        f"Key terms: {', '.join(lecture.get('core_terms', [])[:5])}."
    )


def render_scene_clip(lecture: dict, scene: dict, temp_dir: Path) -> ImageClip:
    sid = scene.get("block_id", "X")
    duration = int(scene.get("duration_s", 120))

    image_path = temp_dir / f"scene_{sid}.png"
    tts_path = temp_dir / f"scene_{sid}_tts.wav"
    amb_path = temp_dir / f"scene_{sid}_amb.wav"

    make_scene_image(lecture, scene, image_path)
    synth_tts_wav(scene_script(lecture, scene), tts_path)
    synth_ambient_wav(amb_path, duration)

    base_clip = ImageClip(str(image_path)).set_duration(duration)
    tts_audio = AudioFileClip(str(tts_path)).volumex(1.0)
    amb_audio = AudioFileClip(str(amb_path)).volumex(0.35)

    mixed = CompositeAudioClip([amb_audio, tts_audio.set_start(0)])
    return base_clip.set_audio(mixed)


def export_lecture(lecture_id: str, output_dir: Path, chunk_by_scene: bool) -> list[Path]:
    course = load_course()
    lecture = find_lecture(course, lecture_id)
    scenes = lecture.get("video_recipe", {}).get("scene_blocks", [])
    if not scenes:
        raise ValueError("Lecture has no scene_blocks")

    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = CACHE_DIR / f"{lecture_id}_{slug(lecture.get('title', 'lecture'))}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    scene_clips = []

    for scene in scenes:
        clip = render_scene_clip(lecture, scene, temp_dir)
        scene_clips.append((scene, clip))

    if chunk_by_scene:
        for scene, clip in scene_clips:
            block_id = scene.get("block_id", "X")
            out_path = output_dir / f"{lecture_id}_scene_{block_id}.mp4"
            clip.write_videofile(str(out_path), fps=30, codec="libx264", audio_codec="aac", verbose=False, logger=None)
            outputs.append(out_path)
            clip.close()
        return outputs

    final = concatenate_videoclips([c for _, c in scene_clips], method="compose")
    out_path = output_dir / f"{lecture_id}_full.mp4"
    final.write_videofile(str(out_path), fps=30, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    final.close()

    for _, clip in scene_clips:
        clip.close()

    outputs.append(out_path)
    return outputs
