# SOLUTION — Native AOT host crash at `main+0x4fc` (for the code agent)

Problem file: [../native-aot-current-problem/CURRENT-PROBLEM.md](../native-aot-current-problem/CURRENT-PROBLEM.md). Written by Claude 2026-11-27.

## Verdict in one paragraph
The crash is **not** a WAMR AOT "GOT/data relocation" bug. `GOT.data.internal.rage::g_DisableInitNan` is an ordinary **wasm global** that holds the address of a **thread-local** variable. Its value is set at runtime by the game's own `wasm_init_tls()` (func 86) to `tls_base + 720`, and only through the export `_emscripten_tls_init` (func 90693). The C++ host runs the Emscripten thread/TLS init **in a different place and order than the working JS runtime** (before `__wasm_call_ctors`, with the import stub doing nothing). Close that difference, but **measure the actual bad value first** (file 03). Nobody has logged it yet.

## Read in order
| # | File | What |
|---|---|---|
| 01 | [01-verified-facts.md](01-verified-facts.md) | Everything Claude proved today (from the wasm binaries, decompile, JS runtime, WAMR source, host code, audit log) |
| 02 | [02-corrected-diagnosis.md](02-corrected-diagnosis.md) | Why "WAMR GOT relocation" is the wrong frame; ranked hypotheses |
| 03 | [03-measure-first.md](03-measure-first.md) | **Do this first:** dump the wasm globals in the host at 5 checkpoints and the same values in JS, then compare |
| 04 | [04-fix-A-match-js-init-order.md](04-fix-A-match-js-init-order.md) | Main fix: do thread_init + tls_init inside the `_emscripten_init_main_thread_js` import, like JS |
| 05 | [05-other-differences-to-close.md](05-other-differences-to-close.md) | Smaller host-vs-JS differences: forced `Load()`, `gta_lod_cutoff`, the i64 arg combine, the stale name section |
| 06 | [06-test-plan-and-pass-checks.md](06-test-plan-and-pass-checks.md) | Run order, pass checks, what to log in ERROR-TRACE |
| 07 | [07-if-it-still-fails.md](07-if-it-still-fails.md) | Next suspects in order, and when to stop and ask the owner |

## Rules
Lessons `think-like-claude\` apply, especially 04 (diff against the working version), 05 (log real values), 08 (match docs to your exact setup), 19 (one change per run), 26 (two fails → research).
One change per run · backup `gta_aot_host.cpp` and `gen_host.py` before edits (`.bak-<what>-20261127`) · the host is **generated** by `E:\gta\_tmp_claude\gen_host.py`, so fix the generator too, or the next regenerate undoes the fix · temp files on E: (C: is full) · no git.
