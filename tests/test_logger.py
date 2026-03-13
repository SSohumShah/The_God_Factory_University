"""Tests for core.logger structured logging."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import core.logger as logger


class TestRedaction:
    def test_redacts_openai_key(self):
        assert "***REDACTED***" in logger._redact("key is sk-abc12345678")

    def test_redacts_github_pat(self):
        assert "***REDACTED***" in logger._redact("token ghp_" + "a" * 36)

    def test_preserves_normal_text(self):
        assert logger._redact("hello world") == "hello world"


class TestLogFunctions:
    def setup_method(self):
        # Reset logger to use a temp file
        logger._logger = None
        self._tmpdir = tempfile.mkdtemp()
        logger.LOG_DIR = Path(self._tmpdir)
        logger.LOG_FILE = logger.LOG_DIR / "test.log"

    def _read_log(self) -> list[dict]:
        if not logger.LOG_FILE.exists():
            return []
        lines = logger.LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def test_log_render(self):
        logger.log_render("lec-1", "completed", duration_s=5.0)
        entries = self._read_log()
        assert len(entries) == 1
        assert entries[0]["category"] == "render"
        assert entries[0]["lecture_id"] == "lec-1"

    def test_log_provider_call(self):
        logger.log_provider_call("openai", "gpt-4o", "success", tokens_in=100, tokens_out=50)
        entries = self._read_log()
        assert len(entries) == 1
        assert entries[0]["provider"] == "openai"

    def test_log_import(self):
        logger.log_import("bulk_json", "completed", items=3)
        entries = self._read_log()
        assert len(entries) == 1
        assert entries[0]["items"] == 3

    def test_log_error_with_id(self):
        logger.log_error("Something broke", error_id="ERR001")
        entries = self._read_log()
        assert entries[0]["level"] == "ERROR"
        assert entries[0]["error_id"] == "ERR001"

    def test_secrets_redacted_in_log(self):
        logger.log_event("Using key sk-abc12345678 for test", category="test")
        entries = self._read_log()
        assert "sk-abc" not in entries[0]["message"]
        assert "***REDACTED***" in entries[0]["message"]
