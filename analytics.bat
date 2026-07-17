@echo off
REM Run analytics over stored messages and save charts.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" analytics.py %*
exit /b %ERRORLEVEL%
