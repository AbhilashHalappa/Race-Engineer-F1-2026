@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe tools\first_run_check.py
) else (
  python tools\first_run_check.py
)
pause
