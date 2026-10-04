@echo off
cd /d "%~dp0"
if exist "RaceEngineer.exe" (
  RaceEngineer.exe --setup
) else if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -m src.product_launcher --setup
) else (
  echo Race Engineer executable or venv not found.
  pause
)
