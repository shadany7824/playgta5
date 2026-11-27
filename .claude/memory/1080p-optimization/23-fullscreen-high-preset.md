# 23 — Fullscreen high-graphics preset added (2026-11-21)

- `Play-Fullscreen-High.cmd`: fullscreen Chrome, HTTPS, **1024x540 internal** (changed from 720p on owner request), `low=0`, max textures/shadows/reflections/particles/grass, 50% city/ped/vehicle/LOD, slots 5. Uses same server (must be running with `--lan --cert --key`).
- `support/settings.html`: added card "6 · High graphics" with the same URL.
- Launched it; Chrome title `game - Google Chrome`, server PID 10392.
- Measured with `log=1`: **7.3–7.9 FPS**, 2696–3758 draws/frame, worker 95–100% busy, 0 validation errors — not 10–15 FPS. The 20-30 FPS option remains `Play-Fullscreen.cmd` (`low=1`, 1024x576, 30 cap). Both can't coexist; high graphics costs ~3-4× frame time.
