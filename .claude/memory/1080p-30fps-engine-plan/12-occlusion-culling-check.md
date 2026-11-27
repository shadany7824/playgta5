# 12 — Is the engine's occlusion culling actually working in this wasm build?

## Why this could be huge
GTA V hides objects behind buildings with a **CPU software rasterizer** (occluder meshes drawn into a small depth buffer; entities fully behind it are skipped before any draw). In a city it can remove a large share of draws. If the wasm port has it **off or broken** (threads, SIMD, a disabled job), the engine draws everything in the view frustum, which would explain the high draw counts at 1080p.

## Engine code present (from `engine-code-map\engine-function-index.tsv`, bodies in `E:\Malik\game\game.dcmp`)
- `rage_fwScanEntities_IsEntityOccluded` (func 5779): the per-entity test, uses SIMD. Called from 4 places.
- `rage_fwScanEntities_CalculateProjectOcclusionOBB` (5778)
- `rage_SoftRasterizer_*` (13156-13189): `PrepareSubmitTilersDependency` (13163), `Wait` (13170), `RasterizeStencilModel` (13180), `SetWaterOccluderResources` (13189)
- `rage_OccludeModel_Draw` (13188), `rage_rstSelectModelOccluders` (13174), `boxoccluder` (13165)
- GPU occlusion queries: `rage_grcDevice_CreateOcclusionQuery` ... `GetOcclusionQueryData` (10021-10025). Check whether the WebGPU backend implements them or returns "not occluded" (these may be the `readback 1.4/frame` submits).

## Steps
1. **Read the 4 callers** of `IsEntityOccluded` and find the enable condition: a global bool/flag that skips the test (look for `if (eqz(<addr>[0]:ubyte)) goto` before the call). Record the address(es).
2. **Read the soft-rasterizer setup** (`PrepareSubmitTilersDependency`): it normally runs as worker jobs (dependency threads). The log shows `[RAGE] Dependency 0` started. Check whether the job ever runs: does the rasterizer output buffer get written, or does `SoftRasterizer_Wait` return immediately?
3. **Runtime proof without patching:** read the enable flag(s) from JS during play (fresh DataView, log every 10 s). Optional: a count. Find a stats counter the engine keeps for occluded entities (`SoftRasterizer_DisplayStats` thunk at 13186 shows what stats exist).
4. If it's **off**: try turning it on (JS write of the flag, or a WAT patch of the condition), one run, and compare draws + screenshots (look for objects wrongly vanishing: false occlusion).
5. If it's **on**: write "occlusion active" with the evidence and move on.

## Pass
Clear evidence either way (addresses + values). If enabling it cuts draws ≥ 20% with no wrongly hidden objects, that's likely the single biggest engine win.

## Risk
Wrong culling makes objects pop in and out. Always compare screenshots while turning the camera.
