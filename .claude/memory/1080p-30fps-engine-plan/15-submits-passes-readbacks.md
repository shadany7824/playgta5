# 15 — Fewer submits, passes and readbacks per frame

## Numbers today (Node 1080p, Stage 19)
- **2.3 submits/frame**: readback 1.4, present ~1.0.
- **~58 render-pass begins/frame**, **21 clears/frame**, **8 proxyCopies/frame** (depth proxy copy passes).
Each submit and each pass begin/end has a fixed CPU cost in Dawn (+ validation), and on Intel iGPUs every render pass also means load/store of its targets in shared RAM.

## Levers (one per run, in a Node-only worker copy, see file 09)
1. **Readback submits (1.4/frame):** find what triggers them (log the reason/caller of each readback: occlusion queries? exposure/luminance? `GetOcclusionQueryData`, see file 12). If the engine reads results one frame late anyway, batch all readbacks of a frame into the present submit instead of a separate submit. Check the engine log "engine waits on the GPU worker: readbacks waited 0". The engine doesn't wait, so the cost is only the extra submit + map work.
2. **Clears (21/frame):** today each clear is its own empty pass with `loadOp:'clear'`, then the next draw opens a second pass (`1080p-optimization\02-code-hotspots.md`). Folding the clear into the next pass's `loadOp` was tried in **Chrome with no FPS gain**. Re-test on Node only if the CPU profile (file 02) shows `beginRenderPass`/`end` time, because the cost structure is different without Chrome's wire.
3. **storeOp `discard`** for targets the engine never reads again (e.g. depth after the last depth-using pass, MSAA temps). This saves iGPU bandwidth, which matters once GPU wait > 0. Low CPU effect.
4. **Depth proxies (8/frame):** the Chrome depthview experiment failed because the active path is `floatToDepthProxy` (a float texture sampled as a comparison depth). Options: render the engine's float depth target directly into a depth format where possible, or cache the proxy and only refresh it when the source changed this frame (track a write epoch per texture). Check how often the source really changes per frame.
5. **Pass count:** log the pass list of one frame (target ids + load/store ops). Look for consecutive passes with the same targets that could be merged (pass A ends and pass B begins on the same RTs with `load`). Merging requires that no copy/readback happens in between.

## Measure
submits/frame, passBegins/frame, TIME present/ensure, FPS, validation errors, and a screenshot for any loadOp/storeOp change (wrong ops = garbage or black areas).

## Pass
Keep changes that lower worker ms/frame with an identical image.
