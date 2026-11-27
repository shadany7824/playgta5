# 09 — Make each draw cheaper: redundant-state skipping in a Node-only worker

## Why
~60 ms of the ~80 ms worker frame is the draw path: ~40 µs per draw. Per frame at 1080p the worker issues ~650 setPipeline, ~2,100 setBindGroup, ~1,530 setVertexBuffer, ~1,350 setIndexBuffer for ~1,720 draws (WIRE counters, Stage 19). The Chrome wire profiler (`1080p-optimization\05-measurements.md`) found most of these state calls are redundant. Native Dawn still validates and records each one, and JS still does the lookups.

## First: make a Node-only worker copy (protects the Chrome launchers)
1. Copy `mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js` → `node-webgpu\wgpu_worker_node.js`.
2. In `node-webgpu\wgpu_wrapper2.js`, change the last `require(...)` to the copy (backup the wrapper).
3. Check the worker for relative paths/requires (`grep -n "require(\|__dirname\|import(" wgpu_worker_node.js`). The shader dir is already absolute through `WGPU_SHADER_DIR`.
4. One run to prove the copy = same FPS as before (`[wgpu]` lines identical in shape). Only then start editing the copy.

## Levers (one per run, each measured as µs/draw = TIME draw ÷ draws)
Read `1080p-optimization\02-code-hotspots.md` and `03-optimization-plan.md` (step 4) for line references. Line numbers move; re-find them with grep. Order: whatever file 02's CPU profile puts on top. Otherwise:
1. **setBindGroup dedup per pass:** keep `lastBG[slot]` per active render pass. If the same GPUBindGroup object is set again, skip the call. Reset on every new pass (`ensurePass` begins a pass). bg ≈ 1.4× draws today; target < draws.
2. **setPipeline dedup:** skip if the same pipeline object is already set in this pass. Add a small MRU (last 4 tuple → pipeline) in front of `getPipeline` (plan 4c), because `pdirty` is set by almost every state change.
3. **VB/IB dedup:** already compared via `passSt`. Check whether offset churn defeats it (same buffer, different offset). If so, try `setVertexBuffer` once per buffer and use `baseVertex`/`firstIndex` in the draw instead of the offset, only where the stride/format allow it.
4. **Bind-group creation:** `bind groups +N` per 10 s is low (cache ~2,390), so creation isn't the issue. Focus on the per-draw `stageBG` fast-path hit rate. Add a counter: fast-path hits vs slow `stageBindGroup` + `packCopy` calls per frame. If the slow path is > 10% of draws, look at `bindEpoch` being too coarse (plan 4a: any `SET_CBUFFERS` invalidates all programs).
5. **Constant-buffer packing (`packCopy`):** if it's hot in the profile, avoid copying unchanged constant buffers (compare a version/epoch per buffer).
6. **Command decode loop:** if the profile shows the opcode switch/decode on top, look for per-command allocations (new arrays/objects, closures) and replace them with preallocated typed arrays.

## Rules
- Every skip must be **correct**: a skipped state call is only safe if the GPU state really is identical **in the same pass**. After every lever: `validation errors +0`, and a screenshot compared with the baseline (any flicker, wrong textures or black objects → revert).
- One lever per run. Keep a table of µs/draw per lever.

## Pass
µs/draw goes down (target: 40 → ≤ 25 µs together with file 03) with an identical image.

## Bigger options (ask the owner first, with numbers)
- **Render bundles** for repeated static draw sequences.
- **Splitting encoding across workers** isn't possible with dawn.node objects (they're per-thread). Don't attempt without research.
