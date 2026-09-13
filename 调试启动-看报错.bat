@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\HUAWEI\miniconda3\python.exe" "%~dp0main.py"
echo.
echo ---- program exited ----
pause
