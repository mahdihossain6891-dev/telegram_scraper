@echo off
REM Scrape, export, and sync dashboard data on a loop (Ctrl+C to stop).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

call check_env.bat
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" auto_update.py
exit /b %ERRORLEVEL%
