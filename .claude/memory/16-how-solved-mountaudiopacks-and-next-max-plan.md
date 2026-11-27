# 16 — How the MountAudioPacks blocker was solved + the plan to MAX (2026-11-23)

Status: **SOLVED.** The Node 24 + native Dawn harness now boots to the loading screen. Proof: `node-webgpu\diag-run-rootdir.txt`.
Cross-links: [CURRENT-PROBLEM.md](CURRENT-PROBLEM.md), [engine-code-map/ERROR-TRACE.md](engine-code-map/ERROR-TRACE.md) (Stages 13-16), core rule `~/.claude/mistakes/U13`.

---

## PART A — How it was solved (method, so it can be repeated)

### A1. Distrust the saved verdict, then check it against raw logs
- Memory said "HARD BLOCKER: std::call_once unsupported, rebuild the wasm".
- Checked 3 things: (1) the Emscripten doc was about *Wasm Workers*, but this game is a *pthreads* build; (2) the same wasm works in Chrome; (3) the real trap stack in `pthread-msg-log.txt` was `operator new` inside a `Load()` **we** force-called. All three said the verdict was wrong.
- Lesson: a forced call from JS outside the normal flow is never root-cause evidence.

### A2. Stage 15 then said "the gate is inside the wasm". That was a guess too.
- The diagnostics themselves were OK: `MODULE_INT` lines printed, so `__diag` works on the main thread, and `MANIFEST` really was never called.
- But "never called" does not mean the cause is in the wasm. The question to ask was: **what file path is the engine trying to open?**

### A3. Read the crash site in the decompile (`E:\Malik\game\game.dcmp`, 191 MB)
- `awk 'NR>=4333012{print; if(/^}/) exit}' game.dcmp` → `CFileMgr_MountAudioPacks`. Every `unreachable` comes right after a failed `rage_fiPackfile_Init(...)` + `rage_diagErrorf(..., 3128086)`.
- `rage_fiDeviceLocal_Open` (line 296643): httpfs is used **only if** the path starts with magic `1835099951` / `12133`. Decode it:
  `python -c "import struct;print(struct.pack('<I',1835099951),struct.pack('<H',12133))"` → `/gam` `e/` → the prefix **`/game/`**. Any other path → plain libc `open()`.
- String addresses: the data segments are **passive** (pthreads build). Rodata = segment 0, loaded at **base 1024**. So text at address A sits at file offset `seg0_start + A - 1024`. Parser script: `scratchpad/seg.py` (temporary; rewrite if needed). Decoded:
  `3128086` = "Unable to find critical archive '%s'", `1504422` = "%ssfx/%s.rpf", `3123153` = "audio:/", `3122485` = "E:/P1/gta5/build/dev_ng/", `3122734` = "/game/".

### A4. One runtime log proved it (the decisive step)
- Added one diag line after `path=SYSCALLS.getStr(...)` in `___syscall_openat` and `___syscall_stat64` in `game-node.js` (backup without it: `game-node.js.bak-pathdiag`):
  `globalThis.__diag&&globalThis.__diag("PATH openat "+path);`
- Run: `cd E:\gta\playgta5\node-webgpu; ..\node24\node_modules\node\bin\node.exe harness.js > diag-run-path.txt 2>&1` (with a timeout of about 150-240 s). Server :8000 must be up.
- Log: `PATH openat E:/P1/gta5/build/dev_ng/x64/audio/audio.rpf`. That is Rockstar's dev root, not `/game/`, so the open failed and MountAudioPacks crashed.

### A5. Compare the launch config with the working browser
- `mirror\playgta5.com\index.html`: `args: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', '-pc:nosocialclub', '-nonetwork', '-output', '-width=..', '-height=..', '-forceResolution', ...LOG_ARGS, ...ENGINE_ARGS, '-frameLimit=..']`
- `node-webgpu\harness.js` line 102 had only `['-low', '-res=640x360']`. The engine had even warned "Unknown option 'low'", which was ignored at the time.

### A6. The fix (one change) and the proof
- harness.js line 102 →
  `arguments: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', '-pc:nosocialclub', '-nonetwork', '-output', '-width=640', '-height=360', '-forceResolution', '-textureQuality=0', '-shadowQuality=-1', '-lodScale=0', '-frameLimit=2'],`
  Backup: `harness.js.bak-rootdir`.
