@echo off
cd /d "%~dp0"

set "APP_NAME=ArchiveManager"
set "FFMPEG_BINARY_ARG="

if exist "tools\ffmpeg.exe" (
    echo [INFO] Found tools\ffmpeg.exe. It will be bundled into EXE.
    set "FFMPEG_BINARY_ARG=--add-binary=tools\ffmpeg.exe;tools"
) else (
    echo [INFO] tools\ffmpeg.exe not found. Using imageio-ffmpeg package.
)

echo ==========================================
echo   %APP_NAME% - onefile production build
echo ==========================================
echo.

if not exist "main.py" (
    echo [ERROR] main.py not found. Run this file from project root.
    pause
    exit /b 1
)

if not exist "assets\app.ico" (
    echo [ERROR] assets\app.ico not found.
    pause
    exit /b 1
)

echo [1/7] Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/7] Activating virtual environment...
call ".venv\Scripts\activate.bat"

echo [3/7] Installing dependencies...
python -m pip install --upgrade pip
if exist "requirements-dev.txt" (
    pip install -r requirements-dev.txt
) else (
    pip install -r requirements.txt
    pip install pyinstaller pytest
)

echo [4/7] Syntax check...
python -m compileall .
if errorlevel 1 (
    echo [ERROR] compileall failed.
    pause
    exit /b 1
)

echo [5/7] Running tests...
python -m pytest -q
if errorlevel 1 (
    echo [ERROR] tests failed.
    pause
    exit /b 1
)

echo [6/7] Cleaning old build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q "%APP_NAME%.spec" 2>nul

echo [7/7] Building onefile EXE...
pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --icon "assets\app.ico" ^
    --manifest "packaging\windows\app.manifest" ^
    --version-file "packaging\windows\version_info.txt" ^
    --add-data "assets\app.ico;assets" ^
    --collect-binaries imageio_ffmpeg ^
    --collect-data imageio_ffmpeg ^
    --hidden-import pillow_heif ^
    --hidden-import pillow_heif._pillow_heif ^
    %FFMPEG_BINARY_ARG% ^
    main.py

if errorlevel 1 (
    echo [ERROR] build failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Done.
echo EXE: dist\%APP_NAME%.exe
echo ==========================================
pause
