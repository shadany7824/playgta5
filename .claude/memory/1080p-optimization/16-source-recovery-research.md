# 16 — Web research: can tools recover source from decompiled output? (2026-11-21)

## Question
Given our `game.dcmp` (pseudo-C), can any tool reconstruct the original GTA V C++ source?

## Research answer: NO tool recovers original source
- WebAssembly design issue #1293 (kripken, Alon Zakai): "impossible to retrieve the original C++ files from the .wasm file (raw bytecode)". Only optional debug info (DWARF/source maps) could help; and even DWARF only maps names/structs, "still very far from original C++" for optimized code.
- Linux Foundation report "WebAssembly for Legal Professionals": wasm-decompile output "does not necessarily resemble the original source code at all" (6-line C → 1800+ lines pseudo-C); "recreate what was originally written" may be impossible; decompiled output should not be relied on as original structure.
- V8 wasm-decompile blog: LLVM heavily optimizes; all data structures become load/store; output is not a real language and cannot be compiled back.
- SecureComm 2024 study (2411.02278): wasm2c = 1000/1000 behavior-correct but low-level/unreadable; wasm-decompile = 649/1000 correct (345 execution discrepancies); Ghidra 818/1000; RetDec 775/1000. Structural similarity to original is poor.

## Tools that improve equivalent-code readability (not original source)
- `wasm2c` (WABT): compilable C, low-level goto/pointer arithmetic.
- Ghidra + `nneonneo/ghidra-wasm-plugin`: disassembly/decompilation with xrefs, C stack recovery.
- `wwwg/wasmdec` (unmaintained), `w2c2`, `wwwg/wasmdec`.
- NotDec (ICSE 2026, github.com/NotDec/NotDec): SSA IR + inter-procedural type recovery; 100% recompile, 85.33% struct member recovery; still equivalent C, not original C++.
- WaDec (LLM-based): 52.11% directly re-compilable, average code similarity >50% — still not original.
- Source maps with `sourcesContent` would embed actual source text, but our wasm has only a name custom section, no source map/DWARF.

## Verdict
We can only inspect behavior or write equivalent C. Original RAGE `.cpp` is unrecoverable, and none of this helps FPS (bottleneck is draw count in the JS worker).
