# 22 — Web research: official 20-30 FPS path + launcher fix (2026-11-21)

## Web findings
- Official Grand-V / playgta5 READMEs: lower-memory profile is `?low=1&fps=30&res=1280x720`; compatibility preset = 720p/30, performance = 540p/60, balanced = 720p/60. Every preset uses `low=1` with shadows off. FPS cap is a cap, not a guarantee.
- Native GTA V Intel HD 620 benchmarks (KnowGamePlay): 1280x720 low ≈ 28-34 FPS, 1366x768 ≈ 26, 1920x1080 ≈ 14. Disabling shadows/reflections and lowering population density are the biggest wins.
- Dual-channel RAM can add up to ~40% on HD 620 (our machine is flex mode 4+16 GB, not dual-channel).
- Web best practice: render at lower internal resolution and upscale to full screen; our WGSL upscale patch already does this. Old WebGL test: full-res 6 FPS, half-res 20 FPS, half-res upscaled 16 FPS.

## Applied
- `touch-controls.js`: ENTER button now dispatches `Enter` (menu Story Mode) instead of `KeyF`; added separate VEH button for `KeyF` (enter/exit vehicle). `node --check` clean.
- `Play-Fullscreen.cmd`: URL changed to `https://localhost:8000/?low=1&mode=sandbox&res=1024x576&fps=30&slots=5&fixed=1` — the measured ~30 FPS preset, rendered low and upscaled to fullscreen by the WGSL shader.
- Relaunched Chrome fullscreen with that URL; title `game - Google Chrome`, server PID 10392.

## Verdict
The 20-30 FPS target is achievable only with the low profile (we measured 30.0 FPS at 1024x576). High-quality max settings remain ~7-9 FPS; fullscreen upscale keeps the image full-size without changing internal resolution.
