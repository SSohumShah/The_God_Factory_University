"""LOC lint — fail if any .py under pages/, media/, llm/ exceeds 500 lines of code.

Lines that are blank or comment-only are excluded from the count.
Exit code 0 = all files pass, 1 = one or more violations found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LOC = 500
SCAN_DIRS = ["pages", "media", "llm"]
ROOT = Path(__file__).resolve().parent.parent


def count_loc(path: Path) -> int:
    """Count non-blank, non-comment lines."""
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def main() -> int:
    violations: list[tuple[Path, int]] = []
    for dirname in SCAN_DIRS:
        scan_root = ROOT / dirname
        if not scan_root.exists():
            continue
        for py in scan_root.rglob("*.py"):
            loc = count_loc(py)
            if loc > MAX_LOC:
                violations.append((py.relative_to(ROOT), loc))

    if violations:
        print(f"LOC violations (>{MAX_LOC} lines of code):")
        for path, loc in sorted(violations):
            print(f"  {path}: {loc} LOC")
        return 1

    print(f"All .py files under {', '.join(SCAN_DIRS)} are within {MAX_LOC} LOC.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
