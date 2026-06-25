@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=ArchiveManager"
set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "FFMPEG_BINARY_ARG="
set "ICON_ARG="
set "MANIFEST_ARG="
set "VERSION_ARG="

if exist "tools\ffmpeg.exe" (
    echo [INFO] Found tools\ffmpeg.exe. It will be bundled into EXE.
    set "FFMPEG_BINARY_ARG=--add-binary=tools\ffmpeg.exe;tools"
) else (
    echo [INFO] tools\ffmpeg.exe not found. Using imageio-ffmpeg package.
)

if exist "assets\app.ico" (
    set "ICON_ARG=--icon=assets\app.ico"
) else (
    echo [WARN] assets\app.ico not found. EXE will be built without custom icon.
)

if exist "assets\app.manifest" (
    set "MANIFEST_ARG=--manifest=assets\app.manifest"
) else (
    echo [WARN] assets\app.manifest not found. EXE will be built without manifest.
)

if exist "assets\version_info.txt" (
    set "VERSION_ARG=--version-file=assets\version_info.txt"
) else (
    echo [WARN] assets\version_info.txt not found. EXE will be built without version info.
)

echo ==========================================
echo   %APP_NAME% - onefile production build
echo ==========================================
echo.

if not exist "main.py" (
    echo [ERROR] main.py not found. Run this file from the project root.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found.
    pause
    exit /b 1
)

echo [1/7] Preparing virtual environment...
if not exist "%PYTHON_EXE%" (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [2/7] Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [3/7] Installing dependencies...
"%PIP_EXE%" install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt.
    pause
    exit /b 1
)

if exist "requirements-dev.txt" (
    "%PIP_EXE%" install -r requirements-dev.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements-dev.txt.
        pause
        exit /b 1
    )
)

"%PIP_EXE%" install pyinstaller pytest pywin32
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo [4/7] Syntax check...
"%PYTHON_EXE%" -m compileall main.py archive_app
if errorlevel 1 (
    echo [ERROR] compileall failed.
    pause
    exit /b 1
)

echo [5/7] Running tests...
if exist "tests" (
    "%PYTHON_EXE%" -m pytest -q
    if errorlevel 1 (
        echo [ERROR] tests failed.
        pause
        exit /b 1
    )
) else (
    echo [WARN] tests folder not found. Skipping tests.
)

echo [6/7] Cleaning old build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q "%APP_NAME%.spec" 2>nul

echo [7/7] Building onefile EXE...
"%PYTHON_EXE%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    %ICON_ARG% ^
    %MANIFEST_ARG% ^
    %VERSION_ARG% ^
    --collect-binaries imageio_ffmpeg ^
    --collect-data imageio_ffmpeg ^
    --hidden-import pillow_heif ^
    --hidden-import pillow_heif._pillow_heif ^
    --hidden-import win32com ^
    --hidden-import win32com.shell ^
    --hidden-import win32com.server ^
    --hidden-import pythoncom ^
    --hidden-import pywintypes ^
    --exclude-module pwd ^
    --exclude-module grp ^
    --exclude-module posix ^
    --exclude-module resource ^
    --exclude-module _posixsubprocess ^
    --exclude-module fcntl ^
    --exclude-module termios ^
    --exclude-module _scproxy ^
    --exclude-module gi ^
    --exclude-module Foundation ^
    --exclude-module java ^
    --exclude-module vms_lib ^
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
exit /b 0
