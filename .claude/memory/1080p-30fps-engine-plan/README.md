# 1080p at 20-30 FPS: engine + harness optimization plan (for the code agent)

Owner goal: **true 1920x1080 at 20 FPS minimum, 30 FPS target**, on the Node 24 + native Dawn harness (`E:\gta\playgta5\node-webgpu\`).
Written 2026-11-23 from real measurements and the decompiled engine (`E:\Malik\game\game.dcmp`). Read the files **in order** (01-11 = main plan; 12-16 = extra high-value levers. After file 02, do **12 early**: it's a cheap check with a huge possible win). Each one is a separate lever with its own pass check.

## Where we are (verified, Stage 19 in `engine-code-map\ERROR-TRACE.md`)
- Node 1080p (texture 2, shadow 0, reflection 1, rest 0, uncapped): **12.4 FPS**, ~1,350-1,570 draws/frame, **GPU wait 0**.
- Chrome, same settings: 6.1 FPS. Node is already ~2x.
- Node frame breakdown (`diag-step3-1080.txt`): **wgpu worker busy 83-93% = ~80 ms/frame**, of which **TIME draw ≈ 60-63 ms** (~40 µs per draw), bind groups ~10 ms, everything else small. 2.3 submits/frame (readback 1.4). passBegins ~58/frame, clears 21/frame.
- **So the limit is CPU: the JS worker encoding draws.** The GPU (HD 620) is not the limit yet.

## Target math
- 20 FPS = 50 ms/frame → worker time must drop from ~80 → **≤ 45 ms (-45%)**.
- 30 FPS = 33 ms/frame → **≤ 30 ms (-63%)**. That needs BOTH fewer draws (engine levers) AND cheaper draws (worker/Dawn levers).
- Cost ≈ draws × µs-per-draw. Two ways down: **fewer draws** (files 05-08) and **cheaper per draw** (03, 09). Do both.
- File 02 also checks the engine's own ceiling. If the engine alone can't make 30 FPS of frames, no worker fix gets there.

## Files (do in this order)
| # | File | Lever | Expected |
|---|---|---|---|
| 01 | [01-rules-and-test-protocol.md](01-rules-and-test-protocol.md) | How every test is run and logged | (mandatory) |
| 02 | [02-measure-first-profile.md](02-measure-first-profile.md) | CPU profile of the worker + engine ceiling | tells which lever matters |
| 03 | [03-dawn-flags-and-backend.md](03-dawn-flags-and-backend.md) | Remove the debug flag, skip validation, try backends | cheap, maybe 10-30% |
| 04 | [04-pipeline-precompile-stutter.md](04-pipeline-precompile-stutter.md) | Pipeline seed cache | kills 125-640 ms hitches |
| 05 | [05-engine-lod-scale-override.md](05-engine-lod-scale-override.md) | Engine LOD scale + flag bit, per-LOD remap | fewer far draws |
| 06 | [06-engine-streaming-near-far.md](06-engine-streaming-near-far.md) | Load near area fully, far area reduced/slow | fewer far objects |
| 07 | [07-engine-population-density.md](07-engine-population-density.md) | Ped/vehicle density globals | fewer peds/cars = fewer draws + CPU |
| 08 | [08-engine-shadows-reflections-lights.md](08-engine-shadows-reflections-lights.md) | Shadow cascades, reflection phases, LOD lights | fewer passes/draws |
| 09 | [09-worker-state-dedup.md](09-worker-state-dedup.md) | Skip redundant setBindGroup/setPipeline/VB/IB in a Node-only worker copy | cheaper per draw |
| 10 | [10-threads-priority-gc.md](10-threads-priority-gc.md) | Process priority, V8 GC flags, pthread pool | smoother, a few % |
| 11 | [11-honest-fallback-upscale.md](11-honest-fallback-upscale.md) | Near-1080p internal + GPU upscale (labelled) | if native 1080p can't reach 20 |
| 12 | [12-occlusion-culling-check.md](12-occlusion-culling-check.md) | Is the engine's CPU occlusion culling (SoftRasterizer) active in wasm? If off → turn on | **could be the biggest engine win** |
| 13 | [13-native-command-processor.md](13-native-command-processor.md) | Replace the JS per-draw path with a C++ Node addon (feasibility report first, ask owner) | **only lever that alone could reach 30** |
| 14 | [14-v8-wasm-tiering-and-wasm-opt.md](14-v8-wasm-tiering-and-wasm-opt.md) | Engine code speed: `--no-liftoff`, wasm-opt on a copy | matters once the worker is faster |
| 15 | [15-submits-passes-readbacks.md](15-submits-passes-readbacks.md) | Fewer submits/passes/readbacks/depth proxies | a few ms/frame |
| 16 | [16-hardware-and-windows-cheap-wins.md](16-hardware-and-windows-cheap-wins.md) | Dual-channel RAM, power, driver, background load, HDD (owner actions) | real, no code |

## Proven tools we already have
- **Write engine globals from JS at runtime** (proven in Chrome: `engine-code-map\runtime-lod-write-result.md`): fresh `DataView`/`Int32Array` on `wasmMemory.buffer` + `Atomics.store`, every frame.
- **Patch one wasm function via WAT** (proven: `1080p-optimization\17-wasm-patch-proof.md`). In Node it's easier: the harness reads `game.wasm` from disk, so point it at a patched copy (no browser cache problem).
- **Read engine code**: `awk 'NR>=<line>{print; if(/^}/) exit}' E:\Malik\game\game.dcmp`. Line numbers via `engine-code-map\engine-function-index.tsv`.
- Data string addresses: passive rodata segment 0, base 1024 (see memory `16-...`).

## Already tried in Chrome and FAILED (don't repeat blindly)
WAT recompile attempt, folding clears, yield 2048, depth-view proxy, post-FX args (`-postFX=0` etc.), LOD write of 1.0/1.5 to `23318984` **without the flag bit** (see file 05: that's why it may have done nothing).
