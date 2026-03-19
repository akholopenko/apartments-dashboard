@echo off
setlocal
cd /d "%~dp0"

python -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload

if errorlevel 1 (
  echo.
  echo Web app exited with an error.
  pause
)
