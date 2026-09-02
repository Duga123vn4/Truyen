@echo off & chcp 65001 >nul & set "PYTHONIOENCODING=utf-8" & set "PYTHONUTF8=1" & set "PYTHONPATH=%~dp0..;%PYTHONPATH%" & for %%P in (python.exe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do @(%%P -X utf8 "%~dp0src\apps\manager_app.py" %* && exit /b 0)
echo [ERROR] Không tìm thấy Python trên hệ thống! Vui lòng cài đặt Python 3.10+.
pause
