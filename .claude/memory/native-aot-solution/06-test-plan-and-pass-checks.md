# 06 — Test plan and pass checks (one change per run)

| Run | Change | Pass check | Log |
|---|---|---|---|
| R0 | none (baseline with the file 03 global dumps added) | Crash reproduces at `main+0x4fc`; dumps printed at all checkpoints | Stage: "AOT TLS dump" with a table of values per checkpoint |
| R0-JS | file 03 JS wrappers | `JS TLS_INIT ret=<v>` printed; wrapper-ran canary present | same Stage, JS column |
| R1 | file 04 (TLS init inside the import, early init removed) | `tls_base` in host = JS value; no OOB at main+0x4fc; next import `wasm_module_js("keepThreads")` | Stage: "AOT init order = JS" |
| R2 | file 05 §1 `GTA_AOT_NO_FORCELOAD=1` | manifest fetched by the engine itself; same or later progress than R1 | Stage |
| R3 | file 05 §2 `gta_lod_cutoff=50` | value read back = 50 | Stage |
| R4 | file 05 §3 i64 arg fix (only if proven needed) | audit args equal JS args for 3 sample imports | Stage |

## Always
- Fresh build proof: log the host build time/version string at startup (lesson U05: prove the new code runs). Note that the audit log starts with `CANARY audit-alive aot-host-v1`, so bump that tag (`-v2`, `-v3`) with every change, so old logs can't be mistaken for new ones.
- Empty the audit log before each run.
- Keep the JS harness working: don't edit shared files the JS path uses, except `game-node.js` for the R0-JS wrapper (backup, and remove it after).

## Report per run (to the owner)
Run → change (file:line) → audit-log evidence (exact lines) → verified / not verified → next run.

## Done for this blocker
Main passes `main+0x4fc`, and the host's import sequence after seq 206 matches the JS reference (`keepThreads` → thread creation → `openat ./this.cmp`). Update `native-aot-current-problem/CURRENT-PROBLEM.md` and the project `CURRENT-PROBLEM.md` top box, and mark the "WAMR GOT relocation" next-step as **retracted** (lesson 28).
