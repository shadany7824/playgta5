# STEP 5 — Make the Node/Dawn path playable (window, input, audio)

## Gate (read first)
**Do this step ONLY if STEP 3 showed a real gain (≥ 15-20%) over Chrome at the same settings.** If not, skip to STEP 6 and write that the Chrome path stays the way to play.
This step is big. **Ask the owner before building each sub-part** (window route, input, audio), and show the measured gain from STEP 3 when you ask.

## Current situation
The harness runs headless: no visible window, no keyboard/mouse, no sound. It renders into Dawn textures; STEP 2 proved the image via PNG readback.

## Part A — Showing the picture (choose ONE route, prove it, measure it)
**Route A1: native window surface (best if it exists)**
- Node uses the npm package `webgpu` **v0.6.2** at `E:\gta\playgta5\node24\wgpu\node_modules\webgpu` (Dawn bindings). Read its `README.md` and `types.d.ts`: is there any way to create a window/surface (`GPUCanvasContext`, `createSurface`, a GLFW/SDL helper)? Many Dawn-for-Node builds are headless only.
- If it isn't supported, look for maintained options: Dawn Node bindings with a surface, or an SDL/GLFW Node binding that can give a native window handle to Dawn. Check versions and Windows support; write the findings to `research_notes`.
**Route A2: stream frames to a local browser page**
- Read back the final frame each present (reuse the worker's `screenshot()` readback path, but keep raw RGBA instead of PNG), send it over a local WebSocket, and draw it into a `<canvas>` in Chrome.
- Cost: GPU→CPU copy + transfer + upload, about 960x540x4 ≈ 2 MB/frame. Measure the FPS drop. If it eats the STEP 3 gain, this route fails; say so.
- Security (owner rule): bind to `127.0.0.1` only, no external port, no open endpoint.
**Pass:** a moving image of the game in a window, with FPS measured while displaying.

## Part B — Input (keyboard + mouse)
- STEP 1 stores the input block address in `globalThis.__inputBlock`.
- Layout (comment at `mirror\playgta5.com\index.html` ~line 189, and `installInput()` ~line 503):
  - bytes 0-255: key states (`keys = new Uint8Array(memory.buffer, block, 256)`). Copy how index.html maps browser key codes to indexes; don't invent a mapping.
  - int32 words from `block+256`: 0 mouseX, 1 mouseY, 2 dX, 3 dY, 4 dZ (wheel), 5 buttons, 6 focus, 7 locked, 8 textHead, 9 textTail; text[64] uint16 at `block+296`.
  - `block+424`: dbgDrawLimit, dbgFrameDraws, winW, winH. `block+440`: startMode.
- Writes must use `Atomics.store` (shared memory, the engine reads it from other threads).
- Input source: the window from Part A (A1: native events; A2: the browser page sends key/mouse events back over the same 127.0.0.1 WebSocket).
- Set focus=1 while the window is focused, or the engine may ignore input.
**Pass:** walk, look around, open the menu, all verified on screen.

## Part C — Audio
- The engine runs `[RAGE Audio] Headless mixer`. The browser gets audio via `wasm_audio_publish_js(ring, capacity)`, which posts `{audio:{memory, ring, capacity}}` to the page. Read how index.html consumes that ring (search `audio` in index.html): format, sample rate, read/write pointers.
- In `game-node.js` that function returns early on Node, same pattern as input. Capture `ring/capacity`, then feed the samples to an audio output: a Node audio package, or send them to the A2 browser page and play them with an AudioWorklet.
**Pass:** you hear game audio with no constant crackle. Note the latency.

## Checks before calling it playable
- 10 minutes of play without a crash. FPS during play is written down, compared with STEP 3/4.
- CPU use is noted: streaming/audio threads compete with the engine on only 2 cores.

## Log it
`## Stage 21+` in ERROR-TRACE: one stage per part (A, B, C), with the route chosen, files changed (with backups), measured FPS and the problems hit.
