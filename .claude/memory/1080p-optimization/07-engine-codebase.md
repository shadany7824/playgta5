# 07 — Engine codebase check (2026-11-21)

## Finding: no engine source exists here
- `E:\gta\playgta5` contains only compiled artifacts: `mirror\playgta5.com\b\8b0b5899ed\game.wasm` (63.2 MB), `game.js`, `loader.js`, `io_worker.js`, `wgpu_worker.js`, shader packs. No `src/`, `engine/`, `*.cpp`, `*.h`, `*.hlsl`, `*.wgsl` engine source.
- `README.md:7` states it is "a compiled client snapshot, not the original game-engine source code".
- `ENGINE_INVESTIGATION.md:7-13`: the wasm's 6.8 MB `name` section has 41,244 `rage::` symbols + 478 D3D11/DXGI symbols and embedded dev paths (`fwdrawlist\drawlist.cpp`, `grcore\effect_d3d11.cpp`) — symbols/strings only, not code. `snapshot\engine-evidence.json` holds parsed evidence.

## What this means for FPS
- The ~2,000–2,700 draws/frame are emitted by the compiled engine and replayed one-by-one by the single JS WebGPU worker. `game-log.txt` shows `gpu wait = 0 ms`, worker idle ≈ 0, `clamped draws +0`.
- Draw count cannot be capped from outside: the only `doDraw()` clamp is a buffer-safety check that never fires; `debugDraw` is Node-only, not a browser URL param.
- Runtime args that CAN be passed via `?args=` (appended last, `homepage.html:406-407`): `-textureQuality`, `-pedVariety`, `-vehicleVariety`, `-shadowQuality`, `-reflectionQuality`, `-particleQuality`, `-grassQuality`, `-cityDensity`, `-lodScale`, `-pedLodBias`, `-vehicleLodBias`, `-numCores`, `-frameLimit`. Never use `-shaderQuality=0`/`-waterQuality=0` (DistortionParams abort).
- In practice density/LOD/variety cuts barely moved max-mode draws/FPS; shadow/reflection quality gave the only real wins. Lower resolution doesn't help (CPU/draw-bound).
- Structural fixes that would actually cut draw cost (render bundles, indirect drawing, or changing what the engine emits) need worker rewrites or recompiling the engine — both high risk and unproven for this changing draw list (see `06-web-research.md`).

## Bottom line
There is no engine source to optimize here. The measured wall is the wasm-emitted draw list replayed on a 2-core i3; all safe JS/config levers are exhausted.
