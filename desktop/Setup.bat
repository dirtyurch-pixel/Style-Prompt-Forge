@echo off
rem Sets up Style Prompt Forge the first time (about a minute), then opens it.
title Style Prompt Forge setup
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import anthropic" >nul 2>&1
if errorlevel 1 (
    echo Setting up Style Prompt Forge, please wait...
    if not exist ".venv\Scripts\python.exe" (python -m venv .venv || py -m venv .venv)
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Python isn't installed. Get it from python.org, tick "Add python.exe to PATH", then try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check anthropic
    if errorlevel 1 (
        echo.
        echo Setup failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)
start "" ".venv\Scripts\pythonw.exe" app.py
