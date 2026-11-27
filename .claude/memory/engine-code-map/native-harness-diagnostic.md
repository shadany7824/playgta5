# Native Node/Dawn harness — full failure diagnostic (2026-11-23)

## What the harness is
`E:\gta\playgta5\node-webgpu\harness.js` boots the GTA V wasm port under **Node 24 + native Dawn**, bypassing Chrome's WebGPU wire (which benchmarks show is 40% of per-dispatch cost). The goal: native WebGPU might raise FPS.

## Verified working pieces ✅
1. `webgpu` npm installed for Node 24 (`node24/wgpu/node_modules/webgpu`); Dawn adapter + device create OK (`ADAPTER true`, `DEVICE true`).
2. Node 24 V8 13.6 **parses game.wasm successfully** (`WebAssembly.validate: true`) — Node 22 V8 12.4 failed with `invalid table elements limits flags` (memory64/table64). Installing Node 24 fixed that.
3. io worker loads and sends `{loaded:true}` after its init message.
4. harness starts game.js in global scope (`vm.runInThisContext`), Module config seen, wasm read from disk via `instantiateWasm`.
5. game.js runs, spawns pthread workers, io + wgpu workers connect.

## EXACT FAILURE (from diag-full.txt, `RangeError [Error]: WebAssembly.Memory(): could not allocate memory`)
```
[harness] waiting for workers...
[harness] worker signal: io loaded
[harness] starting game.js
RangeError [Error]: WebAssembly.Memory(): could not allocate memory
    at initMemory (game-node.js:8:7292)
    at ... Module._compile ... MessagePort.<anonymous> (worker_thread:223)
```

**Where:** a **pthread worker** (spawned by game.js via `new Worker(pthreadMainJs)`) calls `initMemory()`, which tries to allocate the game's 3 GiB shared Memory64 (`initial: 49152 pages`).

**Why it fails there — the broken connection:**
- Emscripten's `initMemory()` has a guard: `if (ENVIRONMENT_IS_PTHREAD) return;` — pthread workers should NOT allocate memory themselves; the main thread creates it and sends it via `msgData.wasmMemory` in message cmd=1.
- `ENVIRONMENT_IS_PTHREAD = ENVIRONMENT_IS_WORKER && globalThis.name == "em-pthread"`.
- In Node worker_threads there is **no `globalThis.WorkerGlobalScope`**, so `ENVIRONMENT_IS_WORKER = false`, so `ENVIRONMENT_IS_PTHREAD = false` even though I pass `name:"em-pthread"` and `workerData:{pthread:true}` when spawning.
- Result: the pthread worker thinks it's the main thread → calls `initMemory()` → tries to allocate a **second** 3 GiB memory → with the main thread's 3 GiB + io + wgpu + Dawn, this exceeds available memory → `could not allocate memory`.

## The fix (NOT yet applied — the last edit attempt failed on a string mismatch)
In `worker-boot.js`, for workers with `workerData.pthread===true`, set BOTH:
```js
globalThis.name = 'em-pthread';
globalThis.WorkerGlobalScope = function(){};   // makes ENVIRONMENT_IS_WORKER true
```
Then `ENVIRONMENT_IS_PTHREAD` becomes true, `initMemory()` returns early, and the worker waits for the main thread to send `wasmMemory` (cmd=1) instead of allocating its own.

`worker-boot.js` currently has NO such line (verified by reading it) — earlier edit attempts to add it were lost. Add this to line ~5:
```js
try { const wt = require('worker_threads'); if (wt.workerData && wt.workerData.pthread) { globalThis.name='em-pthread'; globalThis.WorkerGlobalScope=function(){}; } } catch(e){}
```

## Secondary risks after this fix
- Even with the guard, Node 24 must marshal a 3 GiB `SharedArrayBuffer` to each worker via `postMessage` (Emscripten `msgData.wasmMemory`) — may be slow or hit structured-clone limits; verify.
- No canvas/display in Node — need screenshot readback (`WGPU_SHOT_EVERY`) to verify image, then a streaming path to actually play.
- Dawn native crash risk remains (earlier 0xC0000409 stack-buffer-overrun) when GPU commands actually execute.

## Files / state
- Harness + patches: `E:\gta\playgta5\node-webgpu\` (harness.js, worker-boot.js, game-node.js with pthreadPoolSize=2, max memory patched to 65536n).
- Node 24: `E:\gta\playgta5\node24\node_modules\node\bin\node.exe` (V8 13.6).
- Latest failure log: `node-webgpu/diag-full.txt`.
- Memory doc: `engine-code-map/native-node-dawn-feasibility.md`.

## UPDATE (2026-11-23, later): harness runs but engine never starts — stuck in pthread bootstrap
- With Node 24 + pthread detection fix (`WorkerGlobalScope`+name for pthread workers), the earlier `could not allocate memory` is GONE. Harness runs 130s+ no crash.
- io worker: `loaded` OK. Server on :8000 (Node fetch OK). wgpu worker: never sends `ready` (`wgpuReady=false`).
- Wired BroadcastChannel to `engine-log.txt` in both main + worker shims: file stays 0 bytes → engine emits no logs.
- Conclusion: game.js is stuck in `runDependencies` — Emscripten's pthread pool never signals ready (the wgpu worker's `start` message / ring memory handshake and the pthread wasm-module load-to-workers protocol aren't completing under our shims). The engine never reaches `callMain`, so no world/fps.
- This is a deep Emscripten pthread bootstrap issue (message cmd=1 wasmMemory handoff, worker `ready` signaling). Needs the exact protocol from wgpu_backend.cpp / emscripten runtime — a large remaining task.
- ALL diagnostics kept: `node-webgpu/diag-run.txt`, `engine-log.txt`, harness scripts. Per owner rule (U14), we log-then-fix; the current logged failure is "engine silent, pthread bootstrap never completes".
