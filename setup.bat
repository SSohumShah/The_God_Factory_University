@echo off
setlocal
cd /d "%~dp0"

echo [SETUP] Starting one-time setup...

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  where python3 >nul 2>nul
  if %ERRORLEVEL% NEQ 0 (
    echo [SETUP] Python not found on this computer.
    if exist "install_python.bat" (
      echo [SETUP] Running Python auto-installer...
      call install_python.bat
      if %ERRORLEVEL% NEQ 0 (
        echo [SETUP] Python installation failed. Cannot continue.
        pause
        exit /b 1
      )
      set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else (
      echo [SETUP] Install Python 3.9+ from https://www.python.org/downloads/
      echo [SETUP] Make sure to check "Add Python to PATH" during installation.
      pause
      exit /b 1
    )
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [SETUP] Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] Failed to activate virtual environment.
  pause
  exit /b 1
)

echo [SETUP] Upgrading pip...
python -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] pip upgrade failed.
  pause
  exit /b 1
)

echo [SETUP] Installing Python packages...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] Python dependency install failed.
  pause
  exit /b 1
)

echo [SETUP] FFmpeg is bundled via imageio-ffmpeg (no system install needed).

echo [SETUP] Initialising university database...
python -c "from core.database import init_db; init_db(); print('[SETUP] Database ready.')"
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] Database init failed. Check requirements install.
  pause
  exit /b 1
)

echo [SETUP] Generating lecture pipeline files...
python generate_assets.py
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] Failed generating pipeline files. Continuing anyway...
)

echo [SETUP] Verifying installed dependencies...
python -c "import streamlit,moviepy,edge_tts,PIL,numpy;print('[SETUP] Core deps OK: streamlit='+streamlit.__version__+', moviepy='+moviepy.__version__+', Pillow='+PIL.__version__+', numpy='+numpy.__version__)"
if %ERRORLEVEL% NEQ 0 (
  echo [SETUP] Warning: some dependencies may be missing. Check output above.
)

echo [SETUP] Setup complete. Run start.bat to launch the university.
pause
exit /b 0
