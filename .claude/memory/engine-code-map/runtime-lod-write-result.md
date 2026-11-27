# Runtime LOD-global write via JS — IMPLEMENTED, mechanism works, no gain at 1.0 (2026-11-23)

## Implementation (mirror `wgpu_worker.js`, backup `.bak-lodpatch-20261123` / `.bak-lodpatch2-20261123`)
- Added `patchLod()` in the worker: writes float 1.0 to wasm addresses `19446852` (settings LodScale) and `23318984` (global LOD scale).
- Uses fresh `DataView(mem.buffer)` + `Int32Array` bit pattern + `Atomics.store` (little-endian, avoids stale views after grow + torn values).
- Hooked per-frame at start of `present()`.
- `node --check` OK, validation errors 0 in game.

## Critical discovery: the loader whitelists worker params
- `loader.js` line 13-23 builds `gq = new URLSearchParams()` and only forwards slots/display/syncpipelines/log/low/nopack/shotrt/limits. `?lodpatch=2` on the PAGE never reaches the WORKER's `self.location.search`. First attempt with the flag produced no write. Had to hardcode the value in the worker.
- Any future worker-side flag must be added to the loader whitelist (post a value in `m` and `gq.set(...)`) OR hardcoded.

## Result
- Log confirmed: `[wgpu] lodpatch: wrote 1 to 19446852,23318984 (bits 1065353216)` — **JS writes to wasm memory on Chrome WORK**. Confirms web research.
- Game ran normally: world shown, validation +0, FPS ~5–7.5 at ~3,500 draws.
- **No FPS gain at 1.0** — expected, because `-lodScale=1` in the URL already sets `19446852=1.0` via sysParam. Writing the same value is a no-op.
- The interesting untested value is >1.0 (config clamps to 0..1). But `ApplyLodScaleModifiers` computes `1.0 - lodScale`, so 2.0 → modifier -1.0 → risk of visual corruption. Not attempted yet.



## LOD=1.5 experiment (2026-11-23)
- Wrote 1.5 to both globals (bits 1069547520 confirmed), validation 0, no visual corruption observed.
- FPS ~7.14 avg at ~3,038 draws, CPU 98.8-100% — NO gain vs 1.0 (6.6) / baseline. Draws did not drop. The engine apparently clamps/ignores the negative modifier (1.0-1.5=-0.5).
- **Disabled the patch again (LOD_PATCH=0).** Direct LOD-global writes do not reduce draw count — this mechanism cannot fix FPS. Revert from .bak-lodpatch-20261123 for clean worker.
## Verdict
The Chrome-safe memory-write mechanism is PROVEN. To use it for FPS we need a value beyond the config clamp (e.g. 1.5–2.0) AND verification that rendering doesn't break. That's the next experiment if desired; current state is safe (hardcoded 1.0 = no-op). Revert from `.bak-lodpatch-20261123` to restore the pre-patch worker.
