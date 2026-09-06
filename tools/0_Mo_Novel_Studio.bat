@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"

echo =======================================================
echo 🌟 KHỞI ĐỘNG NOVEL STUDIO UI (LINGUAGACHA EDITION)
echo =======================================================

:: Kiểm tra xem port 8765 đã chạy chưa
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo [INFO] Đang khởi động Backend Server trên cổng 8765...
    for %%P in (
        python.exe
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) do (
        if exist %%P (
            start "" /B %%P -X utf8 "%~dp0src\apps\studio_server.py"
            goto :wait_server
        )
    )
    start "" /B python -X utf8 "%~dp0src\apps\studio_server.py"
)

:wait_server
timeout /t 2 /nobreak >nul

echo [INFO] Đang mở giao diện Desktop Window...

:: Tìm trình duyệt hỗ trợ chế độ App Window (Edge hoặc Chrome)
for %%B in (
    "%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"
    "%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"
    "%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"
    "%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"
    "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
) do (
    if exist %%B (
        start "" %%B --app=http://localhost:8765/studio --window-size=1280,840
        exit /b 0
    )
)

:: Nếu không tìm thấy, mở bằng trình duyệt mặc định
start http://localhost:8765/studio
exit /b 0
