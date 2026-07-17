@echo off
REM Authenticate with Telegram — uses project venv, no activation needed.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

call check_env.bat
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" telegram_client.py
exit /b %ERRORLEVEL%
