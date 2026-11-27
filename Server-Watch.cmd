@echo off
cd /d "%~dp0"
title GTA5 Server (auto)
echo [%date% %time%] watcher started>>server-log.txt

:loop
netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  timeout /t 10 /nobreak >nul
  goto loop
)

echo [%date% %time%] server down - starting>>server-log.txt
powershell.exe -NoProfile -Command "Start-Process -FilePath '%~dp0runtime\python.exe' -ArgumentList '%~dp0serve_local.py' -WorkingDirectory '%~dp0' -WindowStyle Minimized"
timeout /t 25 /nobreak >nul
goto loop
