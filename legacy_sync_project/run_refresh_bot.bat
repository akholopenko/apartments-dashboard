@echo off
setlocal
cd /d "%~dp0"

python refresh_bot.py

if errorlevel 1 (
  echo.
  echo refresh_bot.py exited with an error.
  pause
)