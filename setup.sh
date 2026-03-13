#!/usr/bin/env bash
# ── Arcane University: Setup (macOS / Linux) ──────────────────────────────
set -e
cd "$(dirname "$0")"

echo "[SETUP] Starting one-time setup..."

# ── Find Python 3 ────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[SETUP] Python 3.9+ not found."
    echo ""
    echo "Install Python:"
    echo "  macOS:  brew install python@3.11"
    echo "  Ubuntu: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora: sudo dnf install python3"
    echo ""
    exit 1
fi

echo "[SETUP] Using $PYTHON ($($PYTHON --version))"

# ── Virtual environment ──────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# Activate
source .venv/bin/activate

echo "[SETUP] Upgrading pip..."
python -m pip install --upgrade pip -q

echo "[SETUP] Installing Python packages..."
pip install -r requirements.txt -q

echo "[SETUP] FFmpeg is bundled via imageio-ffmpeg (no system install needed)."

echo "[SETUP] Initialising university database..."
python -c "from core.database import init_db; init_db(); print('[SETUP] Database ready.')"

echo "[SETUP] Generating lecture pipeline files..."
python generate_assets.py || echo "[SETUP] Pipeline generation skipped (non-fatal)."

echo ""
echo "[SETUP] Setup complete. Run ./start.sh to launch the university."
