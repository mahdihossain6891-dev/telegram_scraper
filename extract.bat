@echo off
REM Extract URLs, emails, hashtags, etc. from stored messages.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" entity_extractor.py
exit /b %ERRORLEVEL%
