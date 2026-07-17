@echo off
REM List and select accessible Telegram chats — uses project venv.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" chat_discovery.py
exit /b %ERRORLEVEL%
