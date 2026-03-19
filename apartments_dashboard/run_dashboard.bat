@echo off
setlocal
cd /d "%~dp0"

python dashboard.py --days 21

if errorlevel 1 (
  echo.
  echo dashboard.py exited with an error.
  pause
)
