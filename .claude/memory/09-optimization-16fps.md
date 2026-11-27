# 09 — Optimization pass: 13-15 -> 16.5-16.8 FPS (2026-11-20)

## Starting point
Owner reported high-graphics preset was running 13-15 FPS and asked for a 100% verification pass using the accumulated log data.

## Audit data available
`audit-2026-11-20.csv` (13 samples before the sampler died): GPU 3D 63-79%, RAM 62-76%, 11-13 Chrome processes, top CPU always Chrome renderer. No external CPU hog found. So optimization had to come from the game's own draw-load, not background processes.

## Controlled test (same scene, `log=1`, story mode, 960x540, max textures, particles/grass/city/LOD 0)
- Previous medium: `shadowQuality=1, reflectionQuality=2` → 13-15 FPS, ~1300-1800 draws/frame.
- **New optimized: `shadowQuality=0, reflectionQuality=1`** → steady **16.5-16.8 FPS**, ~1150-1250 draws/frame, worker 98-99% busy, readback 5.0/frame. Verified over two separate 45-60 s windows after `world shown`.
- Further test `shadowQuality=-1, reflectionQuality=0` did NOT reach steady state (game stuck in prologue cutscene and tool focus stole keyboard); result unproven — do not claim.

## Changes made
- `support\settings.html`: preset 2 renamed "High (optimized)" and now uses shadow=0 / reflection=1, card text updated to measured ~16.5 FPS.
- `Play-Presets.cmd`: preset 2 URL updated to the same values; menu label updated.
- Both verified by file read; served settings page previously verified HTTP 200.

## Honest conclusion
- Real gain: ~+2-3 FPS (13-15 → 16.5-16.8) with textures still max and shadows still enabled at the lowest level.
- The hard wall remains: ~1150 draws/frame saturating the single WebGPU worker; GPU itself is only ~56-79% busy. 20+ FPS in true high mode needs fewer engine draws or stronger hardware.
- Keep using the settings page / Play-Presets.cmd; do NOT use the broken in-game Apply (issue #32).
