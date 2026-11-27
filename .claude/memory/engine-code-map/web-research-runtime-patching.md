# Web research: runtime wasm patching on Chrome (2026-11-23)

User challenged the claim that JS can patch the running wasm. Researched MDN/webassembly.org/spec docs. Verdict:

## CONFIRMED
- JS reads/writes wasm linear memory via `new DataView(memory.buffer).setFloat32(offset, val, true)` (little-endian) or `new Float32Array(memory.buffer, offset, 1)[0] = val`. Sources: MDN `WebAssembly.Memory`, webassembly.org "Understanding the JS API", MDN DataView.
- Memory can be **imported from JS** with `shared: true` → `SharedArrayBuffer`. Our game imports `env.memory` from the loader → JS holds the reference. Same for `__indirect_function_table` (Emscripten exports it by default).
- `WebAssembly.Table.prototype.set(index, value)` replaces table entries at runtime; MDN states JS functions can be placed in tables (subject to element type + signature check). `call_indirect` then dispatches to them.

## CAVEATS (corrected my earlier overstatement)
1. **Stale views after growth**: after `Memory.grow`, `memory.buffer` returns a NEW ArrayBuffer; old typed-array/DataView views detach (byteLength 0) and writes silently vanish. Must obtain `new DataView(mem.buffer)` fresh at write time. Our wasm grows to 3072 MB at runtime — this WILL happen.
2. **Torn values / concurrency**: shared memory written from JS while engine threads read can tear. `Atomics` only works on integer typed arrays — store the float's 32-bit bit pattern via `DataView.getUint32` → `Atomics.store(new Int32Array(mem.buffer), addr>>2, bits)`. Or write every frame (timing hook in worker) to make tears harmless.
3. **Table hook reliability conflict**: MDN says JS functions in funcref tables work; the Emscripten `qsort` callback example (Tencent blog, 2023) found `__indirect_function_table.set()` with a plain JS function did NOT work — they needed a dynamically generated wasm shim importing the JS func and re-exporting it. Test live before relying on it.
4. **Memory64**: addresses ≥ 2^32 need BigInt for the JS Memory API. Our target addresses (19446852, 23318984) are < 2^32, so normal typed-array offsets work, but the memory is declared i64 — verify a DataView view covers them (it should: buffer spans 3 GiB).

## Practical plan (untried)
- In `loader.js` (or wgpu_worker.js which shares the same `WebAssembly.Memory`), write LOD globals:
  - `19446852` = settings LodScale (from `-lodScale`)
  - `23318984` = global LOD scale (`CLodScale_SetGlobalScaleFromScript`)
- Write via fresh DataView each time; prefer `Atomics.store` on the Int32 view of the float bits; hook per-frame in the worker command loop so the engine can't overwrite it.
- Verify: game log shows `[settings] LodScale: 1.000000`, draws/frame drop vs baseline, validation errors +0, page passes 20% → world shown.
- If the engine rewrites the value after our write (ApplySettings / sysParam), the per-frame hook handles it.

## Source list
- https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Memory (MDN, little-endian + DataView example)
- https://webassembly.org/getting-started/js-api (import/export memory, typed array writes)
- https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Loading_and_running (table.get from JS)
- https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Table/set (Table.set from JS)
- https://webassembly-wasm.com/.../exporting-a-table-to-javascript (Emscripten __indirect_function_table, table.get/set)
- https://cloud.tencent.com.cn/developer/article/2300996 (qsort callback: table.set with JS func failed, needed wasm shim)
- https://webassembly-wasm.com/.../creating-views-into-wasm-memory-safely (stale views after grow, 40ns view creation in Chrome)
