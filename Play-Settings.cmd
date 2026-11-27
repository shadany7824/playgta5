@echo off
cd /d "%~dp0"
rem Open the local graphics-settings page (works around the broken in-game Apply).

netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
  start "GTA5 Server" /min "%~dp0runtime\python.exe" "%~dp0serve_local.py"
  powershell -NoProfile -Command "for ($i=0; $i -lt 25; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
)

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:8000/__support/settings.html"
echo Opened graphics settings page in Chrome.
timeout /t 3 >nul
