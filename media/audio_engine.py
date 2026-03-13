"""
Audio engine for Arcane University.

Features:
- Edge-TTS (Microsoft Neural, 300+ voices, free – best quality)
- pyttsx3 fallback (fully offline)
- Procedural ambient pads (sine + overtone synthesis)
- Binaural beats for learning:
    gamma_40hz  - 40Hz: peak cognition, focus (most studied)
    alpha_10hz  - 10Hz: relaxed learning, information absorption
    beta_18hz   - 18Hz: active problem solving, concentration
    theta_6hz   - 6Hz:  creative insight, deep reflection
- SFX generator: clicks, chimes, rewards, alerts (all pure math, no files)
"""

from __future__ import annotations

import asyncio
import io
import math
import wave
from pathlib import Path
from typing import Literal

import numpy as np

SAMPLE_RATE = 44100
CACHE_DIR = Path(__file__).resolve().parent.parent / "exports" / "_audio_cache"

VOICES = {
    "Aria (US Female, Natural)":     "en-US-AriaNeural",
    "Guy (US Male, Warm)":           "en-US-GuyNeural",
    "Jenny (US Female, Friendly)":   "en-US-JennyNeural",
    "Davis (US Male, Casual)":       "en-US-DavisNeural",
    "Brian (US Male, Deep)":         "en-US-BrianNeural",
    "Amber (US Female, Warm)":       "en-US-AmberNeural",
    "Emma (US Female, Expressive)":  "en-US-EmmaNeural",
    "Andrew (US Male, Confident)":   "en-US-AndrewNeural",
    "Sonia (UK Female)":             "en-GB-SoniaNeural",
    "Ryan (UK Male)":                "en-GB-RyanNeural",
    "Natasha (AU Female)":           "en-AU-NatashaNeural",
    "William (AU Male)":             "en-AU-WilliamNeural",
    "Clara (CA Female)":             "en-CA-ClaraNeural",
}

BINAURAL_PRESETS = {
    "gamma_40hz":  {"label": "Gamma 40Hz (Peak Focus)",        "base": 200, "beat": 40},
    "beta_18hz":   {"label": "Beta 18Hz (Active Concentration)","base": 180, "beat": 18},
    "alpha_10hz":  {"label": "Alpha 10Hz (Relaxed Learning)",   "base": 150, "beat": 10},
    "theta_6hz":   {"label": "Theta 6Hz (Creative Insight)",    "base": 130, "beat": 6},
    "none":        {"label": "None (No Binaural Layer)",         "base": 0,   "beat": 0},
}


# ─── TTS ──────────────────────────────────────────────────────────────────────

