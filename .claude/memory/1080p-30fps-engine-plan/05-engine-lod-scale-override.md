# 05 — Engine LOD scale override (the engine's own "draw far things simpler")

## Idea (owner's)
Keep the area near the player fully detailed, and make far objects switch to low-detail models (LOD/SLOD) sooner, or not draw them at all. Fewer and cheaper far draws → less worker time.

## What the engine code says (verified in `E:\Malik\game\game.dcmp`)
- Script command `streaming_commands_CommandOverrideLodScaleThisFrame(float)` (func 60408, line 4140792) → calls
  `CLodScale_SetGlobalScaleFromScript(a)` (func 47412, line 3843317):
  ```
  23318984L[0]:float = a;          // global LOD scale from script
  23319072L[0]:byte |= 1;          // FLAG: "script override active this frame"
  ```
- There is also `CLodScale_SetRemappingFromScript(a,b,c,d)` (func 47415, line 3843373): **per-LOD-level remapping**. That's exactly "near full, far reduced": it can scale the HD / LOD / SLOD distance bands separately. Read its body and record which addresses each of the 4 floats goes to.
- Other related code: `CLodMgr_WithinVisibleRange` (47333), `CLodMgr_OverrideLodDist` (47413, per-entity), `CTimeCycle_ApplyLodScaleModifiers` (77611, line 5128333: applies a timecycle modifier with `1.0 - settings.LodScale`), settings LodScale at `19446852` (that's `-lodScale` from the command line).
- **The earlier Chrome experiment (`engine-code-map\runtime-lod-write-result.md`) wrote `23318984` = 1.0/1.5 but never set the flag bit at `23319072`.** The engine probably only uses the script scale when the flag is set, and probably clears the flag every frame ("ThisFrame"). That would explain "no change". This is the main thing to test.

## Steps
1. **Read the consumer first.** Find who reads `23318984` and `23319072`: `grep -n "23318984L\|23319072L" game.dcmp`. Read those functions (likely `CLodScale_Update` or similar). Write down: when the flag is cleared, how the script scale combines with the settings/timecycle scale (multiply? replace? clamp to which range?), and which global holds the final scale.
2. **Hook point (Node):** the write must happen every frame after the engine clears the flag and before it reads it. The simplest proven hook is the wgpu worker's `present()` (it has wasm memory, like the old `patchLod()`); that runs once per frame but on another thread, so it's racy. If the final per-frame scale is a single global (step 1), writing the *final* value may be more reliable than the script input. Alternative: patch the consumer function via WAT (proven method) to use a constant, which is deterministic. Choose and justify.
3. **Values to test (one per run):** script scale 0.8, 0.6, 0.4 (lower = LODs switch closer = fewer HD draws). Then with step 1's knowledge, try the remap: keep HD band 1.0, LOD band 0.7, SLOD band 0.5.
4. Write with fresh views: `const dv=new DataView(mem.buffer); dv.setFloat32(23318984,v,true); Atomics.or(new Uint8Array(mem.buffer),23319072,1)` (Atomics on Uint8Array is allowed). Log once: `[lod] wrote v`.

## Measure
Draws/frame and FPS (file 01), **and screenshots at the same spot before/after**: look for pop-in, missing buildings, blurry near objects. Near objects must stay full detail.

## Pass
- Draws drop ≥ 15% with no visible damage near the player → keep, and record the value.
- No draw change → the hook timing or the flag logic is wrong. Go back to step 1, don't just try bigger numbers.
