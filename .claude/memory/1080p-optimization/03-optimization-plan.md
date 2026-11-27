# 03: Optimization plan for true 1080p (ranked; NONE implemented yet as of 2026-11-21)

Order = expected gain ÷ risk. Do step 0 first: every later step depends on its numbers.

## Step 0: Measure where the 120 ms goes (no gameplay change)
- **0a. Chrome profiler on the worker.** DevTools → Performance → record 10 s in-world at 1080p, then select the `wgpu_worker.js` thread. Note the top self-time functions. This replaces guessing.
- **0b. Add counters to the 10 s `fps:` log line** (`present()` ~:2747): commands/frame by opcode (UPLOAD_BUFFER, SET_*, DRAW), depth-proxy refreshes/frame (increment in `depthProxy`/`floatToDepthProxy` when `px.dirty`), clear passes/frame, render passes/frame (count `beginRenderPass`).
- Save the numbers to `05-measurements.md` in this folder.

## Step 1: Prove whether 1080p itself makes the engine draw more (test B in 04)
Same spot, `res=960x540` vs `res=1920x1080`. If draws jump ~1200 → ~2000, the engine scales LOD/detail with resolution. Then the cheapest real lever is an engine arg (try `-lodScale=0` is already set; also try `-pedLodBias=0,-vehicleLodBias=0` explicitly at 1080p) or a slightly lower internal res (step 6).

## Step 2: Remove depth-proxy copy passes (pixel-scaled, likely biggest 1080p-specific win)
- Where: `depthProxy :953-987`, `floatToDepthProxy :913-950`, callers `prepareDepthProxies :1448`, `srvView :856-891`.
- Why: each refresh = `endPass()` + one full-screen pass per mip x layer. At 1080p that's 2 M pixels per copy, and it breaks the engine's pass, so the next draw re-opens a pass with load/store.
- Change: in `shaderProgram()` (`:441`) rewrite the WGSL of shaders that `textureLoad` a depth SRV as `texture_2d<f32>` to declare `texture_depth_2d` (textureLoad on it returns `f32`; wrap it as `vec4f(v,0,0,1)`). Then bind the depth view (`aspect:'depth-only'`) directly and skip the proxy. Do the depth/float case first; leave the stencil (`r8uint`) proxy as is.
- Risk: medium-high (shader text rewrite, sampler compatibility: `texture_depth_2d` can't be used with a filtering sampler → only for `textureLoad` users). Gate it behind `?noproxy=1` so it can be A/B'd and switched off.
- Expected: only worth it if 0b shows several refreshes per frame.

## Step 3: Fold clears into the next pass (`loadOp:'clear'`)
- Where: `clearRT :2430-2437`, `clearDS :2439+`, `ensurePass :1401-1444`.
- Change: instead of an empty pass, record `pendingClear[texId+mip+slice] = value`. In `ensurePass`, if an attachment has a pending clear, use `loadOp:'clear'` + `clearValue` and delete the entry. Flush any leftover pending clears as today before copies, readbacks, present, or when the target is sampled.
- Saves one full-target write+read per cleared 1080p target and one pass begin/end. Low-medium risk.

## Step 4: Cut per-draw JS cost (CPU wall). Pick from the 0a profile, don't guess.
Candidates, each a separate patch:
- **4a. `bindEpoch` too coarse**: any `SET_CBUFFERS` on a stage invalidates all programs' fast path (`:2904`). It falls back to `sameIds` compares, so check in 0a whether `stageBG` is hot before touching it.
- **4b. Redundant `SET_*` from the engine**: skip state ops whose values are unchanged before they bump epochs or set `pdirty` (`SET_SRVS :2905`: compare before writing, only bump if any slot changed).
- **4c. `getPipeline` per draw**: `pdirty` is set by any blend/dss/raster/VB-stride change. Cache the last 4 (tuple → pipeline) pairs as an MRU in front of the bucket lookup.
- **4d. Vertex-buffer `writeBuffer` per upload** (`uploadBuffer :609`): batch dynamic VB/IB uploads into a staging mirror like the uniform ring, one `writeBuffer` per buffer per flush. Only if 0b shows many UPLOAD_BUFFER to non-shadow buffers.
- **4e. Yield cadence**: the 2 ms yield (`:2950`) means about 60 yields in a 120 ms frame. Try 4 ms. Cheap to test, small gain at best.

## Step 5: Thread budget on 4 threads
- Engine uses `navigator.hardwareConcurrency` = 4 threads, plus the GPU worker, plus Chrome's GPU process: oversubscribed. `cores=2` was worse (note 14). **Test `-numCores=3`** at 1080p (page only adds the arg when `cores<=2`, `index.html:407`, so pass it via `args=-numCores=3`).

## Step 6: Fallback if code steps stall: near-1080p internal + GPU upscale
- `res=1600x900` or `res=1440x810` with the note-13 upscale shader to a 1920x1080 canvas. Measure; if draws/frame drop (step 1), this may land at 11-13 FPS with an image close to 1080p.

## Hardware notes (not code, but real)
- RAM in flex mode (4 GB + 16 GB): only 8 GB is dual-channel. A matching 16 GB stick gives full dual-channel bandwidth. That helps the iGPU and the CPU a little. Expect a small gain, not 3x.
- The true fix for 25 FPS at 1080p is a faster CPU (more cores/IPC) for the worker + engine.

## Done-criteria for any step
04's A/B shows a gain larger than scene noise (±1 FPS) at the same spot, 0 validation errors, image unchanged (screenshot). Then record it in `05-measurements.md` and the main README.
