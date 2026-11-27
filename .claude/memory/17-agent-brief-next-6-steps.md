# AGENT BRIEF — Node/Dawn harness: next 6 steps (written 2026-11-23)

You are continuing work on the GTA V wasm port running under **Node 24 + native Dawn** (not Chrome).
Detailed file per step: `next-steps\STEP-1..6-*.md` (index `next-steps\README.md`).
Read first: `E:\gta\playgta5\.claude\memory\16-how-solved-mountaudiopacks-and-next-max-plan.md` and `CURRENT-PROBLEM.md`.

## Where things stand (verified)
- The MountAudioPacks crash is SOLVED. `node-webgpu\harness.js` line 102 now passes browser-equivalent args including `-rootdir=/game/`.
- The engine boots, httpfs works (MANIFEST + IO_START fire), all engine threads start, and the wgpu worker runs ~31 FPS with 0 validation errors.
- It now **waits at the loading screen**: log line `[wasm] start mode: waiting for the choice on the loading screen`.

## Paths
- Harness: `E:\gta\playgta5\node-webgpu\` (`harness.js`, `game-node.js`, `worker-boot.js`, `wgpu_wrapper2.js`)
- Node 24: `E:\gta\playgta5\node24\node_modules\node\bin\node.exe`
- Browser reference (the working version): `E:\gta\playgta5\mirror\playgta5.com\index.html`, `b\8b0b5899ed\game.js`, `loader.js`, `wgpu_worker.js`
- Decompile: `E:\Malik\game\game.dcmp` (191 MB; read single functions with awk, never the whole file)
- Diag log file: `node-webgpu\pthread-msg-log.txt` (written by `globalThis.__diag(...)`)

## How to run one test
1. The server must be up: `curl http://localhost:8000/data/manifest.json` → 200. If it's down, start it detached (WMI command in memory `01-server-and-launch.md`).
2. `cd E:\gta\playgta5\node-webgpu` → empty `pthread-msg-log.txt` → run `..\node24\node_modules\node\bin\node.exe harness.js > diag-run-<name>.txt 2>&1`, stopping it after 150-300 s (`timeout` in bash).
3. Afterwards, check that no `node.exe` is left running.

## RULES (non-negotiable)
- **One change per run.** Back up a file before every edit (`<file>.bak-<what>`). Run `node --check` on edited JS.
- **Never say "done/works" without proof from the log or a screenshot.** State what is verified and what is not.
- Before calling anything "blocked": compare with what the browser does, log the real values, and read the decompiled function. No guessing (rule U13).
- After every run, append a new `## Stage N` to `engine-code-map\ERROR-TRACE.md` (change, exact result, file, line) and update the top box of `CURRENT-PROBLEM.md`.
- No git commit/push. Don't touch the mirror files the Chrome launchers use unless a step says so; work on the Node copies.

---

## STEP 1 — Answer the loading-screen choice
**Why it's stuck:** the browser writes the start mode into the engine's input block (`index.html` ~line 511: `startModeWord = new Int32Array(memory.buffer, block + 440, 1); Atomics.store(startModeWord, 0, startMode)`; 1 = Story, 2 = Sandbox, 3 = Sandbox env_test). The engine hands over `block` through `wasm_input_publish_js(block)`. In `game-node.js` that function **returns early on Node** (`if(process.versions.node) return;`), so the choice is never written.
**Do:** in `game-node.js`, change the Node branch of `wasm_input_publish_js` to:
```js
const b=Number(block); globalThis.__inputBlock=b;
Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);
globalThis.__diag&&globalThis.__diag("INPUT block="+b+" startMode=2");
```
(Optional, as a separate run only if needed: FOCUS = 1 → `Atomics.store(new Int32Array(wasmMemory.buffer,b+256,10),6,1)`.)
**Pass:** the log shows `INPUT block=...`, then `start mode: sandbox`, then loading progress, with draws/frame rising well above 12.
**If it fails:** check whether `wasm_input_publish_js` is called at all (diag line). If it isn't, find the caller in game.dcmp (`grep -n "wasm_input_publish_js" game.dcmp`) and see what gates it.

