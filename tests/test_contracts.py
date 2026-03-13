"""
Contract tests — verify that every symbol imported by page files actually exists
in the backend modules. This prevents future drift between pages and backends.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"
ROOT = Path(__file__).resolve().parent.parent


def _get_imports_from_file(filepath: Path) -> list[tuple[str, list[str]]]:
    """Parse a Python file's AST and return all 'from X import Y' pairs."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names if alias.name != "*"]
            if names:
                results.append((node.module, names))
    return results


def _get_page_files() -> list[Path]:
    """Return all .py files in the pages/ directory."""
    return sorted(PAGES_DIR.glob("*.py"))


class TestPageImports:
    """Every symbol imported by a page file must exist in its source module."""

    @pytest.fixture(autouse=True)
    def setup_path(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

    @pytest.mark.parametrize("page_file", _get_page_files(), ids=lambda p: p.name)
    def test_page_symbols_exist(self, page_file: Path):
        imports = _get_imports_from_file(page_file)
        errors = []
        for module_name, symbol_names in imports:
            # Skip streamlit and stdlib
            if module_name.startswith(("streamlit", "os", "sys", "json",
                                       "pathlib", "time", "math", "datetime",
                                       "__future__", "typing")):
                continue
            try:
                mod = importlib.import_module(module_name)
            except ImportError:
                errors.append(f"Module {module_name!r} cannot be imported")
                continue
            for sym in symbol_names:
                if not hasattr(mod, sym):
                    errors.append(
                        f"{page_file.name}: {module_name}.{sym} does not exist"
                    )
        assert not errors, "Missing symbols:\n" + "\n".join(errors)


class TestAppImports:
    """app.py imports must all resolve."""

    @pytest.fixture(autouse=True)
    def setup_path(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

    def test_app_symbols_exist(self):
        app_file = ROOT / "app.py"
        imports = _get_imports_from_file(app_file)
        errors = []
        for module_name, symbol_names in imports:
            if module_name.startswith(("streamlit", "os", "sys", "json",
                                       "pathlib", "time", "__future__")):
                continue
            try:
                mod = importlib.import_module(module_name)
            except ImportError:
                errors.append(f"Module {module_name!r} cannot be imported")
                continue
            for sym in symbol_names:
                if not hasattr(mod, sym):
                    errors.append(f"app.py: {module_name}.{sym} does not exist")
        assert not errors, "Missing symbols:\n" + "\n".join(errors)


class TestCoreModulesImport:
    """All core backend modules must import without error."""

    @pytest.fixture(autouse=True)
    def setup_path(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

    @pytest.mark.parametrize("module_name", [
        "core.database",
        "core.help_registry",
        "core.app_docs",
        "llm.providers",
        "llm.professor",
        "media.audio_engine",
        "media.video_engine",
        "ui.theme",
    ])
    def test_module_imports(self, module_name: str):
        mod = importlib.import_module(module_name)
        assert mod is not None


class TestHelpNavigation:
    """Every help_button() topic_key used in pages must have a matching HELP_ENTRIES entry."""

    def test_all_help_button_anchors_exist(self):
        import re
        from core.help_registry import HELP_ENTRIES

        pages_dir = ROOT / "pages"
        app_file = ROOT / "app.py"
        missing = []

        files = list(pages_dir.glob("*.py")) + [app_file]
        for py_file in files:
            text = py_file.read_text(encoding="utf-8")
            for m in re.finditer(r'help_button\(["\']([^"\']+)', text):
                key = m.group(1)
                if key not in HELP_ENTRIES:
                    missing.append(f"{py_file.name}: {key}")

        assert not missing, f"Missing help entries: {missing}"

    def test_minimum_entry_count(self):
        from core.help_registry import HELP_ENTRIES
        assert len(HELP_ENTRIES) >= 32, f"Expected >=32 help entries, got {len(HELP_ENTRIES)}"
