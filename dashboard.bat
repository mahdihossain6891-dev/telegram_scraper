@echo off
REM Launch the Streamlit dashboard in the default browser.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

REM Stop stale Streamlit processes still holding port 8501.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul

".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless false
exit /b %ERRORLEVEL%
