# 05 — Other host-vs-JS differences to close (one per run, after file 04)

## 1. The forced `Load()` before main (lesson 03: forced calls)
- Host: calls table slot 64 (`Load()`, the httpfs init) directly before `main` unless `GTA_AOT_NO_FORCELOAD=1`.
- JS: never calls `Load()` by hand. The engine reaches it through `wasm_httpfs_active()` → `call_once` when it opens a `/game/...` path. The harness only writes the active flag (`h.forceHttpfs(mem.buffer, 8321672)`) in `onRuntimeInitialized`.
- In an earlier Node session, exactly this kind of hand call of `Load()` crashed inside `operator new` (Stage 12) because the allocator/TLS context wasn't ready.
- Action: after file 04 passes, run once with `GTA_AOT_NO_FORCELOAD=1` and compare. Now that `-rootdir=/game/` is delivered (problem file), the engine should reach `Load()` by itself. Keep whichever matches the JS log (manifest fetched once, `IO_START` posted).

## 2. `gta_lod_cutoff` (global 0, f32, exported)
- JS: `r.instance.exports.gta_lod_cutoff.value = +(process.env.WGPU_LOD_CUTOFF || 50)` right after instantiate (`harness.js:63`).
- Host: no reference to it (grep found none). Its value stays at the f32 init in the wasm.
- Action: set it after instantiate with `wasm_runtime_get_export_global_inst` (or the WAMR API of this version) to 50 (or `WGPU_LOD_CUTOFF`). This doesn't affect the TLS crash, but the host must behave like JS for the later FPS comparison (lesson 15).

## 3. i64 argument combine in raw-native stubs
- `imp_052` did `g_tb = args[0] | (args[1] << 32)`. With `wasm_runtime_register_natives_raw`, **each parameter is one 64-bit slot**, so `args[0]` already holds the whole i64 and `args[1]` is the **next parameter** (or junk). It worked here only because `a1=0`.
- Action: grep the generator for the same pattern (`args[1]) << 32` / `args[n+1] << 32`) and fix every i64 parameter read to `args[n]`. Then check a few stubs in the audit log against JS values (e.g. `wgpu_start_worker` ring/size must be `ring, 0x2000000, 0x64748c`).
- Verify the slot layout in WAMR's raw-native docs/source for this version before changing (`wasm_native.c`, `wasm_runtime_invoke_native_raw`): if i64 really uses 2 cells there, keep the combine. **Prove it with one logged call**, e.g. `_emscripten_init_main_thread_js`: a0 must equal 0x1c399c8 on its own.

## 4. Stale name section in `game-lodlive-fixed2.wasm`
- 58 globals, but the global-name labels are those of the 57-global `game.wasm`, so every label from index 1 on is **one off** (fixed2 label "g_DisableInitNan" = index 14 = value 824, but the real g_DisableInitNan GOT is index 15 = value 720).
- Action: don't use fixed2's global names in logs or analysis. Map globals by init value or by the decompile. Optional: regenerate fixed2 with a corrected name section (the tool that inserted `gta_lod_cutoff` should shift names too), or append the new global at the **end** (index 58) next time, so all original indices stay the same.

## 5. Things already matching (no action)
- Main tb `0x1C399C8` = JS `29596104`.
- pthread order (stack limits → thread_init(ptr,0,0,1,0,0) → tls_init).
- argv (19 args incl. `-rootdir=/game/`, NULL-terminated) after the WAMR `execute_main` fix.
