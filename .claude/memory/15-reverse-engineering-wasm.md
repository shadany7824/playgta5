# 15 — Wasm reverse engineering (RAGE engine inside game.wasm) — consolidated memory

**Project:** `E:\gta\playgta5` — local GTA V browser port (Emscripten wasm + WebGPU).
**Created:** 2026-11-21. **Owner ask:** one more memory MD folder/file for reverse engineering the Wasm code.

## Honest answer first (the "91k" question)
- The real binary the browser loads: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm` — **63,201,802 bytes**.
- The wasm keeps a **`name` section with 41,244 `rage::` / `C*` symbols**, and the decompiled code section (`game.dcmp`) has **91,008 named functions**.
- So the "**91k code**" = the **RAGE engine functions inside the Wasm module** — the C++-level engine logic (draw generation, LOD, settings) the JS/WebGPU worker calls via `call_indirect` vtable slots.

## Files we already have (verified 2026-11-23)
| File | What it is |
|---|---|
| `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm` | REAL game binary the browser loads (63,201,802 bytes). Back it up before touching it |
| `E:\Malik\game\game-copy.wasm` | Safe copy to work on |
| `E:\Malik\game\game.dcmp` | 191 MB pseudo-C, the "engine code" to READ; **91,008 named functions** |
| `E:\Malik\game\game.wat` | 591 MB WAT text, the code to EDIT and recompile |
| `E:\Malik\game\game-objdump.txt` | 70 MB section/function/import/export listing |
| `C:\Users\HP\AppData\Local\Temp\opencode\wabt-1.0.41\bin\` | WABT tools: wasm2wat, wat2wasm, wasm-decompile, wasm2c, wasm-objdump, wasm-validate |

## Where to look in the code
- WAT round-trip: `wasm2wat --enable-all game-copy.wasm -o game.wat` → edit WAT → `wat2wasm --enable-all game-patched.wat -o game-patched.wasm` → `wasm-validate --enable-all game-patched.wasm`.
- One function: `grep -n "func \$CTimeCycle_ApplyLodScaleModifiers" game.wat` ; dump: `awk '/^function CTimeCycle_ApplyLodScaleModifiers\(/{p=1} p{print; if(/^}/) exit}' game.dcmp`.
- Vtable calls: `call_indirect(..., a.a[12])` = C++ virtual call (vtable slot 12). `19446816L[0]` = global C++ object at that linear-memory address.

## Proven patch method (for FPS)
- Do NOT no-op draws (18 broke the image).
- Lower LOD scale / draw distance via `CTimeCycle_ApplyLodScaleModifiers`, `CLodScale_*`, `CLodMgr_OverrideLodDist`, etc. Baseline ~2,400 draws at ~8-9 FPS true 1080p.

## Research dead-ends
- WAT round-trip feasible in principle, but 591 MB / 91,026 functions + Memory64 + shared memory + 89k table entries → high-risk rebuild.
- `__indirect_function_table` hook (89,367 entries) via JS `table.get/set` — cleanest hook point but needs the right index + no-op breaks rendering.
- BREWasm / SCRIBE — research-grade.
- wasm2c / Ghidra / NotDec — readable equivalent C, NOT the original.

## Do not
- Do not expect/promise original RAGE C++ source. It does not exist in the binary.
- Do not load PoC patches (`game-patched.wasm` GetGameFrame=0, `game-nodraw.wasm`) for play.
- Do not upload wasm/decompilers output online. Keep local, personal modding only.

## Cross-links
- Core mistakes: U17 (frontend events), U22 (untested tuning), U24 (detached), U05 (stale version).
- Project memory: `E:\gta\playgta5\.claude\memory\` and `C:\Users\HP\.claude\architectures\playgta5.md`.

## Latest session progress (2026-11-21/22 — this thread)
- Goal: **~30 FPS at true 1080p** (best verified true-1080p ≈ **8.6–9.8 FPS** → need ~3.4x). Engine draw wall (~2,000–2,800 draws/frame) is why we're in the Wasm RE.
- Backups: `E:\Malik\game\game.wasm.bak-20261123` (63,201,802), `E:\Malik\game\game-lod.bak-20261121` (591,424,118).
- Patch base: `E:\Malik\game\game-lod.wat` → compiled → `E:\Malik\game\game-lod-patched.wasm` ✅ (wat2wasm ✅ / wasm-validate ✅).
- Lod fn located: line **15649355** (`$CTimeCycle::ApplyLodScaleModifiers_rage::tcKeyframeUncompressed&_`); LOD scale const: line **15649453** (`f32.const 0x1p+0` = `1.0`); LOD Apply call: **15649458`.
- Bad edit attempt broke the WAT (inserted literal `\r?\n` instead of real newlines) → `wat2wasm` exit 1 → **restored from `game-lod.bak-20261121` → recompiled clean ✅**.
- Next: apply LOD fix (`1.0` → `0.5`) in `game-lod.wat` → recompile → re-validate → swap into mirror + bump loader version → A/B → measure.

