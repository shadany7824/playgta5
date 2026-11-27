# 08 — Shadows, reflections, lights: cut whole render passes

## Why
Each render phase re-draws scene objects: shadow cascades draw the world again from the sun (up to 4 cascades), reflection/water/mirror phases draw it again from another camera. At 1080p Node shows ~58 passBegins and 21 clears per frame. **Removing a phase removes all its draws at once.** Use file 02 2D (draws per phase) to pick the biggest first.

Current baseline already has `-shadowQuality=0 -reflectionQuality=1`. Check in 2D how many draws are still in shadow/reflection passes. With shadow 0 there may still be a cascade or a "shadow-less" cheap pass.

## Engine code to read (funcidx from `engine-code-map\engine-function-index.tsv`)
| Area | Functions |
|---|---|
| Cascade shadows | `CRenderPhaseCascadeShadows_GetCullFlags` (44702), `rage_fwScanCascadeShadowInfo_UpdateShadowViewport` (5766), `rage_fwScanCascadeShadowInfo_IsShadowVisible` (5768), `CRenderPhaseCascadeShadowsInterface_Init` (43798) |
| Reflection | `CRenderPhaseReflection_SetReflectionMap` (44154), `SetReflectionMapExt` (44291) |
| Mirrors | `CRenderPhaseMirrorReflection_*` (44816+), `CMirrors_CreateRenderTargets` (43477), `CMirrors_ResolveMirrorRenderTarget` (43481) |
| LOD lights (distant street lights) | `CLODLights_RenderLODLights` (44583), `CLODLights_GetUpdateLodLightRange` (44567: range = product of globals `22873708`, `25501520`, table `1812189`, `22873704`×`7248792`) |
| Distant vehicle lights | `graphics_commands_..._DISABLE_VEHICLE_DISTANTLIGHTS` (51230) |
| Visibility scan | `rage_fwScanNodes_ProcessExteriorVisibility` (5785), `rage_fwScanEntities_ProcessSingleEntityDescSoa` (5784) |
| Draw list | `CRenderListBuilder_AddToDrawList` (43850), `AddToDrawListEntityList` (43857) |

## Steps (one lever per run)
1. **Measure per phase** (file 02 2D) at the baseline. List the top 5 passes by draws.
2. **Shadow cascades:** read `GetCullFlags` + `UpdateShadowViewport`: find the cascade count and the shadow distance (a global or the timecycle). Try fewer cascades (e.g. 4 → 2) or a shorter shadow distance (shadows stay near the player, far shadows go). That's the same near/far idea applied to shadows.
3. **Reflection:** try `-reflectionQuality=0` first (a command-line arg, no patch). Then check whether the water/mirror phases still render; mirrors only matter indoors.
4. **LOD lights range:** halve the final range in `GetUpdateLodLightRange` (WAT patch: multiply the return value by 0.5), or find which of its globals is a user/quality multiplier and write it from JS.
5. **Visibility scan:** read `ProcessExteriorVisibility` for a far-distance cutoff that is applied before the draw list. Lowering it removes far entities from **all** phases at once (a strong lever, also a strong visual cost).

## Measure
Draws per phase, total draws, passBegins/frame, FPS, and screenshots in daylight (shadows visible) at the same spot.

## Pass
Keep a change if FPS rises ≥ 5% and the near-player look is OK (owner judges from the screenshots). Record each kept value. If disabling a whole phase breaks the image (black water, missing sky), revert.

## Note
Shadows at quality 0 already gave Chrome 13-15 → 16.5 FPS (memory 09). Don't expect a huge extra gain from shadows unless 2D shows many shadow draws remain.
