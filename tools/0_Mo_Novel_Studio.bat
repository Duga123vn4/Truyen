@echo off
title 🌟 Novel Studio UI (LinguaGacha Edition)
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    python.exe
) do (
    if exist %%P (
        %%P -X utf8 "%~dp0src\apps\studio_server.py"
        exit /b 0
    )
)

echo [ERROR] Khong tim thay Python tren he thong!
pause
exit /b 1
