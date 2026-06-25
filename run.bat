@echo off
setlocal
title Archive Manager
color 0f

cd /d "%~dp0"

set "PYTHON_CMD="
set "PYTHON_GUI_CMD="
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "PYTHON_GUI_CMD=pythonw"
)

if not defined PYTHON_CMD (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        set "PYTHON_GUI_CMD=pyw -3"
    )
)

if not defined PYTHON_CMD (
    color 0c
    echo [ERROR] Python was not found.
    echo Install Python 3 and add it to PATH, or use the Windows "py" launcher.
    pause
    exit /b 1
)

echo ========================================================
echo                STARTING APPLICATION
echo ========================================================
echo.
echo [INFO] Checking dependencies...

%PYTHON_CMD% -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    color 0e
    echo [WARN] PySide6 is not installed.
    echo.
    choice /C YN /M "Install missing dependencies from requirements.txt?"
    if errorlevel 2 (
        color 0c
        echo.
        echo [ERROR] The application cannot start without dependencies.
        pause
        exit /b 1
    )
    echo.
    echo [INFO] Installing dependencies...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0c
        echo.
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    color 0f
    echo [OK] Dependencies installed successfully.
    echo.
)

echo [INFO] Launching the main program...
echo ========================================================
echo.

start "" %PYTHON_GUI_CMD% main.py
if errorlevel 1 (
    color 0c
    echo [ERROR] Failed to start the graphical application.
    pause
    exit /b 1
)

exit /b 0
