# 14 — Worker optimizations + final true 1080p result (2026-11-20)

## Code optimizations applied (mirror wgpu_worker.js, backup .bak-opt-20261120)
1. `srvEpoch[3]` added; `prepareDepthProxies()` cache now invalidated only on SRV writes instead of any binding op (SET_SRVS increments it). Zero-risk narrowing.
2. Redundant `refreshViews()` removed from READBACK completion callback (`readback()` already refreshes after mapAsync). Zero-risk.
3. Proxy bind-group fast path enabled with a generation guard: `bgProxies` records proxy objects used while building a bind group; `proxyOk(e)` compares stored `tex`/`dirty` before reusing, so cached groups are invalidated if a proxy view changes. Replaced `!e.noFast` gate with `proxyOk(e)`. Medium risk — verified 0 WebGPU validation errors.
4. Earlier in this session: true GPU upscale (canvas at display size, WGSL sampler blit) — see 13.

## Verification
- `node --check` clean; game ran with 0 validation errors after each patch.
- Final **true 1920x1080 internal** test with all patches + optimized args (texture 2, shadow 0, reflection 1, particles/grass/city/LOD 0, slots 5, no CSS fx): **4.4–6.1 FPS**, ~2450–2500 draws/frame, worker 82–83% busy, 135–185 ms/frame. (Extra office tabs were open, so numbers are conservative.)
- Earlier true 1080p baseline was 5.6 FPS with max shadows/reflections; these are not an exact A/B but show no meaningful jump.

## Further optimization (same session, backup .bak-bguid-20261120)
- Bind-group cache keys switched from engine object ids to stable GPU-object ids (`gpuUid(o)`), so recreated SRV/UAV/sampler wrappers no longer force duplicate bind groups. Patched 4 key writes in `stageBindGroup()`; `node --check` clean, 0 validation errors.
- Tested true 1080p with texture=1 / reflection=0 (lower memory): steady **8.4 FPS**, 1962 draws/frame, worker 79% busy, 94.6 ms/frame, bind groups +46 (cache 2651). Best true-1080p number so far, still far from 25. Scene differs from earlier tests, not a strict A/B.

## Yield threshold (backup .bak-yield-20261120)
- MessageChannel yield threshold raised 512 → 1024 commands (halves event-loop round trips/frame). `node --check` clean, 0 validation errors. True 1080p texture=1/reflection=0 now ~7.2–8.8 FPS (1804–2306 draws, 96–129 ms/frame) — within scene noise of the pre-yield 8.4 FPS.

## Readback batching (backup .bak-rbbatch-20261120)
- Reworked `readback()`: copies are recorded into the open encoder and queued in `rbBatch`; one `flush('readback')` runs in a `queueMicrotask` for the whole burst, then all staging buffers are mapped/copied in order and released. `case 42` still fire-and-forgets the promise.
- Verified: `node --check` clean, **0 validation errors**, no `readback failed` lines, game renders. Submits/frame dropped from ~3.2–3.5 (readback ~2.0–2.1) to **~1.5–1.7 (readback ~0.2–0.4)** — a real reduction in GPU submits.
- True 1080p, texture=1/reflection=0: **7.4–9.8 FPS**, 2160 draws/frame, 88–102 ms/frame (best true-1080p numbers so far; scene-dependent).

## Combined config tests at true 1080p (all code patches active)
- `cores=2`: 6.5–7.1 FPS, ~2900 draws, readback 1.3–1.5 (batching weaker). WORSE than default cores.
- `shadowQuality=-1` (off): steady 8.3 FPS, 1922 draws, GPU 79% — no gain over shadow=0; GPU takes more load.
- Best remains default cores, `textureQuality=1, shadowQuality=0, reflectionQuality=0`, particles/grass/city/LOD 0, slots 5: ~8.6–9.8 FPS, ~2000–2160 draws, 3.7 GB RAM free. Restored as the active launch.

## Conclusion
25 FPS at true 1920x1080 internal is still unreachable. The upscale path (13) gives a 1920x1080-sized sharpened image at ~16 FPS. Worker optimizations removed some per-draw overhead but cannot change the engine's draw count, which is the fundamental wall.
