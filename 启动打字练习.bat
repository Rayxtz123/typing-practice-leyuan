@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "C:\Users\HUAWEI\miniconda3\pythonw.exe" "%~dp0main.py"
