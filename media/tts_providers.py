"""Multi-engine TTS provider system with intelligent cycling.

Priority order:
  1. Local open-source engines (unlimited, no internet required)
     - Kokoro  (auto-installed on demand)
     - Piper   (auto-installed on demand)
     - Coqui   (auto-installed on demand)
  2. Cloud free-tier engines (high quality, daily/monthly limits)
     - ElevenLabs  (auto-installed on demand — 10k chars/month free)
     - Edge-TTS    (auto-installed on demand — unlimited, Microsoft cloud)
  3. Offline fallback
     - pyttsx3     (auto-installed on demand — always available, lowest quality)

Dependencies are installed automatically when a student selects an engine
in the Media Setup page. No manual pip commands needed.
"""
from __future__ import annotations

import abc
import importlib
import logging
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "data" / "tts_usage.db"
_log = logging.getLogger(__name__)


# ─── Dependency installer ────────────────────────────────────────────────────

def _pip_install(*packages: str, extra_args: list[str] | None = None) -> tuple[bool, str]:
    """Install packages via pip in the current Python environment.

    Returns (success, message).
    """
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", *packages]
    if extra_args:
        cmd.extend(extra_args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            # Force importlib to rediscover newly installed packages
            importlib.invalidate_caches()
            return True, f"Installed: {', '.join(packages)}"
        return False, result.stderr.strip()[-500:]
    except subprocess.TimeoutExpired:
        return False, "Install timed out after 5 minutes"
    except Exception as exc:
        return False, str(exc)


# ─── Usage tracking ──────────────────────────────────────────────────────────

def _ensure_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS tts_usage (
            engine TEXT NOT NULL,
            date TEXT NOT NULL,
            chars_used INTEGER DEFAULT 0,
            PRIMARY KEY (engine, date)
        )
    """)
    con.commit()
    return con


def _get_chars_used(engine: str) -> int:
    con = _ensure_db()
    try:
        row = con.execute(
            "SELECT chars_used FROM tts_usage WHERE engine = ? AND date = ?",
            (engine, date.today().isoformat()),
        ).fetchone()
        return row[0] if row else 0
    finally:
        con.close()


def _add_chars(engine: str, chars: int) -> None:
    con = _ensure_db()
    try:
        today = date.today().isoformat()
        con.execute("""
            INSERT INTO tts_usage (engine, date, chars_used) VALUES (?, ?, ?)
            ON CONFLICT(engine, date) DO UPDATE SET chars_used = chars_used + ?
        """, (engine, today, chars, chars))
        con.commit()
    finally:
        con.close()


# ─── Abstract base ───────────────────────────────────────────────────────────

class TTSProvider(abc.ABC):
    name: str = "base"
    engine_type: str = "local"          # local | cloud | offline
    daily_char_limit: int | None = None # None = unlimited
    priority: int = 99
    pip_packages: list[str] = []        # Packages to auto-install

    @abc.abstractmethod
    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        """Synthesize text to audio file. Returns True on success."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether this engine is installed and ready."""

    def install_deps(self) -> tuple[bool, str]:
        """Auto-install this engine's pip dependencies. Returns (ok, msg)."""
        if not self.pip_packages:
            return True, "No dependencies needed"
        return _pip_install(*self.pip_packages)

    def remaining_chars(self) -> int | None:
        if self.daily_char_limit is None:
            return None
        return max(0, self.daily_char_limit - _get_chars_used(self.name))

    def voices(self) -> dict[str, str]:
        """Return {display_name: voice_id} dict. Override per engine."""
        return {}


# ─── Local engines ───────────────────────────────────────────────────────────

class KokoroTTSProvider(TTSProvider):
    name = "kokoro"
    engine_type = "local"
    priority = 1
    pip_packages = ["kokoro", "soundfile"]

    def install_deps(self) -> tuple[bool, str]:
        """Install kokoro with misaki[en] but skip spacy (needs Python 3.10+)."""
        ok, msg = _pip_install("kokoro", "soundfile")
        if not ok:
            return False, msg
        # misaki[en] drags in spacy which fails on <3.10; install without deps
        ok2, msg2 = _pip_install("misaki[en]", extra_args=["--no-deps"])
        if not ok2:
            _log.warning("misaki[en] no-deps install failed: %s", msg2)
        # Install the lightweight misaki deps that DO work
        _pip_install("num2words", "espeakng-loader", "phonemizer-fork")
        importlib.invalidate_caches()
        return True, "Kokoro installed (spacy skipped — not required for basic TTS)"

    def is_available(self) -> bool:
        return importlib.util.find_spec("kokoro") is not None

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            from kokoro import KPipeline
            import soundfile as sf
            pipeline = KPipeline(lang_code="a")
            voice_id = voice or "af_heart"
            generator = pipeline(text, voice=voice_id, speed=1.0)
            samples = None
            for _, _, audio in generator:
                if audio is not None:
                    samples = audio if samples is None else __import__("numpy").concatenate([samples, audio])
            if samples is not None:
                sf.write(str(out_path), samples, 24000)
                return out_path.exists() and out_path.stat().st_size > 500
        except Exception:
            pass
        return False

    def voices(self) -> dict[str, str]:
        return {
            "Heart (Female, Warm)": "af_heart",
            "Bella (Female, Soft)": "af_bella",
            "Nicole (Female, Calm)": "af_nicole",
            "Sky (Female, Bright)": "af_sky",
            "Adam (Male, Clear)": "am_adam",
            "Michael (Male, Deep)": "am_michael",
        }


class PiperTTSProvider(TTSProvider):
    name = "piper"
    engine_type = "local"
    priority = 2
    pip_packages = ["piper-tts"]

    def is_available(self) -> bool:
        return importlib.util.find_spec("piper") is not None

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            from piper import PiperVoice
            import wave as _wave
            model_path = voice or self._default_model()
            if not model_path or not Path(model_path).exists():
                return False
            pv = PiperVoice.load(model_path)
            with _wave.open(str(out_path), "wb") as wf:
                pv.synthesize(text, wf)
            return out_path.exists() and out_path.stat().st_size > 500
        except Exception:
            pass
        return False

    def _default_model(self) -> str | None:
        models_dir = _ROOT / "data" / "piper_models"
        if models_dir.exists():
            onnx = list(models_dir.glob("*.onnx"))
            if onnx:
                return str(onnx[0])
        return None

    def voices(self) -> dict[str, str]:
        models_dir = _ROOT / "data" / "piper_models"
        if not models_dir.exists():
            return {}
        return {p.stem: str(p) for p in models_dir.glob("*.onnx")}


class CoquiTTSProvider(TTSProvider):
    name = "coqui"
    engine_type = "local"
    priority = 3
    pip_packages = ["TTS"]

    def is_available(self) -> bool:
        return importlib.util.find_spec("TTS") is not None

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            from TTS.api import TTS as CoquiTTS
            model = voice or "tts_models/en/ljspeech/tacotron2-DDC"
            tts = CoquiTTS(model_name=model, progress_bar=False)
            tts.tts_to_file(text=text, file_path=str(out_path))
            return out_path.exists() and out_path.stat().st_size > 500
        except Exception:
            pass
        return False


# ─── Cloud engines ───────────────────────────────────────────────────────────

class ElevenLabsTTSProvider(TTSProvider):
    name = "elevenlabs"
    engine_type = "cloud"
    daily_char_limit = 10_000  # Free tier: 10k chars/month ≈ 333/day
    priority = 5
    pip_packages = ["elevenlabs"]

    def is_available(self) -> bool:
        if importlib.util.find_spec("elevenlabs") is None:
            return False
        from core.database import get_setting
        key = get_setting("elevenlabs_api_key", "")
        return bool(key)

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            from elevenlabs.client import ElevenLabs
            from core.database import get_setting
            key = get_setting("elevenlabs_api_key", "")
            if not key:
                return False
            client = ElevenLabs(api_key=key)
            voice_id = voice or "Rachel"
            audio = client.generate(text=text, voice=voice_id, model="eleven_multilingual_v2")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            _add_chars(self.name, len(text))
            return out_path.exists() and out_path.stat().st_size > 500
        except Exception:
            pass
        return False

    def voices(self) -> dict[str, str]:
        return {
            "Rachel (Female, Calm)": "Rachel",
            "Drew (Male, Warm)": "Drew",
            "Clyde (Male, Deep)": "Clyde",
            "Domi (Female, Bright)": "Domi",
            "Bella (Female, Soft)": "Bella",
            "Antoni (Male, Conversational)": "Antoni",
        }


class EdgeTTSProvider(TTSProvider):
    name = "edge_tts"
    engine_type = "cloud"
    priority = 10
    pip_packages = ["edge-tts"]

    def is_available(self) -> bool:
        return importlib.util.find_spec("edge_tts") is not None

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            import asyncio
            import edge_tts
            voice_id = voice or "en-US-AriaNeural"

            async def _run():
                comm = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
                await comm.save(str(out_path))

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

            return out_path.exists() and out_path.stat().st_size > 1000
        except Exception:
            pass
        return False

    def voices(self) -> dict[str, str]:
        from media.audio_engine import VOICES
        return VOICES


class Pyttsx3Provider(TTSProvider):
    name = "pyttsx3"
    engine_type = "offline"
    priority = 99
    pip_packages = ["pyttsx3"]

    def is_available(self) -> bool:
        return importlib.util.find_spec("pyttsx3") is not None

    def synthesize(self, text: str, out_path: Path, voice: str = "",
                   rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.save_to_file(text, str(out_path))
            engine.runAndWait()
            return out_path.exists() and out_path.stat().st_size > 100
        except Exception:
            pass
        return False


# ─── Central registry & cycling ──────────────────────────────────────────────

ALL_ENGINES: list[TTSProvider] = [
    KokoroTTSProvider(),
    PiperTTSProvider(),
    CoquiTTSProvider(),
    ElevenLabsTTSProvider(),
    EdgeTTSProvider(),
    Pyttsx3Provider(),
]


def get_available_engines() -> list[TTSProvider]:
    """Return all engines that are installed and ready, sorted by priority."""
    return sorted(
        [e for e in ALL_ENGINES if e.is_available()],
        key=lambda e: e.priority,
    )


def get_all_engine_status() -> list[dict]:
    """Return status info for all engines (for UI display)."""
    result = []
    for e in ALL_ENGINES:
        avail = e.is_available()
        remaining = e.remaining_chars() if avail else None
        result.append({
            "name": e.name,
            "type": e.engine_type,
            "available": avail,
            "priority": e.priority,
            "daily_limit": e.daily_char_limit,
            "remaining_chars": remaining,
        })
    return result


def synth_with_cycling(text: str, out_path: Path, voice: str = "",
                       rate: str = "+0%", pitch: str = "+0Hz",
                       preferred_engine: str = "") -> tuple[bool, str]:
    """Try all available TTS engines in priority order until one succeeds.

    If *preferred_engine* is set and available, try it first.
    Returns (success, engine_name_used).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    engines = get_available_engines()
    if not engines:
        return False, "none"

    # Move preferred engine to front if specified
    if preferred_engine:
        engines = sorted(engines, key=lambda e: (0 if e.name == preferred_engine else 1, e.priority))

    for engine in engines:
        # Check char quota for cloud engines
        if engine.daily_char_limit is not None:
            remaining = engine.remaining_chars()
            if remaining is not None and remaining < len(text):
                continue
        if engine.synthesize(text, out_path, voice, rate, pitch):
            return True, engine.name

    return False, "none"


def get_best_tts_engine() -> TTSProvider | None:
    """Get the highest-priority available engine."""
    engines = get_available_engines()
    return engines[0] if engines else None


def auto_install(engine_name: str) -> tuple[bool, str]:
    """Install dependencies for a specific TTS engine by name.

    Returns (success, message). Called from the Media Setup UI.
    """
    for e in ALL_ENGINES:
        if e.name == engine_name:
            return e.install_deps()
    return False, f"Unknown engine: {engine_name}"


def get_engine(name: str) -> TTSProvider | None:
    """Return the engine instance by name."""
    for e in ALL_ENGINES:
        if e.name == name:
            return e
    return None
