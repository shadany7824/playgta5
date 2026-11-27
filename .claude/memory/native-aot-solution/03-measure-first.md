# 03 — Measure first: dump the TLS globals in the host AND in JS

Goal: one host run + one JS run that show `tls_base`, `thread_ptr`, the g_DisableInitNan GOT global and the tls_init return value at the same points. The difference names the bug.

## Which globals (fixed2 indices, see file 01 B: shifted +1 vs game.wasm)
| fixed2 index | real meaning | type |
|---|---|---|
| 1 | `__stack_pointer` | i64 |
| 2 | `__tls_base` | i64 |
| 4 | `thread_ptr` | i64 |
| 15 | GOT `g_DisableInitNan` (= tls_base + 720) | i64 |
| 11 | GOT `sysMemAllocator_sm_Master` (= tls_base + 840) | i64 |
| 18 | GOT `g_CurrentThreadId` (= tls_base + 0) | i64 |
**Re-verify these indices** by running `E:\gta\_tmp_claude\globals.py` on both wasms and matching **init values** (720, 840, ...) to the decompile's `wasm_init_tls` offsets, **not** by fixed2's name labels (they're off by one).

## Host side: a global dump helper
WAMR doesn't expose non-exported globals through the public API. The AOT instance keeps them in `AOTModuleInstance->global_data`, with each global's offset in the module's global table. Add a debug function next to the existing `aot_log_fault()` in `E:\gta\wamr\core\iwasm\aot\aot_runtime.c` (you already rebuilt this file before):
```c
void aot_debug_dump_globals(WASMModuleInstanceCommon *inst_c, const char *tag) {
    AOTModuleInstance *inst = (AOTModuleInstance *)inst_c;
    AOTModule *mod = (AOTModule *)inst->module;
    uint32 idx[] = { 1, 2, 4, 11, 15, 18 };
    for (uint32 k = 0; k < sizeof(idx)/sizeof(idx[0]); k++) {
        uint32 i = idx[k];
        if (i < mod->import_global_count) continue;
        AOTGlobal *g = &mod->globals[i - mod->import_global_count];
        uint8 *p = inst->global_data + g->data_offset;
        uint64 v = 0; memcpy(&v, p, g->size >= 8 ? 8 : 4);
        os_printf("[GLOB] %s g%u type=%u off=0x%x val=0x%llx\n", tag, i, g->type.val_type, g->data_offset, (unsigned long long)v);
    }
}
```
Field names (`global_data`, `globals`, `data_offset`, `size`, `type.val_type`, `import_global_count`) differ between WAMR versions. **Check them in `aot_runtime.h` / `aot.h` of the checked-out WAMR** and adapt. Expose it in a header the host includes, rebuild `libiwasm.lib`, then call it from the host (and make it write to the audit log instead of `os_printf` if that's easier).
- Also log the **offset of global 15**. If `0x230` = `global_data` offset + global 15's `data_offset`, that also proves the disassembly reads exactly this global.

### Checkpoints in `call_main()` (one run)
1. right after instantiate (expect GOT g15 = 720, tls_base = 0)
2. after `_emscripten_thread_init` (log `tb` used, `thread_ptr`, and `mem[thread_ptr+184]` as u64)
3. after `_emscripten_tls_init`: **log its return value** (it returns i64 `tls_base`; WAMR puts it in the args array after the call)
4. after `__wasm_call_ctors`
5. after the forced `Load()` (table 64)
6. inside `aot_log_fault()` at the exception
Plus inside the `_emscripten_init_main_thread_js` import: log `tb` and dump globals (TLS state in the middle of ctors).

## JS side: the reference values (same wasm, same points)
In `node-webgpu\game-node.js` (backup first), after the instance is received:
- Wrap the TLS/thread init exports so their arguments and return values get logged:
  ```js
  // after wasmExports is assigned (receiveInstance / assignWasmExports)
  const _tls = wasmExports['_emscripten_tls_init'];
  wasmExports['_emscripten_tls_init'] = (...a) => { const r = _tls(...a); globalThis.__diag && globalThis.__diag('JS TLS_INIT ret=' + r); return r; };
  ```
  Note: game.js copies exports into variables (`__emscripten_tls_init = wasmExports[...]`) and `registerTLSInit(...)` captures the function **before** `assignWasmExports`, so wrap at the place it's captured, or wrap both places. Confirm with a log line that the wrapper actually ran (lesson 10).
- Log `tb` in `__emscripten_init_main_thread_js` (already logged earlier as `INIT_MAIN_THREAD tb=29596104`).
- Reading non-exported globals from JS isn't possible directly. `TLS_INIT ret` gives `tls_base`, and from it `GOT g_DisableInitNan = ret + 720`. That's the expected value.

## Read the result
| Host shows | Means | Go to |
|---|---|---|
| tls_init ret ≠ JS ret, or ret huge/odd | H1/H2: wrong time/inputs for TLS init | file 04 |
| g15 correct after ctors, wrong after `Load()` | H4: the forced `Load()` breaks it | file 05 §1 |
| g15 correct at checkpoint 5, wrong at fault | something in main before +0x4fc (imports 204-206) writes it | file 07 |
| g15 correct at the fault, but the exception still fires | H5 (AOT read width/offset) or the `rdi` instance isn't this one (H3) | file 07 |

Write the full dump table into ERROR-TRACE as a new Stage.
