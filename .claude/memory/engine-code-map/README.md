# Engine code map — PlayGTA5 (RAGE engine wasm + JS driver)

> **STATUS:** MountAudioPacks SOLVED (Stage 16, missing `-rootdir=/game/`). Next: loading-screen start choice. Solution + next steps: [../CURRENT-PROBLEM.md](../CURRENT-PROBLEM.md). Full log: [ERROR-TRACE.md](ERROR-TRACE.md).

Created 2026-11-23 so any session can navigate the engine code without re-parsing 191 MB files. Everything here was verified by reading the actual files.

## The two codebases

| Codebase | File | Size | What it is |
|---|---|---|---|
| **RAGE engine** (C++ compiled to wasm) | `E:\Malik\game\game.dcmp` (WABT wasm-decompile pseudo-C) | 191 MB, 91,008 named functions | The game engine itself. Read it to understand settings, LOD, draw generation, AI, network, etc. |
| **JS driver** (our code) | `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js` | ~197 KB, ~3,038 lines, 163 functions | Translates engine commands (shared ring) into WebGPU calls. This is the "driver" the engine waits on. |

Other engine artifacts: `game.wat` (591 MB WAT, editable), `game-objdump.txt` (70 MB section/function listing), `game.wasm` (63 MB binary, hash `11CA8D2C…` known-good). WABT 1.0.41 at `C:\Users\HP\AppData\Local\Temp\opencode\wabt-1.0.41\bin\`.

## File index in this folder

| File | Contents |
|---|---|
| `engine-function-index.tsv` | All 91,008 engine functions: `name<TAB>line<TAB>funcidx`. Grep this to find any function's location in `game.dcmp`. |
| `engine-subsystem-counts.txt` | Function counts grouped by subsystem prefix (network 1865, vehicle 1606, graphics 884, etc.). |
| `driver-wgpu-worker-functions.md` | All 163 `wgpu_worker.js` functions with line + params. |
| `key-call-chains.md` | The LOD / draw / settings call chains discovered in the reverse-engineering work, with exact addresses. |
| `wire-profile.md` | Per-frame WebGPU call counts (the design-gap evidence). |
| `driver-understanding.md` | How the driver works: ring protocol, main loop, command dispatch, state model, doDraw hot path, uniform ring - read before editing wgpu_worker.js |
| `draw-pipeline-understanding.md` | Engine draw/render pipeline actually read from game.dcmp: D3D11 vtable chain, draw-list system, LOD globals (23318984L, 19446852L) |
| `bulk-analysis-10000.md` | Programmatic analysis of 10,000 render/LOD/streaming functions: stubs, vtable trampolines, hot functions, global-write counts |
| `bulk-analysis-10000-batch2.md` | Batch 2: 10,000 gameplay/network/ped/vehicle functions — stubs, vtable, globals |
| `verified-30000-summary.md` + `verified-30000-lines.txt` | 30,280 complete function bodies from dcmp lines 5,001,192-5,054,474, SHA256 verified |
| `semantic-analysis-region1.md` | Semantic decode of the verified 30k region: vehicle/ped TASK AI (exit vehicle, hull pathfinding, move networks) |
| `semantic-304-functions.md` + `deep-reads-region1.md` | Semantic map of all 304 functions (calls/globals/roles) + opcode-level deep reads of the big ones |
| `semantic-analysis-old-batches.md` | Semantic decode of the earlier 20k batches: null-D3D scaffolding, draw-list replay, reflection/networking/PTX effects |
| `semantic-draw-generation.md` | Draw-generation chain: D3D11 vtable trampolines (slots 12/13/20/39/40), grcDevice draws, indirect-draw lead |
| `indirect-draw-lead.md` | Indirect-draw investigation: path unused by RAGE for bulk draws — dead end, D3D11 vtable slot reference |
| `web-research-runtime-patching.md` | Web research (MDN/spec): JS can write wasm memory/table on Chrome — confirmed + stale-view/torn-value caveats |
| `runtime-lod-write-result.md` | JS runtime LOD write: mechanism PROVEN on Chrome (log confirmed), no gain at 1.0; loader param whitelist gotcha |
| `web-research-multithread-webgpu.md` | Multi-worker WebGPU DEAD on Chrome (GPUDevice not transferable); render bundles are the only untried WebGPU-level idea |
| `web-research-alt-launch.md` | Native Node/Dawn launch research: faster than browser but needs missing shader package + display path |
| `native-node-dawn-feasibility.md` | Native Node/Dawn: webgpu npm INSTALLED + adapter/device VERIFIED; harness missing (no launcher/display) |

## How to use
- **Find an engine function:** `grep -i "functionname" engine-function-index.tsv` → gives `game.dcmp` line → read that line range with Python/Select-String (file is 191 MB, do NOT open whole in editor).
- **Find a driver function:** grep `driver-wgpu-worker-functions.md`, then read that line in `wgpu_worker.js`.
- **Decompile commands:** `wasm-decompile --enable-all --ignore-custom-section-errors game-copy.wasm -o game.dcmp` (already done; files exist).

## Critical rules (from the RE work)
- Do NOT patch the wasm via `wasm2wat → edit → wat2wasm` — Chrome rejects the re-encoding (`import kind 127`). Original hash `11CA8D2C…` is the known-good fallback.
- Driver patches are plain JS (node --check + live-load verify). Wire profiler backup: `wgpu_worker.js.bak-wireprof-20261123`.
- Always verify Chrome gets past 20% → "world shown" before keeping any patched binary.
