@echo off
title 1. Dong Bo va Cap Nhat Chuong Vao Web
chcp 65001 >nul
echo ========================================================
echo   DONG BO VA CAP NHAT CHUONG MOI VAO WEB DOC TRUYEN
echo ========================================================
echo.
echo Dang quet thu muc translated/ va dong bo vao chapters.js...
powershell -ExecutionPolicy Bypass -File "%~dp0build_chapters_js.ps1"
echo.
echo ========================================================
echo [OK] Hoan tat! Web da duoc cap nhat day du tat ca cac chuong.
echo ========================================================
echo.
pause
