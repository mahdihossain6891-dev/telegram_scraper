@echo off
REM Run scrape -> extract -> analytics -> export for local testing.
REM Usage: run_test.bat [chat_index] [limit]
REM Example: run_test.bat 1 1000
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

set CHAT_INDEX=%~1
set LIMIT=%~2
if "%CHAT_INDEX%"=="" set CHAT_INDEX=1
if "%LIMIT%"=="" set LIMIT=1000

echo.
echo === Step 1/4: Scrape chat index %CHAT_INDEX% (limit %LIMIT%) ===
".venv\Scripts\python.exe" message_scraper.py %CHAT_INDEX% %LIMIT%
if errorlevel 1 exit /b 1

echo.
echo === Step 2/4: Entity extraction ===
".venv\Scripts\python.exe" entity_extractor.py
if errorlevel 1 exit /b 1

echo.
echo === Step 3/4: Analytics ===
".venv\Scripts\python.exe" analytics.py
if errorlevel 1 exit /b 1

echo.
echo === Step 4/4: Export ===
".venv\Scripts\python.exe" exporter.py
if errorlevel 1 exit /b 1

echo.
echo Pipeline complete. Run dashboard.bat to view results in the browser.
exit /b 0
