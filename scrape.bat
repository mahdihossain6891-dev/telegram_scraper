@echo off
REM Collect messages from a selected chat — uses project venv.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" message_scraper.py
exit /b %ERRORLEVEL%
