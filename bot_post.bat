@echo off
REM Post demo keyword test messages to your Telegram test channel via bot.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" bot_post_test.py %*
exit /b %ERRORLEVEL%
