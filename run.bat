@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Archive Manager
color 0f

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW_EXE=%VENV_DIR%\Scripts\pythonw.exe"

echo ==========================================
echo   Archive Manager - development run
echo ==========================================
echo.

if not exist "main.py" (
    color 0c
    echo [ERROR] main.py not found. Run this file from the project root.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    color 0c
    echo [ERROR] requirements.txt not found.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        color 0c
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Checking dependencies...
"%PYTHON_EXE%" -c "import PySide6, send2trash, PIL, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    color 0e
    echo [WARN] Missing dependencies detected.
    choice /C YN /M "Install dependencies from requirements.txt"
    if errorlevel 2 (
        color 0c
        echo [ERROR] The application cannot start without dependencies.
        pause
        exit /b 1
    )

    echo [INFO] Installing dependencies...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0c
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

color 0f
echo [INFO] Launching application...
start "Archive Manager" "%PYTHONW_EXE%" "%CD%\main.py"
exit /b 0
