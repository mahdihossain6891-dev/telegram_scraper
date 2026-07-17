@echo off
REM Launch the Streamlit dashboard in the default browser.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
exit /b %ERRORLEVEL%
