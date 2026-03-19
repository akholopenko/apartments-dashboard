@echo off
setlocal
cd /d "%~dp0"

python monitor_calendar.py

if errorlevel 1 (
  echo.
  echo monitor_calendar.py exited with an error.
  pause
)
