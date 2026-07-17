@echo off
REM Scrape keyword-flagged messages from ALL accessible chats.
REM Usage: scrape_all.bat [scope] [limit]
REM Scopes: all (default), private, groups, channels, non-private
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

call check_env.bat
if errorlevel 1 exit /b 1

set SCOPE=%~1
set LIMIT=%~2
if "%SCOPE%"=="" set SCOPE=private
if "%LIMIT%"=="" set LIMIT=1000

if /I "%SCOPE%"=="all" (
    ".venv\Scripts\python.exe" message_scraper.py all %LIMIT%
) else (
    ".venv\Scripts\python.exe" message_scraper.py all-%SCOPE% %LIMIT%
)
exit /b %ERRORLEVEL%
