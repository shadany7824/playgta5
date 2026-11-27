# 09 — How to decompile the game wasm (web research 2026-11-21)

## Format
`game.wasm` = WebAssembly binary (Emscripten/wasm64 shared memory + threads). No DWARF/source maps; only a 6.8 MB `name` custom section with 41,244 `rage::` symbols. Decompilation yields WAT or pseudo-C, **not original C++ source**.

## Tools (local, recommended)
- **WABT** (reference toolkit): `wasm-objdump -x`, `wasm2wat`, `wasm-decompile`, `wasm2c`. Docs: webassembly.github.io/wabt/doc/{wasm2wat,wasm-decompile,wasm-objdump}.1.html; repo github.com/WebAssembly/wabt.
- **JEB Decompiler** (commercial): wasm plugin produces C-like pseudo-code; supports wasm 3.0, SIMD, multi-memory/tables from 5.36; no code patching. pnfsoftware.com/jeb/manual/webassembly.
- **Ghidra** WASM plugin (free), **diswasm** (higher-level pseudocode), **wasmdec** (older, WASM→C), **wasm-tools print**, **Binaryen wasm-dis / wasm-opt** (simplify before decompile).

## Commands for this file (Windows)
File: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm`

```
wasm-objdump -x game.wasm
wasm2wat --enable-all game.wasm -o game.wat
wasm-decompile --enable-all --ignore-custom-section-errors game.wasm -o game.dcmp
```
`--enable-all` covers Memory64 + threads + SIMD; `--generate-names` helps if names were stripped (not needed here). Output will be huge: 48 MB code section → WAT/dcmp can be hundreds of MB+. Use `wasm-objdump -x/-d` and symbol names from `snapshot/engine-evidence.json` to target individual functions instead of reading everything.

## Install on Windows
- Download prebuilt WABT zip from github.com/WebAssembly/wabt/releases, or `npm install -g wabt` (Node/npm available here), then `wasm2wat --version`.
- Avoid public online decompilers: 63 MB proprietary game binary and its output should stay local.

## Limits
LLVM/O2 optimized wasm has lost original structure; wasm-decompile output is low-level pseudo-C and cannot be compiled back to wasm. Even with symbols, you cannot recover readable RAGE `.cpp` or safely patch engine draw generation.
