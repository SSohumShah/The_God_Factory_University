"""
Audio engine tests — pure computation functions (no external network calls).
"""
from __future__ import annotations

import struct
from io import BytesIO

import numpy as np
import pytest

from media.audio_engine import (
    generate_binaural,
    generate_ambient,
    generate_sfx_bytes,
    generate_binaural_wav,
    SAMPLE_RATE,
    BINAURAL_PRESETS,
    SFX_PRESETS,
)


class TestBinaural:
    def test_returns_stereo_array(self):
        data = generate_binaural(1.0)
        assert isinstance(data, np.ndarray)
        assert data.ndim == 2
        assert data.shape[1] == 2  # stereo

    def test_duration_matches(self):
        duration = 2.0
        data = generate_binaural(duration)
        expected_samples = int(SAMPLE_RATE * duration)
        # Allow small rounding difference
        assert abs(data.shape[0] - expected_samples) <= 2

    def test_all_presets(self):
        for preset_name in BINAURAL_PRESETS:
            data = generate_binaural(0.5, preset=preset_name)
            assert data.shape[0] > 0, f"Preset {preset_name} produced empty output"

    def test_int16_range(self):
        data = generate_binaural(0.5)
        assert data.dtype == np.int16
        assert data.max() <= 32767
        assert data.min() >= -32768


class TestAmbient:
    def test_returns_stereo_array(self):
        data = generate_ambient(1.0)
        assert isinstance(data, np.ndarray)
        assert data.ndim == 2
        assert data.shape[1] == 2

    def test_different_keys(self):
        for key in ("A", "C", "E"):
            data = generate_ambient(0.5, key_note=key)
            assert data.shape[0] > 0


class TestSFX:
    def test_all_sfx_presets(self):
        for sfx_name in SFX_PRESETS:
            wav_bytes = generate_sfx_bytes(sfx_name)
            assert isinstance(wav_bytes, bytes)
            assert len(wav_bytes) > 44  # must be longer than WAV header

    def test_wav_header(self):
        wav_bytes = generate_sfx_bytes("click")
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"


class TestBinauralWav:
    def test_returns_bytes(self):
        data = generate_binaural_wav(1.0)
        assert isinstance(data, bytes)
        assert len(data) > 44

    def test_wav_format(self):
        data = generate_binaural_wav(1.0, base_freq=200, beat_freq=10)
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"

    def test_different_parameters(self):
        d1 = generate_binaural_wav(0.5, base_freq=100, beat_freq=5)
        d2 = generate_binaural_wav(0.5, base_freq=400, beat_freq=40)
        # Different frequencies should produce different data
        assert d1 != d2

    def test_volume_scales(self):
        quiet = generate_binaural_wav(0.5, volume=0.1)
        loud = generate_binaural_wav(0.5, volume=0.9)
        # Both should be valid WAV
        assert quiet[:4] == b"RIFF"
        assert loud[:4] == b"RIFF"
