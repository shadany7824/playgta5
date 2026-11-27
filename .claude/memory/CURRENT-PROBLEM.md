# CURRENT STATUS — Native Node/Dawn harness (updated 2026-11-23, after world load + screenshot)

> ## 2026-11-27: native C++ AOT host is now the active task
> See [native-aot-current-problem/CURRENT-PROBLEM.md](native-aot-current-problem/CURRENT-PROBLEM.md) — root cause found (AOT GOT data relocation for `rage_g_DisableInitNan` resolves out of bounds at `main+0x4fc`), fix pending. **Solution folder: [native-aot-solution/README.md](native-aot-solution/README.md)**: not a WAMR relocation; TLS init order differs from JS. The JS harness status below remains the FPS reference.

> ## NEXT GOAL (2026-11-23): true 1080p at 20-30 FPS on Node/Dawn
> Baseline Stage 19: Node 1080p 12.4 FPS (Chrome 6.1), worker ~80 ms/frame (draw encode ~60 ms, ~40 us/draw), GPU wait 0 = CPU-bound. Plan: [1080p-30fps-engine-plan/README.md](1080p-30fps-engine-plan/README.md) (do files 01→11 in order).

> ## ✅ SOLVED: loading stall — duplicate pthread message delivery in `worker-boot.js`
> **Root cause (proven by log):** `worker-boot.js` `Object.defineProperty(globalThis,'onmessage',{set(fn){... parentPort.on('message', bridge)}})` attached a NEW `parentPort` message listener each time Emscripten reassigned `self.onmessage` (stub → `handleMessage`, and again on pool-worker reuse). A cmd=2 start was delivered multiple times → `invokeEntryPoint`/`rage::sysIpcThreadWrapper` re-entered → `RuntimeError: table index is out of bounds` → the `[RAGE] EnumerationThread` died → main thread blocked forever at `CSavegameAutoload::CheckEnumeration` (savegame autoload never finished).
> **Fix applied (backup `worker-boot.js.bak-onmsgfix`):** one bridge listener installed on first `onmessage` set; the setter only swaps the `_onmessage` handler slot, matching browser semantics.
> **Verified (`node-webgpu\diag-bridgfix.txt`, 110 s):** 0 `UNCAUGHT`, `CheckEnumeration has finished`, `ms_NumberOfSaveGameSlots...`, `game skel`, `Init Session`, 177 `Script Name` lines, `Using controller`, 1313 packfile promotions, draws 14 → 502/frame. Prior fixes retained: startMode write in `game-node.js` (`start mode: story`, mode=1), audio ring drain + heartbeat, `-rootdir=/game/` in `harness.js`.
> **✅ STEP-2 PASSED — real pixels:** `node-webgpu\shots\shot_001500.png` (and 000900/001200/001800/002100), opened and verified: Franklin in a red jacket inside a building with glass walls, another character, HUD minimap. Run command: `node-webgpu\run-step2.cmd`. Screenshots on: ~21 FPS, 659–664 draws/frame (readbacks skew FPS).
> **NEXT:** STEP 3 — fair A/B vs Chrome with screenshots OFF (see `next-steps\README.md`, rewritten). Do not re-investigate the solved loading stall.
> **Known debug state:** harness SEARCH has `console=1` (full console); game-node.js still has MEMSTATE/PROXY/ALIVE/PATH/table/tid diags. Cleanup is STEP 6.
> Full method: [16-how-solved-mountaudiopacks-and-next-max-plan.md](16-how-solved-mountaudiopacks-and-next-max-plan.md); current steps: [next-steps\README.md](next-steps\README.md).

Everything below this box is earlier (pre-world-load) investigation history.

