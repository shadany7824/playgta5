@echo off
cd /d "%~dp0"
rem ============================================================
rem  PlayGTA5 - tuned for i3-7100U + HD 620 + 4GB -> 30 FPS
rem  800x450 render, 30 FPS cap, low-mem profile, GPU priority
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

rem Ensure self-healing game server (watcher starts python if down; survives this launcher closing)
start "GTA5 Server" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Server-Watch.ps1"
echo Waiting for the game server...
powershell.exe -NoProfile -Command "for ($i=0; $i -lt 25; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
if errorlevel 1 (
  echo The game server did not start on port 8000.
  echo Close this window and run Play-Optimized.cmd again.
  pause
  exit /b 1
)

rem 800x450 = ~50%% of 1600x900 window cost; 30 FPS VSync cap for stability
rem low=1 forces lowest settings even if browser lies about RAM
rem extra --disable-features: no Windows efficiency-mode (EcoQoS) on the game
rem process, no Energy Saver / Memory Saver inside this game session
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --start-maximized ^
  --disable-gpu-watchdog ^
  --disable-background-timer-throttling ^
  --disable-renderer-backgrounding ^
  --disable-backgrounding-occluded-windows ^
  --disable-features=CalculateNativeWinOcclusion,UseEcoQoSForBackgroundProcess,BatterySaverModeAvailable,HighEfficiencyModeAvailable ^
  --audio-buffer-size=960 ^
  --force-device-scale-factor=1 ^
  --enable-gpu-rasterization ^
  --disk-cache-size=1 ^
  "http://localhost:8000/?low=1&res=800x450&fps=30&fixed=1&slots=2"

rem Keep the game responsive: raise Chrome priority while playing (re-applied 3x)
start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"

echo.
echo ============================================
rem  Game launched at 800x450, 30 FPS cap.
rem  Press = (equals key) in-game to show FPS.
rem  If still under 30: close ALL other tabs/apps,
rem  then run Play-Ultra.cmd (640x360).
echo ============================================
timeout /t 6 >nul
