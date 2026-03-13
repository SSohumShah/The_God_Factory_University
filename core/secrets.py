"""
Lightweight key encryption for API keys stored in SQLite.
Uses Fernet (cryptography package) if available, otherwise base64 obfuscation.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

_KEY_FILE = Path(__file__).resolve().parent.parent / ".secret_key"

# Try to use Fernet for real encryption
try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _get_or_create_key() -> bytes:
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key() if _HAS_FERNET else base64.urlsafe_b64encode(os.urandom(32))
    _KEY_FILE.write_bytes(key)
    return key


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _get_or_create_key()
    if _HAS_FERNET:
        f = Fernet(key)
        return "ENC:" + f.encrypt(plaintext.encode()).decode()
    # Fallback: base64 obfuscation (not true encryption)
    encoded = base64.urlsafe_b64encode(plaintext.encode()).decode()
    return "OBF:" + encoded


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    if ciphertext.startswith("ENC:"):
        key = _get_or_create_key()
        if _HAS_FERNET:
            f = Fernet(key)
            return f.decrypt(ciphertext[4:].encode()).decode()
        return ""  # Can't decrypt without Fernet
    if ciphertext.startswith("OBF:"):
        return base64.urlsafe_b64decode(ciphertext[4:].encode()).decode()
    # Plain text (legacy, not encrypted)
    return ciphertext


def is_encrypted(value: str) -> bool:
    return value.startswith("ENC:") or value.startswith("OBF:")
