# STEP 1 — Answer the loading-screen choice (Story / Sandbox)

## Goal
Get the engine past `[wasm] start mode: waiting for the choice on the loading screen` so it loads the world under Node 24 + native Dawn.

## Background (verified 2026-11-23)
- The MountAudioPacks crash is already fixed (`-rootdir=/game/` in `node-webgpu\harness.js` line 102). See memory `16-how-solved-...md`.
- Proof run: `node-webgpu\diag-run-rootdir.txt`. The engine reached the loading screen, wgpu was at ~31 FPS with 12 draws/frame, and nothing crashed for 240 s.
- The engine now waits for the player to choose a start mode.

## How the browser does it (the working reference)
File `mirror\playgta5.com\index.html`:
- Line ~192: `let startMode = q.get('mode') === 'story' ? 1 : q.get('mode') === 'sandbox' ? (q.get('map') === 'env_test' ? 3 : 2) : 0;`
- Values: **1 = Story Mode, 2 = Sandbox, 3 = Sandbox on env_test**.
- Line ~511, inside `installInput(memory, block)`:
  `startModeWord = new Int32Array(memory.buffer, block + 440, 1); if (startMode) Atomics.store(startModeWord, 0, startMode);`
- `block` is the engine's `WasmInputBlock` (C++: `wasm/platform/input/browser_input_wasm.cpp`). The engine gives its address to JS by calling the import `wasm_input_publish_js(block)`. In the browser that does `postMessage({input:{memory:wasmMemory, block:Number(block)}})`, and the page calls `installInput`.
- Layout (comment at index.html ~line 189): 256 key bytes, then int32 words mouseX, mouseY, dX, dY, dZ, buttons, focus, locked, textHead, textTail, then text[64] (uint16). Offset 424 = 4 ext words (dbgDrawLimit, dbgFrameDraws, winW, winH). **Offset 440 = startMode.**

## Why Node is stuck
`node-webgpu\game-node.js`:
```js
function wasm_input_publish_js(block){if(typeof process!=="undefined"&&process.versions&&process.versions.node)return; postMessage(...)}
```
On Node it returns immediately, so nobody writes startMode and the engine waits forever.

## The fix (one change)
1. Back up: `copy game-node.js game-node.js.bak-step1`.
2. Replace the early `return;` in the Node branch with:
```js
{const b=Number(block);globalThis.__inputBlock=b;
 Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);
 Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),2,640);
 Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),3,360);
 globalThis.__diag&&globalThis.__diag("INPUT block="+b+" startMode=2");return;}
```
   The winW/winH writes copy what the browser does (`Atomics.store(ext, 2, W); Atomics.store(ext, 3, H)`); keep them equal to `-width/-height` in harness.js.
3. Do the replacement with an exact-string Python edit (as in earlier `fix*.py` scripts), not by hand in a 125 KB one-line file.
4. `..\node24\node_modules\node\bin\node.exe --check game-node.js` must pass.
5. Note: `wasmMemory.buffer` is a SharedArrayBuffer. If memory grows, views must be recreated; that's fine here because we create a new view each call.

## Run
```
cd E:\gta\playgta5\node-webgpu
type nul > pthread-msg-log.txt
timeout 300 ..\node24\node_modules\node\bin\node.exe harness.js > diag-run-step1.txt 2>&1
```
(In bash: `: > pthread-msg-log.txt; timeout 300 ../node24/node_modules/node/bin/node.exe harness.js > diag-run-step1.txt 2>&1`.) Server :8000 must answer 200 on `/data/manifest.json` first.

## Pass checks (all required)
- `pthread-msg-log.txt` contains `INPUT block=<number> startMode=2`.
- `diag-run-step1.txt` shows `[wasm] start mode: sandbox` (not `waiting`).
- Later `[wgpu] fps:` lines show **draws/frame far above 12** (world rendering, typically hundreds to thousands).
- No `RuntimeError` / `unreachable`.

## If it fails
- **No INPUT line:** the import is never called. `grep -n "wasm_input_publish_js" E:\Malik\game\game.dcmp` and read the caller with awk to see what gates it (it may wait for a page or focus flag; compare `wasm_has_page_js`).
- **INPUT line but still waiting:** read the engine side. Find where offset 440 is read: search game.dcmp for `440` near the input-block code, or the "start mode" log string. Check that it isn't expecting FOCUS=1 too. As a separate run, try `Atomics.store(new Int32Array(wasmMemory.buffer,b+256,10),6,1)`.
- **Crash after the choice:** that's a new stage. Log the exact stack and read that function in game.dcmp. Do not guess.

## Log it
Add `## Stage 17` to `engine-code-map\ERROR-TRACE.md` (change, file, result, log lines) and update the top box of `CURRENT-PROBLEM.md`.
