# STEP 6 — Clean-up, launcher, documentation

## Goal
Leave the project so the owner (or any future session) can start the Node/Dawn path with one double-click, understand every patch, and undo any patch. Do this step even if STEP 3 said "no gain": the investigation must still be documented and the diagnostics cleaned up.

## Part A — Remove or gate the diagnostics
These were added while debugging and slow down every run:
1. **PATH diag** in `node-webgpu\game-node.js`, inside `___syscall_openat` and `___syscall_stat64`:
   `globalThis.__diag&&globalThis.__diag("PATH openat "+path);` (and the `stat64` one).
   They write one line per file open (thousands). Either remove them, or wrap them as `process.env.PATH_DIAG&&globalThis.__diag&&...`.
   Backup without them (from before STEP 1): `game-node.js.bak-pathdiag`. **Don't just restore that backup**: it doesn't have the STEP 1 input fix. Edit in place.
2. **MANIFEST / IO_START / HAS_PAGE / MODULE_INT diag** lines (added in Stage 15): gate them behind `process.env.HTTPFS_DIAG` the same way.
3. **`wgpu_wrapper2.js`** logs every message to `wgpu-wrapper-log.txt`. Gate it behind `process.env.WRAP_DIAG`.
4. `harness.js` `globalThis.__diag` writes to `pthread-msg-log.txt`. Leave it (it's cheap if nothing calls it).
5. After the edits: `node --check` on every changed file, then one full run to confirm nothing broke (the world still loads, FPS same or better).

## Part B — Tidy the folder (without deleting history)
- `node-webgpu\` has ~100 throwaway scripts (`fix*.py`, `check*.py`, `dbg*.js`, `testmem*.js`, ...). **Don't delete them yet.** Move them into `node-webgpu\_history\` and list the move in the ERROR-TRACE stage. Ask the owner before deleting anything.
- Keep at the top level: `harness.js`, `worker-boot.js`, `game-node.js`, `wgpu_wrapper2.js`, `package.json`, `node_modules`, `opfs-store`, `shots`, and the `*.bak-*` backups.
- `objdump.txt` (141 MB): keep, but note in the README that it's a header/sections dump only. Disassembly lives in `E:\Malik\game\game.wat` / `game.dcmp`.

## Part C — One-click launcher
Create `E:\gta\playgta5\Play-Node-Dawn.cmd`:
1. Check the server on :8000 (`curl -s -o nul -w "%{http_code}" http://localhost:8000/data/manifest.json`). If it isn't 200, start it **detached** with the WMI method from memory `01-server-and-launch.md` (a normal `start` dies with the shell: mistake U24). Wait until it answers.
2. `cd /d E:\gta\playgta5\node-webgpu`
3. Optional preset choice (`Balanced` / `Max` from STEP 4) by setting an env var that harness.js reads for the args (if you add this, keep `-rootdir=/game/` in all presets).
4. Run `..\node24\node_modules\node\bin\node.exe harness.js`, logging to `node-webgpu\last-run.txt`.
5. If STEP 5 made a window/stream page, open it.
**Test the launcher yourself:** double-click equivalent `cmd /c Play-Node-Dawn.cmd`, confirm the world loads (log line + FPS), then close it, and check no `node.exe` / `python.exe` is left over unintentionally.
Don't change or replace the existing Chrome launchers (`Play-Final.cmd` etc.).

## Part D — Documentation (required by the owner's global rules)
1. **Architecture report:** update `C:\Users\HP\.claude\architectures\playgta5.md` (line 2 path is stale: the real folder is `E:\gta\playgta5`). Add a "Node/Dawn native path" section: the files and what each does (harness.js, worker-boot.js shims, game-node.js patches with function names, wgpu_wrapper2.js), the launch args, env vars (`WGPU_*`, `*_DIAG`), the data flow (io worker ↔ httpfs ↔ engine; wgpu worker ↔ Dawn), and the measured results.
2. **Project memory:** update `E:\gta\playgta5\.claude\memory\README.md` (status line + index rows), `CURRENT-PROBLEM.md` (final state), and `ERROR-TRACE.md` (final stage: summary of steps 1-6, with verified vs not verified).
3. **Benchmarks:** make sure `02-performance-benchmarks.md` has the Node rows next to the Chrome rows.
4. **Mistakes:** if any step went wrong and was fixed, log it as a universal rule (`/log-mistake`, `~/.claude/mistakes/`).

## Part E — Final report to the owner
- What works (with proof: log lines, screenshot paths, FPS table).
- What doesn't work / not verified.
- How to launch it, and how to undo every patch (list each `.bak-*` file and which file it restores).
- A recommendation: Node/Dawn or Chrome for daily play, based on the numbers.

## Rules
- No git commit/push (owner's git).
- Verify every claim yourself before reporting (rule U01). Run the launcher, don't assume it works.
