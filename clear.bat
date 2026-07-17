@echo off
REM Clear private chats and/or runtime data (session, DB, logs, exports).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" clear_data.py %*
exit /b %ERRORLEVEL%
