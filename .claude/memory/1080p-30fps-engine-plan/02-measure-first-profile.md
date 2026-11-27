# 02 — Measure first: where do the 80 ms go, and what is the engine's own ceiling?

No gameplay change in this file. It decides which later files matter most.

## 2A. CPU profile of the wgpu worker (Node built-in profiler)
- The worker is started in `harness.js` (`new Worker(wgpuWorkerPath, { env, execArgv: ['--require', .../worker-boot.js] })`).
- Add `'--cpu-prof', '--cpu-prof-dir=E:/gta/playgta5/node-webgpu/prof'` to that worker's `execArgv` (backup harness.js first). Profiles are written when the worker exits **cleanly**. If the run ends by kill/timeout, add a clean stop: e.g. after 240 s post a message the wrapper handles with `process.exit(0)` inside the worker, or use `--cpu-prof-interval` with a shorter run that exits by itself.
- Open the `.cpuprofile` in Chrome DevTools (Performance → Load profile) or parse it with a small script. Sort by **self time**.
- Write the top 15 functions (name, self ms %, file:line in `wgpu_worker.js`).
- Expected suspects (from `1080p-optimization\02-code-hotspots.md`): the per-draw path (`objs.get`, `prepareDepthProxies`, `ensurePass`, `getPipeline`, `stageBG`/`stageBindGroup` + `packCopy`, VB/IB loop), the ring/command decode loop, and time inside Dawn native calls (shows as native frames).
- **Key question:** what % is in Dawn native calls vs JS? Mostly native → file 03 (Dawn flags) is the lever. Mostly JS → file 09 (dedup/fast paths).

## 2B. Engine ceiling (how fast can the engine produce frames if the worker were free?)
Pick ONE method and say which:
1. Engine log profile: the game log prints thread waits (Chrome logs showed `DL_BEGIN_DRAW > Wait on queued frames [sleep]` 56-71% and main `Wait for render` 46%). Find the same lines in the Node console output (`console=1` may be needed for this one run). The engine's busy time = frame time − wait time. If the engine waits more than 50% of the time, it has headroom for 2x.
2. Worker no-op test: in a Node-only worker copy (file 09), make `DRAW` handling return early after counting (the engine still runs, nothing is encoded). Measure `[wasm]` frame rate. **Temporary**, revert after.
- Result: the engine-only FPS at 1080p. **If it is < 30, write that 30 FPS needs engine levers (05-08) to reduce engine work too**, not only worker speed.

## 2C. Per-frame counters (cheap, keep while optimizing)
Make sure the 10 s line reports, per frame: draws, setPipeline, setBindGroup, setVertexBuffer, setIndexBuffer, writeBuffer/uploads, passBegins, clears, proxyCopies. The `WIRE pl/bg/vb/ib/...` field already gives most of these. Confirm which number is which by reading the code that prints it (`present()` ~line 2747+ in the worker).
Today at 1080p: pl ~650, bg ~2,100, vb ~1,530, ib ~1,350, draw ~1,720, up ~1,800 per frame. **bg > draws = more than one bind-group set per draw** → dedup candidate.

## 2D. Draws by render phase (tells which engine lever cuts the most)
- The engine renders in phases (GBuffer, cascade shadows, reflection, water, mirror, alpha, post). Count draws per pass, using passBegins + render target id (`frameStats.targets` in the worker already groups draws by `rt0=<tex>(WxH format)`, printed by `dumpFrameStats()` on screenshot frames: run one short `WGPU_SHOT_EVERY` run just for this).
- Map each target size/format to a phase (shadow maps are depth-only square textures; reflection is a small cube/2D target; GBuffer is 1920x1080 with multiple RTs).
- Output: a table `phase | draws/frame | % of total`. This picks between files 05 (world LOD), 07 (peds/cars) and 08 (shadow/reflection).

## Deliverable
`## Stage N — profile` in ERROR-TRACE with 2A top-15, 2B engine ceiling, 2C counters, 2D phase table, and a ranked recommendation: which of files 03-11 to do first.
