"""Scene clip assembly — TTS, audio mixing, clip construction."""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from core.database import get_setting
from core.tts_config import get_tts_settings
from media.audio_engine import (
    audio_duration,
    generate_ambient,
    generate_binaural,
    synth_tts,
    write_wav_stereo,
)
from media.video.frame_renderer import build_frame_renderer, init_particles

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


# ─── VFX config loader ────────────────────────────────────────────────────────

def load_vfx_config() -> dict:
    """Load VFX configuration from settings. Returns defaults if not set."""
    raw = get_setting("vfx_config", "")
    defaults = {
        "transitions": True,
        "ken_burns": True,
        "color_grade": True,
        "text_overlay": True,
        "ambient_particles": True,
        "watermark": False,
    }
    if raw:
        try:
            cfg = json.loads(raw)
            defaults.update(cfg)
        except (json.JSONDecodeError, ValueError):
            pass
    return defaults


def _build_narration_script(lecture: dict, scene: dict, scene_index: int, total_scenes: int) -> str:
    """Build a full narration script for a scene that fills the target duration.

    Average speaking rate is ~150 words/minute. For a 120s scene we need ~300 words.
    We expand the narration_prompt with objectives, terms, visual descriptions,
    and transitional phrases to create a full-length lecture segment.
    """
    title = lecture.get("title", "this topic")
    course_title = lecture.get("course_title", "")
    module_title = lecture.get("module_title", "")
    narration_prompt = scene.get("narration_prompt", "")
    visual_prompt = scene.get("visual_prompt", "")
    objectives = lecture.get("learning_objectives", [])
    terms = lecture.get("core_terms", [])
    target_s = scene.get("duration_s", 60)
    # ~2.5 words/second for natural speech
    target_words = max(int(target_s * 2.5), 50)

    arc_type = scene.get("block_id", "").split("_")[-1] if "_" in scene.get("block_id", "") else ""
    narrative_arc = lecture.get("video_recipe", {}).get("narrative_arc", [])

    parts: list[str] = []

    # Opening — adapt based on position in lecture
    if scene_index == 0:
        if course_title:
            parts.append(f"Welcome to {title}, part of {course_title}.")
        else:
            parts.append(f"Welcome to today's lecture on {title}.")
        if module_title:
            parts.append(f"This lesson is part of our module on {module_title}.")
        if objectives:
            parts.append("By the end of this session, you should be able to:")
            for obj in objectives:
                parts.append(f"  {obj}.")
    elif scene_index == total_scenes - 1:
        parts.append(f"Let's wrap up our discussion of {title}.")
    else:
        parts.append(f"Continuing our exploration of {title}.")

    # Core content — the narration prompt is the main directive
    if narration_prompt:
        parts.append(narration_prompt)

    # NOTE: visual_prompt is for diffusion models only — never narrate it.

    # Expand with terminology with actual definitions for non-summary scenes
    if scene_index < total_scenes - 1 and terms:
        scene_terms = terms[scene_index * 3:(scene_index + 1) * 3] or terms[:3]
        if scene_terms:
            parts.append("Let's break down some key concepts you need to know.")
            for term in scene_terms:
                parts.append(
                    f"First, let's talk about {term}. "
                    f"In the context of {title}, {term} refers to a core concept "
                    f"that you will encounter repeatedly. Pay special attention to how "
                    f"{term} connects to the other topics we cover in this lecture."
                )

    # Summary/closing for last scene
    if scene_index == total_scenes - 1:
        if terms:
            parts.append(
                f"To recap, the key terms we've covered include: "
                f"{', '.join(terms[:8])}."
            )
        if objectives:
            parts.append("Remember our learning objectives:")
            for obj in objectives:
                parts.append(f"  {obj}.")
        parts.append(
            "Take a moment to review these concepts. Practice is the best way "
            "to reinforce what you've learned. In the next lecture, we'll build "
            "on these ideas."
        )

    script = " ".join(parts)

    # If still too short, pad with educational filler tied to the topic
    current_words = len(script.split())
    if current_words < target_words:
        gap = target_words - current_words
        filler_parts = []
        if objectives:
            for obj in objectives:
                filler_parts.append(
                    f"Let me elaborate further. {obj}. "
                    f"This is a concept that comes up frequently in practice, "
                    f"and understanding it deeply will help you in more advanced topics."
                )
                if len(" ".join(filler_parts).split()) >= gap:
                    break
        if len(" ".join(filler_parts).split()) < gap:
            for term in terms:
                filler_parts.append(
                    f"Another important point about {term}: this concept connects "
                    f"to many areas of study. As you progress, you'll see {term} "
                    f"appear in different contexts, each adding new layers of understanding."
                )
                if len(" ".join(filler_parts).split()) >= gap:
                    break
        script += " " + " ".join(filler_parts)

    # Strip praise/compliment language — lectures are not interactive
    _PRAISE_RE = re.compile(
        r"\b(good job|well done|great work|excellent|you('re| are) doing (great|amazing|wonderful)"
        r"|congratulations|bravo|keep it up|nice work|fantastic job)\b",
        re.IGNORECASE,
    )
    script = _PRAISE_RE.sub("", script)
    # Clean up any artifacts (double spaces, orphan punctuation)
    script = re.sub(r"[.!,]\s*[.!,]", ".", script)
    script = re.sub(r"  +", " ", script)

    return script.strip()


