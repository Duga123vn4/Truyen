@echo off
title 1. Dong Bo va Cap Nhat Chuong Vao Web
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
echo ========================================================
echo   DONG BO VA CAP NHAT CHUONG MOI VAO WEB DOC TRUYEN
echo ========================================================
echo.
echo Dang quet thu muc translated/ va dong bo vao web/chapters.js...

python -X utf8 "%~dp0src\services\web_builder.py"
if %errorlevel% neq 0 (
    echo [Canh bao] Python gap loi, chuyen sang che do fallback PowerShell...
    powershell -ExecutionPolicy Bypass -File "%~dp0build_chapters_js.ps1"
)

echo.
echo ========================================================
echo [OK] Hoan tat! Web cuc bo da duoc cap nhat day du chuong moi.
echo ========================================================
echo.
set /p PUSH_CHOICE="Ban co muon dong bo day chuong moi len GitHub Pages luon khong? (Y/N, mac dinh N): "
if /i "%PUSH_CHOICE%"=="y" (
    echo.
    echo Dang day du lieu len GitHub...
    git add -A
    git commit -m "Novel Studio: Cap nhat chuong moi vao Web Reader"
    git push origin main
    echo [OK] Da day len GitHub thanh cong!
)
echo.
pause

