@echo off
cd /d "%~dp0"
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo PySide6 is not installed.
    echo Run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)
python main.py
pause
