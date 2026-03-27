"""Canonical audio/TTS configuration helpers."""
from __future__ import annotations

from core.database import get_setting, set_setting


def _int_setting(key: str, default: int = 0) -> int:
    raw = get_setting(key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def format_rate(rate: int) -> str:
    return f"+{rate}%" if rate >= 0 else f"{rate}%"


def format_pitch(pitch: int) -> str:
    return f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"


def get_tts_settings() -> dict[str, str | int]:
    voice_id = get_setting("tts_voice", "") or get_setting("voice_id", "en-US-AriaNeural")
    rate = _int_setting("tts_rate", 0)
    pitch = _int_setting("tts_pitch", 0)
    binaural = get_setting("binaural_preset", "") or get_setting("binaural_mode", "gamma_40hz")
    return {
        "voice_id": voice_id,
        "rate": rate,
        "pitch": pitch,
        "rate_str": format_rate(rate),
        "pitch_str": format_pitch(pitch),
        "binaural": binaural,
    }


def save_tts_settings(voice_id: str, rate: int, pitch: int) -> None:
    set_setting("tts_voice", voice_id)
    set_setting("voice_id", voice_id)
    set_setting("tts_rate", str(rate))
    set_setting("tts_pitch", str(pitch))


def save_binaural_setting(preset: str) -> None:
    set_setting("binaural_preset", preset)
    set_setting("binaural_mode", preset)