# 05 — Measurements (1080p optimization folder)

## Environment
True 1920x1080 internal, sandbox, slots 5, no CSS fx, texture=1 / shadow=0 / reflection=0, particles/grass/city/LOD 0. Extra office tabs open (conservative numbers). All worker patches from note 14 active.

## Baseline before this folder's steps
- 8.6 FPS, 1977 draws, 1.5 submits (readback 0.4), worker 97% busy, 111.6 ms/frame, 0 validation errors, GPU 44%, RAM 82% (3.7 GB free).

## Steps from 03 applied so far
| Step | Change | Result | Verdict |
|---|---|---|---|
| 4b | Skip redundant `SET_SRVS` writes; bump `bindEpoch`/`srvEpoch` only when a slot actually changed. Backup `wgpu_worker.js.bak-srvskip-20261121` | 7.4–8.4 FPS, 2253–2767 draws, 116–129 ms/frame, 0 validation errors | No clear gain (scene had more draws); kept — harmless |
| (note 14) | prior worker patches + readback batching | 8.6–9.8 FPS, ~2000 draws | Kept |

## Not yet applied from 03
- Step 0b: counters per opcode/proxy/clear/render-pass in the 10 s log (no gameplay change).
- Step 2: depth-proxy elimination via WGSL rewrite (medium-high risk, gated `?noproxy=1`).
- Step 3: fold clears into `loadOp:'clear'` of the next pass (low-medium risk).
- Step 4c/4d: pipeline MRU cache, batched VB/IB uploads (need 0a profile first).
- Step 5: `-numCores=3` (cores=2 was worse; 3 untested).
- Step 6: near-1080p internal (1600x900 / 1440x810) + GPU upscale.

## Counter data 2026-11-23 (Step 0b — counters added to wgpu_worker.js, backed up .bak-counters-20261123)
- At true 1080p world, `lodScale=1`: **~20 clears/frame, ~56–65 passBegins/frame, ~7 proxy copies/frame** (title screen: 1 clear, 1 pass, 0 proxies).
- Confirms pass churn + pixel-scaled clears/proxies are a major cost, not just the ~2,000 draws. Step 3 (fold clears into loadOp:'clear' of next pass) and Step 2 (eliminate depth-proxy copies) are the right levers.
- Counter patch is measurement-only, currently LIVE in the mirror worker (backup `.bak-counters-20261123`); safe to keep or revert.

## Step 3 (fold clears) ATTEMPTED 2026-11-23 — FAILED, REVERTED
- Implemented pending-clear map: clearRT/clearDS record instead of emit; ensurePass consumes via loadOp:'clear'; flush-net in flush/copyRegion/copyResource/resolve/readback/proxies/present. node --check OK.
- Result: clears/frame stayed ~24 (no reduction), passBegins ~59, proxy copies 8, FPS 7.53 — NO gain. Validation errors 0 (rendering fine).
- Root cause of failure: the safety `flushPendingClears()` calls on the ~8 proxy refreshes + copies per frame fire BEFORE ensurePass can consume the pending clear, so every clear got flushed as a real pass anyway. The fold was defeated by its own safety net. A tighter design would flush only clears for the specific texture being sampled — more work, not attempted.
- Reverted from `.bak-prefold-20261123` → counters-only worker restored. Do NOT re-attempt the naive global flush-net fold.

## Step 4e (yield 1024→2048) ATTEMPTED 2026-11-23 — NO CLEAR GAIN, REVERTED
- One-line change, node --check OK, validation 0. A/B confounded by scene: before 8.56 FPS @ 2377 draws, after 8.95 FPS @ 1702 draws — the gain is explained by fewer draws (corr -0.899), not the patch. Yield cadence is NOT a useful lever here. Reverted from `.bak-yield2048-20261123` → counters-only worker.

## Honest cumulative result 2026-11-23
- Tried: WAT wasm recompile (Chrome rejects, `import kind 127`), fold-clears (safety flushes defeat it), yield 2048 (no gain). All reverted; counters-only worker + original game.wasm = stable ~7–10.6 FPS at true 1080p MAX.
- Confirmed real win: `-lodScale=1` config (~25%). Other code steps (depth-proxy WGSL rewrite, batched uploads) remain untried but high-risk/uncertain. 15 FPS at true 1080p NOT achieved.

## Honest status
No step has produced a gain larger than scene noise (±1 FPS) at the same spot. The 4-thread i3-7100U + ~2000 draws/frame remains the hard wall. Target 11–13 FPS from the code plan is unproven; 25 FPS remains out of reach.

