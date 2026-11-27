@echo off
cd /d "%~dp0"
rem ============================================================
rem  PlayGTA5 - 720p SHARP profile (experiment)
rem  1280x720 render = much sharper picture (1.2x upscale vs 1.9x)
rem  Same proven settings as Play-Quality + FXAA anti-aliasing
rem  EXPECTATION: sharper look, but likely 15-25 FPS and more lag
rem  than Play-Quality.cmd (720p = 2.5x the pixels of 800x450)
rem  If too laggy: go back to Play-Quality.cmd
rem ============================================================

rem High performance power plan
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1

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
    echo Close this window and run Play-720p.cmd again.
    pause
    exit /b 1
  )
)

rem FXAA flags: three spellings passed because the engine accepts the one it knows
rem (unknown options are warnings only, proven safe in the logs)
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
  "http://localhost:8000/?low=0&cores=2&res=1280x720&fps=30&fixed=1&slots=2&args=-textureQuality=1,-shadowQuality=-1,-reflectionQuality=0,-particleQuality=1,-grassQuality=0,-waterQuality=1,-shaderQuality=1,-anisotropicQualityLevel=2,-multiSampleQuality=0,-FXAA_Enabled=1,-fXAA_Enabled=1,-fxaa=1,-cityDensity=0,-pedVariety=0,-vehicleVariety=0,-lodScale=0,-pedLodBias=0,-vehicleLodBias=0"

echo.
echo ============================================
echo  720p SHARP profile launched.
echo  - Much sharper picture than 800x450
echo  - FXAA anti-aliasing on (smoother edges)
echo  - No shadows/reflections/grass (kept smooth-ish)
echo.
echo  IMPORTANT: keep laptop PLUGGED IN while playing.
echo  If FPS feels too low, close everything and use
echo  Play-Quality.cmd (800x450) instead.
echo  Press = in-game to show FPS.
echo ============================================
timeout /t 6 >nul
