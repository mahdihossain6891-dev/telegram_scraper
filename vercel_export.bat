@echo off
REM Copy local SQLite export into the Vercel web dashboard folder.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

if not exist "exports\export.json" (
    echo No exports\export.json found. Run export.bat first.
    exit /b 1
)

if not exist "web\public\data" mkdir "web\public\data"
copy /Y "exports\export.json" "web\public\data\export.json" >nul
echo Copied exports\export.json to web\public\data\export.json
echo.
echo Next steps:
echo   1. Review the JSON and remove anything sensitive if needed
echo   2. Commit and push to GitHub
echo   3. Redeploy the Vercel project (root directory: web)
exit /b 0
