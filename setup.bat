@echo off
REM Create venv and install dependencies — no PowerShell activation required.
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found on PATH. Install Python 3.11+ first.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env from .env.example — add your Telegram API credentials.
)

echo.
echo Setup complete. Run auth.bat to log in to Telegram.
exit /b 0
