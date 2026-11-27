@echo off
cd /d "%~dp0"
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1 || powercfg /setactive 44444444-4444-4444-4444-444444444449 >nul 2>&1
reg add "HKCU\Software\Microsoft\DirectX\UserGpuPreferences" /v "C:\Program Files\Google\Chrome\Application\chrome.exe" /t REG_SZ /d "GpuPreference=2;" /f >nul 2>&1
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
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
  "http://localhost:8000/?log=1&low=0&mode=sandbox&res=1920x1080&fps=0&slots=5&args=-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=0"
start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"