## ⚠️ CRITICAL FINDING (2026-11-23) — WAT round-trip patch FAILS to load in Chrome
- Applied the LOD patch (line 15649453 `0x1p+0`→`0x1p-1` = scale 1.0→0.5) with a line-number-based edit. `wat2wasm --enable-all` ✅ exit 0, `wasm-validate --enable-all` ✅ exit 0, sections/imports/type-count IDENTICAL to original on `wasm-objdump`.
- Swapped patched wasm into mirror (backup `E:\Malik\game\game.wasm.bak-lodswap-20261123`, hash `11CA8D2C…`).
- **RESULT: game hung at 20% "Downloading and compiling the engine (60 MB)" for 277+ s. Browser console error: `import kind 127`.** WABT accepts the binary but Chrome 158's WebAssembly validator does NOT — the round-trip re-encoding of the Memory64 + shared + 89k-table module produces a binary Chrome rejects.
- **Action taken:** restored mirror `game.wasm` from `game.wasm.bak-lodswap-20261123` → hash `11CA8D2C…` confirmed = original. Game loads normally again.
- **RULE — do NOT use `wasm2wat → edit WAT → wat2wasm` as a patch path for `game.wasm` on this machine.** WABT exit-0 + wasm-validate is NOT sufficient proof; must verify Chrome actually compiles it (page passes 20% → world shown) before keeping any patched wasm. Always keep the original hash `11CA8D2C…` as the known-good fallback.
- Next real patch path to try (NOT yet done): runtime `__indirect_function_table` hook via JS `table.get/set` (no wasm recompile), or binary-level byte patch of the single f32 constant directly in `game.wasm` (no WAT round-trip) — both still need the same Chrome live-load verification.

## FPS check 2026-11-23 (restored original wasm)
- Launched via WMI (Chrome PID 10156, not Play-*.cmd which kills opencode) with URL `?low=0&res=1920x1080&fps=60&slots=5&log=1&mode=sandbox&args=-textureQuality=1,-shadowQuality=0,-reflectionQuality=0,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=0`.
- Steady-state world FPS: **~5.3–6.6 FPS** in this sandbox scene, ~2,200–2,330 draws/frame, worker busy 72–85% (~125–147 ms/frame). Title screen 33–46 FPS (12 draws). Lower than memory's ~8.6–9.8 because of the specific sandbox scene + draw count.
- Confirms: 30 FPS needs the engine draw count cut; config alone cannot.

## FPS "deducted" investigation 2026-11-23 (root cause: scene draw count, NOT a regression)
- Owner said FPS dropped. Proved via logs + live state: original wasm hash `11CA8D2C…` in place; only ONE server (PID 8760 via watcher), ONE watcher, ONE game tab; no duplicates.
- The "fast" 51/45/33 FPS lines were TITLE SCREEN at only 12–17 draws/frame, not gameplay.
- In-game steady-state: ~5–7.6 FPS at ~2,200–2,860 draws/frame, GPU process 372 CPU-s, worker busy 72–85% — the known engine draw wall. Consistent with memory baseline (true-1080p max 5.6 FPS @ 2,743 draws). The ~8.6–9.8 figure was a lighter scene (~2,000 draws). Nothing broken; scene draw count differs.
- Playable today: low mode `?low=1&res=1024x576&fps=30&slots=5` (30 FPS) or Play-Final.cmd (~16 FPS upscaled). 30 at true 1080p still needs engine draw cut.

