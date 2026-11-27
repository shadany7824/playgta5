# 14 — Make the engine code itself run faster: V8 wasm tiering + wasm-opt

## Why
The 63 MB `game.wasm` starts in V8's fast-to-compile **Liftoff** tier and is re-compiled to optimized **TurboFan** code only for "hot" functions, in the background, over time. On a 2-core CPU that background compile competes with the game for minutes, and some engine code may stay in slow Liftoff code. When the worker gets faster (03, 09, 13), the **engine** becomes the limit, so its code speed matters.

## Lever A: V8 flags (main isolate + pthread workers), one run each
The engine runs on the Node main thread + pthread workers (all instantiate the same module).
1. `--no-liftoff`: compile everything with TurboFan up front. Expect a much longer startup (could be minutes for 63 MB on 2 cores) and then full speed immediately. Measure startup time and steady FPS.
2. Alternatively keep dynamic tiering and check that it finishes. The `--trace-wasm-compilation-times` / `--trace-wasm-tier-up` style flags exist in some V8 versions (check `node --v8-options | findstr wasm` with Node 24) to see whether hot engine functions get tiered up.
3. **Code cache:** compiling once and reusing matters if `--no-liftoff` startup is slow. Check whether Node 24 caches compiled wasm (`WebAssembly.Module` can be serialized through `v8.serialize` in some versions. Research what works on Node 24 before building anything).
- How to pass the flags: node command line in the run `.cmd` for the main thread. For pthread workers, add them to the `execArgv` where `game-node.js` creates workers (`new Worker(pthreadMainJs, {... execArgv: [...]})`). Note: some V8 flags are process-wide.

## Lever B: Binaryen `wasm-opt` on a COPY of game.wasm
- `wasm-opt -O3 --enable-threads --enable-simd --enable-memory64 --enable-bulk-memory ... game.wasm -o game-opt.wasm` (enable every feature the module uses, or it fails. `--detect-features` may work). Check the version supports memory64 and table64.
- Only useful if the original build wasn't already fully optimized. Compare the sizes first; if `-O3` changes almost nothing, the build was already optimized, so stop.
- **Keep the names section** (the decompile and the stack traces rely on names): use `--debuginfo` / `-g`.
- Point `harness.js` at the copy (one config switch). `wasm-validate --enable-all` before use.
- Risk: a wasm-opt bug or feature mismatch can crash the engine. Run 300 s plus a screenshot run.

## Measure
Startup time (process start → first world frame), steady FPS, engine wait % (file 02 2B: does engine busy time per frame drop?). Do this lever **after** the worker levers, otherwise the worker hides any engine gain.

## Pass
The engine's own frame time drops ≥ 10%, or steady FPS rises once the worker is no longer the limit, with no crashes.
