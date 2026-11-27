# 24 — SOLUTION: how to reverse engineer game.wasm and get RAGE engine code (2026-11-23)

## Honest answer first
- The **original RAGE C++ source cannot be recovered**. No source map/DWARF exists, and LLVM -O2 erased the structure (see 16).
- What we CAN get: **readable equivalent code for every engine function, with real names**. The wasm keeps a `name` section with 41,244 `rage::`/`C*` symbols. `game.dcmp` has **91,008 named functions**.
- That is enough to read engine logic, find settings/globals, and patch behavior (proven in 17 and 18).

## Files we already have (verified 2026-11-23)
| File | What it is |
|---|---|
| `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm` | REAL game binary the browser loads (63,201,802 bytes). Back it up before touching it |
| `E:\Malik\game\game-copy.wasm` | Safe copy to work on |
| `E:\Malik\game\game.dcmp` | 191 MB pseudo-C, the "engine code" to READ |
| `E:\Malik\game\game.wat` | 591 MB WAT text, the code to EDIT and recompile |
| `E:\Malik\game\game-objdump.txt` | 70 MB section/function/import/export listing |
| `C:\Users\HP\AppData\Local\Temp\opencode\wabt-1.0.41\bin\` | WABT tools: wasm2wat, wat2wasm, wasm-decompile, wasm2c, wasm-objdump, wasm-validate (all present, checked 2026-11-23) |

WABT **1.0.41** is required: 1.0.42 removed `wasm-decompile`. Temp folder can be wiped; re-download from github.com/WebAssembly/wabt/releases and verify the .sha256.

## Step 1 — Decompile (already done; redo only if files are lost)
```
wasm-objdump -x game-copy.wasm > game-objdump.txt
wasm2wat --enable-all game-copy.wasm -o game.wat
wasm-decompile --enable-all --ignore-custom-section-errors game-copy.wasm -o game.dcmp
```
`--enable-all` is mandatory (Memory64 + shared memory + threads + SIMD). Run locally only and never upload the binary online.

## Step 2 — Get the engine code for one system (the practical way)
Never Read the big files whole; grep them.
```bash
# list all functions of a subsystem (LOD, render, peds, vehicles...)
grep -oE "^function [A-Za-z_0-9]*LodScale[A-Za-z_0-9]*" game.dcmp | sort -u
# dump ONE function's code (tested 2026-11-23 on CTimeCycle_ApplyLodScaleModifiers, func77611, line 5128333)
awk '/^function CTimeCycle_ApplyLodScaleModifiers\(/{p=1} p{print; if(/^}/) exit}' game.dcmp
# same function in editable WAT
grep -n "func \$CTimeCycle_ApplyLodScaleModifiers" game.wat
```
Reading tips:
- `19446816L[0]` = a global C++ object at that linear-memory address. `[7]:float` = field at offset 7*4 bytes.
- `call_indirect(..., a.a[12])` = C++ virtual call (vtable slot 12).
- `cxa_guard_acquire` / `cxa_atexit` = C++ static constructor; skip it.
- Example found: `ApplyLodScaleModifiers` reads `CSettingsManager_GetSettings(...)[7]:float` and applies a timecycle LOD modifier with `1.0 - value`. So the LOD scale is driven by a **settings field**, a clean patch target.

Useful subsystems to export into readable per-system files: `CLodScale_*`, `CLodMgr_*`, `CLodDistTweaker_*`, `rage_SDrawDistanceDetails_*`, `CTimeCycle_*`, `CSettingsManager_*`, `RageDirect3DDeviceContext11_*`, `wasm_null_d3d_*`, `rage_grc*`.

## Step 3 — Better readability (optional, all local and free)
1. **Ghidra + nneonneo/ghidra-wasm-plugin**: cross-references (who calls what), struct recovery, renaming. Best tool to *understand* a subsystem.
2. **wasm2c** (WABT): compilable C, 100% behavior-correct but low-level.
3. **NotDec** (github.com/NotDec/NotDec): better types/structs; still equivalent C, not the original.
4. Paste one exported function into Claude and ask for "rewrite as readable C++ with guessed names". This works per function and is good for understanding. It is NOT the real source.

## Step 4 — Patch the engine (proven method)
1. Back up: copy the mirror `game.wasm` to `game.wasm.bak-<name>-<date>`.
2. Edit ONE function body in `game.wat` (copy first, as in game-patched.wat).
3. `wat2wasm --enable-all game-patched.wat -o game-patched.wasm`
4. `wasm-validate --enable-all game-patched.wasm` must exit 0.
5. Copy it into the mirror folder AND bump the loader's wasm URL/version, or Chrome serves the cached original.
6. A/B on the same spot and camera (04-test-protocol). Restore the backup if it is worse.

Alternative without a rebuild: JS hook through the exported `__indirect_function_table` (89,367 entries). `table.get(i)` / `table.set(i, fn)` with an identical signature can wrap or replace virtual calls at runtime.

## Recommended next patch (for FPS)
Do not no-op draws (18 showed it breaks the image). Lower **LOD scale / draw distance** so the engine itself emits fewer draws:
- Targets: `CTimeCycle_ApplyLodScaleModifiers`, `CLodScale_SetGlobalScaleFromScript`, `CLodMgr_OverrideLodDist`, `rage_fwBaseEntityContainer_SetLodDistCached`.
- Idea: force the settings LOD float lower, or multiply the global LOD scale by about 0.5. Then measure draws (baseline ~2,400 draws at ~8-9 FPS true 1080p).

## Do not
- Do not expect or promise "the original RAGE source". It does not exist in the binary.
- Do not load `game-patched.wasm` (GetGameFrame=0 PoC) or `game-nodraw.wasm` for play.
- Do not upload the wasm or outputs to online decompilers.
- Do not share or publish extracted engine code: it is Rockstar's proprietary code. Keep it local for personal modding only.
