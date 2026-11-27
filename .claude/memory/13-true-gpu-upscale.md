# 13 — True GPU upscale patch (2026-11-20)

## Goal
Instead of letting Chrome bilinearly stretch a 960x540 canvas to the viewport, render the final blit at the **display resolution** with a WGSL sampler (bilinear + unsharp + grade). This is a real FSR-like spatial upscale done in the WebGPU worker.

## Files patched (mirror = the copies actually loaded by the browser)
- `mirror\playgta5.com\index.html` — worker.postMessage now sends `displayW = innerWidth * devicePixelRatio`, `displayH = innerHeight * devicePixelRatio`.
- `mirror\playgta5.com\b\8b0b5899ed\loader.js` — forwards them to the GPU worker as `?display=WxH`.
- `mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js` — parses `DISPLAY`, creates a linear `blitSampler`, `makeBlit()` now uses `textureSampleLevel` with UV + 4 neighbour taps, and `present()` configures the canvas at `DISPLAY` size instead of back-buffer size; bind group has texture (binding 0) + sampler (binding 1).
- Backups: `*.bak-upscale-20261120` next to each file. Earlier shader backups: `wgpu_worker.js.bak-real-20261120`, `wgpu_worker.js.bak-20261120`.

## Verification
- `node --check` clean on wgpu_worker.js + loader.js + index.html module script.
- Launched with no CSS `fx=` at 960x540: **0 WebGPU validation errors**, no WGSL errors, world renders. Dense scene ~10–12 FPS at ~2800–3200 draws (scene-dependent, not an A/B).
- CSS `fx=` filters are now redundant for this path — `Play-Shader.cmd` runs the upscale shader.

## Revert
Copy the three `.bak-upscale-20261120` files back over their originals, reload.
