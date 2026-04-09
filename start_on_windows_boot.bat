@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "APP_PY=%SCRIPT_DIR%app.py"

if not exist "%APP_PY%" (
    echo [AIWBM] app.py not found next to this batch file.
    exit /b 1
)

set "PYTHON_CMD="
if exist "%SCRIPT_DIR%.venv\Scripts\pythonw.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%venv\Scripts\pythonw.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%venv\Scripts\pythonw.exe"
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    where pythonw >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=pythonw"
    ) else (
        where pyw >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_CMD=pyw"
        ) else (
            where py >nul 2>nul
            if not errorlevel 1 (
                set "PYTHON_CMD=py -3"
            ) else (
                where python >nul 2>nul
                if not errorlevel 1 (
                    set "PYTHON_CMD=python"
                )
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo [AIWBM] Python launcher not found. Install Python or add it to PATH.
    exit /b 1
)

echo [AIWBM] Launching startup mode...
start "AI Workstation Boot Manager" "%PYTHON_CMD%" "%APP_PY%" --startup --startup-auto-close

if errorlevel 1 (
    echo [AIWBM] Failed to launch app.
    exit /b 1
)

echo [AIWBM] Launch handed off. Exiting wrapper.
exit /b 0
