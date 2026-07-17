@echo off
REM Validate .env before running Telegram commands.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" check_env.py
exit /b %ERRORLEVEL%
