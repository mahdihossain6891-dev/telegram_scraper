@echo off
REM Start MongoDB in Docker (requires Docker Desktop running).
cd /d "%~dp0"

set "DOCKER=%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"
if not exist "%DOCKER%" set "DOCKER=docker"

"%DOCKER%" compose up -d
if errorlevel 1 (
    echo.
    echo Failed to start MongoDB container.
    echo 1. Open "Docker Desktop" from the Start menu
    echo 2. Finish first-run setup / reboot if prompted
    echo 3. Wait until Docker shows "Engine running"
    echo 4. Re-run mongo.bat
    exit /b 1
)
echo MongoDB is running on mongodb://127.0.0.1:27017
exit /b 0
