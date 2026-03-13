"""
Green build gate: run before merging any feature work.
Checks: pytest, py_compile all .py files, file size audit (< 1000 LOC).
Exit 0 = green, exit 1 = red.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"
python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
MAX_LOC = 1000
failures = []


def run_pytest():
    print("=" * 60)
    print("STEP 1: pytest")
    print("=" * 60)
    result = subprocess.run(
        [python, "-m", "pytest", str(ROOT / "tests"), "-q", "--tb=short"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        failures.append("pytest failed")
    return result.returncode == 0


def compile_all():
    print("=" * 60)
    print("STEP 2: py_compile all .py files")
    print("=" * 60)
    ok = True
    for py_file in sorted(ROOT.rglob("*.py")):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        result = subprocess.run(
            [python, "-m", "py_compile", str(py_file)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  FAIL: {py_file.relative_to(ROOT)}")
            print(f"        {result.stderr.strip()}")
            failures.append(f"compile: {py_file.relative_to(ROOT)}")
            ok = False
    if ok:
        print("  All files compile OK")
    return ok


def loc_audit():
    print("=" * 60)
    print(f"STEP 3: LOC audit (max {MAX_LOC})")
    print("=" * 60)
    ok = True
    for py_file in sorted(ROOT.rglob("*.py")):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        if py_file.name.startswith("test_"):
            continue
        lines = len(py_file.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LOC:
            print(f"  OVER LIMIT: {py_file.relative_to(ROOT)} = {lines} LOC")
            failures.append(f"LOC: {py_file.relative_to(ROOT)} ({lines})")
            ok = False
        elif lines > 800:
            print(f"  WARNING: {py_file.relative_to(ROOT)} = {lines} LOC (split at 800)")
    if ok:
        print("  All files under LOC limit")
    return ok


if __name__ == "__main__":
    run_pytest()
    compile_all()
    loc_audit()

    print("\n" + "=" * 60)
    if failures:
        print("BUILD: RED")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("BUILD: GREEN")
        sys.exit(0)
