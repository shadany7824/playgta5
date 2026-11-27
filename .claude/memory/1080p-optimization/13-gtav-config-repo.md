# 13 — gamingbyWPG/GTAV_config repo + frame-scaling test (2026-11-21)

Repo: `github.com/gamingbyWPG/GTAV_config` — only two folders: `Default Low/` and `Lowest/`, each containing `settings.xml` for **native GTA V** (schema `version=27`). The `Lowest` one sets all graphics to 0 and has `<VideoCardDescription>Intel(R) UHD Graphics 620</VideoCardDescription>`.

## What we tried from it
Our port's `settings.xml` (from IndexedDB `/userdata/Documents/Rockstar Games/GTA V/settings.xml`) was minimal:
```
<Settings><SamplingMode value="3" /><VideoCardDescription>N</VideoCardDescription>
```
- `VideoCardDescription` was garbage (`N`), so we set it to the real GPU `Intel(R) HD Graphics 620` (via `support/userdata-fix.html`, logged as `[USERDATA-FIXED]`).
- `SamplingMode=3` = GTA V frame scaling 0.75x (native GTA V: 1920x1080 output, 1440x810 internal). Kept it.

## Result
True 1920x1080 test after the fix: **~5.9–6.4 FPS, ~2800 draws/frame**, worker 89–92% busy — no change from before. The port's engine command line includes `-forceResolution -width=1920 -height=1080` (index.html:406), so the engine ignores `SamplingMode` for internal resolution. So the GitHub config offers no FPS win here.

## Verdict
Native `settings.xml` configs don't apply to this browser port. Our internal-resolution + WGSL upscale path (note 13) remains the only way to lower draws while keeping a 1080p-sized image.
