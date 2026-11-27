# 15 — Web research: fixing what the decompile exposed (2026-11-21)

## The problem seen in the decompile
Draw calls are C++ vtable calls lowered to `call_indirect`:
```c
function RageDirect3DDeviceContext11_DrawIndexed(a:{ a:long, b:long }, b:int, c:int, d:int) {
  a = a.b;
  call_indirect(a, b, c, d, a.a[12]:long);
}
```
There is no readable engine draw-generation logic to edit.

## Research findings
1. **WAT round-trip patching**: webassembly.org says `wasm2wat` → edit WAT → `wat2wasm` gives lossless round-trip and is the standard way to "try optimization algorithms, tracing, inserting debugging hooks". Feasible in principle, but our WAT is 591 MB / 91,026 functions and the module uses Memory64 + shared memory + 89k table entries — editing one function and rebuilding is high-risk. Patched wasm also needs the loader's fetch URL/version changed (Grand-V PR #38 did exactly that for a photo fix), or Chrome serves the cached original.
2. **`call_indirect` table hooking**: our `wasm-objdump` shows `Export[22]` includes `table[0] -> "__indirect_function_table"` (89,367 elements). Web research (webassembly-wasm.com, MDN) confirms JS can `table.get(i)` / `table.set(i, fn)` to swap a slot, provided the replacement has the exact same signature; Emscripten's `addFunction` makes JS wrappers. This is the cleanest hook point into the engine, but it still requires finding which table index the draw vtable slot uses, and a no-op replacement breaks rendering.
3. **Academic binary rewriters**: BREWasm (static Wasm rewriting framework) and SCRIBE (recompile decompiled functions + layout-preserving retrofit) can patch selected function bodies. Research-grade, not practical for a 63 MB game here.
4. **wasm-tools mutate/shrink** are fuzzing/minimization tools, not targeted semantic patchers.

## Practical verdict
Safe surface remains: JS worker code (already patched heavily) and runtime args/settings (already explored). Wasm patching/table hooking could instrument or skip draws but cannot safely reduce the engine's draw count without ruining the image; 25 FPS at true 1080p still needs stronger hardware.
