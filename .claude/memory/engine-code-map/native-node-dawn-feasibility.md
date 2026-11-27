# Native Node/Dawn launch — feasibility tested (2026-11-23)

## Milestone: Dawn works on this machine
- Installed `webgpu` npm package: `npm install webgpu --prefix E:\gta\playgta5\node-webgpu` → "added 4 packages" ✅ (npm at `C:\Program Files\nodejs\npm.cmd`, v10.9.8).
- Test (`node-webgpu/test.js`): `create([])` → `requestAdapter` → `ADAPTER_OK`, `requestDevice` → `DEVICE_OK` ✅. Intel HD 620 is accessible from native Dawn on Windows.
- Shader package EXISTS: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\shaders\index.json` + 6,615 files (set `WGPU_SHADER_DIR` to this path; the worker reads `.wgsl`/`.consts.json` from disk in Node mode).

## What's missing / blocking
- No Node launcher harness: the original `D:/wasm_build` build environment (which had the main-thread + pthread + worker host script) is absent. `game.js` supports Node (`ENVIRONMENT_IS_NODE`, `worker_threads`), and `wgpu_worker.js` has a full `isNode` path (Dawn, fs shader loading, file screenshots), but no script here wires the workers + Module startup together.
- No display: Node WebGPU renders to textures + readback only; no canvas. Need a presentation path (Sunshine/Moonlight streaming, or write PNG frames — neither built; memory 21-cloud-gaming-clarification).
- Need env vars: `WGPU_NODE_MODULE=E:/gta/playgta5/node-webgpu/node_modules/webgpu`, `WGPU_SHADER_DIR=E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders`.

## Next steps to actually try (substantial)
1. Write a Node host harness that boots `game.js` as the main Emscripten module with the right args, spawns wgpu/io workers via worker_threads, passes the shared ring memory + message protocol (wgpu_backend.cpp expectations), and pumps stdin/events.
2. Point env vars at the installed Dawn + shader dir.
3. Run headless: render N frames to a texture, read back, write PNG to verify image correctness vs Chrome.
4. Only then consider a display/streaming path for actual play.
This is a multi-hour project with uncertain payoff (native is 1.5-4x faster in benchmarks, but the port's Node path was a dev-loop tool, not a shipped player).

## Status
Package installed and Dawn verified working. Harness NOT built. Original browser play remains the practical path. All data saved so a future session can continue from here.

## Harness build attempt (2026-11-23) — PARTIAL, blocked on Emscripten Memory64 issue
- Built `E:\gta\playgta5\node-webgpu\harness.js` + `worker-boot.js`. Solved in order: self/postMessage shims in workers, io worker init message, wgpu worker Node quirk (sends `ready` not `loaded`, starts on `start` message), main-thread addEventListener shim, CommonJS Module shadowing (switched to `vm.runInThisContext` so globalThis.Module is seen).
- Progress: io worker loads, game.js runs in global scope, creates pthread workers.
- BLOCKER: `initMemory()` in game.js throws `Cannot convert a BigInt value to a number` (Memory64 `WebAssembly.Memory({initial:BigInt(...),maximum:262144n,shared:true,address:"i64"})`). Also pthread workers spawned from raw game.js path lack the worker-boot shim ("self is not defined"). This is Emscripten Memory64 + Node 22 incompatibility that the original D:/wasm_build harness handled with a specific setup we don't have.
- Also: no canvas/display in Node; would need readback-to-PNG + streaming path even if it boots.
- Files kept in `node-webgpu/` for a future attempt. Native Dawn adapter/device still VERIFIED working.

## FINAL BLOCKER (2026-11-23): Node 22 V8 cannot parse game.wasm
- Built a working harness (`node-webgpu/harness.js`, `game-node.js` patched, `worker-boot.js`) that boots game.js under Node with native Dawn.
- Solved: Memory64 BigInt (patched game.js to pass Numbers), max memory 262144→65536 pages (Node cap), wasm disk loading (instantiateWasm), Module shadowing (globalThis.Module), worker shims, pthread spawn.
- **DEFINITIVE BLOCKER:** `WebAssembly.instantiate(): invalid table elements limits flags @+119238`. Node 22's V8 rejects the game.wasm element/table section (post-MVP table encoding) even with `--experimental-wasm-memory64`. Chrome 158 supports it; Node 22 V8 does not. Only Node 22 is installed; no table64 flag exists. **Native Node launch is impossible on this machine without a newer Node/V8 that supports the wasm's table features.**
- Harness files kept in `node-webgpu/` for future attempts with a newer Node. Native Dawn adapter/device still verified working (once parsing is fixed, the path is viable).
