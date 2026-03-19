@echo off
setlocal
cd /d "%~dp0"

python server.py

if errorlevel 1 (
  echo.
  echo server.py exited with an error.
  pause
)
