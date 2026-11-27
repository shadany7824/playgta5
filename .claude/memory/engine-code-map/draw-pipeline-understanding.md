# Understanding the engine's draw/render pipeline (read from game.dcmp, 2026-11-23)

I actually READ these function bodies (not just indexed them). Line numbers are in `game.dcmp`.

## 1. The D3D11 → vtable → driver chain (CONFIRMED)

`RageDirect3DDeviceContext11_DrawIndexed(a:{a:long,b:long}, b:int, c:int, d:int)` — line 867056, func10337:
```
a = a.b;                              // the object's vtable pointer
call_indirect(a, b, c, d, a.a[12]:long);   // vtable slot 12 = DrawIndexed
```
- This is a **1-line trampoline**. Every D3D11 context method (`Draw`, `Map`, `Unmap`, `PSSetConstantBuffers`) is the same pattern: load `a.b` (vtable), `call_indirect` with a fixed **vtable slot** (DrawIndexed=12, Draw=13, Map=14, Unmap=15).
- The vtable lives in wasm **linear memory** (the `a.a[12]` long is a function pointer into the table). The JS driver receives the resulting command via the ring — it does NOT see these functions directly.
- `rage_grcDevice_DrawIndexedPrimitive(a,b,c)` — line 857286, func10029:
  ```
  if (12483660L[0]:ubyte) { rage_grcStateBlock_DoFlush() }
  rage_grcDevice_SetUpPriorToDraw(a);
  d = tls_base+1160 -> device object
  if (12374960L[0]:ubyte==1) { call_indirect(d, ..., (d[0])[20]) // instanced path }
  call_indirect(d, c, b, 0, (d[0])[12]:long);  // slot 12 again
  // then updates a primitive counter at tls_base+1168 (br_table by topology a)
  ```
- **Conclusion:** the ~2,900 draws/frame each originate in RAGE's draw-list system, funnel through `grcDevice_DrawIndexedPrimitive`, and become a `DRAW` opcode (32) in the ring. The driver (`doDraw`) then replays each.

## 2. LOD / draw-distance functions actually read

