@echo off
title Overcast Agent Installer

echo.
echo ========================================
echo   Overcast Agent Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.9 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i

echo Found Python version: %PYTHON_VERSION%
echo.

REM Check if we're in the correct directory
if not exist "overcast_installer.py" (
    echo ERROR: overcast_installer.py not found!
    echo.
    echo Please make sure you're running this batch file from the
    echo overcast-installer directory.
    echo.
    pause
    exit /b 1
)

REM Check if template file exists
if not exist "overcast_agent_template.py" (
    echo ERROR: overcast_agent_template.py not found!
    echo.
    echo The installer template file is missing. Please re-download
    echo the complete installer package.
    echo.
    pause
    exit /b 1
)

echo Starting Overcast GUI Installer...
echo.
echo TIP: The installer window should open shortly.
echo      If it doesn't appear, check your taskbar!
echo.

REM Launch the Python installer
python overcast_installer.py

REM Check if the installer ran successfully
if errorlevel 1 (
    echo.
    echo ERROR: The installer encountered an error.
    echo.
    echo Common solutions:
    echo - Make sure you have Python 3.9 or higher
    echo - On some systems, try: python3 overcast_installer.py
    echo - Install tkinter if missing: pip install tk
    echo.
) else (
    echo.
    echo Installer completed successfully!
    echo.
)

echo.
echo Press any key to close this window...
pause >nul 