## STEP 2 — Prove real pixels
- Find the screenshot/readback option in the wgpu worker that Node loads: `grep -n "SHOT\|screenshot\|readback" node-webgpu\wgpu_wrapper2.js mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js`. Verified: `WGPU_SHOT_EVERY=<n>` + `WGPU_SHOT_PREFIX=<path>` exist (mirror wgpu_worker.js ~line 2733). The default prefix `D:/wasm_tmp/` does not exist here, so set it.
- If none exists, add a minimal one: every N seconds, copy the presented texture → buffer → `mapAsync` → write a PNG (or raw RGBA + size) to `node-webgpu\shots\`.
- **Pass:** open the image file yourself and describe what's in it (loading screen / world / black). Black or garbage is a FAIL; investigate, don't report success.

## STEP 3 — Fair A/B vs Chrome (the whole point of this harness)
- Chrome baselines from memory 02/09/10/14: low 1024x576 ≈ 30 FPS; best high preset 960x540 shadow 0 / reflection 1 = 16.5-16.8 FPS; true 1080p = 4.4-8 FPS. The Chrome bottleneck is the JS worker / WebGPU wire, with GPU wait 0.
- Run Node with the **same** resolution + args + sandbox scene. Collect 60+ s of `[wgpu] fps:` lines and record FPS, draws/frame, worker busy %, and gpu wait.
- Only compare runs with similar draws/frame. Write a results table to ERROR-TRACE + `02-performance-benchmarks.md`.
- **Answer plainly:** is Node/Dawn faster than Chrome, and by how much? If it is not faster, say so and stop before step 5.

## STEP 4 — Push to MAX, one lever per run
1. Resolution: 960x540 → 1280x720 → 1920x1080 (`-width/-height` in harness.js args, and the wgpu display size).
2. Quality args, adding ONE per run: `-textureQuality=2`, `-shadowQuality=2`, `-reflectionQuality=2`, `-particleQuality=2`, `-grassQuality=2`, `-cityDensity=2`, `-lodScale=2`, `-pedVariety=2`, `-vehicleVariety=2`.
3. `-frameLimit=0` only to measure the ceiling; use 1 (60) or 2 (30) for real play.
- Record FPS for every run. Never label a low-setting number as "max" (U23). Hardware: i3-7100U 2C/4T + Intel HD 620. If gpu wait > 0, the GPU is the limit and no software lever remains; say so.

## STEP 5 — Make it playable (ONLY if step 3 showed a real gain)
- Node has no window, input or audio. Research and pick ONE route, then prove it:
  a) a native window/surface from the `webgpu` npm package (check whether the installed version supports one);
  b) read frames back and stream them to a local browser page (measure the added latency; it may eat the gain);
  c) input: write keys/mouse into the input block (`globalThis.__inputBlock`; layout: 256 key bytes, then int32 mouseX, mouseY, dX, dY, dZ, buttons, focus, locked, textHead, textTail; see the comment at `index.html` ~line 189).
- Audio: the engine runs a "Headless mixer"; see `wasm_audio_publish_js` in game.js for how the browser gets audio.
- Ask the owner before building a big piece here.

## STEP 6 — Clean-up and documentation
- Remove the `PATH openat/stat64` diag lines from `game-node.js` (or gate them behind `process.env.PATH_DIAG`). The backup without them is `game-node.js.bak-pathdiag`.
- Create a launcher `E:\gta\playgta5\Play-Node-Dawn.cmd` with the final working command, and test that it starts.
- Update `~/.claude/architectures/playgta5.md` (Node/Dawn path, files, args) and memory `README.md`.

## Report format back to the owner (after each step)
Step N → what changed (file:line) → exact result from the log/screenshot → verified / not verified → next step.
