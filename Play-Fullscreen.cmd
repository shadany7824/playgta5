@echo off
cd /d "%~dp0"
rem Fullscreen preset: smooth low profile, 1024x576 internal render, ~20-30 FPS.
rem Requires the LAN HTTPS server (serve_local.py --lan --cert --key) on port 8000.
netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
  echo Server not running. Start serve_local.py with --lan --cert --key first.
  pause
  exit /b 1
)
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --start-fullscreen ^
  --ignore-certificate-errors ^
  --window-size=1920,1080 ^
  --disable-gpu-watchdog ^
  --disable-background-timer-throttling ^
  --disable-renderer-backgrounding ^
  --disable-backgrounding-occluded-windows ^
  --disable-features=CalculateNativeWinOcclusion,UseEcoQoSForBackgroundProcess,BatterySaverModeAvailable,HighEfficiencyModeAvailable ^
  --audio-buffer-size=960 ^
  --force-device-scale-factor=1 ^
  --enable-gpu-rasterization ^
  --disk-cache-size=1 ^
  "https://localhost:8000/?low=1&mode=sandbox&res=1024x576&fps=30&slots=5&fixed=1"
start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"
echo Fullscreen preset launched. Press ENTER for Story, SPACE for Sandbox.
timeout /t 5 >nul