## ✅ CONFIRMED WIN 2026-11-23: `-lodScale=1` gives ~25% more FPS (no patch!)
- Deep vtable research found: `CSettingsManager_GetSettings(...)[7]:float` = sysParam at wasm address `19446852`; `CTimeCycle_ApplyLodScaleModifiers` applies `1.0 - lodScale`. `-lodScale=0` → modifier 1.0 (full LOD); `-lodScale=1` → modifier 0 (max LOD/draw reduction). The `lodScale` sysParam string exists in the wasm (`50368472`).
- A/B (same scene, last 40 world frames each): `lodScale=0` avg **6.97 FPS** (1.8–9.4, avg 2938 draws) → `lodScale=1` avg **8.74 FPS** (6.8–10.1, avg 2772 draws) = **+25.5%**. Min FPS 1.8→6.8 (fewer heavy stalls). Confirmed by controlled log comparison.
- Best MAX URL so far: `?low=0&res=1920x1080&fps=60&slots=5&log=1&mode=sandbox&args=-textureQuality=1,-shadowQuality=0,-reflectionQuality=0,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=1`.
- **Rule: always use `-lodScale=1` for true-MAX runs** — it is the best verified config, beats the old default `-lodScale=0` from index.html LOW_ARGS.

## Step 5 `-numCores=3` test (2026-11-23) — NO GAIN
- A/B with same URL + `-numCores=3`: `usingCores` stayed **4** (arg did NOT take effect — index.html only adds `-numCores=` when `cores<=2`, and passing via `args=` may not override). FPS avg 7.58 (6.5–8.9, 2778 draws) — no gain vs 8.29 baseline, and arg wasn't applied so test inconclusive. Do not re-run without first proving `usingCores:3` in `[page env]`.

## Vtable research detail (why the runtime hook is hard)
- `__indirect_function_table` IS exported (89,367 entries). LOD Apply fn idx 6406, `CTimeCycle_ApplyLodScaleModifiers` = func 77611, body offset 40,468,290 (1,007 bytes) in the original wasm.
- BUT the LOD function pointer is reached via a C++ vtable in wasm linear memory (`call_indirect(..., (b[0]:long)[vtable_slot])`), NOT a fixed table index — need the vtable slot + object instance. Binary byte-patch also failed: WAT's `f32.const 1.0` is NOT a literal in the binary (WABT folded it), so no 4-byte patch target. Full `wasm-objdump -d` of 91,026 functions takes >15 min (killed).
- Best remaining *code* steps from `1080p-optimization/03`: step 3 (fold clears into `loadOp:'clear'`), step 4c/4d (pipeline MRU, batched VB uploads) — plain `wgpu_worker.js` patches (no wasm recompile, Chrome-safe). Step 2 (depth-proxy WGSL rewrite) medium-high risk.

## FPS-vs-draws proof 2026-11-23 (why FPS "rises then falls")
- Within one session, FPS ranged 6.5–11.8 and draws 1,309–3,430. Correlation FPS↔draws = **-0.899** (strong inverse). Buckets: <1500 draws → 11.39 FPS; 1500–2200 → 10.44; 2200–2800 → 8.71; 2800–4000 → 8.23.
- So "FPS is increasing" = camera moved into a lighter scene (fewer draws), NOT a permanent speedup. Best case now ~11.7 FPS in light scenes with `lodScale=1`; heavy scenes still ~7–8. Confirms draws are the wall; to hold 11+ everywhere, engine draw count must drop in heavy scenes.
- Update (owner reported ~13, verified 2026-11-23): peaks 12.1-13 FPS in light scenes (~600-1,300 draws), session avg ~10, 868/4272 world samples >=12 FPS. Setup DOES touch 12-13 in good areas but not sustained; still short of 15 everywhere.