def synth_tts(text: str, out_path: Path, voice_id: str = "en-US-AriaNeural", rate: str = "+0%", pitch: str = "+0Hz") -> Path:
    """Synthesize speech. Tries edge-tts first, falls back to pyttsx3."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _synth_edge_tts(text, out_path, voice_id, rate, pitch)
        if out_path.exists() and out_path.stat().st_size > 1000:
            return out_path
    except Exception:
        pass
    _synth_pyttsx3(text, out_path)
    return out_path


def _synth_edge_tts(text: str, out_path: Path, voice: str, rate: str, pitch: str) -> None:
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(str(out_path))

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _run()).result()
        else:
            loop.run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())


def _synth_pyttsx3(text: str, out_path: Path) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()


def audio_duration(path: Path) -> float:
    """Return duration of an audio file in seconds."""
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(str(path)) as clip:
            return clip.duration
    except Exception:
        try:
            with wave.open(str(path)) as w:
                return w.getnframes() / w.getframerate()
        except Exception:
            return 30.0


# ─── Binaural beats ───────────────────────────────────────────────────────────

def generate_binaural(duration_s: float, preset: str = "gamma_40hz", volume: float = 0.18) -> np.ndarray:
    """
    Returns stereo int16 array (shape: [N, 2]).
    Left ear = base_freq, Right ear = base_freq + beat_freq.
    The beating frequency between channels induces the target brainwave band.
    Science refs: Oster (1973), Lavallee et al. (2011), Kraus & Bhatt (2020).
    """
    p = BINAURAL_PRESETS.get(preset, BINAURAL_PRESETS["gamma_40hz"])
    base_freq = p["base"]
    beat_freq = p["beat"]
    if base_freq == 0:
        n = int(SAMPLE_RATE * duration_s)
        return np.zeros((n, 2), dtype=np.int16)

    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    # Carrier tones
    left  = np.sin(2 * math.pi * base_freq * t)
    right = np.sin(2 * math.pi * (base_freq + beat_freq) * t)
    # Add subtle harmonics to sound like a pad, not a pure tone
    left  += 0.3 * np.sin(2 * math.pi * base_freq * 2 * t)
    right += 0.3 * np.sin(2 * math.pi * (base_freq + beat_freq) * 2 * t)
    # Amplitude envelope: fade in/out over 3 seconds
    fade_samples = min(int(3 * SAMPLE_RATE), len(t) // 4)
    fade_in  = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    envelope = np.ones(len(t))
    envelope[:fade_samples] = fade_in
    envelope[-fade_samples:] = fade_out
    left  = (left  * envelope * volume).clip(-1, 1)
    right = (right * envelope * volume).clip(-1, 1)
    stereo = np.stack([left, right], axis=1)
    return (stereo * 32767).astype(np.int16)


# ─── Ambient pad ──────────────────────────────────────────────────────────────

def generate_ambient(duration_s: float, key_note: str = "A", volume: float = 0.12) -> np.ndarray:
    """
    Synthesize an atmospheric ambient pad using additive synthesis.
    Returns stereo int16 (shape: [N, 2]).
    """
    NOTE_FREQS = {
        "C": 130.81, "D": 146.83, "E": 164.81, "F": 174.61,
        "G": 196.00, "A": 220.00, "B": 246.94,
    }
    base = NOTE_FREQS.get(key_note, 220.0)
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)

    # Chord: root + major third + fifth
    chord_freqs = [base, base * 1.25, base * 1.5, base * 2.0]
    wave_sum = np.zeros(len(t))
    for i, freq in enumerate(chord_freqs):
        amp = volume / (i + 1)
        wave_sum += amp * np.sin(2 * math.pi * freq * t)
        # Subtle tremolo
        tremolo = 1 + 0.04 * np.sin(2 * math.pi * 0.3 * t + i)
        wave_sum *= tremolo

    # Slow amplitude modulation (breathing effect)
    breathe = 0.85 + 0.15 * np.sin(2 * math.pi * 0.08 * t)
    wave_sum *= breathe

    # Fade
    fade = min(int(4 * SAMPLE_RATE), len(t) // 4)
    wave_sum[:fade] *= np.linspace(0, 1, fade)
    wave_sum[-fade:] *= np.linspace(1, 0, fade)
    wave_sum = wave_sum.clip(-1, 1)

    stereo = np.stack([wave_sum, wave_sum], axis=1)
    return (stereo * 32767).astype(np.int16)


# ─── SFX ──────────────────────────────────────────────────────────────────────

SFX_PRESETS = {
    "click":    {"type": "click",   "freq": 800,  "duration": 0.04},
    "success":  {"type": "chime",   "freq": 880,  "duration": 0.4, "notes": [880, 1108, 1320]},
    "unlock":   {"type": "fanfare", "freq": 440,  "duration": 0.8, "notes": [440, 554, 659, 880]},
    "error":    {"type": "buzz",    "freq": 180,  "duration": 0.25},
    "xp_gain":  {"type": "chime",   "freq": 660,  "duration": 0.3, "notes": [660, 770]},
    "level_up": {"type": "fanfare", "freq": 528,  "duration": 1.2, "notes": [528, 660, 784, 1056]},
    "page_turn":{"type": "click",   "freq": 400,  "duration": 0.06},
    "collect":  {"type": "chime",   "freq": 1047, "duration": 0.2, "notes": [1047, 1319]},
}


def generate_sfx_bytes(sfx_name: str) -> bytes:
    """Generate a sound effect as WAV bytes (for st.audio or HTML autoplay)."""
    preset = SFX_PRESETS.get(sfx_name, SFX_PRESETS["click"])
    sfx_type = preset["type"]
    duration = preset["duration"]
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)

    if sfx_type == "click":
        freq = preset["freq"]
        signal = np.sin(2 * math.pi * freq * t) * np.exp(-20 * t)

    elif sfx_type == "chime":
        signal = np.zeros(len(t))
        notes = preset.get("notes", [preset["freq"]])
        for i, freq in enumerate(notes):
            onset = int(i * 0.08 * SAMPLE_RATE)
            remaining = len(t) - onset
            if remaining <= 0:
                continue
            t_local = t[:remaining]
            note = np.sin(2 * math.pi * freq * t_local) * np.exp(-5 * t_local)
            signal[onset:onset + remaining] += note
        signal *= 0.5

    elif sfx_type == "fanfare":
        signal = np.zeros(len(t))
        notes = preset.get("notes", [preset["freq"]])
        step = len(t) // len(notes)
        for i, freq in enumerate(notes):
            start = i * step
            end = min(start + step + step // 2, len(t))
            t_local = t[start:end] - t[start]
            sustain = int(len(t_local) * 0.7)
            attack_decay = np.exp(-2 * t_local[:sustain]) if sustain > 0 else np.array([])
            note_env = np.concatenate([attack_decay, np.linspace(attack_decay[-1] if len(attack_decay) else 1, 0, len(t_local) - sustain)])
            signal[start:end] += np.sin(2 * math.pi * freq * t_local) * note_env * 0.4
            signal[start:end] += 0.15 * np.sin(2 * math.pi * freq * 2 * t_local) * note_env

    elif sfx_type == "buzz":
        freq = preset["freq"]
        signal = np.sign(np.sin(2 * math.pi * freq * t)) * np.exp(-8 * t) * 0.3

    else:
        signal = np.zeros(len(t))

    signal = signal.clip(-1, 1)
    mono = (signal * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(mono.tobytes())
    return buf.getvalue()


def write_wav_stereo(path: Path, data: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())


def mix_audio_files(tts_path: Path, ambient_path: Path, out_path: Path,
                    tts_vol: float = 1.0, amb_vol: float = 0.3) -> Path:
    """Mix TTS and ambient WAV files into a single stereo WAV."""
    try:
        from moviepy.editor import AudioFileClip, CompositeAudioClip
        tts = AudioFileClip(str(tts_path)).volumex(tts_vol)
        amb = AudioFileClip(str(ambient_path)).volumex(amb_vol)
        # Loop ambient if shorter than TTS
        if amb.duration < tts.duration:
            from moviepy.editor import concatenate_audioclips
            repeats = int(tts.duration / amb.duration) + 1
            amb = concatenate_audioclips([amb] * repeats).subclip(0, tts.duration)
        else:
            amb = amb.subclip(0, tts.duration)
        mixed = CompositeAudioClip([amb, tts])
        mixed.write_audiofile(str(out_path), fps=SAMPLE_RATE, codec="pcm_s16le", verbose=False, logger=None)
        return out_path
    except Exception:
        import shutil
        shutil.copy(str(tts_path), str(out_path))
        return out_path




def generate_binaural_wav(duration_s: float, base_freq: int = 200, beat_freq: int = 40, volume: float = 0.25) -> bytes:
    """Return raw WAV bytes for a binaural beat tone.  Left ear = base_freq Hz, right = base_freq+beat_freq Hz."""
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), dtype=np.float32)
    left  = (np.sin(2 * np.pi * base_freq * t) * volume * 32767).astype(np.int16)
    right = (np.sin(2 * np.pi * (base_freq + beat_freq) * t) * volume * 32767).astype(np.int16)
    stereo = np.stack([left, right], axis=1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(stereo.tobytes())
    return buf.getvalue()
