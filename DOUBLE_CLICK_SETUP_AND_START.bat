@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call setup.bat
  if %ERRORLEVEL% NEQ 0 (
    echo [LAUNCH] Setup failed.
    pause
    exit /b 1
  )
)

call start.bat
