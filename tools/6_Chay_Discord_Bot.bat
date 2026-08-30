@echo off
chcp 65001 >nul
title NOVEL AI — DISCORD BOT STUDIO V3.0
color 0b
cls

echo ===============================================================================
echo      🤖 NOVEL AI DISCORD STUDIO — TRẠM RADIO & THƯ VIỆN TRUYỆN DISCORD V3.0
echo ===============================================================================
echo.
echo   • Kết nối Discord Server, phát Radio Audio TTS và đọc truyện qua Slash Commands
echo.
echo -------------------------------------------------------------------------------
echo [1] 🚀 Khởi Chạy Discord Bot Ngay
echo [2] ⚙️ Cấu Hình Token Bot Discord
echo [3] 📦 Cài Đặt / Cập Nhật Thư Viện (discord.py, edge-tts)
echo [0] 🚪 Thoát
echo -------------------------------------------------------------------------------
echo.

set /p choice="👉 Nhập lựa chọn của bạn [0-3]: "

if "%choice%"=="1" goto run_bot
if "%choice%"=="2" goto config_bot
if "%choice%"=="3" goto install_deps
if "%choice%"=="0" exit /b
goto menu

:run_bot
cls
echo ===============================================================================
echo   🚀 ĐANG KHỞI CHẠY DISCORD BOT NOVEL AI...
echo   (Nhấn Ctrl + C để dừng Bot)
echo ===============================================================================
echo.
python "%~dp0tools\discord_novel_bot.py"
pause
exit /b

:config_bot
cls
echo ===============================================================================
echo   ⚙️ CẤU HÌNH DISCORD BOT TOKEN
echo ===============================================================================
echo.
notepad "%~dp0tools\discord_bot_config.json"
exit /b

:install_deps
cls
echo ===============================================================================
echo   📦 ĐANG CÀI ĐẶT THƯ VIỆN DISCORD BOT...
echo ===============================================================================
echo.
python -m pip install "discord.py[voice]" edge-tts PyNaCl imageio-ffmpeg
echo.
echo ✅ Cài đặt hoàn tất!
pause
exit /b
