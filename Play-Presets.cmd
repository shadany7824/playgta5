@echo off
cd /d "%~dp0"
rem ============================================================
rem  PlayGTA5 - graphics PRESETS (avoid the broken in-game Apply)
rem  Known port bug (GitHub issue #32): changing graphics in the
rem  in-game menu and pressing Apply can freeze or refuse to save
rem  on Windows and macOS. These presets set the graphics through
rem  launch arguments instead, which the engine always honours.
rem ============================================================

echo.
echo Select graphics preset:
echo  1 = LOW       (smooth, ~30 FPS, lowest quality)
echo  2 = HIGH OPT  (max textures, shadows 0, reflections 1, ~16 FPS)
echo  3 = MAX       (everything max, 720p, ~7 FPS)
echo  4 = MAX + HD  (same as 3 with sharpen filter for a 1080p look)
echo.
set "PRESET="
set /p PRESET=Enter 1/2/3/4:

if "%PRESET%"=="1" set "URL=http://localhost:8000/?low=1&res=1024x576&fps=30&slots=5"
if "%PRESET%"=="2" set "URL=http://localhost:8000/?low=0&res=960x540&fps=60&slots=5&args=-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-pedVariety=0,-vehicleVariety=0,-lodScale=0,-pedLodBias=0"
if "%PRESET%"=="3" set "URL=http://localhost:8000/?low=0&res=1280x720&fps=60&shadows=1&slots=5&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2"
if "%PRESET%"=="4" set "URL=http://localhost:8000/?low=0&res=1280x720&fps=60&shadows=1&slots=5&fx=hd&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2"

if not defined URL (
  echo Invalid choice.
  pause
  exit /b 1
)

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
)

taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --disable-gpu-watchdog ^
  --disable-background-timer-throttling ^
  --disable-renderer-backgrounding ^
  --disable-backgrounding-occluded-windows ^
  --disable-features=CalculateNativeWinOcclusion,UseEcoQoSForBackgroundProcess,BatterySaverModeAvailable,HighEfficiencyModeAvailable ^
  --audio-buffer-size=960 ^
  --force-device-scale-factor=1 ^
  --enable-gpu-rasterization ^
  --disk-cache-size=1 ^
  "%URL%"

start "GTA5 Prio" /min powershell.exe -NoProfile -Command "Start-Sleep -Seconds 8; foreach ($i in 1..3) { Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { try { $_.PriorityClass = 'High' } catch {} }; Start-Sleep -Seconds 15 }"

echo.
echo Launched preset %PRESET%. Do NOT use in-game Graphics / Apply -
echo relaunch with this menu to change graphics instead.
timeout /t 5 >nul
