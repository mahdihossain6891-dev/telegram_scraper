@echo off
REM Copy export.json for Streamlit Cloud deployment.
cd /d "%~dp0"

if not exist "exports\export.json" (
    echo No exports\export.json found. Run export.bat first.
    exit /b 1
)

if not exist "demo" mkdir "demo"
copy /Y "exports\export.json" "demo\export.json" >nul
echo Copied exports\export.json to demo\export.json
echo.
echo Next steps:
echo   1. Review demo\export.json and remove sensitive data if needed
echo   2. git add demo\export.json
echo   3. git commit -m "Add dashboard export data"
echo   4. git push
echo   5. Deploy on https://share.streamlit.io using main file app.py
exit /b 0
