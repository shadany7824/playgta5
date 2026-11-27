# 14 — WASM decompiled locally (2026-11-21)

## What was done (no online upload, original untouched)
- Copied `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm` (63,201,802 bytes) to `C:\Users\HP\AppData\Local\Temp\opencode\game-copy.wasm`.
- WABT 1.0.41 Windows x64 downloaded from GitHub releases, SHA-256 verified against release `.sha256`, extracted to `...\Temp\opencode\wabt-1.0.41\bin`.
  - WABT 1.0.42 removed `wasm-decompile`, so 1.0.41 is the last release with it.
- Commands:
  - `wasm-objdump -x game-copy.wasm` → `game-objdump8.txt` (69.9 MB), 0 errors.
  - `wasm2wat --enable-all game-copy.wasm -o game.wat` → `game.wat` (591 MB), 0 errors.
  - `wasm-decompile --enable-all --ignore-custom-section-errors game-copy.wasm -o game.dcmp` → `game.dcmp` (191 MB), 0 errors.

## Confirmed from the outputs
- Module: `wasm 0x1`, module name `<game.wasm>`.
- Imported memory: `memory[0] pages: initial=49152 max=262144 shared i64 <- env.memory` = 3 GiB initial / 16 GiB max, Memory64, shared.
- Sections: Import[86], Function[91026], Table[1], Global[57], Export[22], Code[91026], Data[4077].
- Decompiled pseudo-C has real symbol names, e.g. `function rage_CheckpointSystemMemory(a:long, b:int) { // func108 }` and `function RageDirect3DDeviceContext11_DrawIndexed(...) { a = a.b; call_indirect(...); }`.

## Verdict (as expected)
The output is low-level pseudo-C / WAT, not original C++ source. Draw functions are thin vtable thunks (`call_indirect`), so there is no readable "engine draw generation" logic to edit. Useful only for inspecting a specific function; cannot restore `.cpp` or safely rewrite the engine.

Output files are in temp (large). Use Grep, never Read whole files. Duplicate copy + outputs also created in `E:\Malik\game\` (`game-copy.wasm`, `game-objdump.txt`, `game.wat`, `game.dcmp`) on owner request; all 0 errors.
