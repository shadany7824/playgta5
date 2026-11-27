# 01 — Server + launch recipes (verified 2026-11-20)

## Real paths
- Game: `E:\gta\playgta5` — has `runtime\python.exe`, `serve_local.py`, `Server-Watch.ps1`, `mirror\playgta5.com\index.html`, `support\`, launchers `Play-*.cmd`, `game-log.txt`, `server-log.txt`.
- **Old `Start-Process` server died when the tool shell ended.** Start it detached with WMI:
```powershell
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = '"E:\gta\playgta5\runtime\python.exe" "serve_local.py"'
  CurrentDirectory = 'E:\gta\playgta5'
}
# then start watchdog:
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "E:\gta\playgta5\Server-Watch.ps1"'
  CurrentDirectory = 'E:\gta\playgta5'
}
```
Verify: `Get-NetTCPConnection -LocalPort 8000 -State Listen` and `Invoke-WebRequest http://localhost:8000/__support/` → 200.

## Chrome launch (flags that were used successfully)
`--disable-gpu-watchdog --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --enable-gpu-rasterization --force-device-scale-factor=1`

Close one game tab with `WScript.Shell.AppActivate(<chrome main PID>)` + `SendKeys('^w')` before relaunching (two tabs double the load).

## Verified URL recipes
- Smooth / low (owner says this is already good at ~30 FPS):
  `http://localhost:8000/?low=1&res=1024x576&fps=30&slots=5`
- True MAX (owner wants FPS improved HERE, not in low):
  `http://localhost:8000/?low=0&res=1280x720&fps=60&shadows=1&slots=5&log=1&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2,-vehicleVariety=2`
  → measured 7 FPS (see 02). Do NOT present low-mode overrides as "max".

## Log analysis
`game-log.txt` only grows when URL has `log=1`. Mark its length before a run, then read only the appended bytes with `[IO.File]::OpenRead` + `Seek(mark)` — the file is 35+ MB and full of old runs. Key lines: `[wgpu] fps: …`, `POSSIBLE STALL`, `[page env]`, `[mem] wasm memory`.
