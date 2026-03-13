@echo off
setlocal

echo [FFMPEG] Checking existing installation...
where ffmpeg >nul 2>nul
if %ERRORLEVEL%==0 (
  echo [FFMPEG] ffmpeg already available on PATH.
  goto :eof
)

echo [FFMPEG] Trying winget...
where winget >nul 2>nul
if %ERRORLEVEL%==0 (
  winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  where ffmpeg >nul 2>nul
  if %ERRORLEVEL%==0 (
    echo [FFMPEG] Installed via winget.
    goto :eof
  )
)

echo [FFMPEG] Trying choco...
where choco >nul 2>nul
if %ERRORLEVEL%==0 (
  choco install ffmpeg -y
  where ffmpeg >nul 2>nul
  if %ERRORLEVEL%==0 (
    echo [FFMPEG] Installed via choco.
    goto :eof
  )
)

echo [FFMPEG] Trying scoop...
where scoop >nul 2>nul
if %ERRORLEVEL%==0 (
  scoop install ffmpeg
  where ffmpeg >nul 2>nul
  if %ERRORLEVEL%==0 (
    echo [FFMPEG] Installed via scoop.
    goto :eof
  )
)

echo [FFMPEG] Auto-install failed. Please install ffmpeg manually and rerun setup.
echo [FFMPEG] Download: https://ffmpeg.org/download.html
exit /b 1