- `rage_fwBaseEntityContainer_SetLodDistCached(a, b, c)` — line 565162, func5720. Writes a **short LOD-distance value `c`** into a per-entity slot in an SoA container. `b==65535` = no-op. `a[16]:ushort` encodes container layout (high 2 bits = kind, low 14 = count). Uses `br_table` for 3 container layouts. This is where the engine caches per-entity LOD distances — a target for forcing lower draw distance.
- `EntityDetails_GetLODDist(a, b:short_ptr)` — line 2409012, func30042. **Debug/UI only** — reads `a[84]:ushort` LOD distance and appends a formatted string to `b`. Not part of the render hot path (don't patch for FPS).
- `CLodMgr_StartSlodModeCb()` / `StopSlodModeCb()` — lines 3832821/3832833, func47187/47188. Toggle a byte at `23389032L` and pack 8 input bytes into `23389028L` (slod-mode = script LOD override debug). Debug console callbacks.
- `CTimeCycle_ApplyLodScaleModifiers` — line 5128333, func77611 (already documented in key-call-chains.md): applies `1.0 - CSettingsManager_GetSettings(...)[7]:float` = `1.0 - lodScale`. This IS in the render path.
- `CLodScale_*`, `CLodMgr_OverrideLodDist` exist in the index but were not read yet.

## 3. Draw-list system (how the ~2,900 draws/frame are generated)

- `rage_dlDrawListMgr` family (~30 functions, lines 530k-532k): manages draw lists (`NewDrawList`, `EndCurrentDrawList`, `BeginDrawListCreation`, `ResetHighestLOD`, `SetHighestLOD`, `GetDrawListEntityCount`, `AdjustFragmentLOD`, `AdjustVehicleHD`).
- `rage_dlDrawListMgr_AdjustFragmentLOD(a,b,c)` — line 532126, func5015: clamps an LOD int in `b[0]` down to `max(a[3]/a[4], f[7]/f[8])`. This directly controls how much detail (fragment LOD) is drawn — another draw-count lever.
- `rage_dlCmdNewDrawList_ExecuteStatic(a)` — line 526848, func4868: executes a static draw-list command, tracks a fence index at `11012076L`, logs. Draw lists are recorded once and replayed.
- `rage_fwRenderListBuilder_AddToDrawListEntityListCore(...)` — line 545700, func5273: builds the per-frame entity list; checks visibility masks (`f.g/f.f/f.h/f.i` bitmasks), SIMD loops over entity batches (`i32x4`, `v128_or`). This is the culling stage — entities that pass get added to draw lists.
- `rage_fwRenderPhase_DrawListPrologue` / `Epilogue` — lines 548250/548325: begin/end a render phase's draw list via `call_indirect` (vtable again).
- `rage_fwScan_AddCullShape()` — line 566756, func5760: allocates a 368-byte cull-shape struct from a global pool (`11115040L`, count at `11124760L`). Cull shapes bound the visibility tests.
- `rage_fwDrawData_AddToDrawList` — line 522609, func4721: **returns 0 — it's a stub** in this wasm build. Don't chase it.

## 4. Key insight for optimization
The FPS problem is **not** one heavy function — it's the *volume*: the draw-list system legitimately emits thousands of draws, each becoming a ring command and ~3-4 WebGPU wire calls. `SetLodDistCached`, `AdjustFragmentLOD`, `ApplyLodScaleModifiers`, and the global `lodScale` are the engine-side knobs that reduce draw volume. The only knob we've successfully used is `-lodScale=1` (config). The rest need a C++-level patch (vtable/global write) that Chrome will accept — the wasm recompile path failed, so the remaining route is runtime memory writes via JS (not yet done).

## 5. LOD control globals (READ 2026-11-23 — the writable targets!)
- CLodScale_SetGlobalScaleFromScript(float a) — line 3843317, func47412: writes  to global **23318984L** (float) and sets flag bit at 23319072L. THIS is the global LOD scale!
- CLodScale_SetRemappingFromScript(a,b,c,d) — line 3843373, func47415: writes 4 floats to 23319092L..23319104L, sets flag bit 8 at 23319072L. LOD remapping curve.
- CLodMgr_OverrideLodDist(a, b) — line 3843322, func47413: sets low 16 bits of [21] to  (if high bits match a tag), then call_indirect(a, vtable[37]). Per-entity LOD override.
- streaming_commands_CommandOverrideLodScaleThisFrame(a) — line 4140792, func60408: just calls CLodScale_SetGlobalScaleFromScript(a).
- streaming_commands_CommandRemapLodScaleRangeThisFrame — func60409 → SetRemappingFromScript.
- LODDrawable_CalculateDrawableLODFlags(a,b) — func47414: computes bucket mask via 
age_rmcLodGroup_GetBucketMask(a, 0) & (256<<b-8 & 65280).
- 
age_fwScanNodes_ProcessEntityContainer(a,b,c,d) — line 574286, func5790: entity container scan; reads [16]:ubyte, [17]:ubyte, [9]:ushort, container stats via [394], processes entities in a loop with atomics. Hot in visibility.
- CCutSceneCameraEntity_GetMapLodScale(a) — func29489: returns [13]->[26]:float or -1. Cutscene-only.
- CSettingsManager_GetSafeModeSettings — func65644: fills a settings struct with constants; [26]:int=1065353216 = 1.0f float bits.

**Optimization implication:** 23318984L (global LOD scale) and 19446852L (settings LodScale) are the two writable globals that control draw distance. A runtime JS write to wasm memory at these addresses (via the exported memory, no wasm recompile) is the untried path that could cut draws without Chrome rejection. Needs the correct timing (after ApplySettings / per frame) and verification.



## 6. Immediate-mode vertex path — TRACED (2026-11-23) — hypothesis DISPROVEN
- 
age_grcBegin(a,b) (func9561, line 817371): reserves *36 bytes via 
age_grcBatcher_Reserve (thread-local batcher at 	ls_base+1136) OR calls grcDevice_BeginIndexedVertices(a,b,36,...) writing pointer to 12484536L, resets counters 12484544L=0 (vertex count), 12484548L=b (primitive type).
- 
age_grcVertex(...) (func9562, line 817396): writes one 36-byte vertex record (j.a..j.i, with g byte-swapped) to the buffer; increments pointer +36 and counter. In batcher mode just k[16]=j+36.
- 
age_grcEnd() (func9563, line 817434): issues **ONE** 
age_grcDevice_DrawVertices() (or DrawInstancedVertices() if flag 12374960L==1), then clears pointer.
- **CORRECTION (verified by reading `rage_grcBatcher_RenderInternal`, func9732, spans 2,175 lines 830958-833133):** the immediate-mode path has TWO modes. Non-batcher mode = one DrawVertices per Begin/End. BUT batcher mode (tls_base+1136 active) accumulates vertices via `grcBatcher_Reserve` and `RenderInternal` iterates batches with loops (line 831011) and issues `rage_grcDevice_DrawVertices()`/`DrawInstancedVertices()` **per batch inside the loop** (831104/831115), plus 2d quad/line draws (831270-831293). So immediate-mode CAN emit many draws — my earlier "DISPROVEN" claim was wrong for the batcher path. Still unverified: which mode is active in-game and how many batches/frame. Do NOT claim either way without checking the live game.
## Remaining gaps (honest)
I have NOT read the bodies of: `CLodScale_SetGlobalScaleFromScript`, `CLodMgr_OverrideLodDist`, `rage_fwScanNodes::ProcessEntityContainer` (line 1159661), `CSettingsManager_ApplySettings` (only partially), the `streaming_commands_*` LOD commands, and the rest of the ~90k functions. The index (`engine-function-index.tsv`) has all their locations for when they're needed.
