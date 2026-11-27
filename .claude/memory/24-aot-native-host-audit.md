# 24 — AOT native host: audit logging in every function (2026-11-26)

## Rule (owner request, 2026-11-26)
When the game moves from the Node JS bootstrap to the WAMR AOT C++ host,
**every function in the new host must log its own entry and exit** to
`E:\gta\_tmp_claude\native-host-audit.log`, including the real arguments and
the real return value. No function is "too small" to log. This is how we
audit a crash without guessing (lessons 05, 10, 27, 31).

## Why
The host registers ~85 wasm imports and calls into a 91k-function engine.
A silent import stub means "never called" could be a broken logger OR a
different engine branch (lesson 09/10). A per-function log with a shared tag
lets us diff both sides of the wasm→C++ boundary (lesson 31) and see exactly
which import broke the run.

## Implementation in this project
- File: `E:\gta\playgta5\node-webgpu\native\gta_aot_host.cpp`
- Generated from the REAL wasm import table: `E:\gta\_tmp_claude\gen_host.py`
  reads `E:\Malik\game\game-lodlive-fixed2.wasm` (type + import sections),
  so signatures and names cannot drift from the binary.
- Log helper: `AUDIT_ENTER(fn, ...)` / `AUDIT_EXIT(fn, ...)` write
  `[time tid] ENTER fn args...` / `EXIT fn ret=...` to the audit log file.
- Canary (lesson 10): `main()` writes `CANARY audit-alive` before loading;
  an empty log means the logger is broken, not that functions were not called.
- Imports are registered with `wasm_runtime_register_natives_raw(..., NULL
  signature)` so memory64 i64 pointers are NOT rewritten by WAMR's i32
  pointer logic (`wasm_native.c:134` rejects `*` for i64 params). Stubs read
  raw `uint64_t* args` and convert app→native addresses only when needed.

## Pass checks
- `gta_aot_host.exe` starts, audit log has `CANARY audit-alive` then
  `ENTER main`, and the module load either reports success or the exact error.
- For each import actually called: `ENTER <name>` and `EXIT <name>` with
  matching argument values on both sides.
- On a crash: the last `ENTER` line with no matching `EXIT` names the function.

## Status
- Host code generated/instrumented 2026-11-26. AOT compile of
  `gta-sl1-opt1.aot` still in progress when this was written.