def _sanitize_for_tts(text: str) -> str:
    """Strip markdown, special chars, and formatting that breaks TTS engines."""
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove bullet/list markers
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    # Remove backticks (inline code)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove code fences
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


def build_scene_clip(lecture: dict, scene: dict, temp_dir: Path, tts_settings: dict,
                     output_mode: str = "full", bg_image=None,
                     scene_index: int = 0, total_scenes: int = 1) -> VideoClip:
    """Build a single scene's video clip with audio layers."""
    bid = scene.get("block_id", "A")
    lid = lecture.get("lecture_id", "lec")
    W = int(get_setting("video_width", "960"))
    H = int(get_setting("video_height", "540"))
    fps = int(get_setting("video_fps", "15"))
    target_dur = scene.get("duration_s", 60)

    # ── Build full narration script ──────────────────────────────────────────
    narration = _build_narration_script(lecture, scene, scene_index, total_scenes)
    narration = _sanitize_for_tts(narration)

    # ── TTS — generates the actual audio ─────────────────────────────────────
    tts_path = temp_dir / f"{lid}_{bid}_tts.mp3"
    synth_tts(
        narration,
        tts_path,
        voice_id=str(tts_settings["voice_id"]),
        rate=str(tts_settings["rate_str"]),
        pitch=str(tts_settings["pitch_str"]),
    )
    tts_dur = audio_duration(tts_path)
    if tts_dur < 2.0:
        tts_dur = 30.0  # fallback for broken TTS

    # Use the longer of TTS duration or target scene duration
    dur = max(tts_dur, target_dur)

    # ── Ambient pad (same duration as TTS) ───────────────────────────────────
    amb_data = generate_ambient(dur, volume=0.10)
    amb_path = temp_dir / f"{lid}_{bid}_amb.wav"
    write_wav_stereo(amb_path, amb_data)

    # ── Binaural layer ────────────────────────────────────────────────────────
    bin_data = generate_binaural(dur, preset=str(tts_settings["binaural"]), volume=0.12)
    bin_path = temp_dir / f"{lid}_{bid}_bin.wav"
    write_wav_stereo(bin_path, bin_data)

    # ── Mix audio ─────────────────────────────────────────────────────────────
    try:
        layers = []
        if output_mode in ("full", "music_only"):
            layers.append(AudioFileClip(str(amb_path)).volumex(0.35))
            layers.append(AudioFileClip(str(bin_path)).volumex(0.20))
        if output_mode in ("full", "narration_only"):
            tts_clip = AudioFileClip(str(tts_path)).volumex(1.0)
            layers.append(tts_clip)
        audio_mix = CompositeAudioClip(layers) if layers else AudioFileClip(str(tts_path))
        # Truncate audio to video duration to prevent container corruption
        audio_mix = audio_mix.set_duration(dur)
    except Exception:
        audio_mix = AudioFileClip(str(tts_path)).set_duration(dur)

    # ── Video frames ──────────────────────────────────────────────────────────
    vfx = load_vfx_config()
    particles = init_particles(hash(f"{lid}{bid}") & 0xFFFF, W, H)
    narration_words = narration.split()
    make_frame = build_frame_renderer(lecture, scene, particles, narration_words, dur, W, H,
                                      vfx=vfx, bg_image=bg_image)

    video = VideoClip(make_frame, duration=dur).set_fps(fps)
    video = video.set_audio(audio_mix)
    return video


def assemble_clips(clips: list[tuple[dict, VideoClip]], vfx: dict) -> VideoClip:
    """Assemble scene clips into a single lecture clip with optional crossfades."""
    if len(clips) == 1:
        return clips[0][1]

    if vfx.get("transitions", True) and len(clips) > 1:
        try:
            crossfade_dur = 0.5
            scene_clips = [c for _, c in clips]
            composed = [scene_clips[0]]
            for i in range(1, len(scene_clips)):
                composed.append(scene_clips[i].crossfadein(crossfade_dur))
            return concatenate_videoclips(composed, padding=-crossfade_dur, method="compose")
        except Exception:
            pass

    return concatenate_videoclips([c for _, c in clips], method="compose")
