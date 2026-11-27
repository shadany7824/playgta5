# 20 — Back up before every edit, and write down the way back

## The lesson
Before you change a file, copy it with a clear name. After the change, write in memory **which backup restores which state**. A fix you can't undo is a risk; a fix with a known way back is an experiment.

## What happened here
This project survives because every patch has a backup:
- `harness.js.bak-rootdir` (before the launch-args fix)
- `game-node.js.bak-pathdiag` (before the PATH diagnostics)
- `worker-boot.js.bak-onmsgfix` (before the message-bridge fix)
- `wgpu_worker.js.bak-20261120`, `.bak-real-20261120`, `.bak-upscale-20261120` (shader and upscale patches)
- `.bak-lodpatch-20261123`, `.bak-wireprof-20261123`, `.bak-depthview-20261123` (experiments, reverted from these)
A trap that was written down: **don't restore `game-node.js.bak-pathdiag` blindly**. It was made before the start-menu fix, so restoring it would remove a working fix. Backups capture a moment; you must know which moment.

## How to apply
- Name: `<file>.bak-<what>-<date>`. Never overwrite an older backup.
- Make the backup **in the same step** as the edit, not "later".
- In the stage log, write: "restore = copy X over Y" and what that would undo.
- Prefer reversible switches for risky features: env flags (`WGPU_FLATTEN_SWIZZLE=0`, `WGPU_NATIVE_DRIVER=0`), so turning it off needs no edit.
- Big binaries (wasm): patch a **copy** (`game-patched.wasm`) and point the config at it. The original stays untouched.

## One-line rule
**No backup, no edit. No written way back, no experiment.**
