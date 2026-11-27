# STEP 2 — Prove real pixels (screenshot from the Node/Dawn run)

## Goal
Show with an actual image file that Dawn renders the GTA V world correctly under Node. FPS numbers alone do not prove rendering: a black screen can run at 30 FPS.

## Precondition
STEP 1 passed: the log shows `start mode: sandbox` and draws/frame well above 12.

## What already exists (verified in code 2026-11-23)
Node loads the mirror GPU worker through the wrapper:
`node-webgpu\wgpu_wrapper2.js` → `require('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js')`.

That worker already has a **built-in screenshot feature for Node**:
- Line ~2733: `let shotEvery = isNode ? +(process.env.WGPU_SHOT_EVERY || 0) : 0;`
- Line ~2734: `const shotPrefix = isNode ? (process.env.WGPU_SHOT_PREFIX || 'D:/wasm_tmp/shot_') : 'present';`
- Line ~2761 comment: `WGPU_SHOT_EVERY=<n> WGPU_SHOT_PREFIX=<path prefix>` writes `<prefix><presentNumber>.png` every n-th present.
- Line ~2602: on Node it writes a PNG with its own `encodePng(w, h, out)` (no extra package needed).
- Line ~2855: on each shot it also calls `dumpFrameStats()` (render targets + pipelines used that frame), which is useful for debugging a black image.

**Danger:** the default prefix `D:/wasm_tmp/shot_` is the original developer's folder and does NOT exist on this machine. You must set the prefix.

Note: this mirror `wgpu_worker.js` contains the owner's patches (custom WGSL shader, GPU upscale; memory 12/13/14). The Chrome launchers use the same file. **Do not edit it in this step.** Env vars are enough.

## How to set the env vars
`harness.js` starts the wgpu worker with `env: process.env`, so set them before starting node:
```
cd E:\gta\playgta5\node-webgpu
mkdir shots
set WGPU_SHOT_EVERY=300
set WGPU_SHOT_PREFIX=E:/gta/playgta5/node-webgpu/shots/shot_
timeout 300 ..\node24\node_modules\node\bin\node.exe harness.js > diag-run-step2.txt 2>&1
```
Bash: `WGPU_SHOT_EVERY=300 WGPU_SHOT_PREFIX=E:/gta/playgta5/node-webgpu/shots/shot_ timeout 300 ../node24/node_modules/node/bin/node.exe harness.js > diag-run-step2.txt 2>&1`
At ~30 FPS, 300 = one shot every ~10 s. If harness.js overwrites `process.env` values at the top (it sets `WGPU_NODE_MODULE`, `WGPU_SHADER_DIR`, `WGPU_WORKER`), confirm it doesn't touch `WGPU_SHOT_*`.

## Pass checks
1. PNG files appear in `node-webgpu\shots\`, with a non-trivial size (a black PNG compresses to a few KB; a real frame is usually 100 KB+).
2. **Open the newest PNGs yourself** (an image-reading tool) and describe them: loading screen, sky, roads, buildings, character?
3. Compare with Chrome at the same settings: run `Play-Final.cmd` or the low URL from memory `01` and take a Chrome screenshot of a similar moment. Colors and geometry should look like the same game.

## If the image is black / garbage
- Black but draws > 0: check the `dumpFrameStats()` output in the log. Which render targets were written? Is the presented texture the final one? Try `WGPU_SHOT_ALLRT` handling (line ~1976 dumps up to 24 render targets) to find the RT that holds the world.
- Garbage/stripes: probably a format or row-pitch problem in readback. Check `bytesPerRow` alignment (256) in `screenshot()`.
- No files at all: the prefix folder is wrong, or `isNode` is false inside the worker. Log `isNode` once at worker start.
- Any Dawn crash (earlier sessions saw `0xC0000409`): record the exact exit code and the last log lines. Try `WGPU_DAWN_FLAGS` (exists in the worker) only after reading how it's parsed.

## Don't
- Don't report "renders correctly" without opening an image.
- Don't leave `WGPU_SHOT_EVERY` on for the FPS tests in STEP 3. Readbacks cost time and skew FPS.

## Log it
Add `## Stage 18` to ERROR-TRACE.md with the PNG paths, sizes, what each image shows, and the settings used. Copy the best image path into `CURRENT-PROBLEM.md`.
