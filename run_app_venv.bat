@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD="
if exist "%SCRIPT_DIR%.venv\Scripts\pythonw.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    echo [AIWBM] Virtual environment not found. Please run from repo root with .venv installed.
    pause
    exit /b 1
)

echo [AIWBM] Launching AI Workstation Boot Manager (startup mode)...
start "AI Workstation Boot Manager" "%PYTHON_CMD%" "%SCRIPT_DIR%app.py" --startup --startup-auto-close
exit /b 0
