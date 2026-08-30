@echo off
chcp 65001 > nul
title 5. Chuyen Doi Van Ban Sang Audio MP3

if "%~1"=="" (
    echo.
    echo ====================================================================
    echo HUONG DAN SU DUNG:
    echo 1. Hay KEO THA bat ky file van ban nao (.txt, .md, .docx) de len file nay.
    echo 2. Chuong trinh se tu dong tao file Audio .mp3 trong thu muc audio/
    echo ====================================================================
    echo.
    pause
    exit /b
)

echo [*] Dang tao file Audio MP3 cho: %~1
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0export_audio.ps1" -InputFile "%~1"
echo.
pause
