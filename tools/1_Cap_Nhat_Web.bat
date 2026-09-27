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
echo [Dang day len GitHub Pages...]
git add -A
git commit -m "Novel Studio: Cap nhat chuong moi vao Web Reader"
git push origin main
echo [OK] Da day len GitHub thanh cong!
echo Trang web online se cap nhat sau 1-2 phut: https://duga123vn4.github.io/Truyen/
echo.
pause

