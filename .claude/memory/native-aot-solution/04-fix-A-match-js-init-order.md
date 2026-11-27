# 04 — Fix A: run thread/TLS init where JS runs it (inside the import, during ctors)

## Why
JS (the working reference) does: ctors start → C runtime sets up the main pthread struct → import `__emscripten_init_main_thread_js(tb)` → `_emscripten_thread_init(tb,1,1,can_block,1048576,0)` → `_emscripten_tls_init()` → ctors continue → main.
The host does it **before** ctors with the import as a no-op. Lessons 04/12: make the broken setup match the working one.

## Change 1 — the import does the work (in `gta_aot_host.cpp` AND in `gen_host.py`)
Replace the body of `imp_052__emscripten_init_main_thread_js`:
```cpp
static void imp_052__emscripten_init_main_thread_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_init_main_thread_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_init_main_thread_js", 1, args);
  g_tb = (uint64_t)args[0];                       // raw native: one 64-bit slot per param (see file 05 §3)
  wasm_module_inst_t inst = wasm_runtime_get_module_inst(env);
  wasm_function_inst_t ti = wasm_runtime_lookup_function(inst, "_emscripten_thread_init");
  wasm_function_inst_t tl = wasm_runtime_lookup_function(inst, "_emscripten_tls_init");
  bool ok1 = false, ok2 = false; uint64_t tls_ret = 0;
  if (ti) { uint32_t a[7] = { (uint32_t)g_tb, (uint32_t)(g_tb >> 32), 1, 1, 1, 1048576, 0 };
            ok1 = wasm_runtime_call_wasm(env, ti, 7, a); }
  if (tl) { uint32_t z[2] = { 0, 0 };
            ok2 = wasm_runtime_call_wasm(env, tl, 0, z);
            memcpy(&tls_ret, z, 8); }
  audit_line("INFO", "_emscripten_init_main_thread_js", "tb=0x%llx thread_init=%d tls_init=%d tls_base=0x%llx exc=%s",
             (unsigned long long)g_tb, ok1, ok2, (unsigned long long)tls_ret, wasm_runtime_get_exception(inst));
  AUDIT_EXIT("_emscripten_init_main_thread_js", 0);
}
```
- `can_block`: JS uses `!ENVIRONMENT_IS_WEB` = 1 in Node. Keep 1.
- **Check the real function type** of `_emscripten_thread_init` in the wasm (the generator reads the type section): the cell count must match (i64 tb = 2 cells + five i32 = 7). If `default_stacksize` is i64 in this build, it's 8 cells. Don't guess (lesson 11).
- Re-entrancy: calling wasm from inside a native import with the **same `env`** is the normal WAMR pattern (callbacks). The old comment said the host avoided it "to avoid re-entrant calls". If it fails, log the exact exception text; don't silently fall back (file 07).

## Change 2 — remove the early init in `call_main()`
Delete (or gate behind `GTA_AOT_EARLY_TLS=1` for A/B) the block before `__wasm_call_ctors` that calls `_emscripten_thread_init` and `_emscripten_tls_init`. Keep everything else unchanged in this run (one change, lesson 19).

## Change 3 — pthreads stay as they are
`pthread_thread_cb` already matches JS's worker order (stack limits → `_emscripten_thread_init(ptr,0,0,1,0,0)` → `_emscripten_tls_init`). Leave it.

## Build and run
Regenerate the host with the fixed `gen_host.py`, or patch both files identically and diff them. Then build with the command in the problem file, run as before, and read the audit log.

## Pass checks
- Audit log: `_emscripten_init_main_thread_js tb=0x1c399c8 thread_init=1 tls_init=1 tls_base=0x<value>`, and that value **equals the JS `TLS_INIT ret`** from file 03.
- No OOB at `main+0x4fc`. The next import after seq 206 should be `wasm_module_js("keepThreads")` (problem file, JS reference), then thread creation and `openat ./this.cmp`.
- If the crash moves later: that's progress. Log the new site as a new Stage. Don't revert.
