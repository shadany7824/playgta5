# How the driver actually works — understanding doc (2026-11-23)

Read from `wgpu_worker.js` top-to-bottom. This is the "driver" that translates RAGE engine commands into WebGPU. Understanding this is the key to any real FPS optimization.

## 1. Why this worker exists (header lines 1-23)
- WebGPU objects **cannot cross threads**; D3D11 resources are created by any engine thread (streaming/main/render). So ALL WebGPU objects live in this one worker. Game threads only emit commands into a **ring buffer in shared wasm memory**.
- WebGPU is async (device creation, mapAsync, onSubmittedWorkDone). The worker has a normal event loop; the game's blocking C++ threads never yield to JS — they wait on a futex/fence word in the ring when they need a result.

## 2. The ring protocol (lines 14-21, 27-36)
- Header int32 words at ring base: `[0] head` (producer writes), `[1] tail` (worker writes), `[2] state` (0 starting/1 running/2 failed), `[3]` executed count, `[4]` error count, `[5] sleeping` flag.
- Commands start at byte offset 64 (`RING_DATA`). Each command = opcode word + payload-word-count word + payload. `WRAP` opcode means continue at RING_DATA.
- 48 opcodes (`OP` table): resources (CREATE_TEXTURE/BUFFER/SHADER/LAYOUT/STATE/SRV), state (SET_*), DRAW (32), copies, readback (42), present (7), fence (8).

## 3. The main loop (`loop()`, lines 2970-3000)
```
refreshViews() → head = ring[0]
if head == tail:  idle — flush if pending, compileAhead, set sleeping flag,
                  Atomics.waitAsync(100ms) → sleep
else:  tail = await runCommands(tail, head)  → busy time
       publish tail, notify producer
```
- `Atomics.waitAsync` with 100 ms timeout lets the worker sleep when idle instead of spinning.
- Producers only notify while `sleeping` (header[5]) is set — avoids lost wakeups.

## 4. Command dispatch (`runCommands`, lines 2854-2968)
- A single `switch(op)` with **numeric cases** (V8 jump table — `case OP.X` with property loads was slower).
- Per command: parse payload from `u32[p]`, call the handler, `tail += n*4 + 8`.
- Every **1024 commands**: publish tail + executed count (Atomics notify), and if >2 ms elapsed, `await yieldTask()` (MessageChannel macrotask boundary) so completion callbacks (fences/readbacks) get a turn. **This is the yield cadence we tested at 2048 — no gain.**
- Crucial detail (line 2949 comment): an atomic add per command was measurable at ~25,000 commands/frame → batched every 1024.

## 5. State model (`S`, lines 685-712)
A single global `S` mirrors the D3D11 pipeline state: shaders[3], layout, topology, 16 vertex-buffer slots, index buffer, constant buffers [3 stages × 16], SRVs [3 × 128], UAVs, samplers, 8 render targets + depth-stencil, blend/depth-stencil/raster state, viewports, scissors.
- `pdirty` = pipeline key changed (set by most SET_* ops); `lastPl` memo avoids lookup when nothing changed.
- `resetState()` on CLEAR_STATE.

## 6. The hot path: `doDraw` (lines ~1724-1844)
Per draw (~2,000-4,000/frame):
1. `shaderProgram(vs/ps)` — lazy compile from fetched WGSL, cached on `sh.program`; parse bindings via `parseWgsl`.
2. `prepareDepthProxies` ×2 — scan texture bindings for depth-as-float / float-as-depth, refresh proxies if dirty (the ~7 copies/frame).
3. `ensurePass()` — begin/continue render pass; key from RT+DS state; `loadOp:'load'` normally.
4. `getPipeline()` — hash bucket lookup on integer tuple; async pipeline compilation when state is new (`PIPELINE_PENDING` → skip draw until ready, compiled ahead by `compileAhead`).
5. `stageBG` ×2 — build/reuse bind groups (constant buffers packed into uniform ring with dynamic offsets).
6. Bind vertex/index buffers (with `passSt` dedupe), set dynamic state (viewport/scissor/blend/stencil), clamp draw counts to buffer sizes, `pass.drawIndexed()`.

## 7. Uniform ring (lines 731-780) — already optimized
- `ubo` ring with FRAME_SLOTS (3) chunks in ONE GPU buffer. Dynamic offsets = base + offset.
- `packCopy()` copies each draw's constants into a **JS mirror** (`stageReserve`), and `flushUniforms()` does **one `writeBuffer` per dirty chunk per flush** — a writeBuffer per draw was ~10% of worker time at 1,700 draws. Already done.

## 8. What the audits proved
- Wire profiler: ~10,000 WebGPU state calls/frame at ~2,900 draws (3,970 bind groups, 2,748 VB, 2,655 IB, 1,306 pipeline, 3,696 uploads) — each crossing Chrome's IPC wire. **This is the design gap** (native D3D11 driver absorbs this; our JS driver forwards it serially).
- Engine frame profile: render thread 56-71% `Wait on queued frames`, main 46% `Wait for render` — engine blocks on the driver.
- The real fix is architectural (multi-worker pass-parallel command building + ordered submit), not small patches.

## 9. Rules when editing this file
- `node --check` after every edit; re-grep line numbers (they drift).
- Keep a `.bak-<name>-<date>` backup; verify live: page passes 20% → "world shown", validation errors +0.
- Current backups: `.bak-counters-20261123`, `.bak-prefold-20261123`, `.bak-yield2048-20261123`, `.bak-depthview-20261123`, `.bak-wireprof-20261123`, `.bak-timeprof-20261123`.
- **Current live state:** time profiler instrumentation added (TP.* timers in fps line). Revert from `.bak-wireprof-20261123` for a clean wire profiler, or earlier backups for clean driver.
