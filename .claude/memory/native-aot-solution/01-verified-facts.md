# 01 — Verified facts (Claude, 2026-11-27)

## A. What the crashing pointer really is
- Decompile (`E:\Malik\game\game.dcmp`, built from the original `game.wasm`), `wasm_init_tls` (func 86, line 280463):
  ```
  tls_base = a;
  MemoryInit(a, 0, 3572);                       // copy the TLS template into the block
  GOT_data_internal_rage_sysMemAllocator_sm_Master = tls_base + 840L;
  ...
  GOT_data_internal_rage_g_DisableInitNan = tls_base + 720L;   // the pointer main uses
  GOT_data_internal_rage_g_CurrentThreadId = tls_base;
  ... (~47 more, all tls_base + offset)
  ```
- `wasm_apply_tls_relocs` (func 89) is **empty**.
- Only caller: export `emscripten_tls_init` (func 90693, line 6092462):
  ```
  a = tls_base; c = thread_ptr; b = c[23];          // c[23] = pthread struct + 184
  if (b != 0) { c[23] = 0; wasm_init_tls(b); return b; }
  if (eqz(eqz(g_needs_dynamic_alloc) & a != 0)) { g_needs_dynamic_alloc = 1; a = internal_memalign(16, 3572); }
  wasm_init_tls(a); return a;
  ```
- So `GOT.data.internal.*` are **wasm globals** (thread-local addresses), written only by this function. **They are not WAMR AOT relocations.**

## B. The AOT's source wasm has one extra global at index 0
Parsed the global sections with `E:\gta\_tmp_claude\globals.py`:
| | `game.wasm` (mirror, original) | `game-lodlive-fixed2.wasm` (AOT source) |
|---|---|---|
| globals | 57 | **58** |
| global 0 | `__stack_pointer` i64 = 33798800 | **`gta_lod_cutoff` f32** (exported) |
| `__stack_pointer` | index 0 | index **1** |
| g_DisableInitNan GOT (init 720) | index 14 | index **15** |
- The **name section of fixed2 was not shifted**: in fixed2, the label "g_DisableInitNan" sits on index 14 (value 824 = really `sysMemAllowResourceAlloc`). Any tool that names fixed2 globals from its name section is **off by one** (file 05).
- The JS harness runs this same fixed2 (`node-webgpu\harness.js:63`) and works, so the inserted global itself is valid. JS sets `gta_lod_cutoff = WGPU_LOD_CUTOFF || 50` after instantiate.
- All 58 globals have plain const init expressions (52 `i64.const`, 5 `i32.const`, 1 `f32.const`). No `global.get`/extended-const, so **there's no init-expression evaluation problem.**

## C. WAMR's aux-stack detection is not involved
- `E:\gta\wamr\core\iwasm\interpreter\wasm_loader.c` ~6550-6600: it only searches for an aux-stack global if the module **exports `__data_end` and `__heap_base` globals**, and then only a **mutable i32** global.
- fixed2 exports only one global (`gta_lod_cutoff`); `game.wasm` exports none. → `aux_stack_top_global_index` stays unset. (Note the memory64 gap anyway: the real stack pointer is i64 and would never match.)

## D. JS init order (the working reference), from `mirror\...\game.js`
1. `initRuntime()` → `wasmExports["__wasm_call_ctors"]()`.
2. **Inside ctors**, the C startup code calls the import `__emscripten_init_main_thread_js(tb)`:
   `__emscripten_thread_init(tb, !ENVIRONMENT_IS_WORKER /*1*/, 1, can_block, 1048576, false); PThread.threadInitTLS();`
3. `threadInitTLS()` runs `_emscripten_tls_init` (registered via `registerTLSInit(wasmExports["_emscripten_tls_init"])`).
4. Ctors continue (now with TLS set up the normal way), then `main`.
- Worker threads (cmd=2): `establishStackSpace(ptr); __emscripten_thread_init(ptr,0,0,1,0,0); PThread.threadInitTLS(); ...`
- Earlier JS log: `INIT_MAIN_THREAD called tb=29596104` = **0x1C399C8**.

## E. The C++ host's order (`node-webgpu\native\gta_aot_host.cpp`)
- `call_main()` (~line 1499): **before** ctors it calls `_emscripten_thread_init(tb = g_tb ? g_tb : 0x1c399c8, 1,1,1,1048576,0)` and `_emscripten_tls_init()` (return value ignored). Then `__wasm_call_ctors`, then a **forced** `Load()` via table slot 64, then startup writes, then `__main_argc_argv`.
- Import `imp_052__emscripten_init_main_thread_js` (~line 925) only stores `g_tb` and logs `"init deferred to host"`. **It does not run thread_init/tls_init.**
- Audit log lines 20-25 (`E:\gta\_tmp_claude\native-host-audit.log`): `thread_init ok=1`, `tls_init ok=1`, then inside ctors `_emscripten_init_main_thread_js a0=1c399c8`. So the hard-coded tb matches the JS tb, but the **timing** differs from JS.
- Threads: `wasm_runtime_spawn_exec_env(env)` + `std::thread`. In WAMR this creates a new module instance per thread, so globals are per-thread like in JS.

## F. Not known yet (must be measured, file 03)
The actual value of the GOT global (and `tls_base`, `thread_ptr`) at the fault. The fault log prints memory size and some data globals, but **not** these wasm globals or `rax`.
