# 12 — Custom WGSL post shader applied (2026-11-20)

## What changed
- Patched the **mirror copy actually used by the browser**: `mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js`, function `makeBlit()` (~line 2423). Backup: `wgpu_worker.js.bak-20261120`.
- Replaced the 1:1 `textureLoad(src, pos, 0)` blit with a 5-tap WGSL post pass: 4-neighbour unsharp (`0.14` strength), slight saturation (1.05) + contrast/brightness grade, clamped to 0..1. No new bindings, no packs, no COOP/COEP change.
- `node --check` on the patched JS: clean.
- Launched with **no `fx=`** (so no double sharpening) at 960x540, shadow 0 / reflection 1, `log=1`: `validation errors +0`, no shader/WGSL errors, world renders correctly (screenshot verified). FPS in a dense scene ~11–12 (2581 draws) — scene-dependent, not a clean A/B vs the CSS preset.
- Root `E:\gta\playgta5\wgpu_worker.js` is a dev copy and was NOT patched; the browser loads the mirror one.

## Realistic grade (later same day)
- Owner asked for a "realistic" look → patched the same `makeBlit()` FS again, backup `wgpu_worker.js.bak-real-20261120`.
- New grade: unsharp reduced 0.14→0.10, saturation 1.05→0.96, gentle S-curve contrast (`mix(col, col*col*(2-col), 0.22)`), warm highlights / cool shadows split-tone, vignette ×0.30 at corners, subtle static grain ±0.007. Verified `node --check` clean, 0 WebGPU validation errors, game renders. Dense scene ~10.2 FPS at 2366 draws (scene-dependent; no clean A/B).
- To revert to the earlier clean shader: copy `wgpu_worker.js.bak-real-20261120` over the mirror file. To revert to stock: use `wgpu_worker.js.bak-20261120`.

## Notes
- `Verify-Game.cmd` will now report this mirror file as modified vs SHA-256 inventory — expected after a deliberate shader patch.
- To revert: copy `wgpu_worker.js.bak-20261120` over the mirror file, then reload.
- Launcher: `Play-Shader.cmd` (GPU shader preset, no CSS filter).
- This is the browser-port equivalent of a tiny ReShade/SweetFX preset, implemented in WGSL.
