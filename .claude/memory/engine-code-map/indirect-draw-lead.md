# Indirect-draw lead — INVESTIGATED, dead end (2026-11-23)

## The lead
D3D11 context vtable slots 39/40 = DrawIndexedInstancedIndirect / DrawInstancedIndirect. One indirect draw can replace thousands of CPU draws if draw params are batched into a GPU buffer. Our driver supports `drawIndexedIndirect`/`drawIndirect` (doDraw case 4). If RAGE used this for bulk draws, FPS could jump.

## Investigation (searched all of game.dcmp)
- **Call sites of `DrawIndexedInstancedIndirect`**: only 2 — the null-D3D stub definition (line 308311) and the trampoline definition itself (867424). **No engine caller.**
- **`DrawInstancedIndirect`**: only 2 — same pattern (308356, 867429). **No engine caller.**
- The "slot 39/40" `call_indirect` hits found by raw scanning are **other object types' vtables** (pgStreamer, parInstanceVisitor, sysMemAllocator, dlDrawCommandBuffer) — NOT the D3D11 context. Slot numbers are per-vtable, not universal.
- `EBStatic_PlaceDrawableIndirectArgs` (line 3745789) DOES create a 104-byte `grcBufferD3D11` buffer for indirect draw args — but it's tied to a specific static-geometry path, not bulk draws.
- `CGrassBatchDrawHandler_DrawInstancedGrass` is called 4× by `CDrawGrassBatchDC_ExecuteStatic` — grass IS instanced (good), but that's already batched and `grassQuality=0` in our MAX URL disables it.
- `rage_grmGeometryQB_DrawInstanced` exists (instanced geometry) but has 1 caller definition only.

## Verdict
**The indirect-draw path is essentially unused by RAGE for the bulk draws in this build.** The ~2,900 draws/frame come from ordinary `DrawIndexed` (slot 12) calls via draw lists. There is no engine support to "force" bulk draws down the indirect path without a major engine rewrite — which requires a wasm patch (Chrome-rejected) or a runtime vtable/memory patch (unproven, high risk).

**Dead end confirmed. Do not re-chase.** This matches all prior audits: the wall is draw volume from the engine's retained draw lists, and the only safe lever remains `-lodScale=1`.

## Where slot numbers matter (reference)
D3D11 DeviceContext vtable: 12=DrawIndexed, 13=Draw, 20=DrawIndexedInstanced, 21=DrawInstanced, 39=DrawIndexedInstancedIndirect, 40=DrawInstancedIndirect, 41=Dispatch, 42=DispatchIndirect, 7=BeginDraw(list executor), 8=EndDraw. Vtable pointer = `obj.b`; function ptr = `(obj.b.a)[slot]`.