## LIVE AUDIT 2026-11-23 (while owner played) — definitive bottleneck
- 4295 world FPS samples: avg 9.66, median 8.90, max 48.7. DRAWS avg 2060, max 4913. Worker busy avg 87.1% at ~163 ms/frame.
- FPS↔draws buckets: <1000 draws 12.70 FPS; 1000-1500 9.66; 1500-2000 9.58; 2000-2500 9.34; 2500-3000 8.99; 3000+ 7.97. Clear monotonic draw wall.
- Submit reasons: readback 1.86/frame, present 1.0, idle 0.28, texture upload 0.0. Readbacks NOT the bottleneck.
- Async resource placement stalls: 1080 total but only ~12 in 14 min of recent play (median 45ms) = occasional hitches, not average drag. "time bar Start" stalls (1494, 2-3s) = known 2-core mission-load issue, not in-world FPS.
- **Engine frame profile (from game log) = ROOT CAUSE:** render thread 56-71% "DL_BEGIN_DRAW>Wait on queued frames [sleep]", main thread 46% "Wait for render [semaphore]". The ENGINE THREADS sleep waiting for the GPU worker to drain queued draws. Worker draw-replay throughput is THE wall — exactly where all failed patches targeted. To raise FPS, must increase draws/sec the worker can replay (or cut engine draws). No more config lever exists.

## Step 2 depthview experiment 2026-11-23 — FAILED, REVERTED
- Added ?depthview=1 flag to reinterpret depth texture directly as r32float view in depthProxy('depth') (skip copy pass). node --check OK, validation 0, no SRV view failures.
- Result: proxyCopies/f stayed ~6-7 (unchanged), FPS ~6.4-7.9 (no gain). The ~7 proxies/frame are mostly loatToDepthProxy (float texture sampled as comparison depth), NOT the depth-as-float path I patched. Reverted from .bak-depthview-20261123.
- Conclusion: the working proxy path is floatToDepthProxy; eliminating it needs a different WGSL approach (comparison sampling of r32float isn't allowed). All 4 patch attempts (WAT recompile, fold clears, yield 2048, depthview) failed to raise FPS. The audit's root cause (engine threads sleeping waiting for worker draw replay, ~2060 draws/frame, 87% worker busy) stands; no safe code patch found.

## LIVE 2-MIN MONITOR 2026-11-23 10:52-10:54 (owner playing, true 1080p MAX, lodScale=1)
- 12 world samples (1 per 10s): avg 6.47 FPS, median 6.50, min 5.0, max 8.2. Draws avg 2640 (1806-3671) = heavy scene window.
- 30s windows: 7.60 -> 6.00 -> 5.40 -> 6.87 FPS.
- Confirms scene variance: earlier window ~10.6 avg at lighter draws; this 2-min window 6.47 at 2640 draws. Draw wall + scene variance, nothing broken.

## WIRE-CALL PROFILER 2026-11-23 (counters added to wgpu_worker.js, backup .bak-wireprof-20261123)
- Per-frame WebGPU calls at ~2,900 draws: setPipeline 1306, setBindGroup 3970, setVertexBuffer 2748, setIndexBuffer 2655, draw 3037, uploadBuffer 3696, viewport 61, stencil 281, blend 50, scissor 0, writeBuffer 1.4.
- **This is the design gap:** ~10,000+ state calls/frame, most redundant, each crossing Chrome's wire to GPU process. Engine sets state repeatedly; worker forwards it all. THIS is why engine threads sleep waiting.
- vb/ib already compare via passSt (so ~2748/2655 are real changes OR comparisons defeated by offset churn). setBindGroup/setPipeline are the prime targets. This is fixable IN CODE (state dedup/batching), confirming owner's point that the wall is design not raw hardware.
- Profiler currently LIVE in mirror worker (read-only counters). Revert from .bak-wireprof-20261123 after analysis.

## OWNER'S DESIGN-GAP INSIGHT (2026-11-23) — the wall is fixable in code
- Owner argued the wall is NOT raw hardware but engine design (built for strong CPU/native driver) and we can fix gaps in code. Wire profiler CONFIRMED: ~2900 draws -> 1306 setPipeline, 3970 setBindGroup, 2748 setVertexBuffer, 2655 setIndexBuffer, 3037 draw, 3696 uploadBuffer per frame (~10k wire calls). Engine threads sleep waiting on this serial JS 'driver'.
- Real fix = multi-worker architecture: pool of workers each building command buffers for independent render passes in parallel, ordered submit. Requires replicating ObjectStore state across workers + pass distribution. Large rewrite, not attempted. Owner's reasoning is sound; this is the legitimate path to higher FPS without new hardware.
