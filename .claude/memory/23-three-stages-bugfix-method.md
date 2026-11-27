# 22 — Three-stage C++ port: how the bugs were found & fixed (2026-11-25)

> Read this before touching Stages 6/7/8 (copy / dispatch / occlusion query) in `native_worker.cpp`.
> The value here is the **method**: each bug was found by logging the real boundary values and testing
> one flag at a time — not by guessing.

## What was ported (Stages 6/7/8 of the C++ worker conversion)
- **Stage 6 copy**: `copyBuffer(srcId,dstId,srcOff,dstOff,size)` + `copyTexture(...)` in C++, using the buffer/texture registries and the encoder handle set by `getEncoder()`.
- **Stage 7 dispatch**: `setCompute(cp,bg,pass)` + `dispatch(x,y,z)` — compute pipeline/bind-group/pass handles, one `wgpuComputePassEncoderDispatchWorkgroups`.
- **Stage 8 occlusion**: `beginOcclusion(slot)` / `endOcclusion()` on the current render pass.
- All with **stats counters** (`copyBuf/copyTex/dispatch/occl`) in `native_worker.stats()` — lesson 10: prove the instrument before believing silence/zero.

## Bug 1 — the test crashed at Stage 8 (exit 0xC0000409), was NOT my code
- **Symptom**: combined unit test died with a native stack-buffer-overrun right after "Stage7 dispatch no throw".
- **Wrong theory**: my `beginOcclusion` was broken.
- **What fixed it (lessons 02 + 05)**: added step logs (`STEP 1..7`) to an isolated occlusion-only test. Output showed the crash happened at `enc.beginRenderPass({ colorAttachments: [], occlusionQuerySet })` — **before any C++ call**. Root cause: a render pass with **empty color attachments + occlusion query set** crashes native-dawn. Adding a real color attachment (`bgra8unorm` view + clear) → `beginOcclusion OK / endOcclusion OK / DONE`, exit 0.
- **Rule**: when a crash happens *before* your code runs, don't patch your code — fix the test setup. Believe the step log, not the suspicion.

## Bug 2 — full game: `DXGI_ERROR_DEVICE_HUNG` with all 3 flags on
- **Symptom**: all-flags run reached the world (`draw=16671`), then device removed: `DXGI_ERROR_DEVICE_HUNG (0x887A0006)`.
- **Method (lesson 19 — one change per run)**: ran each flag alone:
  - COPY alone → 1973 lines, no hang, stable.
  - DISPATCH alone → **DXGI hang**.
  - QUERY alone → 13077 lines, no hang, `occl=9` in real frames — works.
- **Root cause (Discovered, not fully fixed)**: C++ `Dispatch` calls `wgpuComputePassEncoderSetBindGroup(pass, 0, bg, 0, nullptr)` — **0 dynamic offsets**. The compute bind group uses dynamic uniform offsets (same pattern as the draw path, which needed `dyn[0]`). Wrong bind-group offsets → GPU state corruption → device hang.
- **Resolution (FIXED in Stage 56)**: JS `setCompute` now passes `g0.dyn[0]` as 4th arg; C++ `SetCompute` stores `g_cdyn` and `Dispatch` passes it via `setBindGroup(..., g_cdyn?1:0, d)` — same as the draw path's `CSetBG`. Both sides log `dyn`: JSDISPATCH vs SETCOMPUTE showed matching `dyn=1539072`. Verified: no device hang, 40 fps lines, dispatch counter 4→132, validation +0. `CPP_DISPATCH` now opt-in (`=1`).

## Bug 3 — "counters are 0" is not "path didn't run"
- `stats()` resets counters every call, and the fps line calls it once per 10s window. Early samples showed `copyBuf=0/occl=0`; a mid-run sample showed `occl=9`. Always read **multiple samples**, and place counters where the call actually happens (lesson 10).

## Current flag defaults (worker `wgpu_worker_node.js`)
- `CPP_COPY` / `CPP_QUERY`: opt-in (`=1`) — stable, verified.
- `CPP_DISPATCH`: `false && ...` — hard-disabled until dynamic-offset fix + A/B.
- `CPP_CLEAR`: opt-in (`=1`) — crashed the full game earlier (Stage 54), leave off.

## Re-run recipes
```
# unit (3 stages, real Dawn):
node24 E:\gta\_tmp_claude\test-3stages.js          # expect 9/9
node24 E:\gta\_tmp_claude\test-occl-only.js        # step logs, expect DONE
# full game, one flag at a time (lesson 19):
set WGPU_CPP_COPY=1  /  WGPU_CPP_QUERY=1  /  WGPU_CPP_DISPATCH=1
node24 harness.js > E:\gta\_tmp_claude\diag-XXX.txt 2>&1
# checks: select-string 'DEVICE_HUNG' (want none), '"occl":'/'"copyBuf":' (want >0 somewhere), fps lines
```

## Related
- `ERROR-TRACE.md` Stages 53-55, `21-cpp-worker-draw-win.md`, `think-like-claude/02,05,10,18,19,31`.
