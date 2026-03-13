"""
Structured logging for Arcane University.

Provides JSON-formatted log entries for render jobs, provider calls,
import operations, and general events. Logs to logs/university.log.
Secrets are automatically redacted before writing.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "university.log"

_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{36,}|key-[A-Za-z0-9]{8,}|"
    r"hf_[A-Za-z0-9]{8,}|gsk_[A-Za-z0-9]{8,})",
)


def _redact(text: str) -> str:
    """Redact API keys and tokens from log messages."""
    return _SECRET_PATTERN.sub("***REDACTED***", text)


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _ensure_log_dir()
    _logger = logging.getLogger("arcane_university")
    _logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    return _logger


def _emit(level: str, category: str, message: str, **extra) -> None:
    entry = {
        "ts": time.time(),
        "level": level,
        "category": category,
        "message": _redact(message),
    }
    for k, v in extra.items():
        entry[k] = _redact(str(v)) if isinstance(v, str) else v
    _get_logger().info(json.dumps(entry, default=str))


# ─── Public API ────────────────────────────────────────────────────────────────

def log_render(lecture_id: str, status: str, duration_s: float = 0, **extra) -> None:
    _emit("INFO", "render", f"Render {status}: {lecture_id}",
          lecture_id=lecture_id, status=status, duration_s=duration_s, **extra)


def log_provider_call(provider: str, model: str, status: str,
                      tokens_in: int = 0, tokens_out: int = 0, **extra) -> None:
    _emit("INFO", "provider", f"{provider}/{model} {status}",
          provider=provider, model=model, status=status,
          tokens_in=tokens_in, tokens_out=tokens_out, **extra)


def log_import(source: str, status: str, items: int = 0, **extra) -> None:
    _emit("INFO", "import", f"Import {status}: {source}",
          source=source, status=status, items=items, **extra)


def log_event(message: str, category: str = "general", level: str = "INFO", **extra) -> None:
    _emit(level, category, message, **extra)


def log_error(message: str, category: str = "error", error_id: str = "", **extra) -> None:
    _emit("ERROR", category, message, error_id=error_id, **extra)
