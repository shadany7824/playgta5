@echo off
cd /d "%~dp0"
rem ============================================================
rem  PlayGTA5 - BALANCED profile (v3) for 4GB HD620
rem  800x450 30 FPS base + sharp textures, particles, 4x aniso
rem  Shadows/reflections/grass OFF (they caused 500-2000ms freezes)
rem  NOTE: heavier quality profile; for smoothest play use Play-Optimized.cmd
rem  WARNING: on this 4GB machine this profile exhausted memory before
rem  (game heap hit the 3072 MB cap -> THREAD REJECTION crash).
rem  Use only after a RAM upgrade; otherwise stick to Ultra/Optimized.
rem ============================================================

rem Warn if running on battery (battery mode halves performance)
powershell -NoProfile -Command "if (-not (Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue).PowerOnline) { Write-Host '*** ON BATTERY: PLUG IN THE CHARGER - battery mode cuts FPS ***' -ForegroundColor Yellow }"

rem High performance power plan (falls back to this PC's custom max plan)
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1 || powercfg /setactive 44444444-4444-4444-4444-444444444449 >nul 2>&1

rem Free RAM: close background bloat before playing (4GB machine)
taskkill /f /im copilotapp.exe >nul 2>&1
taskkill /f /im copilotapphost.exe >nul 2>&1
taskkill /f /im msedge.exe >nul 2>&1
taskkill /f /im OneDrive.exe >nul 2>&1
taskkill /f /im opencode.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

rem Give Chrome high GPU priority (Windows graphics preference)
reg add "HKCU\Software\Microsoft\DirectX\UserGpuPreferences" /v "C:\Program Files\Google\Chrome\Application\chrome.exe" /t REG_SZ /d "GpuPreference=2;" /f >nul 2>&1

if not exist "runtime\python.exe" (
  echo Runtime missing. Run Download-Game.cmd first.
  pause
  exit /b 1
)

rem Start local server if not already listening on 8000 (own minimized window: survives this launcher closing)
netstat -ano | findstr /r ":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
  start "GTA5 Server" /min "%~dp0runtime\python.exe" "%~dp0serve_local.py"
  echo Waiting for the game server...
  powershell.exe -NoProfile -Command "for ($i=0; $i -lt 25; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
  if errorlevel 1 (
    echo The game server did not start on port 8000.
    echo Close this window and run Play-Quality.cmd again.
    pause
    exit /b 1
  )
)

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --start-maximized ^
  --autoplay-policy=no-user-gesture-required ^
  --disable-background-timer-throttling ^
  --disable-renderer-backgrounding ^
  --disable-backgrounding-occluded-windows ^
  --disable-features=CalculateNativeWinOcclusion,UseEcoQoSForBackgroundProcess,BatterySaverModeAvailable,HighEfficiencyModeAvailable ^
  --audio-buffer-size=960 ^
  --force-device-scale-factor=1 ^
  --enable-gpu-rasterization ^
  --disk-cache-size=1 ^
  "http://localhost:8000/?low=0&cores=2&res=800x450&fps=30&fixed=1&slots=2&args=-textureQuality=1,-shadowQuality=-1,-reflectionQuality=0,-particleQuality=1,-grassQuality=0,-waterQuality=1,-shaderQuality=1,-anisotropicQualityLevel=2,-multiSampleQuality=0,-cityDensity=0,-pedVariety=0,-vehicleVariety=0,-lodScale=0,-pedLodBias=0,-vehicleLodBias=0"

rem Keep the game responsive: raise Chrome priority while playing (re-applied 3x)
start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"

echo.
echo ============================================
echo  BALANCED launched: 800x450, sharp textures,
echo  particles, 4x anisotropic filter, 30 FPS cap.
echo.
echo  IMPORTANT: if a small "GTA5 Server" window appears,
echo  LEAVE IT OPEN - it serves the game files.
echo  Press = in-game to show FPS. For smoothest play use Play-Optimized.cmd.
echo.
echo  WARNING: this heavy profile crashed this laptop twice
echo  (out of memory at the 3 GB engine cap). If the game dies,
echo  use Play-Ultra.cmd instead.
echo ============================================
timeout /t 6 >nul
