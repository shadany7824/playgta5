# Wire-call profile — the design-gap evidence (2026-11-23)

Measured with counters added to `wgpu_worker.js` (backup `wgpu_worker.js.bak-wireprof-20261123`). Each counter increments at the WebGPU call site; the fps log line reports calls/frame.

## Per-frame WebGPU calls at ~2,900 draws (true 1080p MAX, lodScale=1)

| Call | /frame | Note |
|---|---|---|
| setBindGroup | 3,970 | 2 per draw (vs+ps groups) minus cache hits; g0/g1 cache compares only `dyn[0]` |
| setVertexBuffer | 2,748 | cache compares via `passSt.vb` — these are genuine changes or offset churn |
| setIndexBuffer | 2,655 | ditto |
| draw (drawIndexed/direct) | 3,037 | unavoidable per draw |
| uploadBuffer (writeBuffer) | 3,696 | each a `queue.writeBuffer` wire call |
| setPipeline | 1,306 | cache via `lastPl`/`pdirty`; ~1 per 2 draws |
| setStencilReference | 281 | dynamic state |
| setViewport | 61 | |
| setBlendConstant | 50 | |
| setScissorRect | 0 | |
| queue.writeBuffer (uniform ring) | 1.4 | batched already |

**~10,000 state calls/frame**, each crossing Chrome's wire (IPC) from the worker to the GPU process.

## Why this is a design gap, not raw hardware
The RAGE engine was written for a native D3D11 driver that absorbs thousands of state changes cheaply in the kernel/GPU driver. Here `wgpu_worker.js` is the driver — a single JS worker forwarding every call over an IPC wire. The engine threads sleep (`Wait on queued frames` 56–71%) waiting for this serial driver. Worker is 87% busy.

## Implication for fixes
- Per-call dedupe: limited — the state genuinely changes (dynamic uniform offsets per draw).
- Real fix: a **multi-worker pool** building command buffers for independent render passes in parallel, then ordered submit. Needs ObjectStore replication + pass distribution. Not attempted (large rewrite, risk).
- Small wins ruled out (all reverted): fold clears (safety flushes defeat it), yield 2048 (no gain), depthview direct r32float (wrong proxy path), WAT wasm recompile (Chrome rejects).

## Counter patch status
Wire profiler is LIVE in the mirror worker currently. Revert with `wgpu_worker.js.bak-wireprof-20261123` if a clean driver is wanted. The counters are read-only (no behavior change) and validation errors stayed 0.
