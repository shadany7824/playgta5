# Semantic analysis of the earlier 20k batches (2026-11-23)

The two `bulk-analysis-10000*.md` files were **static classification only** (stubs/vtable/global counts). This doc adds the semantic layer: what these 20,000 functions actually ARE, based on their names + representative full bodies I read.

## Batch 1 (render/LOD/streaming prefixes) — what it really covers

The selected names span several distinct subsystems:

1. **`wasm_null_d3d_*` — the null D3D11 device (MANY functions, lines ~302k-308k).** `wasm_null_d3d_NullAdapter_CheckInterfaceSupport`, `NullSwapChain_GetBuffer`, `NullDevice_GetImmediateContext`, `NullContext_OMSetRenderTargetsAndUnorderedAccessViews`, `NullView_*` (shader resource / unordered access / render target / depth stencil view desc helpers). **Semantics:** this is a stub D3D11 implementation used when the game queries hardware capabilities. `NullContext_*` methods are mostly no-ops returning dummy objects. This is the layer the ORIGINAL game uses to talk to D3D11; the wasm port replaces it with the WebGPU backend. Not an FPS lever — it's compatibility scaffolding.

2. **`rage_dlCmd*_ExecuteStatic` — draw-list command executors (line ~526k).** `BeginDraw`: `call_indirect(b, a[16]:ubyte, (b[0])[7])` = vtable slot 7 to begin a draw; `EndDraw`: slot 8. `LockRenderTarget`/`UnlockRenderTarget` use global `12372136L` device + vtable slots 20/21. **Semantics:** the draw list is a recorded command buffer; these ~30 functions replay each command type via vtable calls into the renderer. This is the direct producer of the ring commands our driver consumes.

3. **`rage_fwDrawData_*` (line 522581+).** `Update` = `call_indirect(a[4], b, vtable[3])`; `AddToDrawList` = **returns 0 (stub)**. Helper conversions `WaypointRecordingRoute_SideDisttoUNIT8` etc. quantize floats to bytes for network recording. Not FPS-relevant.

4. **`rage_atHashStringNamespaceSupport_*` (line 322927+).** `ComputeHash(a,b)` = `call_indirect(b, table[a*72+1043739])`; `AddString(a,b,c)` inserts a hashed string into one of 5 global hash tables (lock at `8349872L + a*72`, buckets at `8349856L`), with `strcasecmp` dedup and `sm_Current` allocator. **Semantics:** RAGE's global string interning (5 namespaces). Called constantly at load; not per-frame hot.

5. **`rage_par*` — the parser/reflection system (lines 390k-500k+).** `parInstanceVisitor_*` (BoolMember, VecBoolVMember, Mat33VMember, StringMember, AtStringMember, EnumMember, BitsetMember, BeginArrayMember, BeginMapMember...) and `parCguDestructor_*`/`parStructure_*` for clip/move/network data. **Semantics:** generated reflection code that walks data structures for serialization/loading (par = "parameter"?). Used for loading CLIP/MOVE/XML resources; not runtime-render hot.

6. **`rage_fwAnimDirectorComponent*_*` (lines 508k-513k).** `ShutdownPoolClass` for Motion/Creature/Move/Expressions/RagDoll/SyncedScene/FacialRig. **Semantics:** pooling cleanup for animation components. Startup/shutdown only.

7. **`sfRenderer_CreateTextureYUV`** — creates a YUV texture (video playback / Bink). The log's "Unable to open movie: Bink not available" ties in; this path is dead for movies.

## Batch 2 (gameplay prefixes) — what it really covers

1. **`rage_parInstanceVisitor_*` / `parMemberPlacementVisitor_*` / `parStreamInXml_*` / `parCguDestructor_*`** — same reflection/serialization system as above (a large fraction of batch 2). Not per-frame.

2. **`rage_net*` (line 713007+).** `netInterface_IsHost`, `FlushAllLogFiles`, `netArrayHandlerBase_GetUnsyncedPlayers`, `netSocket_NativeGetReceiveBufferQueueLength`, `CPacketBase` family. **Semantics:** RAGE networking layer (host determination, replication, socket buffers). Not FPS-relevant in single-player.

3. **`rage_ptxu_*` (lines 705k-707k).** `Decal_InitPoint`, `Light_InitPoint`, `Liquid_InitPoint`, `River_InitPoint`, `ZCull_InitPoint`/`UpdateFinalize`. **Semantics:** PTX effects (particle/texture effects) keyframe systems — decals, lights, liquid, river, and **ZCull** (occlusion culling). `ZCull_UpdateFinalize(a,b)` = `if (a[87]==4) call_indirect(a,b,vtable[14])`. This is the one group with indirect FPS relevance (occlusion culling decides what's not drawn).

4. **`rage_ph*` — physics (InstBreakable etc.), **`CVehicle`/`CPed`** — entity gameplay, **`money`/`stats`/`hud_commands`** — UI/economy script commands. None are draw-generation code.

## Honest conclusion
Neither old batch contains the FPS answer:
- Batch 1's render-relevant part = **draw-list replay** (`dlCmd*_ExecuteStatic`), already understood from `draw-pipeline-understanding.md`; the rest is null-D3D scaffolding, string hashing, reflection, animation pooling.
- Batch 2 is mostly reflection/serialization, networking, PTX effects, physics, and gameplay. The only FPS-adjacent piece is PTX `ZCull` (occlusion culling) — but patching culling risks visual holes.

This matches every prior audit: the draw wall is the volume of legitimate draws, and the engine-side draw-count knobs (lodScale, LOD globals) are the only safe levers. The 20k static batches remain useful as a search index, not as optimization targets.
