@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [START] Environment missing. Running setup first...
  call setup.bat
  if %ERRORLEVEL% NEQ 0 (
    echo [START] Setup failed. Exiting.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
  echo [START] Failed to activate virtual environment.
  pause
  exit /b 1
)

python -c "from core.database import init_db; init_db()" 2>nul

echo [START] Launching university...
streamlit run app.py --server.headless false
