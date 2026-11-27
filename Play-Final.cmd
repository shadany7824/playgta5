@echo off
cd /d "%~dp0"
rem ============================================================
rem  PlayGTA5 - FINAL optimized preset (verified 2026-11-20)
rem  Screen: 1920x1080 maximized window
rem  Render: 960x540 + soft HD sharpen filter -> sharp 1080p look
rem  Quality: max textures, shadows 0, reflections 1,
rem           particles/grass/city/LOD off, 5 GPU frame slots
rem  Measured: 16.5-16.8 FPS on i3-7100U / HD 620 / 20 GB RAM
rem  Known: in-game Graphics/Apply is broken (port issue #32).
rem         Change graphics with Play-Settings.cmd, not in-game.
rem ============================================================

powershell -NoProfile -Command "if (-not (Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue).PowerOnline) { Write-Host '*** ON BATTERY: PLUG IN THE CHARGER - battery mode cuts FPS ***' -ForegroundColor Yellow }"

powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1 || powercfg /setactive 44444444-4444-4444-4444-444444444449 >nul 2>&1

reg add "HKCU\Software\Microsoft\DirectX\UserGpuPreferences" /v "C:\Program Files\Google\Chrome\Application\chrome.exe" /t REG_SZ /d "GpuPreference=2;" /f >nul 2>&1

if not exist "runtime\python.exe" (
  echo Runtime missing. Run Download-Game.cmd first.
  pause
  exit /b 1
)

netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
  echo Starting local game server...
  start "GTA5 Server" /min "%~dp0runtime\python.exe" "%~dp0serve_local.py"
  powershell -NoProfile -Command "for ($i=0; $i -lt 25; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
  if errorlevel 1 (
    echo The game server did not start on port 8000.
    pause
    exit /b 1
  )
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
  "http://localhost:8000/?low=0&mode=sandbox&res=960x540&fps=60&slots=5&fx=hd&args=-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-pedVariety=0,-vehicleVariety=0,-lodScale=0,-pedLodBias=0"

start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"

echo.
echo ============================================
echo  FINAL preset launched.
echo  960x540 render, soft HD filter, full-screen.
echo  Expected ~16-17 FPS. Press = for FPS.
echo  For other graphics presets: Play-Settings.cmd
echo ============================================
timeout /t 6 >nul