- Result (240 s, ended by timeout, no crash):
  - `MANIFEST` called → `IO_START posted` → 4,217 io fetches.
  - All engine threads started (DVD/HDD streamers, RenderThread, ResourcePlacement, audio mixer, StreamingLive).
  - `[wasm] start mode: waiting for the choice on the loading screen`.
  - wgpu worker ~31 FPS, 12 draws/frame, validation errors +0.
  - Only benign errors: Bink movies (same as in the browser), network asserts from `-nonetwork`.
- **Not verified yet:** real pixels (no screenshot), in-world FPS.

### A7. Universal rule from this
> When a port/harness fails where the original works: **(1) diff the launch config (args/env/query) against the working one, (2) log the real file paths at the syscall level, (3) read the crash function in the decompile.** Do these before blaming the binary or the toolchain. Two wrong verdicts (call_once, then "a gate inside the wasm") were avoided this way the third time.

---

## PART B — Plan to MAX (next steps, in order; one change per run, log each as a new ERROR-TRACE stage)

### B1. Answer the loading-screen choice (NEXT problem)
- How the browser does it (`index.html`):
  - `installInput(memory, block)` line ~511: `startModeWord = new Int32Array(memory.buffer, block + 440, 1); Atomics.store(startModeWord, 0, startMode)`.
  - startMode: **1 = Story, 2 = Sandbox, 3 = Sandbox on env_test**.
  - The page receives `block` from the engine via `wasm_input_publish_js(block)` → `postMessage({input:{memory, block}})`.
- Why Node is stuck: in `game-node.js`, `wasm_input_publish_js` **returns early on Node** (`if(process.versions.node) return;`), so nobody ever writes startMode.
- Fix to try: in the Node branch of `wasm_input_publish_js`, do
  `const b=Number(block); globalThis.__inputBlock=b; Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);`  (2 = sandbox).
  Optionally also set FOCUS = 1: word index 6 of the `Int32Array(buffer, b+256, 10)`.
- Pass: the log changes from `start mode: waiting` to `start mode: sandbox`, and game.js progress messages "Loading the world" etc. appear.

### B2. See real pixels
- Turn on a screenshot readback in the wgpu worker (`WGPU_SHOT_EVERY` env, see native-harness-diagnostic.md) → save PNG → open it and look at it. Until a PNG shows the world, do not claim "it renders".

### B3. Measure honestly (A/B vs Chrome on the SAME settings)
- Chrome baselines (memory 02/09/10/14): low 1024x576 = ~30 FPS; best high preset 960x540 shadow0/refl1 = 16.5-16.8 FPS; true 1080p = 4.4-8 FPS. The bottleneck there was the JS worker / WebGPU wire (~120 ms/frame at 1080p), with GPU wait 0.
- Run Node with the **identical** args/res/scene (`mode=sandbox`), read the `[wgpu] fps:` lines plus draws/frame and worker busy %. Compare like-for-like only (same draws/frame range).
- This measurement answers the whole point of the harness: does native Dawn remove the wire overhead?

### B4. Then push to MAX, one lever at a time
1. Res steps: 960x540 → 1280x720 → 1920x1080 (`-width/-height` in harness args + wgpu `display`).
2. Quality args (true MAX, see 01): `-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2,-vehicleVariety=2`. Add them one at a time and record FPS for each.
3. `-frameLimit=0` (uncapped) only to measure the ceiling; use 1 (60) or 2 (30) for play.
4. Keep the worker optimizations from 14 (srvEpoch, proxy fast-path) in the wgpu worker that Node loads (`wgpu_wrapper2.js` → mirror wgpu_worker.js).
- Never present low-mode numbers as "max" (U23). Hardware ceiling: i3-7100U 2C/4T + HD 620 (memory 00). If the GPU becomes the limit (GPU wait > 0), no software lever is left.

### B5. Make it playable (only if B3 shows a real gain)
- Node has **no window/input**. Options: (a) Dawn native window/surface via the `webgpu` npm package if it supports one; (b) readback frames → stream to a local browser page (adds latency + copies, which may eat the gain); (c) feed keyboard/mouse into the input block (`keys` = first 256 bytes, mouse words from offset 256; layout comment at index.html line ~189).
- Audio: the engine runs a "Headless mixer". The audio output path in Node is still to be designed (`wasm_audio_publish_js`).

### B6. Clean-up after it works
- Remove the `PATH openat/stat64` diag (or gate it behind an env flag): it writes a log line per file open.
- Write down the final launch command as a `.cmd` launcher and update the architecture report (`~/.claude/architectures/playgta5.md`).
