@echo off
cd /d "%~dp0"
rem 720p with max shadows + max reflections, 50% density/variety/LOD.
netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
  start "GTA5 Server" /min "%~dp0runtime\python.exe" "%~dp0serve_local.py"
  powershell -NoProfile -Command "for ($i=0; $i -lt 25; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
)
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
  "http://localhost:8000/?low=0&mode=sandbox&res=1280x720&fps=60&slots=5&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=1,-pedVariety=1,-vehicleVariety=1,-lodScale=1,-pedLodBias=1,-vehicleLodBias=1"
start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"
echo 720p High preset launched. Press = for FPS.
timeout /t 5 >nul
