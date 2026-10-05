@echo off
rem Double-click to start the Go With The Flow GUI.
rem The first run downloads Python 3.12 and the libraries (needs internet).
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed.
    echo Install it once by running this in PowerShell, then try again:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

uv run --python 3.12 --with-requirements requirements.txt GUI.py
if errorlevel 1 pause
