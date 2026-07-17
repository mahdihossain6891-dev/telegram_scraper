@echo off
REM Export stored data to CSV and JSON in exports/
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" exporter.py
exit /b %ERRORLEVEL%
