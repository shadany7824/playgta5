# Semantic analysis: how the engine GENERATES draws (2026-11-23)

Read from `game.dcmp`. This is the FPS-relevant region I searched for — the chain that produces the ~2,900 draws/frame.

## The complete draw chain (all verified from full bodies)

```
RAGE gameplay/draw-list
  -> RageDirect3DDeviceContext11_Draw*      [1-line D3D11 vtable trampolines]
  -> rage_grcDevice_Draw*                    [SetUpPriorToDraw + vtable + counters]
  -> ring command DRAW (opcode 32)
  -> wgpu_worker.js doDraw()                 [our driver replays to WebGPU]
```

## Layer 1: D3D11 context trampolines (RageDirect3DDeviceContext11_*)

All are 1-line `call_indirect` stubs into the D3D11 device vtable — the slot number is the method:
- `DrawIndexed` (line 867056, func10337) → **slot 12**
- `Draw` (867061) → slot 13
- `DrawIndexedInstanced` (867168, func10345) → **slot 20** (6 args: indexCount, instanceCount, startIndex, baseVertex, startInstance)
- `DrawInstanced` (867173) → slot 21
- **`DrawIndexedInstancedIndirect` (867424, func10364) → slot 39** (args: buffer, offset) — GPU reads draw params from a buffer
- **`DrawInstancedIndirect` (867429, func10365) → slot 40**
- `Dispatch` (867419) → slot 41, `DispatchIndirect` (867424) → slot 42
- `OMSetRenderTargets` (867372) → vtable, `OMSetBlendState` (867384), `OMSetDepthStencilState` (867405), `ClearRenderTargetView` (867482), `ClearDepthStencilView` (867497) — all trampolines.

**Key insight:** the engine DOES expose indirect draws (slots 39/40) — one GPU draw can replace thousands of CPU-submitted draws if the draw params are batched into a buffer. Our driver supports indirect draws (`case 4 pass.drawIndexedIndirect` in doDraw, counted as `indirectDraws`). The question is whether the engine *uses* them for the bulk draws — the wire profile showed ~3,037 `draw` calls/frame, so it mostly does NOT. If RAGE's draw lists could be forced down the indirect path, that's the real draw-count fix. Unproven; needs research into which draw lists use slots 39/40.

## Layer 2: grcDevice draw functions

- `rage_grcDevice_DrawIndexedPrimitive(a,b,c)` (857286, func10029): `if (12483660L) DoFlush()`, `SetUpPriorToDraw(a)`, then `call_indirect(device, c, b, 0, vtable[12])` — i.e. it最终 calls DrawIndexed slot 12. Then updates primitive counters (`tls_base+1168`) via `br_table` on topology `a` (triangle list/strip/fan: divide by 3, subtract 2, etc.).
- `rage_grcDevice_DrawIndexedInstancedVertices(a,b,c,d)` (856892, func10015): sets globals `12623632L=32` (primitive topology?), `12623568L=0`, `12623440L=b`; calls `SetUpPriorToDraw`, then slot 20 (DrawIndexedInstanced). Updates counters with `a*d` then br_table divide by topology.
- `rage_grcDevice_DrawVertices` (815973, func9548, 32 lines): one draw via slot 13 (or triangle-restart handling when `12631104L==5`), updates counters.
- `rage_grcDevice_BeginIndexedVertices` (815935, func9547) — starts immediate-mode vertex buffer.

## Layer 3: draw list execution
- `rage_dlCmdBeginDraw_ExecuteStatic` (526940, func4872): `call_indirect(b, a[16]:ubyte, (b[0])[7])` → vtable slot 7 = begin draw on the render backend.
- `rage_dlCmdEndDraw_ExecuteStatic` (526945, func4873): slot 8 = end draw.
- The draw lists record these commands; `dlDrawListMgr` replays them per frame.

## Semantic verdict for FPS
1. **The engine already has an indirect-draw path** (slots 39/40, `drawIndexedIndirect` in our driver). Forcing draws through it is the theoretically correct way to cut ~3,000 CPU draw calls to a handful — but requires RAGE to batch its draw params into GPU buffers, which the decompile has not shown to happen for the bulk draws.
2. The immediate-mode path (`grcVertex` → `grcEnd`/batcher) and draw lists both funnel into vtable slot 12/13/20 → ring DRAW → our driver. No single "heavy function" — it's volume.
3. **No safe patch target found in this region.** Any fix would need to change how RAGE batches draws (engine-side vtable/global patch — the wasm recompile path already failed) or extend our driver to merge consecutive draws with identical state (complex, stateful, not attempted).

## Honest status
Read ~10 more full bodies here (trampolines + grcDevice + draw-list executors). The indirect-draw observation is new and worth remembering, but it's a lead, not a fix.
