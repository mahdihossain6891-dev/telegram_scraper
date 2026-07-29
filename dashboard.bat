@echo off
REM Launch FastAPI live API + Next.js dashboard.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

REM Prefer PATH, then default Node.js install location (fresh installs often
REM need a new terminal before PATH updates).
set "NODE_DIR=%ProgramFiles%\nodejs"
if exist "%NODE_DIR%\node.exe" set "PATH=%NODE_DIR%;%PATH%"

where node >nul 2>&1
if errorlevel 1 (
    echo Node.js is not installed or not on PATH.
    echo Install Node.js LTS from https://nodejs.org then reopen this terminal.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo npm was not found. Reinstall Node.js LTS from https://nodejs.org
    exit /b 1
)

if not exist "web\node_modules" (
    echo Installing Next.js dependencies...
    pushd web
    call npm install
    if errorlevel 1 (
        echo npm install failed.
        popd
        exit /b 1
    )
    popd
)

if not exist "web\.env.local" (
    if exist "web\.env.local.example" copy /Y "web\.env.local.example" "web\.env.local" >nul
)

set "API_PORT=8510"

REM Stop stale processes still holding API / Next ports.
echo Stopping stale API and dashboard processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-dashboard.ps1"

echo Starting FastAPI live API on http://127.0.0.1:%API_PORT%
start "telegram-scraper-api" cmd /k "cd /d "%~dp0" && "%~dp0.venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port %API_PORT% --reload"

timeout /t 2 /nobreak >nul
start "" "http://localhost:3000"

echo Starting Next.js dashboard on http://127.0.0.1:3000
pushd web
call npm run dev
popd
exit /b %ERRORLEVEL%
